"""Live watch, runs catalog, and steer for gddp."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent



def _menu_back():
    import gddp
    return gddp._MENU_BACK


def _menu_quit():
    import gddp
    return gddp._MENU_QUIT

def _import_module(name: str):
    import gddp
    return gddp._import_module(name)


def resolve_runtime_root() -> Path:
    import gddp
    return gddp.resolve_runtime_root()


def load_runtime_jobs_module():
    import gddp
    return gddp.load_runtime_jobs_module()


def run_runtime_jobs(*args, **kwargs):
    import gddp
    return gddp.run_runtime_jobs(*args, **kwargs)


from gddp_proxy import console


def _clear_screen() -> None:
    import gddp
    gddp._clear_screen()


def _pause(message: str = "press any key to continue") -> str:
    import gddp
    return gddp._pause(message)

def _recorded_attempt_dirs(runtime_root: Path) -> list[Path]:
    """Reserved attempt directories persisted on executor_sessions."""
    db_path = runtime_root / "db" / "queue.db"
    if not db_path.is_file():
        return []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(executor_sessions)")
        }
        if "attempt_dir" not in columns:
            return []
        rows = con.execute(
            "SELECT attempt_dir FROM executor_sessions "
            "WHERE attempt_dir IS NOT NULL AND attempt_dir <> ''"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    found: list[Path] = []
    for (raw,) in rows:
        found.append(Path(raw).expanduser())
    return found

def _spool_roots(runtime_root: Path) -> list[Path]:
    """Canonical attempt root, leftover historical root, recorded parents."""
    roots: list[Path] = []
    seen: set[Path] = set()

    def add(raw: str | Path | None) -> None:
        if not raw:
            return
        path = Path(raw).expanduser().resolve()
        if path in seen:
            return
        seen.add(path)
        roots.append(path)

    add(os.environ.get("GDDP_ATTEMPT_SPOOL_DIR"))
    add(os.environ.get("GDDP_LOCAL_SUBPROCESS_SPOOL_DIR"))
    add(runtime_root / "jobs" / "local-subprocess-spool")
    add(runtime_root / "jobs" / "cursor-cli-spool")
    for recorded in _recorded_attempt_dirs(runtime_root):
        add(recorded.parent)
    return roots

def _discover_attempts(runtime_root: Path) -> list[dict]:
    extras = [path for path in _recorded_attempt_dirs(runtime_root) if path.is_dir()]
    return _scan_attempts_roots(_spool_roots(runtime_root), extras)

def _attempt_info(attempt_dir: Path) -> dict | None:
    packet_path = attempt_dir / "packet.json"
    if not packet_path.is_file():
        return None
    try:
        packet = json.loads(packet_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    pid = None
    try:
        pid = int((attempt_dir / "pid").read_text().strip())
    except (OSError, ValueError):
        pass
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            pass
    # Prefer supervisor.pid when worker pid file is stale/missing.
    if not alive:
        try:
            spid = int((attempt_dir / "supervisor.pid").read_text().strip())
            os.kill(spid, 0)
            alive = True
            pid = pid or spid
        except (OSError, ValueError):
            pass
    done = (attempt_dir / "result.json").is_file() or (
        attempt_dir / "exit.json"
    ).is_file()
    worktree = None
    try:
        worktree = (attempt_dir / "worktree_path").read_text().strip() or None
    except OSError:
        pass
    try:
        last_write = (attempt_dir / "events.jsonl").stat().st_mtime
    except OSError:
        last_write = attempt_dir.stat().st_mtime
    # Done wins even if pid linger; otherwise alive process = running.
    if done and not alive:
        state = "done"
    elif alive:
        state = "running"
    elif done:
        state = "done"
    else:
        state = "dead"
    return {
        "dir": attempt_dir,
        "name": attempt_dir.name,
        "job_id": str(packet.get("job_id") or ""),
        "execution_attempt_id": str(packet.get("execution_attempt_id") or ""),
        "node_id": str(packet.get("node_id") or ""),
        "project_id": str(packet.get("project_id") or ""),
        "pid": pid,
        "state": state,
        "worktree": worktree,
        "last_write": last_write,
        "created": attempt_dir.stat().st_ctime,
        "events_path": str(attempt_dir / "events.jsonl"),
    }

def _scan_attempts(spool: Path) -> list[dict]:
    if not spool.is_dir():
        return []
    found = []
    for child in sorted(spool.iterdir()):
        if child.is_dir():
            info = _attempt_info(child)
            if info:
                found.append(info)
    order = {"running": 0, "done": 1, "dead": 2}
    found.sort(key=lambda a: (order[a["state"]], -a["created"]))
    return found

def _scan_attempts_roots(
    spools: list[Path], extra_dirs: list[Path] | None = None
) -> list[dict]:
    found: list[dict] = []
    seen_dirs: set[str] = set()

    def add(info: dict | None) -> None:
        if info is None:
            return
        key = str(Path(info["dir"]).resolve())
        if key in seen_dirs:
            return
        seen_dirs.add(key)
        found.append(info)

    for spool in spools:
        for info in _scan_attempts(spool):
            add(info)
    for extra in extra_dirs or []:
        add(_attempt_info(extra))
    order = {"running": 0, "done": 1, "dead": 2}
    found.sort(key=lambda a: (order[a["state"]], -a["created"]))
    return found

def _git(worktree: str, *git_args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", worktree, *git_args],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""

def _diff_summary(worktree: str | None) -> tuple[str, int]:
    """(compact 'Nf +X/-Y', untracked file count) for the attempt worktree."""
    if not worktree or not Path(worktree).is_dir():
        return "-", 0
    shortstat = _git(worktree, "diff", "--shortstat", "HEAD")
    files = re.search(r"(\d+) file", shortstat)
    ins = re.search(r"(\d+) insertion", shortstat)
    dele = re.search(r"(\d+) deletion", shortstat)
    compact = (
        f"{files.group(1) if files else 0}f "
        f"+{ins.group(1) if ins else 0}/-{dele.group(1) if dele else 0}"
    )
    untracked = len(
        _git(worktree, "ls-files", "--others", "--exclude-standard").split()
    )
    return compact, untracked

def _age(ts: float, now: float) -> str:
    seconds = max(0, int(now - ts))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"

def _event_brief(evt: dict) -> str:
    et = evt.get("type") or (evt.get("event") or {}).get("type") or "?"
    detail = ""
    for key in ("name", "command", "path", "tool"):
        value = evt.get(key) or (evt.get("event") or {}).get(key)
        if isinstance(value, str) and value:
            detail = value
            break
    return f"{et} {detail}".strip()[:110]

def _recent_events(attempt_dir: Path, count: int = 8) -> list[str]:
    events = attempt_dir / "events.jsonl"
    try:
        lines = events.read_text(errors="replace").splitlines()
    except OSError:
        return []
    briefs = []
    for line in lines[-200:]:
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        briefs.append(_event_brief(evt))
    return briefs[-count:]

def _agent_obs_command() -> list[str]:
    """Use the installed CLI, or the companion checkout's environment."""
    installed = shutil.which("agent-obs")
    if installed:
        return [installed]
    root = Path(os.environ.get("GDDP_AGENT_OBS_ROOT") or ROOT.parent / "agent-observability").expanduser().resolve()
    cli = root / ".venv" / "bin" / "agent-obs"
    if cli.is_file() and os.access(cli, os.X_OK):
        return [str(cli)]
    uv = shutil.which("uv")
    if uv and (root / "pyproject.toml").is_file():
        return [uv, "run", "--project", str(root), "agent-obs"]
    raise RuntimeError(
        "agent-obs CLI unavailable; install agent-obs on PATH or set "
        "GDDP_AGENT_OBS_ROOT to its checkout (with uv or a configured .venv)"
    )

def _attempt_worktree(info: dict) -> Path:
    """Use the spool path, then the executor's durable per-attempt map."""
    if info.get("worktree"):
        return Path(info["worktree"]).expanduser().resolve()
    map_path = Path(os.environ.get("GDDP_WORKTREE_MAP_PATH") or
                    Path.home() / ".local/share/droid-observability/gddp-worktree-map.ndjson").expanduser()
    worktrees: set[Path] = set()
    try:
        with map_path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue  # An append may still be in progress.
                if not isinstance(row, dict) or not info.get("job_id") or row.get("job_id") != info["job_id"]:
                    continue
                if info.get("execution_attempt_id") and row.get("execution_attempt_id") != info["execution_attempt_id"]:
                    continue
                raw = row.get("worktree_path") or row.get("worktree_name")
                if isinstance(raw, str) and raw:
                    worktrees.add(Path(raw).expanduser().resolve())
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RuntimeError(f"could not read worktree map {map_path}: {exc}") from exc
    if len(worktrees) != 1:
        raise RuntimeError(
            f"{'ambiguous' if worktrees else 'missing'} worktree for "
            f"{info.get('execution_attempt_id') or info.get('job_id') or info['name']}; "
            f"checked {info['dir']}/worktree_path and {map_path}"
        )
    return worktrees.pop()

def _agent_obs_session(info: dict, db_path: Path) -> str:
    """Join worktree → Layer 1 sessions.id without mutating its index."""
    worktree = _attempt_worktree(info)
    try:
        con = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute("SELECT id, cwd FROM sessions WHERE cwd IS NOT NULL").fetchall()
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"could not read agent-obs index {db_path}: {exc}; "
            "set AGENT_OBS_DB to the Layer 1 index"
        ) from exc
    matches = [sid for sid, cwd in rows if cwd and Path(cwd).expanduser().resolve() == worktree]
    # The executor records this unique basename for macOS /var ↔ /private/var
    # aliases, including worktrees already pruned. Never fuzzy-match repo names.
    if not matches and worktree.name.startswith("gddp-agent-wt-"):
        matches = [sid for sid, cwd in rows if Path(cwd).name == worktree.name]
    if not matches:
        raise RuntimeError(
            f"no agent-obs session indexed for {worktree} in {db_path}; "
            "check AGENT_OBS_DB and Layer 1 ingestion for this attempt"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"multiple agent-obs sessions for {worktree}: {', '.join(sorted(matches))}; "
            "select the intended session with agent-obs feed --watch <session_id>"
        )
    return matches[0]

def _watch_agent_events(info: dict) -> int:
    """Transfer live-stream ownership to Layer 1, preserving its exit/signal handling."""
    try:
        command = _agent_obs_command()
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        db_path = Path(os.environ.get("AGENT_OBS_DB") or data_home / "agent-obs/agent-obs.db").expanduser().resolve()
        session_id = _agent_obs_session(info, db_path)
        command += ["--db", str(db_path), "feed", "--watch", session_id]
        print(shlex.join(command), file=sys.stderr, flush=True)
        sys.stdout.flush()
        os.execvp(command[0], command)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: agent-obs live feed unavailable: {exc}", file=sys.stderr)
        return 1
    return 0

def _find_attempt(attempts: list[dict], target: str) -> dict | None:
    for info in attempts:
        if target in (info["job_id"], info["node_id"], info["name"]):
            return info
    matches = [a for a in attempts if a["name"].startswith(target)]
    return matches[0] if len(matches) == 1 else None

def _filter_attempts(
    attempts: list[dict],
    *,
    running_only: bool = True,
    project: str | None = None,
) -> list[dict]:
    """Default view is live work only; --all and project filters apply here."""
    out = attempts
    if running_only:
        out = [a for a in out if a["state"] == "running"]
    if project:
        # Prefer packet project_id; fall back to DB job→project map.
        job_projects = _job_project_map()
        filtered = []
        for a in out:
            pid = a.get("project_id") or job_projects.get(a.get("job_id") or "", "")
            if pid == project or (
                not pid and a.get("node_id") and _node_in_project(project, a["node_id"])
            ):
                filtered.append(a)
        out = filtered
    return out

def _job_project_map() -> dict[str, str]:
    try:
        jobs_status = load_runtime_jobs_module()
        con = jobs_status.connect()
    except Exception:
        return {}
    try:
        rows = con.execute(
            "SELECT job_id, project_id FROM jobs WHERE project_id IS NOT NULL"
        ).fetchall()
        return {
            str(r["job_id"]): str(r["project_id"])
            for r in rows
            if r["job_id"] and r["project_id"]
        }
    except Exception:
        return {}
    finally:
        try:
            con.close()
        except Exception:
            pass

def _node_in_project(project: str, node_id: str) -> bool:
    try:
        path = ROOT / "graphs" / project / "nodes" / f"{node_id}.yaml"
        return path.is_file()
    except OSError:
        return False

def _render_fleet(
    attempts: list[dict],
    now: float,
    *,
    running_only: bool,
    project: str | None = None,
    showing_history: bool = False,
) -> None:
    if showing_history and project:
        scope = f"recent · {project}"
    elif project:
        scope = f"running · {project}"
    elif running_only:
        scope = "running"
    else:
        scope = "all"
    print(
        f"gddp watch · {scope} — {len(attempts)} attempt(s)  "
        f"({time.strftime('%H:%M:%S')})"
    )
    if not attempts:
        if project:
            print(f"  (no attempts recorded for {project})")
        else:
            print("  (none live right now)")
            print("  tip: gddp watch --all   ·   gddp jobs live")
        return
    print(
        f"{'NODE':34} {'STATE':8} {'AGE':>7} {'DIFF':>22} {'QUIET':>6}  JOB"
    )
    for info in attempts:
        import gddp
        shortstat, untracked = gddp._diff_summary(info["worktree"])
        diff = shortstat
        if untracked:
            diff = f"{diff} +{untracked}new"
        quiet = _age(info["last_write"], now)
        flag = (
            " !"
            if info["state"] == "running" and now - info["last_write"] > 180
            else ""
        )
        node = (info["node_id"] or info["name"])[:34]
        job = (info["job_id"] or "")[-14:]
        state = info["state"]
        # Color only when TTY — keep columns stable with plain tokens.
        if sys.stdout.isatty():
            color = {
                "running": "\033[1;35m",
                "done": "\033[1;32m",
                "dead": "\033[1;31m",
            }.get(state, "")
            reset = "\033[0m" if color else ""
            state_s = f"{color}{state:8}{reset}"
        else:
            state_s = f"{state:8}"
        print(
            f"{node:34} {state_s} {_age(info['created'], now):>7} "
            f"{diff:>22} {quiet:>5}{flag}  {job}"
        )
    print()
    print("  live feed: gddp watch <node-id|job-id>  (agent-obs)")
    print("  snapshot:  gddp watch <node-id|job-id> --once")

def _render_single(info: dict, now: float) -> None:
    print(
        f"gddp watch {info['node_id'] or info['name']} — {info['state']}  "
        f"age {_age(info['created'], now)}  pid {info['pid']}  "
        f"({time.strftime('%H:%M:%S')})"
    )
    print(f"  job:      {info['job_id'] or '-'}")
    print(f"  worktree: {info['worktree'] or '-'}")
    print(f"  spool:    {info['dir']}")
    print(f"  events:   {info.get('events_path') or (info['dir'] / 'events.jsonl')}")
    if (info["dir"] / "result.json").is_file():
        print(
            "  ** turn complete — verdict pending; "
            "review: gddp review / gddp node browse"
        )
    print("\n-- diff vs HEAD " + "-" * 50)
    if info["worktree"] and Path(info["worktree"]).is_dir():
        stat = _git(info["worktree"], "diff", "--stat", "HEAD").strip()
        lines = stat.splitlines()
        print("\n".join(lines[-25:]) if lines else "  (clean)")
        untracked = _git(
            info["worktree"], "ls-files", "--others", "--exclude-standard"
        ).split()
        for path in untracked[:10]:
            print(f"  [new] {path}")
    else:
        print("  (no worktree recorded yet)")
    print("\n-- recent events " + "-" * 49)
    events = _recent_events(info["dir"], count=12)
    if events:
        print("\n".join(f"  {e}" for e in events))
    else:
        print("  (none)")
    print("\n  live stream:  gddp watch " + shlex.quote(info["name"]) + "  (agent-obs)")

def cmd_watch(args) -> int:
    """Live execution view. Default fleet = running only (`--all` for history)."""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: live/watch unavailable: {exc}", file=sys.stderr)
        print("  Set GDDP_RUNTIME_ROOT to a gddp-runtime checkout.", file=sys.stderr)
        return 2
    import gddp
    roots = gddp._spool_roots(runtime_root)
    if not any(spool.is_dir() for spool in roots) and not gddp._recorded_attempt_dirs(
        runtime_root
    ):
        joined = ", ".join(str(s) for s in roots)
        print(f"no attempt spools found; checked: {joined}", file=sys.stderr)
        print("  set GDDP_ATTEMPT_SPOOL_DIR in gddp.env, then rerun.", file=sys.stderr)
        return 1
    tty = sys.stdout.isatty()
    running_only = not bool(getattr(args, "all", False))
    project = getattr(args, "project", None) or None
    fallback_all = bool(getattr(args, "fallback_all_when_empty", False))
    try:
        while True:
            all_attempts = gddp._discover_attempts(runtime_root)
            showing_history = False
            if args.target:
                info = _find_attempt(all_attempts, args.target)
                if info is None:
                    # Retry against unfiltered spool names even if done.
                    info = _find_attempt(gddp._discover_attempts(runtime_root), args.target)
                if info is None:
                    print(f"no attempt matching {args.target!r}", file=sys.stderr)
                    return 1
                if not args.once:
                    return _watch_agent_events(info)
            else:
                attempts = gddp._filter_attempts(
                    all_attempts, running_only=running_only, project=project
                )
                if (
                    running_only
                    and project
                    and fallback_all
                    and not attempts
                ):
                    attempts = gddp._filter_attempts(
                        all_attempts, running_only=False, project=project
                    )
                    showing_history = bool(attempts)
            if tty and not args.once:
                sys.stdout.write("\033[2J\033[H")
            now = time.time()
            if args.target:
                _render_single(info, now)
            else:
                _render_fleet(
                    attempts,
                    now,
                    running_only=running_only,
                    project=project,
                    showing_history=showing_history,
                )
            if args.once or not tty:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        return 0

def interactive_watch(project: str | None = None) -> object:
    """Front-page ``w``: the same live/watch surface as ``gddp watch``."""
    _clear_screen()
    console.print(Text("live", style="bold").append(
        f"  ·  {project}" if project else "  ·  running executors",
        style="dim",
    ))
    console.print(Text("ctrl-c returns to menu", style="dim"))
    console.print()
    ns = argparse.Namespace(
        target=None,
        interval=2.0,
        once=False,
        all=False,
        project=project,
        fallback_all_when_empty=bool(project),
    )
    try:
        import gddp
        rc = gddp.cmd_watch(ns)
    except KeyboardInterrupt:
        print()
        return _menu_back()
    except RuntimeError as exc:
        console.print(Text(f"ERROR: live/watch unavailable: {exc}", style="bold red"))
        console.print(Text("Set GDDP_RUNTIME_ROOT to a gddp-runtime checkout.", style="dim"))
        _pause()
        return _menu_back()
    if rc != 0:
        _pause("live/watch could not start — press any key to return")
    return _menu_back()

def _runs_catalog_rows(
    attempts: list[dict],
    *,
    now: float | None = None,
) -> list[tuple[str, str, dict]]:
    """(value=spool_dir, display_label, info) for fzf / --list."""
    now = now if now is not None else time.time()
    rows: list[tuple[str, str, dict]] = []
    for info in attempts:
        node = info.get("node_id") or info["name"][:40]
        job = info.get("job_id") or "-"
        state = info["state"]
        age = _age(info["created"], now)
        quiet = _age(info["last_write"], now)
        import gddp
        shortstat, untracked = gddp._diff_summary(info.get("worktree"))
        diff = shortstat
        if untracked:
            diff = f"{diff}+{untracked}n"
        # Fixed-ish columns for scanning (like agent-runs labels).
        label = (
            f"{state:<8}  {node:<36}  age {age:>6}  quiet {quiet:>5}  "
            f"{diff:<18}  {job[-16:]}"
        )
        rows.append((str(info["dir"]), label, info))
    return rows

def _print_attempt_preview(attempt_dir: Path, *, event_count: int = 40) -> int:
    """Render a compact card for fzf --preview (one attempt spool dir)."""
    info = _attempt_info(attempt_dir)
    if info is None:
        print(f"(not an attempt dir: {attempt_dir})")
        return 1
    now = time.time()
    print(f"state:  {info['state']}   age {_age(info['created'], now)}   quiet {_age(info['last_write'], now)}")
    print(f"node:   {info.get('node_id') or '-'}")
    print(f"job:    {info.get('job_id') or '-'}")
    print(f"pid:    {info.get('pid') or '-'}")
    print(f"tree:   {info.get('worktree') or '-'}")
    print(f"spool:  {info['dir']}")
    print(f"events: {info.get('events_path')}")
    print()
    print("-- recent events --")
    briefs = _recent_events(info["dir"], count=event_count)
    if briefs:
        for line in briefs:
            print(f"  {line}")
    else:
        print("  (none yet)")
    return 0

def _runs_preview_script() -> str:
    """Shell preview for fzf: call back into this CLI (escaped path via {1})."""
    # Prefer the same interpreter running this process.
    py = sys.executable or "python3"
    # Locate gddp.py next to this file.
    gddp_py = str(Path(__file__).resolve())
    # fzf shell-escapes {1}; do not wrap in extra quotes.
    return f"{py} {gddp_py} runs --preview {{1}}"

def cmd_runs(args) -> int:
    """agent-runs-style fzf over executor attempts; Enter → live watch.

    Shell aliases: ``gddp-runs``, espanso ``;gdr``. Default list is running
    only (``--all`` for done/dead history).
    """
    # fzf --preview callback (must be first — no spool scan needed beyond dir).
    preview_dir = getattr(args, "preview", None)
    if preview_dir:
        return _print_attempt_preview(Path(preview_dir))

    runtime_root = resolve_runtime_root()
    import gddp
    roots = gddp._spool_roots(runtime_root)
    if not any(spool.is_dir() for spool in roots) and not gddp._recorded_attempt_dirs(
        runtime_root
    ):
        joined = ", ".join(str(s) for s in roots)
        print(f"no attempt spools found; checked: {joined}", file=sys.stderr)
        return 1

    running_only = not bool(getattr(args, "all", False))
    project = getattr(args, "project", None) or None
    attempts = gddp._filter_attempts(
        gddp._discover_attempts(runtime_root),
        running_only=running_only,
        project=project,
    )
    rows = _runs_catalog_rows(attempts)
    if getattr(args, "list", False):
        if not rows:
            print("no attempts")
            return 0
        for value, label, _info in rows:
            print(f"{label}\t{value}")
        return 0

    if not rows:
        scope = "running" if running_only else "all"
        print(f"no {scope} attempts" + (f" for {project}" if project else ""))
        print("  tip: gddp runs --all   ·   gddp watch --once")
        return 0

    fzf = _import_module("fzf_pick")
    items = [(value, label) for value, label, _ in rows]
    by_dir = {value: info for value, _label, info in rows}

    if not fzf.available():
        # Non-TTY / no fzf: print catalog + suggest watch.
        print(f"gddp runs · {'running' if running_only else 'all'} ({len(rows)})")
        for i, (_v, label, info) in enumerate(rows, 1):
            print(f"  {i:>2}  {label}")
        print()
        print("  drill in: gddp watch <node-id|job-id>")
        print("  install fzf for the picker (agent-runs style)")
        return 0

    height = str(getattr(args, "height", None) or "90%")
    selected = fzf.pick(
        items,
        prompt="gddp-runs> ",
        header=(
            "Enter watch  ·  esc cancel  ·  "
            f"{'running only' if running_only else 'all history'}"
            + (f"  ·  project={project}" if project else "")
        ),
        preview_cmd=_runs_preview_script(),
        preview_window="right:55%:wrap:border-left",
        multi=False,
        height=height,
    )
    if not selected:
        return 0
    attempt_dir = selected[0]
    info = by_dir.get(attempt_dir)
    if info is None:
        print(f"unknown selection: {attempt_dir}", file=sys.stderr)
        return 1

    target = info.get("job_id") or info.get("node_id") or info["name"]
    # Optional action via env or second mode later; default = live watch.
    action = (getattr(args, "action", None) or "watch").strip().lower()
    if action in {"events", "tail", "e"}:
        return _watch_agent_events(info)
    if action in {"show", "job", "j"}:
        return run_runtime_jobs(["show", target])
    if action in {"path", "print"}:
        print(attempt_dir)
        print(info.get("events_path") or "")
        return 0

    # Default: enter live single-target watch (same as agent-runs → open).
    import gddp
    return gddp.cmd_watch(
        argparse.Namespace(
            target=info["name"],  # preserve the picked attempt, even across retries
            interval=float(getattr(args, "interval", 2.0) or 2.0),
            once=bool(getattr(args, "once", False)),
            all=True,  # single target: allow done attempts too
            project=None,
        )
    )

def cmd_steer(args) -> int:
    runtime_root = resolve_runtime_root()
    attempts = _discover_attempts(runtime_root)
    info = _find_attempt(attempts, args.target)
    if info is None:
        print(f"no attempt matching {args.target!r}", file=sys.stderr)
        return 1
    if info["state"] != "running":
        print(
            f"{info['name']} is {info['state']}; steer only delivers to a running attempt",
            file=sys.stderr,
        )
        return 1
    message = " ".join(args.message).strip()
    if not message:
        print("empty steer message", file=sys.stderr)
        return 1
    attempt_dir = info["dir"]
    capabilities_path = attempt_dir / "capabilities.json"
    capabilities: dict | None = None
    if capabilities_path.is_file():
        try:
            loaded = json.loads(capabilities_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                capabilities = loaded
        except (OSError, json.JSONDecodeError):
            capabilities = None
    if capabilities is not None:
        executor = str(capabilities.get("executor") or info.get("executor") or "executor")
        if capabilities.get("midturn_steering") is not True:
            print(
                f"steer refused: executor {executor} does not support mid-turn steering",
                file=sys.stderr,
            )
            return 1
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "message": message}
    )
    with (attempt_dir / "steer.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(f"steer queued for {info['node_id'] or info['name']}: {message}")
    if capabilities is not None:
        print("delivered on the supervisor's next read cycle (needs the steer-aware runtime)")
    else:
        print(
            "unknown capability; message queued but the runtime may not consume it"
        )
    return 0
