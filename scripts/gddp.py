#!/usr/bin/env python3
"""gddp — unified CLI for graph truth and runtime evidence.

Subcommands:
    node browse       Open the node review TUI, optionally at one project
    node new          Interactive TUI node scaffold (full field editor)
    node rapid        Minimal-keystroke rapid node adder
    node batch        Walk through pending/REPLACE_ME nodes in a project
    node import       Import a node YAML from file or stdin (agent pipeline)
    node validate     Validate all nodes (or one project)
    node list         List nodes (ID | GRAPH | RUNTIME | VERDICT)
    node show         Show one node + evaluator summary (read-only runtime)
    node status       Show status summary for all projects

    jobs list         List runtime jobs and queue states
    jobs show         Show one runtime job and its evidence
    jobs live         Live running executors (alias for watch)
    jobs results      Summarize evaluator output
    jobs set          Change runtime job state with an audit reason

    evaluations       List evaluator receipts (verdict + timing)

    watch [target]    Live running fleet (default); drill-in by node/job id
    runs              fzf picker over attempts (agent-runs style; Enter → watch)
    steer <target>    Send an operator message into a running attempt's session

    <graph> [executor] [--yes]  Dispatch the graph's ready frontier (positional)
    <node> [executor] [--yes]   Dispatch one ready node; --yes skips confirm

    verify node       Run deterministic node evaluation; emit a receipt
    receipt           Append a mission worker node receipt to GDDP_RECEIPTS_PATH

    obsidian export   Export one graph to ~/Obsidian/gdd-<project>/

    project new       Create project skeleton (from graphify, outline, or empty shell)
    project validate  Validate project.yaml structure

Usage:
    python3 scripts/gddp.py node browse --project gddp-runtime
    python3 scripts/gddp.py node rapid --project my-app --repo org/repo
    python3 scripts/gddp.py node validate --project vault-doctor
    python3 scripts/gddp.py node import --file draft.yaml --project my-app
    python3 scripts/gddp.py node import --file draft.yaml --project my-app --update
    python3 scripts/gddp.py gddp-runtime local_subprocess --yes
    python3 scripts/gddp.py node batch --project my-greenfield
    python3 scripts/gddp.py node list --project gddp-runtime --active
    python3 scripts/gddp.py node show --project gddp-runtime canary-retry-proof
    python3 scripts/gddp.py jobs list --state awaiting_review
    python3 scripts/gddp.py gddp-runtime
    python3 scripts/gddp.py verdict-confidence-split local_subprocess
    python3 scripts/gddp.py jobs show <job-id> --full
    python3 scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import secrets
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
    from rich import box
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Install deps:  pip install pyyaml rich")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
_PIPE_WIDTH = None if sys.stdout.isatty() else 120
console = Console(soft_wrap=True, highlight=False, width=_PIPE_WIDTH)
_MENU_BACK = object()
_MENU_QUIT = object()
_MENU_REFRESH = object()
_RUNTIME_JOB_COMMANDS = frozenset({"list", "show", "results", "set", "retry"})
_CLI_COMMANDS = frozenset(
    {
        "node",
        "jobs",
        "evaluations",
        "verify",
        "eval",
        "review",
        "receipt",
        "obsidian",
        "deliver",
        "project",
        "watch",
        "runs",
        "steer",
    }
)
_ABSTRACT_EXECUTION_MODES = frozenset({"agent", "human"})

# --------------------------------------------------------------------------- #
# Runtime settings (executor + evaluator configuration)
# --------------------------------------------------------------------------- #
# Human-editable config lives in runtime/settings.env (KEY=value lines). gddp
# loads it at startup into os.environ so every subprocess it spawns inherits
# executor and evaluator configuration. The interactive `config` menu edits
# this file; `gddp eval` and the dispatch/evaluate menu paths read it.

SETTINGS_FILE = ROOT / "runtime" / "settings.env"

SETTINGS_FIELDS: dict[str, tuple[str, str]] = {
    "GDDP_EXECUTOR_OVERRIDE": (
        "executor",
        "force a concrete executor for all dispatch (empty = per-project default; pi_rpc, local_subprocess, jules, droid, factory_mission)",
    ),
    "GDDP_PI_RPC_MODEL": (
        "pi_rpc model",
        "model id for the pi_rpc executor (e.g. xai/grok-4.5)",
    ),
    "GDDP_PI_RPC_TOOLS": (
        "pi_rpc tools",
        "comma-separated tool allowlist for the pi_rpc executor",
    ),
    "GDDP_PI_RPC_TURN_TIMEOUT_S": (
        "pi_rpc turn timeout",
        "seconds before a single executor turn is considered hung",
    ),
    "GDDP_VERIFY_SEMANTIC_ARGS": (
        "evaluator lanes",
        "semantic lane args: --semantic-provider <p> --semantic-pi-model <m> --semantic-thinking <level>",
    ),
    "GDDP_INTEGRITY_MODE": (
        "integrity lane",
        "on/off — intent/integrity evaluation always runs when on",
    ),
    "GDDP_DEEPSEEK_KEY_CMD": (
        "evaluator key cmd",
        "shell command that prints the DeepSeek API key (default: pass show api/deepseek)",
    ),
}

DEFAULT_SEMANTIC_ARGS = (
    "--semantic-mode live --semantic-harness pi --semantic-provider deepseek "
    "--semantic-pi-model deepseek-v4-flash --semantic-thinking medium"
)


def _load_runtime_settings() -> None:
    """Load runtime/settings.env into os.environ (setdefault semantics).

    Subprocesses spawned later inherit these values. Explicit shell env always
    wins over the settings file, so an operator can override on the command
    line without editing the file."""
    if not SETTINGS_FILE.is_file():
        return
    try:
        for line in SETTINGS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            os.environ.setdefault(key, value)
    except OSError as exc:
        print(f"warning: could not read {SETTINGS_FILE}: {exc}", file=sys.stderr)


def _write_runtime_settings(settings: dict[str, str]) -> None:
    """Persist executor/evaluator settings to runtime/settings.env."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# gddp runtime settings — edited via `gddp config` (front-page c)",
        "# Loaded into the environment for every executor/evaluator subprocess.",
    ]
    for key in SETTINGS_FIELDS:
        value = settings.get(key, "").strip()
        if value:
            lines.append(f"{key}={value}")
    SETTINGS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key, value in settings.items():
        if value.strip():
            os.environ[key] = value.strip()
        else:
            os.environ.pop(key, None)


# --------------------------------------------------------------------------- #
# Positional dispatch: gddp <graph|node> [executor]
# --------------------------------------------------------------------------- #

class DispatchError(Exception):
    """Operator-facing dispatch validation failure."""


def _graph_projects(config_root: Path) -> list[str]:
    graphs = Path(config_root) / "graphs"
    if not graphs.is_dir():
        return []
    return sorted(
        d.name for d in graphs.iterdir()
        if d.is_dir() and (d / "project.yaml").is_file()
    )


def _executor_allowed(executor: str, modes: list[str]) -> bool:
    """Treat `agent` as executor-neutral, never as a runnable adapter name."""
    return executor not in _ABSTRACT_EXECUTION_MODES and (
        executor in modes or "agent" in modes
    )


def _configured_executor(project_doc: dict, modes: list[str]) -> str:
    policy = project_doc.get("execution_policy") or {}
    default = policy.get("default_executor") or "jules"
    if not modes or _executor_allowed(default, modes):
        return default
    concrete_modes = [mode for mode in modes if mode != "agent"]
    if concrete_modes:
        return concrete_modes[0]
    raise DispatchError(
        "executor-neutral mode 'agent' requires a concrete "
        "execution_policy.default_executor"
    )


def _node_status_pairs(config_root: Path, project_id: str) -> dict:
    """node_id -> {summary, yaml, modes} across both graph status surfaces.

    project.yaml summaries are the readiness authority (the same contract
    GraphReader reads); node YAMLs carry modes. A summary/YAML disagreement
    is graph drift and must be shown, never silently resolved.
    """
    project_doc = _import_module("node_cli").load_project_doc(config_root, project_id)
    summary = {
        n.get("id"): n.get("status")
        for n in project_doc.get("nodes", [])
        if n.get("id")
    }
    out = {}
    nodes_dir = Path(config_root) / "graphs" / project_id / "nodes"
    for path in sorted(nodes_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        nid = data.get("node_id") or path.stem
        out[nid] = {
            "summary": summary.get(nid),
            "yaml": data.get("status"),
            "modes": list(data.get("allowed_execution_modes") or []),
        }
    for nid in summary:
        out.setdefault(nid, {"summary": summary[nid], "yaml": None, "modes": []})
    return out


def build_dispatch_plan(config_root, target, executor, project_hint=None):
    """Resolve target graph-first, validate everything, return a plan dict.

    Exact-node errors refuse that node. Graph dispatch excludes and explains
    invalid members while preserving the valid frontier. Unknown or ambiguous
    targets remain hard errors.
    project_hint (menu path) qualifies a node lookup to one graph. When the
    target is that same graph ID, the hint came from the graph-wide menu path
    and the target must remain a graph frontier, not be reinterpreted as a node.
    """
    config_root = Path(config_root)
    projects = _graph_projects(config_root)
    plan_excluded = []
    if target in projects and project_hint in (None, target):
        project_id = target
        nodes = []
        pairs = _node_status_pairs(config_root, project_id)
        for nid, pair in sorted(pairs.items()):
            if pair["summary"] != "ready":
                continue
            node = {"node_id": nid, "modes": pair["modes"]}
            if pair["yaml"] is None:
                plan_excluded.append((node, "no — graph drift: node YAML missing"))
                continue
            if pair["yaml"] != "ready":
                plan_excluded.append((
                    node,
                    "no — graph drift: summary ready / yaml {}".format(pair["yaml"]),
                ))
                continue
            if executor and not _executor_allowed(executor, pair["modes"]):
                plan_excluded.append((
                    node,
                    "no — executor {!r} not allowed".format(executor),
                ))
                continue
            nodes.append(node)
        if not nodes and not plan_excluded:
            raise DispatchError(f"graph {target!r} has no ready nodes")
    else:
        if project_hint is not None:
            matches = [project_hint] if (
                config_root / "graphs" / project_hint / "nodes" / f"{target}.yaml"
            ).is_file() else []
        else:
            matches = [
                p for p in projects
                if (config_root / "graphs" / p / "nodes" / f"{target}.yaml").is_file()
            ]
        if not matches:
            raise DispatchError(
                f"no graph or node named '{target}' "
                f"(graphs: {', '.join(projects) or 'none'})"
            )
        if len(matches) > 1:
            raise DispatchError(
                f"node '{target}' exists in multiple graphs: {', '.join(matches)}; "
                "dispatch is exact — qualify from the interactive menu"
            )
        project_id = matches[0]
        pair = _node_status_pairs(config_root, project_id).get(
            target, {"summary": None, "yaml": None, "modes": []}
        )
        if pair["summary"] != pair["yaml"]:
            raise DispatchError(
                f"graph drift for '{target}': project.yaml summary is "
                f"'{pair['summary']}', node YAML is '{pair['yaml']}' — "
                "reconcile before dispatch"
            )
        if pair["summary"] != "ready":
            raise DispatchError(
                f"node '{target}' is '{pair['summary']}', not ready"
            )
        modes = pair["modes"]
        if executor and not _executor_allowed(executor, modes):
            raise DispatchError(
                f"executor '{executor}' not in {target}.allowed_execution_modes: "
                f"{modes or []}"
            )
        nodes = [{"node_id": target, "modes": modes}]

    project_doc = _import_module("node_cli").load_project_doc(config_root, project_id)

    def resolve_item(node):
        return {
            "node_id": node["node_id"],
            "executor": executor or _configured_executor(project_doc, node["modes"]),
        }

    items = [resolve_item(node) for node in nodes]
    return {
        "project_id": project_id,
        "repo": project_doc.get("repo") or "",
        "items": items,
        "excluded": [
            (resolve_item(node), reason) for node, reason in plan_excluded
        ],
    }


def insert_dispatch_events(con, project_id, repo, items, *, actor=None):
    """Insert one schema-valid intake event per node; the heartbeat pipeline
    claims, classifies (via the node: tag in url), scopes, reserves, and
    dispatches. Each item already contains the concrete executor resolved by
    the dispatch plan; persist it so runtime never re-plans operator intent."""
    now = datetime.now(timezone.utc)
    event_ids = []
    for item in items:
        event_id = (
            f"evt_dispatch_{now.strftime('%Y%m%dT%H%M%S')}_"
            f"{item['node_id']}_{secrets.token_hex(3)}"
        )
        routing = json.dumps({"selected_executor": item["executor"]})
        con.execute(
            "INSERT INTO events (event_id, schema_version, received_at, source, "
            "event_type, actor, url, project_id, project_node_candidates, "
            "scope_status, priority, risk_level, routing, status, repo) "
            "VALUES (?, '1.0', ?, 'manual_inject', 'issue.opened', ?, ?, ?, ?, "
            "'pending', 'pending', 'pending', ?, 'received', ?)",
            (
                event_id,
                now.isoformat(),
                actor or os.environ.get("USER") or "operator",
                f"manual-dispatch://node: {item['node_id']}",
                project_id,
                json.dumps([item["node_id"]]),
                routing,
                repo,
            ),
        )
        event_ids.append(event_id)
    con.commit()
    return event_ids


def _connect_events_db(db_path: Path):
    if not db_path.is_file():
        raise DispatchError(f"runtime DB not initialized at {db_path}")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    try:
        con.execute("SELECT 1 FROM events LIMIT 1")
    except sqlite3.OperationalError as exc:
        con.close()
        raise DispatchError(f"runtime DB missing events table: {exc}") from exc
    return con


def _classify_dispatch_items(con, config_root, plan):
    """Return the plan's genuinely dispatchable and blocked items.

    This is the single truth path for both the interactive frontier display and
    the final dispatch gate: graph-ready status alone is never presented as
    dispatchable when dependencies or live runtime motion still block a node.
    """
    frontier = _import_module("frontier")
    try:
        blockers = frontier.dispatch_blockers(con, plan["project_id"])
    except sqlite3.Error as exc:
        raise DispatchError(
            f"runtime state unreadable ({exc}); "
            "refusing to dispatch without duplicate-checking"
        ) from exc
    graph = frontier.load_graph(config_root, plan["project_id"])
    movable, excluded = [], list(plan.get("excluded", []))
    for item in plan["items"]:
        if item["node_id"] in blockers:
            excluded.append((item, "no — in flight"))
            continue
        deps = frontier.unsatisfied_deps(graph, item["node_id"])
        if deps:
            detail = ", ".join(f"{dep} [{status}]" for dep, status in deps)
            excluded.append((item, f"no — dep-blocked: {detail}"))
            continue
        movable.append(item)
    return movable, excluded


def _confirm_dispatch(count: int) -> bool:
    """Confirm insert. Enter / y = yes. n = abort. Never default to no.

    TTY uses the same one-key menu as the rest of the control plane. Pipes
    and tests fall back to a line prompt defaulting to y.
    """
    console.print(
        Text(
            f"Dispatch {count} event(s) through the heartbeat pipeline?",
            style="bold",
        )
    )
    try:
        if sys.stdin.isatty() and sys.stdout.isatty():
            actions = {
                "y": ("yes", f"insert {count} event(s) — start heartbeat work"),
                "n": ("no", "abort — insert nothing"),
            }
            return _menu_choice(actions, default="y") == "y"
        answer = Prompt.ask(
            f"Dispatch {count} event(s)? [Y/n]",
            default="y",
        )
        return answer.strip().lower() in {"", "y", "yes"}
    except (EOFError, KeyboardInterrupt):
        console.print("\naborted; no events inserted")
        return False


def _dispatch_flow(con, config_root, target, executor, project_hint=None,
                   yes=False) -> int:
    """Shared shell/menu path: validate, exclude in-flight nodes, preview once,
    confirm once, insert. A node executing, being evaluated, or awaiting
    review is never offered for duplicate dispatch."""
    try:
        plan = build_dispatch_plan(config_root, target, executor, project_hint)
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    try:
        movable, excluded = _classify_dispatch_items(con, config_root, plan)
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    if not movable:
        console.print(
            "[bold red]ERROR:[/] nothing dispatchable; requested nodes were excluded:"
        )
        for item, reason in excluded:
            console.print(f"  {item['node_id']}: {reason}", markup=False)
        return 2
    table = Table(title=f"dispatch preview — {plan['project_id']}")
    table.add_column("node", style="bold")
    table.add_column("executor")
    table.add_column("dispatch?", style="yellow")
    for item in movable:
        table.add_row(item["node_id"], item["executor"], "yes")
    for item, reason in excluded:
        table.add_row(item["node_id"], item["executor"], Text(reason))
    console.print(table)
    if not yes:
        if not _confirm_dispatch(len(movable)):
            console.print("aborted; no events inserted")
            return 1
    event_ids = insert_dispatch_events(
        con,
        plan["project_id"],
        plan["repo"],
        movable,
    )
    for event_id in event_ids:
        console.print(f"  event [cyan]{event_id}[/] → received")
    console.print("next heartbeat tick claims, scopes, reserves, and dispatches.")
    return 0


def cmd_dispatch(argv, *, config_root=None, db_path=None) -> int:
    """Positional dispatch: gddp <graph|node> [executor] [--yes]."""
    yes = False
    positional = []
    for arg in argv:
        if arg == "--yes":
            yes = True
            continue
        if arg.startswith("-"):
            console.print("[bold red]usage:[/] gddp <graph|node> [executor] [--yes]")
            return 2
        positional.append(arg)
    if len(positional) not in (1, 2):
        console.print("[bold red]usage:[/] gddp <graph|node> [executor] [--yes]")
        return 2
    target = positional[0]
    executor = positional[1] if len(positional) == 2 else None
    config_root = Path(config_root) if config_root else ROOT
    try:
        con = _connect_events_db(
            Path(db_path) if db_path else resolve_runtime_root() / "db" / "queue.db"
        )
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    try:
        return _dispatch_flow(con, config_root, target, executor, yes=yes)
    finally:
        con.close()


def _print_frontier_text(text: str) -> None:
    """Color frontier section heads and phase tokens for scannable output."""
    section_styles = {
        "ready now (dispatchable):": "bold cyan",
        "in flight (not offered for dispatch):": "bold magenta",
        "awaiting correction (may be redispatched):": "bold yellow",
        "blocked (incomplete dependencies):": "yellow",
        "runtime/graph drift:": "bold red",
        "unlocks on acceptance:": "bold green",
    }
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            console.print()
            continue
        if line.startswith("frontier:"):
            t = Text()
            t.append("frontier: ", style="bold")
            t.append(line[len("frontier:"):].strip(), style="bold cyan")
            console.print(t)
            continue
        if line.strip() in section_styles:
            console.print(Text(line, style=section_styles[line.strip()]))
            continue
        if " — " in line:
            left, right = line.split(" — ", 1)
            t = Text(left + " — ")
            phase = right.split("  ", 1)[0]
            rest = right[len(phase):]
            t.append(phase, style=_graph_status_style(phase))
            if rest:
                t.append(rest, style="dim")
            console.print(t)
            continue
        if line.strip() == "(none)":
            console.print(Text(line, style="dim"))
            continue
        console.print(line)


def _show_frontier(selected: list[str]) -> None:
    frontier = _import_module("frontier")
    try:
        con = frontier.connect_readonly(resolve_runtime_root() / "db" / "queue.db")
        note = None
    except frontier.FrontierUnavailable as exc:
        con = None
        note = str(exc)
    try:
        for pid in selected:
            graph = frontier.load_graph(ROOT, pid)
            runtime = {}
            pid_note = note
            if con is not None:
                try:
                    runtime = frontier.load_runtime(con, pid)
                except sqlite3.Error as exc:
                    pid_note = str(exc)
            _print_frontier_text(
                frontier.render_text(
                    pid, frontier.derive(graph, runtime), runtime_note=pid_note
                )
            )
            console.print()
    finally:
        if con is not None:
            con.close()


_GRAPH_ARCHIVE_AFTER = timedelta(days=7)
_ARCHIVE_SENTINEL = "__archive__"


def _parse_activity_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _job_last_activity_by_project() -> dict[str, datetime]:
    """project_id -> latest jobs.created_at from runtime queue DB (best effort)."""
    out: dict[str, datetime] = {}
    try:
        db_path = resolve_runtime_root() / "db" / "queue.db"
    except RuntimeError:
        return out
    if not db_path.is_file():
        return out
    try:
        con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT project_id, MAX(created_at) AS last_at "
                "FROM jobs WHERE project_id IS NOT NULL AND project_id != '' "
                "GROUP BY project_id"
            ).fetchall()
        except sqlite3.Error:
            return out
        finally:
            con.close()
    except sqlite3.Error:
        return out
    for row in rows:
        when = _parse_activity_ts(row["last_at"])
        if when is not None:
            out[str(row["project_id"])] = when
    return out


def _graph_file_activity(project_id: str) -> datetime:
    """Latest mtime under graphs/<id>/ (project.yaml + node YAMLs)."""
    root = ROOT / "graphs" / project_id
    latest = 0.0
    if not root.is_dir():
        return datetime.fromtimestamp(0, tz=timezone.utc)
    for path in root.rglob("*"):
        if path.is_file():
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    if latest <= 0:
        try:
            latest = root.stat().st_mtime
        except OSError:
            return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromtimestamp(latest, tz=timezone.utc)


def _graph_activity_at(
    project_id: str,
    job_times: dict[str, datetime] | None = None,
) -> datetime:
    """Most recent signal: last job or graph file edit."""
    job_times = job_times if job_times is not None else _job_last_activity_by_project()
    candidates = [_graph_file_activity(project_id)]
    if project_id in job_times:
        candidates.append(job_times[project_id])
    return max(candidates)


def _format_activity_age(when: datetime, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    secs = int((now - when).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = secs // 86400
    return "1d ago" if days == 1 else f"{days}d ago"


def partition_graphs_by_activity(
    project_ids: list[str] | None = None,
    *,
    now: datetime | None = None,
    archive_after: timedelta = _GRAPH_ARCHIVE_AFTER,
    job_times: dict[str, datetime] | None = None,
) -> tuple[list[tuple[str, datetime]], list[tuple[str, datetime]]]:
    """Split graphs into active vs archive (> archive_after idle), newest first."""
    now = now or datetime.now(timezone.utc)
    ids = project_ids if project_ids is not None else _graph_projects(ROOT)
    job_times = job_times if job_times is not None else _job_last_activity_by_project()
    active: list[tuple[str, datetime]] = []
    archive: list[tuple[str, datetime]] = []
    for pid in ids:
        when = _graph_activity_at(pid, job_times)
        if now - when <= archive_after:
            active.append((pid, when))
        else:
            archive.append((pid, when))
    active.sort(key=lambda item: item[1], reverse=True)
    archive.sort(key=lambda item: item[1], reverse=True)
    return active, archive


def _graph_pick_items(
    rows: list[tuple[str, datetime]],
    *,
    now: datetime | None = None,
) -> list[tuple[str, str | Text]]:
    """(project_id, '3d ago · N nodes') for paged menus."""
    now = now or datetime.now(timezone.utc)
    node_cli = _import_module("node_cli")
    items: list[tuple[str, str | Text]] = []
    for pid, when in rows:
        age = _format_activity_age(when, now=now)
        try:
            count = len(node_cli.iter_nodes(ROOT, pid))
            detail = f"{age} · {count} node{'s' if count != 1 else ''}"
        except Exception:
            detail = age
        desc = Text()
        desc.append(age, style="bold cyan" if (now - when) <= timedelta(days=2) else "dim")
        if " · " in detail:
            desc.append(detail[len(age):], style="dim")
        items.append((pid, desc))
    return items


def _pick_graph(
    heading: str,
    *,
    back_label: str = "main menu",
    include_archive: bool = True,
) -> str | object:
    """Activity-sorted graph picker; ``r`` reloads graph and runtime state."""
    archive_mode = False
    while True:
        active, archive = partition_graphs_by_activity()
        now = datetime.now(timezone.utc)
        rows = archive if archive_mode else active
        items = _graph_pick_items(rows, now=now)
        if not archive_mode and include_archive and archive:
            items.append((
                _ARCHIVE_SENTINEL,
                Text(
                    f"archive · {len(archive)} inactive (>7d)",
                    style="dim",
                ),
            ))
        if not items:
            if archive_mode:
                console.print(Text("Archive empty.", style="dim"))
                archive_mode = False
                continue
            _clear_screen()
            console.print(Text("No graphs found.", style="yellow"))
            _pause()
            return _MENU_BACK
        picked = _pick_list(
            f"{heading} · archive" if archive_mode else heading,
            items,
            preview_cmd=_project_preview_cmd(),
            back_label="active graphs" if archive_mode else back_label,
            refreshable=True,
        )
        if picked is _MENU_REFRESH:
            continue
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            if archive_mode:
                archive_mode = False
                continue
            return _MENU_BACK
        if picked == _ARCHIVE_SENTINEL:
            archive_mode = True
            continue
        return picked


def interactive_frontier(project: str | None = None):
    """Derived frontier view; recomputes from live graph + runtime on open."""
    if project:
        _clear_screen()
        _show_frontier([project])
        _pause()
        return _MENU_BACK
    frontier = _import_module("frontier")
    projects = frontier.project_ids(ROOT)
    if not projects:
        console.print(Text("no graphs found", style="yellow"))
        return _MENU_BACK
    actions = {
        "a": ("all", "frontier for every project"),
        "o": ("one", "pick one project"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("frontier", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            _show_frontier(projects)
            _pause()
            continue
        picked = _pick_graph("frontier · graphs", back_label="frontier")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        _clear_screen()
        _show_frontier([str(picked)])
        _pause()


def _dispatch_for_project(project: str, *, back_label: str = "graphs"):
    """Dispatchability table + target pick for one graph."""
    try:
        con = _connect_events_db(resolve_runtime_root() / "db" / "queue.db")
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        _pause()
        return _MENU_BACK
    try:
        try:
            plan = build_dispatch_plan(
                ROOT, project, None, project_hint=project
            )
            movable, excluded = _classify_dispatch_items(con, ROOT, plan)
        except DispatchError as exc:
            console.print(f"[bold red]ERROR:[/] {exc}")
            _pause()
            return _MENU_BACK

        _clear_screen()
        table = Table(title=f"dispatchability — {project}")
        table.add_column("node", style="bold")
        table.add_column("executor")
        table.add_column("state")
        for item in movable:
            table.add_row(
                item["node_id"],
                item["executor"],
                Text("ready now", style="bold cyan"),
            )
        for item, reason in excluded:
            table.add_row(
                item["node_id"],
                item["executor"],
                Text(str(reason), style="yellow"),
            )
        console.print(table)
        if not movable:
            console.print(
                Text("No nodes are dispatchable now.", style="yellow")
            )
            _pause()
            return _MENU_BACK

        target_items = [
            (
                project,
                Text(
                    f"entire dispatchable frontier · {len(movable)} node"
                    f"{'s' if len(movable) != 1 else ''}",
                    style="bold cyan",
                ),
            ),
            *[
                (
                    item["node_id"],
                    Text(
                        f"{item['executor']} · ready now",
                        style="bold cyan",
                    ),
                )
                for item in movable
            ],
        ]
        target = _pick_list(
            f"dispatch · {project}",
            target_items,
            back_label=back_label,
        )
        if target is _MENU_QUIT:
            return _MENU_QUIT
        if target is _MENU_BACK:
            return _MENU_BACK
        # Executor already shown on each row; override is shell-only
        # (`gddp <node> <executor>`). Empty Prompt.ask "():" was noise that
        # trained people to hit Enter into the next default-no confirm.
        _dispatch_flow(
            con,
            ROOT,
            target,
            None,
            project_hint=project,
        )
        _pause()
        return _MENU_BACK
    finally:
        con.close()


def interactive_dispatch(project: str | None = None):
    """Pick a graph (activity-sorted) and dispatch ready targets."""
    if project:
        return _dispatch_for_project(project, back_label="graph")
    while True:
        picked = _pick_graph("dispatch · graphs", back_label="main menu")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            return _MENU_BACK
        outcome = _dispatch_for_project(str(picked), back_label="graphs")
        if outcome is _MENU_QUIT:
            return _MENU_QUIT
        # After a dispatch attempt, return to main (same as before).
        return outcome


def _import_module(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    return __import__(name)


def _clear_screen() -> None:
    """Start each interactive view at the top of a clean terminal."""
    if console.is_terminal:
        console.clear()


def _graph_status_style(status: str) -> str:
    """Bright styles so list rows are scannable — pass ≠ review ≠ ready."""
    plain = (status or "").strip().lower().replace("_", " ")
    if plain.startswith("desync"):
        return "bold red"
    if plain in {"pass", "passed"}:
        return "bold green"
    if plain in {"fail", "failed"}:
        return "bold red"
    if plain == "awaiting review":
        return "bold yellow"
    if plain == "awaiting result":
        return "bold cyan"
    key = plain.split()[0] if plain else ""
    return {
        "complete": "bold green",
        "ready": "bold cyan",
        "queued": "bold blue",
        "provisional": "bold yellow",
        "pending": "yellow",
        "deferred": "magenta",
        "running": "bold magenta",
        "failed": "bold red",
        "desync": "bold red",
        "cancelled": "dim",
        "blocked": "yellow",
        "intake": "dim",
        "classified": "dim",
    }.get(key, "bold white")


def _verdict_chip(verdict: str | None) -> str:
    """Uppercase evaluator chip, or empty when there is no verdict yet."""
    raw = str(verdict or "").strip().lower().replace("-", "_")
    if raw in {"pass", "passed"}:
        return "PASS"
    if raw in {"fail", "failed"}:
        return "FAIL"
    return ""


def _ellipsize(text: str, width: int) -> str:
    """Truncate to width with a single ellipsis; empty when width is gone."""
    body = str(text or "")
    if width <= 0:
        return ""
    if len(body) <= width:
        return body
    if width == 1:
        return "…"
    return body[: width - 1] + "…"


def _is_running_state(runtime: str) -> bool:
    token = str(runtime or "").strip().lower().replace(" ", "_")
    return token == "running"


def _runtime_label(queue_state: str = "-", job_status: str = "-") -> str:
    """Prefer live queue state; fall back to job status. Never invent graph truth."""
    queue = str(queue_state or "").strip()
    if queue and queue != "-":
        return queue
    job = str(job_status or "").strip()
    if job and job != "-":
        return job
    return "-"


def _is_node_list_desc(description: object) -> bool:
    return isinstance(description, dict) and {
        "graph", "runtime", "title",
    }.issubset(description.keys())


def _runtime_column(runtime: str, width: int) -> Text:
    """Fixed-width runtime cell; running uses a mark + reverse, not color alone."""
    running = _is_running_state(runtime)
    mark = "▶" if running else " "
    label = str(runtime or "-").replace("_", " ")
    body = mark + _ellipsize(label, max(0, width - 1))
    cell = Text(f"{body:<{width}}")
    if running:
        cell.stylize("bold magenta reverse")
    else:
        cell.stylize(_graph_status_style(runtime))
    return cell


def _node_column_budget(room: int) -> tuple[int, int, int, int]:
    """GRAPH / RUNTIME / EVAL / TITLE widths for a given remainder."""
    room = max(0, int(room))
    # mark + "awaiting review" needs 16 so the live phase stays readable.
    if room < 30:
        rt_w = min(16, room) if room >= 6 else room
        title_w = max(0, room - rt_w - (2 if room - rt_w >= 2 else 0))
        return 0, rt_w, 0, title_w
    if room < 52:
        g_w, rt_w, c_w = 12, 16, 4
        used = g_w + 2 + rt_w + 2 + c_w
        if used > room:
            c_w = 0
            used = g_w + 2 + rt_w
        title_w = max(0, room - used - (2 if room > used else 0))
        return g_w, rt_w, c_w, title_w
    g_w, rt_w, c_w = 16, 16, 4
    title_w = max(0, room - g_w - 2 - rt_w - 2 - c_w - 2)
    return g_w, rt_w, c_w, title_w


def _format_node_columns(
    *,
    graph: str,
    runtime: str,
    verdict: str | None,
    title: str,
    room: int,
) -> Text:
    """Aligned GRAPH / RUNTIME / VERDICT / TITLE; collapse by priority when narrow."""
    chip = _verdict_chip(verdict)
    g_w, rt_w, c_w, title_w = _node_column_budget(room)
    out = Text()
    if rt_w <= 0 and g_w <= 0:
        mark = "▶" if _is_running_state(runtime) else "-"
        return Text(_ellipsize(mark, max(0, int(room))))
    if g_w:
        out.append(_ellipsize(graph, g_w).ljust(g_w), style=_graph_status_style(graph))
        out.append("  ")
    out.append_text(_runtime_column(runtime, rt_w))
    if c_w:
        out.append("  ")
        if chip:
            out.append(f"{chip:<{c_w}}", style=_graph_status_style(chip))
        else:
            out.append(f"{'-':<{c_w}}", style="dim")
    if title_w:
        out.append("  ")
        out.append(_ellipsize(title, title_w), style="dim")
    return out


def _node_column_header(room: int) -> Text:
    """Same widths as ``_format_node_columns`` so headers stay under the cells."""
    g_w, rt_w, c_w, title_w = _node_column_budget(room)
    bits: list[str] = []
    if g_w:
        bits.append(f"{'GRAPH':<{g_w}}")
    if rt_w:
        bits.append(f"{'RUNTIME':<{rt_w}}")
    if c_w:
        bits.append(f"{'EVAL':<{c_w}}")
    if title_w:
        bits.append("TITLE")
    return Text("  ".join(bits), style="dim")


def _node_list_desc(
    graph: str,
    runtime: str,
    title: str = "",
    verdict: str | None = None,
) -> dict[str, str]:
    """Structured picker row: graph truth, runtime, evaluator chip, title."""
    return {
        "graph": str(graph or "-"),
        "runtime": str(runtime or "-"),
        "verdict": "" if verdict is None else str(verdict),
        "title": str(title or ""),
    }


def _node_row_description(
    phase: str,
    title: str = "",
    verdict: str | None = None,
) -> Text:
    """List/status row: PASS/FAIL first, then runtime/graph phase, then title."""
    desc = Text()
    chip = _verdict_chip(verdict)
    if chip:
        desc.append(chip, style=_graph_status_style(chip))
        desc.append(" · ")
    desc.append(phase, style=_graph_status_style(phase))
    if title:
        desc.append(f" · {title}")
    return desc


def _node_menu_phase(
    graph_status: str,
    queue_state: str = "-",
    job_status: str = "-",
) -> str:
    """Picker label: waiting-for-review wins over bare graph ready.

    Graph complete/deferred stays graph truth. Active runtime phases
    (awaiting review, running, …) override a still-open graph status so the
    operator can tell human-review work from dispatchable ready.
    """
    graph = (graph_status or "").strip()
    if graph.upper().startswith("DESYNC"):
        return graph
    g = graph.lower()
    if g in {"complete", "deferred"}:
        return g
    runtime = queue_state if queue_state not in (None, "", "-") else job_status
    runtime = str(runtime or "-").strip().lower()
    if runtime == "awaiting_review":
        return "awaiting review"
    if runtime == "awaiting_result":
        return "awaiting result"
    if runtime == "running":
        return "running"
    if runtime == "ready":
        return "queued"
    if runtime == "failed":
        return "failed"
    return graph or "?"


def _pause(message: str = "press any key to continue") -> str:
    """Keep command output visible until the operator is ready to redraw."""
    console.print(Text(message, style="dim"))
    choice = _import_module("terminal").getch()
    if choice == "\x03":
        raise KeyboardInterrupt
    return choice.lower()


def _plain_desc(description: str | Text | dict | None) -> str:
    """Strip Rich markup for fzf labels."""
    if _is_node_list_desc(description):
        chip = _verdict_chip(description.get("verdict"))
        bits = [b for b in (
            chip,
            str(description.get("graph") or ""),
            str(description.get("runtime") or ""),
            str(description.get("title") or ""),
        ) if b and b != "-"]
        return " · ".join(bits)
    if isinstance(description, Text):
        return description.plain
    return str(description) if description is not None else ""


_RICH_TO_ANSI = {
    "bold green": "\033[1;32m",
    "bold yellow": "\033[1;33m",
    "bold cyan": "\033[1;36m",
    "bold blue": "\033[1;34m",
    "bold magenta": "\033[1;35m",
    "bold red": "\033[1;31m",
    "bold white": "\033[1;37m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "dim": "\033[2m",
}


def _ansi(text: str, style: str, width: int = 0) -> str:
    """Fixed-width ANSI span for fzf ``--ansi`` labels."""
    body = f"{text:<{width}}" if width else text
    return f"{_RICH_TO_ANSI.get(style, '')}{body}\033[0m"


def _split_list_desc(plain: str) -> tuple[str, str, str]:
    """chip, phase, rest — from ``PASS · ready · title`` or ``ready · title``."""
    if " · " not in plain:
        return "", "", plain
    parts = [p.strip() for p in plain.split(" · ", 2)]
    if parts[0] in {"PASS", "FAIL"}:
        return (
            parts[0],
            parts[1] if len(parts) > 1 else "",
            parts[2] if len(parts) > 2 else "",
        )
    return "", parts[0], parts[1] if len(parts) > 1 else ""


def _project_preview_cmd() -> str:
    """fzf preview: 4-line project card ({1} = project id).

    fzf shell-escapes placeholders (``{1}`` → ``'aa-cli'``). Never put
    ``{1}`` *inside* double quotes or the quotes become path characters:
    ``".../{1}/..."`` → ``".../'aa-cli'/..."`` → file not found.
    """
    return f"{sys.executable} {SCRIPTS_DIR}/fzf_preview.py project {ROOT} {{1}}"


def _node_preview_cmd(project: str) -> str:
    """fzf preview: title/status/why card ({1} = node id)."""
    return (
        f"{sys.executable} {SCRIPTS_DIR}/fzf_preview.py "
        f"node {ROOT} {project} {{1}}"
    )


def _job_preview_cmd() -> str:
    """fzf preview: runtime jobs show ({1} = job_id).

    ``{1}`` is a bare argv token so fzf's own quoting is correct.
    """
    try:
        runtime_root = resolve_runtime_root()
        py = runtime_python(runtime_root)
        script = runtime_root / "scripts" / "jobs_status.py"
        return (
            f'GDDP_RUNTIME_ROOT={runtime_root} {py} {script} show {{1}} '
            f'2>/dev/null | head -n 8 || echo "(job show failed)"'
        )
    except RuntimeError as exc:
        return f'echo "runtime unavailable: {exc}"'


def _fzf_items(
    items: list[tuple[str, str | Text | dict]],
) -> list[tuple[str, str]]:
    """(value, ANSI label) — status column first so rows scan as columns."""
    out: list[tuple[str, str]] = []
    for value, description in items:
        if _is_node_list_desc(description):
            graph = str(description.get("graph") or "-")
            runtime = str(description.get("runtime") or "-")
            title = str(description.get("title") or "")
            chip = _verdict_chip(description.get("verdict"))
            running = _is_running_state(runtime)
            mark = "▶" if running else " "
            bits = [
                _ansi(_ellipsize(graph, 16).ljust(16), _graph_status_style(graph), 16),
                _ansi(
                    (mark + _ellipsize(runtime.replace("_", " "), 15)).ljust(16),
                    "bold magenta" if running else _graph_status_style(runtime),
                    16,
                ),
            ]
            if chip:
                bits.append(_ansi(chip, _graph_status_style(chip), 4))
            else:
                bits.append(_ansi("-", "dim", 4))
            bits.append(str(value))
            if title:
                bits.append(title)
            out.append((value, "  ".join(bits)))
            continue
        lab = _plain_desc(description).strip()
        if not lab or lab == value:
            out.append((value, value))
            continue
        chip, phase, rest = _split_list_desc(lab)
        if phase:
            bits = []
            if chip:
                bits.append(_ansi(chip, _graph_status_style(chip), 4))
            bits.append(_ansi(phase, _graph_status_style(phase), 16))
            bits.append(str(value))
            if rest:
                bits.append(rest)
            out.append((value, "  ".join(bits)))
            continue
        out.append((value, f"{value}  {lab}"))
    return out


def _run_fzf(
    heading: str,
    items: list[tuple[str, str | Text | dict]],
    *,
    preview_cmd: str | None = None,
    multi: bool = False,
) -> list[str] | None:
    """Step into fzf; return selected values or None (cancel / unavailable)."""
    fzf = _import_module("fzf_pick")
    if not fzf.available():
        console.print(
            Text("fzf not installed (brew install fzf)", style="yellow")
        )
        return None
    header = "tab multi · enter · esc" if multi else "enter · esc"
    return fzf.pick(
        _fzf_items(items),
        prompt=f"{heading}> ",
        header=header,
        preview_cmd=preview_cmd,
        multi=multi,
    )


def _pick_list(
    heading: str,
    items: list[tuple[str, str | Text | dict]],
    *,
    preview_cmd: str | None = None,
    multi: bool = False,
    back_label: str = "back",
    fzf_header: str | None = None,
    refreshable: bool = False,
):
    """Rich paged list by default. Optional fzf via ``f``.

    multi=False → value | _MENU_BACK | _MENU_QUIT | _MENU_REFRESH
    multi=True  → value | list[str] | _MENU_BACK | _MENU_QUIT | _MENU_REFRESH
      (list when space/m has checked 2+ rows and Enter is pressed)
    """
    del fzf_header  # callers used to pass verbose fzf chrome; paged owns help now
    return _paged_menu(
        heading,
        items,
        back_label=back_label,
        fzf_preview_cmd=preview_cmd,
        fzf_multi=multi,
        refreshable=refreshable,
    )


def _batch_node_status(project: str, node_ids: list[str]):
    """One target status + shared reason → dual-write each selected node."""
    node_cli = _import_module("node_cli")
    _clear_screen()
    console.print(Text(f"batch status · {project}", style="bold"))
    console.print(Text(f"{len(node_ids)} node(s):", style="dim"))
    for nid in node_ids:
        console.print(f"  {nid}")
    console.print()

    status_items = [(s, s) for s in node_cli.GRAPH_STATUSES]
    status = _pick_list(
        "target status",
        status_items,
        multi=False,
        back_label="nodes",
    )
    if status in {_MENU_BACK, _MENU_QUIT}:
        return status

    try:
        reason = Prompt.ask(Text("shared reason", style="cyan")).strip()
    except EOFError:
        console.print(Text("Unchanged — reason required.", style="dim"))
        return _MENU_BACK
    if not reason:
        console.print(Text("Unchanged — need a short reason.", style="yellow"))
        return _MENU_BACK

    if status == "complete":
        console.print(
            Text(
                "Note: batch complete skips per-node acceptance merge prompts. "
                "Merge attempt branches yourself if needed.",
                style="yellow",
            )
        )

    actions = {
        "y": ("yes", f"set {len(node_ids)} node(s) → {status}"),
        "n": ("no", "leave graph truth unchanged"),
    }
    _print_action_menu(actions)
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return _MENU_BACK

    ok = 0
    failed = 0
    for node_id in node_ids:
        console.rule(f"{project} / {node_id}", style="dim")
        rc = node_cli.cmd_set_status(
            project=project,
            node_id=node_id,
            status=status,
            yes=True,
            reason=reason,
        )
        if rc == 0:
            ok += 1
        else:
            failed += 1
    console.print(
        Text(f"batch done — ok={ok} failed={failed}", style="bold green" if failed == 0 else "bold yellow")
    )
    # Offer publish once if any dual-write left dirty graph paths.
    dirty: list[str] = []
    for node_id in node_ids:
        dirty.extend(_dirty_graph_status_paths(project, node_id))
    dirty = sorted(set(dirty))
    if dirty and ok:
        # Reuse single-node publish on the first id; paths cover the batch.
        _offer_publish_graph_status(project, node_ids[0], status, reason)
    _pause()
    return _MENU_BACK


def _runtime_job_items(
    state_filter: str | None = None,
    project: str | None = None,
) -> list[tuple[str, str]]:
    """(job_id, scan label) from the runtime queue DB."""
    jobs_status = load_runtime_jobs_module()
    con = jobs_status.connect()
    try:
        q = (
            "SELECT job_id, node_id, queue_state, created_at, project_id FROM jobs"
        )
        clauses: list[str] = []
        params: list = []
        if state_filter:
            clauses.append("queue_state = ?")
            params.append(state_filter)
        if project:
            clauses.append("project_id = ?")
            params.append(project)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC"
        rows = con.execute(q, tuple(params)).fetchall()
        items: list[tuple[str, str]] = []
        for r in rows:
            created = str(r["created_at"] or "")[:10]
            state = str(r["queue_state"] or "?")
            node = str(r["node_id"] or "")
            items.append((str(r["job_id"]), f"{state}  {node}  {created}"))
        return items
    finally:
        con.close()


def _batch_job_state(job_ids: list[str], states: list[tuple[str, str | Text]]):
    """Set the same queue state on multiple runtime jobs with one reason."""
    _clear_screen()
    console.print(Text(f"batch job update · {len(job_ids)} job(s)", style="bold"))
    for jid in job_ids:
        console.print(f"  {jid}")
    state = _pick_list("job state", states, multi=False, back_label="jobs")
    if state in {_MENU_BACK, _MENU_QUIT}:
        return state
    try:
        reason = Prompt.ask(Text("shared reason", style="cyan")).strip()
    except EOFError:
        console.print(Text("Unchanged — reason required.", style="dim"))
        return _MENU_BACK
    if not reason:
        console.print(Text("Unchanged — need a short reason.", style="yellow"))
        return _MENU_BACK
    actions = {
        "y": ("yes", f"set {len(job_ids)} job(s) → {state}"),
        "n": ("no", "leave runtime jobs unchanged"),
    }
    _print_action_menu(actions)
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return _MENU_BACK
    ok = failed = 0
    for jid in job_ids:
        console.rule(jid, style="dim")
        rc = run_runtime_jobs(["set", jid, state, "--reason", reason, "--yes"])
        if rc == 0:
            ok += 1
        else:
            failed += 1
    console.print(
        Text(
            f"batch jobs done — ok={ok} failed={failed}",
            style="bold green" if failed == 0 else "bold yellow",
        )
    )
    _pause()
    return _MENU_BACK


# Named keys from terminal.getch — keep display short and match actions exactly.
_NAMED_KEY_LABELS = {
    "LEFT": "←",
    "RIGHT": "→",
    "UP": "↑",
    "DOWN": "↓",
    "HOME": "Home",
    "END": "End",
}


def _key_label(key: str) -> str:
    """Human-facing key glyph for menus and echoed choices."""
    return _NAMED_KEY_LABELS.get(key, key)


def _letter_keys(actions: dict[str, tuple[str, str | Text]]) -> tuple[str, ...]:
    """Displayed single-letter shortcuts — must stay in sync with handlers."""
    return tuple(key for key in actions if len(key) == 1 and not key.isdigit())


def _handled_letter_keys(
    actions: dict[str, tuple[str, str | Text]],
    handlers: dict[str, object] | None = None,
) -> tuple[str, ...]:
    """Letters the menu can actually act on: action keys plus navigation."""
    handled = set(_letter_keys(actions))
    if handlers:
        handled.update(
            key for key in handlers if len(key) == 1 and not key.isdigit()
        )
    # q/b are always selectable when shown; they are handled by the menu loop.
    return tuple(sorted(handled))


def _print_action_menu(actions: dict[str, tuple[str, str | Text]]) -> None:
    """Static action list (no cursor). Prefer ``_menu_choice`` for interactive pick."""
    for key, (name, description) in actions.items():
        row = Text()
        row.append(f"  {_key_label(key):<6}", style="bold cyan")
        row.append(f"{name:<16}", style="bold")
        if isinstance(description, Text):
            row.append_text(description)
        elif description:
            row.append(str(description), style="dim")
        console.print(row)


def _menu_choice(
    actions: dict[str, tuple[str, str | Text]],
    default: str,
    *,
    echo: bool = True,
) -> str:
    """Cursor action menu: ↑/↓ + Enter, letter shortcuts, optional 1–9.

    Cursor starts on ``default`` (top when default is the first item — main
    menu). Letter keys still jump. Named action keys (``LEFT``/``RIGHT``) still
    select when registered. Escape: ``b`` → ``q`` → default. Ctrl-C quits.

    ``echo`` is accepted for call-site compatibility; the cursor UI paints the
    selection in place, so nothing extra is printed on success.
    """
    del echo  # API compat; cursor paint replaces the old single-key echo.
    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = getattr(terminal, "clear_lines", lambda _n: None)

    selectables = [(key, name, desc) for key, (name, desc) in actions.items()]
    if not selectables:
        raise ValueError("menu has no actions")
    by_key = {key: i for i, (key, _, _) in enumerate(selectables)}
    cursor = by_key.get(default, 0)
    drawn = 0
    first_paint = True

    while True:
        lines: list[Text] = []
        for offset, (key, name, description) in enumerate(selectables):
            marker = "›" if offset == cursor else " "
            row = Text()
            row.append(f"{marker} {_key_label(key):<6}", style="bold cyan")
            row.append(f"{name:<16}", style="bold")
            if isinstance(description, Text):
                row.append_text(description)
            elif description:
                row.append(str(description), style="dim")
            lines.append(row)
        lines.append(
            Text(
                "  ↑/↓ move · enter open · letters jump · 1-9 pick · esc back",
                style="dim",
            )
        )

        if first_paint:
            first_paint = False
        else:
            clear_lines(drawn)
        for line in lines:
            console.print(line)
        drawn = len(lines)

        choice = getch()
        if choice == "\x03":
            raise KeyboardInterrupt
        if not choice:
            continue
        if choice == "\x1b":
            if "b" in by_key:
                return "b"
            if "q" in by_key:
                return "q"
            return default
        if choice in {"\r", "\n"}:
            return selectables[cursor][0]
        if choice == "UP":
            cursor = (cursor - 1) % len(selectables)
            continue
        if choice == "DOWN":
            cursor = (cursor + 1) % len(selectables)
            continue
        if choice == "HOME":
            cursor = 0
            continue
        if choice == "END":
            cursor = len(selectables) - 1
            continue
        # Registered named keys (e.g. LEFT/RIGHT sibling actions).
        if len(choice) > 1:
            if choice in by_key:
                return choice
            continue
        if choice.isdigit() and choice != "0":
            idx = int(choice) - 1
            if 0 <= idx < len(selectables):
                return selectables[idx][0]
            continue
        key = choice.lower()
        if key in by_key:
            return key
        console.print(Text(f"{key!r} is not an option", style="yellow"))
        drawn += 1


def _format_list_description(description: str | Text | dict, room: int) -> Text:
    """One-line description: aligned columns for node rows; else status · title."""
    if _is_node_list_desc(description):
        return _format_node_columns(
            graph=str(description.get("graph") or "-"),
            runtime=str(description.get("runtime") or "-"),
            verdict=description.get("verdict"),
            title=str(description.get("title") or ""),
            room=room,
        )
    if isinstance(description, Text):
        plain = description.plain
        if len(plain) > room:
            plain = plain[: max(1, room - 1)] + "…"
            if " · " in plain:
                status, rest = plain.split(" · ", 1)
                out = Text()
                out.append(status, style=_graph_status_style(status))
                out.append(f" · {rest}")
                return out
            return Text(plain)
        return description.copy()

    plain = str(description)
    if len(plain) > room:
        plain = plain[: max(1, room - 1)] + "…"
    if " · " in plain:
        status, rest = plain.split(" · ", 1)
        out = Text()
        out.append(status, style=_graph_status_style(status))
        out.append(f" · {rest}")
        return out
    return Text(plain)


def _checked_values(
    items: list[tuple[str, str | Text | dict]],
    checked: set[str],
):
    """Checked ids in list order. One id stays a scalar (opens that item)."""
    ordered = [value for value, _ in items if value in checked]
    if not ordered:
        return None
    return ordered if len(ordered) > 1 else ordered[0]


def _paged_menu_key_spec(
    *,
    page_count: int,
    fzf_ok: bool,
    refreshable: bool,
    fzf_multi: bool,
    back_label: str = "back",
) -> tuple[list[str], frozenset[str]]:
    """Help chrome and the letter keys it advertises. Displayed ⊆ handled."""
    help_bits = ["↑/↓"]
    letters: set[str] = set()
    if fzf_multi:
        help_bits.append("space")
        letters.add(" ")
    help_bits.extend(["enter", "1-9"])
    letters.update(str(i) for i in range(1, 10))
    if page_count > 1:
        help_bits.append("←/→ page")
        letters.update({"p", "n"})
    if fzf_ok:
        help_bits.append("f filter")
        letters.add("f")
    if refreshable:
        help_bits.append("r refresh")
        letters.add("r")
    help_bits.extend([f"b {back_label}", "q quit"])
    letters.update({"b", "q"})
    return help_bits, frozenset(letters)


def _paged_menu(
    heading: str,
    items: list[tuple[str, str | Text | dict]],
    *,
    page_size: int = 9,
    back_label: str = "back",
    fzf_preview_cmd: str | None = None,
    fzf_multi: bool = False,
    refreshable: bool = False,
):
    """Rich cursor list: ↑/↓, Enter, numbers; ←/→ page.

    Optional fzf step-in (does not replace this path):
      ``f`` / Ctrl-F  — fuzzy filter + preview
      (tab multi when ``fzf_multi`` is set)

    When ``fzf_multi`` is set, space / ``m`` toggles a checkbox on the
    current row. Enter with 2+ checked returns that list;
    Enter with 0–1 checked opens that one item.

    Static list content is redrawn in place (clear-to-end), not via a full
    terminal clear on every arrow key.
    """
    if not items:
        _clear_screen()
        console.print(Text("No items found.", style="yellow"))
        _pause()
        return _MENU_BACK

    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = terminal.clear_lines
    try:
        fzf_ok = bool(_import_module("fzf_pick").available())
    except Exception:
        fzf_ok = False
    page = 0
    cursor = 0
    drawn = 0
    first_paint = True
    checked: set[str] = set()

    while True:
        page_count = (len(items) + page_size - 1) // page_size
        page = page % page_count
        start = page * page_size
        visible = items[start:start + page_size]
        cursor = min(cursor, len(visible) - 1)

        # One logical line per row so clear_lines stays accurate; truncate.
        width = console.width or 80
        title = Text(heading, style="bold")
        if page_count > 1:
            title.append(f"  ·  {page + 1}/{page_count}", style="dim")
        if fzf_multi:
            n = len(checked)
            title.append(
                f"  ·  {n} selected",
                style="green" if n else "dim",
            )
        id_w = max((len(str(value)) for value, _ in visible), default=0)
        if width < 72:
            id_w = min(id_w, max(8, width // 3))
        node_list = bool(visible) and all(
            _is_node_list_desc(description) for _, description in visible
        )
        lines: list[Text] = [title]
        if node_list:
            header = Text()
            header.append("  #", style="dim")
            if fzf_multi:
                header.append("  ", style="dim")
            header.append(f"  {'ID':<{id_w}}", style="dim")
            used = 4 + 1 + (2 if fzf_multi else 0) + 2 + id_w + 2
            header.append("  ")
            header.append_text(_node_column_header(max(4, width - used)))
            lines.append(header)
        for offset, (value, description) in enumerate(visible, start=1):
            marker = "›" if offset - 1 == cursor else " "
            row = Text()
            row.append(f"{marker} {offset}", style="bold cyan")
            if fzf_multi:
                on = value in checked
                row.append(" ✓" if on else "  ", style="green" if on else "dim")
            shown_id = _ellipsize(str(value), id_w).ljust(id_w)
            row.append(f"  {shown_id}", style="bold")
            used = 4 + len(str(offset)) + (2 if fzf_multi else 0) + 2 + id_w + 2
            room = max(4, width - used)
            row.append("  ")
            row.append_text(_format_list_description(description, room))
            lines.append(row)

        # One help line — no stacked chrome. Letters here must be handled below.
        help_bits, _displayed = _paged_menu_key_spec(
            page_count=page_count,
            fzf_ok=fzf_ok,
            refreshable=refreshable,
            fzf_multi=fzf_multi,
            back_label=back_label,
        )
        lines.append(Text("  " + " · ".join(help_bits), style="dim"))

        if first_paint:
            _clear_screen()
            first_paint = False
        else:
            clear_lines(drawn)

        for line in lines:
            console.print(line, overflow="crop", crop=True, no_wrap=True)
        drawn = len(lines)

        # Read keys here so navigation does not echo "up"/"down" or full-clear.
        while True:
            choice = getch()
            if choice == "\x03":
                raise KeyboardInterrupt
            if not choice:
                continue
            if choice == "\x1b":
                choice = "b"
            if choice in {"\r", "\n"}:
                if fzf_multi:
                    picked = _checked_values(items, checked)
                    if picked is not None:
                        return picked
                return visible[cursor][0]
            if fzf_multi and choice in {" ", "\t", "m", "M"}:
                value = visible[cursor][0]
                if value in checked:
                    checked.discard(value)
                else:
                    checked.add(value)
                break
            if choice == "UP":
                cursor = (cursor - 1) % len(visible)
                break
            if choice == "DOWN":
                cursor = (cursor + 1) % len(visible)
                break
            if choice in {"LEFT", "p", "P"} and page_count > 1:
                page = (page - 1) % page_count
                cursor = 0
                break
            if choice in {"RIGHT", "n", "N"} and page_count > 1:
                page = (page + 1) % page_count
                cursor = 0
                break
            # f / Ctrl-F — opt-in fzf. Cancel returns to this menu.
            if choice in {"f", "F", "\x06"} and fzf_ok:
                selected = _run_fzf(
                    heading,
                    items,
                    preview_cmd=fzf_preview_cmd,
                    multi=fzf_multi,
                )
                if selected:
                    if fzf_multi:
                        picked = _checked_values(items, set(selected))
                        if picked is not None:
                            return picked
                    return selected[0]
                first_paint = True  # fzf wrecked the screen; full redraw
                break
            if choice in {"f", "F", "\x06"} and not fzf_ok:
                console.print(
                    Text("  fzf not installed (brew install fzf)", style="yellow")
                )
                drawn += 1
                continue
            if refreshable and choice in {"r", "R"}:
                return _MENU_REFRESH
            if choice in {"b", "B"}:
                return _MENU_BACK
            if choice in {"q", "Q"}:
                return _MENU_QUIT
            if choice.isdigit() and choice != "0":
                idx = int(choice) - 1
                if 0 <= idx < len(visible):
                    return visible[idx][0]
            # invalid key: stay put, no redraw needed


def _confirm_status_change(project: str, node_id: str, status: str) -> int:
    """Confirm with one key, collect a real reason, then dual-write + history."""
    node_cli = _import_module("node_cli")
    _clear_screen()
    console.rule(f"{project} / {node_id}", style="dim")
    actions = {
        "y": ("yes", f"set {node_id} to {status}"),
        "n": ("no", "leave graph truth unchanged"),
    }
    console.print(
        f"Set [bold]{project}/{node_id}[/bold] graph status to "
        f"[bold cyan]{status}[/bold cyan]?"
    )
    choice = _menu_choice(actions, default="n")
    if choice != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    try:
        reason = Prompt.ask(
            Text("reason", style="cyan"),
        ).strip()
    except EOFError:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not reason:
        console.print(Text("Unchanged — need a short reason for the history trail.", style="yellow"))
        return 1
    if status == "complete" and not _offer_acceptance_merge(project, node_id):
        console.print(
            Text(
                "Status not updated — result commit still off mainline "
                "(merge it, or choose skip on the merge prompt).",
                style="bold yellow",
            )
        )
        return 1
    rc = node_cli.cmd_set_status(
        project=project,
        node_id=node_id,
        status=status,
        yes=True,
        reason=reason,
    )
    if rc == 0:
        _offer_publish_graph_status(project, node_id, status, reason)
    return rc


def _config_git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run git in the gddp-config checkout (graph truth lives here)."""
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _graph_status_relpaths(project: str, node_id: str) -> list[str]:
    """Paths dual-written by set-status, relative to config ROOT."""
    return [
        f"graphs/{project}/nodes/{node_id}.yaml",
        f"graphs/{project}/project.yaml",
    ]


def _dirty_graph_status_paths(project: str, node_id: str) -> list[str]:
    """Which dual-write paths currently differ from HEAD."""
    rels = _graph_status_relpaths(project, node_id)
    proc = _config_git("status", "--porcelain", "--", *rels)
    if proc.returncode != 0:
        return []
    dirty: list[str] = []
    for line in proc.stdout.splitlines():
        # porcelain: XY PATH or XY ORIG -> PATH
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path in rels:
            dirty.append(path)
    return dirty


def _offer_publish_graph_status(
    project: str, node_id: str, status: str, reason: str
) -> None:
    """After graph YAML is written: commit/push it, or leave dirty on purpose.

    Status writes without a publish step is what leaves gddp-config full of
    modified node files. This is the real confirmation — not another scold.
    """
    dirty = _dirty_graph_status_paths(project, node_id)
    if not dirty:
        return

    console.print()
    console.print(Text("Graph YAML written — still only local until published:", style="bold"))
    for path in dirty:
        console.print(f"  {path}")
    diff = _config_git("diff", "--stat", "--", *dirty)
    if diff.stdout.strip():
        console.print(Text(diff.stdout.rstrip(), style="dim"))

    actions = {
        "p": ("commit + push", "add these files, commit, push to origin"),
        "c": ("commit only", "add + commit; you push later"),
        "s": ("skip", "leave the working tree dirty"),
    }
    choice = _menu_choice(actions, default="p")
    if choice == "s":
        console.print(Text(
            "Left dirty — remember to commit graphs/ when you're ready.",
            style="yellow",
        ))
        return

    add = _config_git("add", "--", *dirty)
    if add.returncode != 0:
        console.print(Text(
            f"git add failed:\n{(add.stderr or add.stdout).strip()}",
            style="bold red",
        ))
        return

    msg = (
        f"graph({project}): {node_id} → {status}\n\n"
        f"{reason.strip()}\n"
    )
    commit = _config_git("commit", "-m", msg)
    if commit.returncode != 0:
        console.print(Text(
            f"git commit failed:\n{(commit.stderr or commit.stdout).strip()}",
            style="bold red",
        ))
        return
    sha = _config_git("rev-parse", "--short", "HEAD").stdout.strip()
    console.print(Text(f"committed {sha} — {', '.join(dirty)}", style="green"))

    if choice != "p":
        console.print(Text("Not pushed (commit only).", style="dim"))
        return

    push = _config_git("push", timeout=120)
    if push.returncode != 0:
        console.print(Text(
            f"git push failed:\n{(push.stderr or push.stdout).strip()}",
            style="bold red",
        ))
        console.print(Text("Commit is local; push when the remote is ready.", style="yellow"))
        return
    branch = _config_git("branch", "--show-current").stdout.strip() or "HEAD"
    console.print(Text(f"pushed {sha} → origin/{branch}", style="bold green"))


def _latest_receipt(project: str, node_id: str) -> dict | None:
    """Newest receipt for the node (pipeline or manual), or None."""
    rdir = ROOT / "verification" / project / node_id
    if not rdir.is_dir():
        return None
    best: dict | None = None
    for path in sorted(rdir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            data["_receipt_path"] = str(path)
            best = data
    return best


def _resolve_project_repo(project: str, repo_path: str | None = None) -> Path | None:
    """Same candidate chain as verify node: flag, env root, sibling checkout."""
    import yaml

    repo_name = ""
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    if project_yaml.is_file():
        with open(project_yaml) as f:
            repo_name = str((yaml.safe_load(f) or {}).get("repo", "")).split("/")[-1]
    candidates: list[Path] = []
    if repo_path:
        candidates.append(Path(repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None


def _default_branch(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show-ref", "--verify", "refs/heads/main"],
        capture_output=True, timeout=30, check=False,
    )
    if proc.returncode == 0:
        return "main"
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return proc.stdout.strip() or "HEAD"


def _acceptance_merge_state(repo: Path, sha: str) -> str:
    """merged | pending | unavailable — is the result commit in the mainline?"""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=30, check=False,
        )

    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return "unavailable"
    if git("merge-base", "--is-ancestor", sha, _default_branch(repo)).returncode == 0:
        return "merged"
    return "pending"


def _render_evaluation_and_diff(
    project: str, node_id: str, repo_path: str | None = None, full: bool = False
) -> None:
    """Latest verdict + what the attempt actually changed + merge state."""
    receipt = _latest_receipt(project, node_id)
    if not receipt:
        console.print(Text("no receipts under verification/ — nothing evaluated yet", style="dim"))
        return
    console.print(Text(f"latest receipt: {receipt['_receipt_path']}", style="dim"))
    verdict = receipt.get("verdict")
    line = Text("verdict: ")
    line.append(str(verdict), style=_graph_status_style(str(verdict or "")))
    line.append(
        f"  criteria: {receipt.get('criteria_verdict')}  "
        f"confidence: {receipt.get('confidence')}  "
        f"generated: {receipt.get('generated_at')}"
    )
    console.print(line)
    subject_diff = (receipt.get("deterministic") or {}).get("subject_diff") or {}
    if subject_diff.get("status") == "ok":
        console.print(Text(
            f"subject diff {subject_diff['base'][:8]}..{subject_diff['tip'][:8]} "
            f"— {subject_diff.get('file_count')} file(s):",
            style="bold",
        ))
        for entry in subject_diff.get("files", []):
            console.print(f"  {entry['status']}  {entry['path']}")
        if subject_diff.get("truncated"):
            console.print("  … (truncated)")
    tip = receipt.get("merge_commit_sha") or receipt.get("evaluated_commit_sha")
    repo = _resolve_project_repo(project, repo_path)
    if not tip or repo is None:
        return
    state = _acceptance_merge_state(repo, tip)
    branch = _default_branch(repo)
    style = {"merged": "green", "pending": "yellow", "unavailable": "dim"}[state]
    console.print(Text(f"merge state: {state} ({repo.name} {branch})", style=style))
    if state == "merged":
        return
    base = receipt.get("expected_base_commit_sha") or branch
    diff_args = ["git", "-C", str(repo), "diff"]
    if not full:
        diff_args.append("--stat")
    diff_args.append(f"{base}..{tip}")
    proc = subprocess.run(diff_args, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        print(proc.stdout.rstrip())
    else:
        console.print(Text(f"(diff unavailable: {proc.stderr.strip()[:200]})", style="dim"))


def _offer_acceptance_merge(project: str, node_id: str) -> bool:
    """Merge the accepted result commit into the project repo's mainline.

    False only when the human aborts (``n``) or git merge fails.
    True when already merged, nothing to merge, unavailable tip (manual
    later), or the human explicitly skips the merge and still wants graph
    status advanced.
    """
    receipt = _latest_receipt(project, node_id) or {}
    tip = receipt.get("merge_commit_sha") or receipt.get("evaluated_commit_sha")
    repo = _resolve_project_repo(project)
    if not tip or repo is None:
        return True
    state = _acceptance_merge_state(repo, tip)
    if state == "merged":
        return True
    branch = _default_branch(repo)
    if state == "unavailable":
        console.print(Text(
            f"result commit {tip[:12]} not in {repo} — "
            "graph can still complete; merge the attempt branch yourself later",
            style="yellow",
        ))
        return True
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", f"{branch}..{tip}"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    console.print()
    console.print(Text(
        f"Result commit not on {repo.name} {branch} yet — "
        f"{tip[:12]} still on the attempt branch:",
        style="bold yellow",
    ))
    print(log.stdout.strip() or "(no log output)")
    console.print(
        Text("This is the last step before graph status updates.", style="dim")
    )
    actions = {
        "y": ("merge", f"ff/merge {tip[:12]} into {branch}, then set complete"),
        "s": ("skip merge", "set graph complete anyway (repo left as-is)"),
        "n": ("abort", "leave repo and graph unchanged"),
    }
    # Cursor starts on default ``y``; letters still jump. No silent Enter-abort.
    choice = _menu_choice(actions, default="y")
    if choice == "n":
        console.print(Text("Aborted — graph status not changed.", style="yellow"))
        return False
    if choice == "s":
        console.print(Text(
            f"Skipping merge — {tip[:12]} stays off {branch}; graph will still update.",
            style="yellow",
        ))
        return True
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge", "--ff-only", tip],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "-C", str(repo), "merge", "--no-ff", tip,
             "-m", f"accept({node_id}): human-approved result {tip[:12]}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if proc.returncode != 0:
            console.print(Text(f"merge failed:\n{proc.stderr.strip()}", style="bold red"))
            console.print(Text(
                "Graph status not updated. Fix the repo, then retry complete.",
                style="yellow",
            ))
            return False
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, timeout=30, check=False,
    ).stdout.strip()
    console.print(Text(f"merged — {repo.name} {branch} now at {head}", style="green"))
    return True


def cmd_review(args) -> int:
    """Human-gate review surface: node summary, latest verdict, diff, merge state."""
    node_cli = _import_module("node_cli")
    node_cli.cmd_show(project=args.project, node_id=args.node, trace=False, view="summary")
    _render_evaluation_and_diff(args.project, args.node, repo_path=args.repo_path, full=args.full)
    return 0


def _node_review_pick_action(
    *,
    has_siblings: bool,
    default_key: str = "e",
    allow_batch: bool = False,
) -> str:
    """Pick a node-review action with split arrow roles.

    ↑/↓ move the action cursor (Enter activates). ←/→ mean previous/next
    sibling when the project has more than one node. Letter keys still work
    as direct shortcuts. Escape maps to back.
    """
    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = getattr(terminal, "clear_lines", lambda _n: None)

    # Primary work only. contract / trace / diff live under "more".
    # Horizontal sibling nav (←/→) is separate chrome, not a peer option.
    selectables: list[tuple[str, str, str]] = [
        ("e", "evaluation", "verdict, why, criteria — current job evidence"),
        ("v", "evaluate", "run the live judge — same path as gddp eval"),
        ("u", "update", "set graph status (your decision)"),
        ("x", "reject + retry", "return to ready; retry with your fix-list"),
        ("m", "more", "contract · diff · trace"),
        ("b", "back", "choose another node"),
        ("q", "quit", ""),
    ]
    if allow_batch:
        selectables.insert(
            2,
            ("s", "same status", "one status + reason for this set"),
        )
    by_key = {key: i for i, (key, _, _) in enumerate(selectables)}
    cursor = by_key.get(default_key, 0)
    drawn = 0
    first_paint = True

    while True:
        lines: list[Text] = []
        if has_siblings:
            for key, name, description in (
                ("LEFT", "prev", "previous node"),
                ("RIGHT", "next", "next node"),
            ):
                row = Text()
                row.append(f"  {_key_label(key):<8}", style="bold cyan")
                row.append(f"{name:<12}", style="bold")
                row.append(description, style="dim")
                lines.append(row)
        for offset, (key, name, description) in enumerate(selectables):
            marker = "›" if offset == cursor else " "
            row = Text()
            row.append(f"{marker} {key:<6}", style="bold cyan")
            row.append(f"{name:<12}", style="bold")
            row.append(description, style="dim")
            lines.append(row)
        help_bits = ["↑/↓ move", "enter open"]
        if has_siblings:
            help_bits.insert(0, "←/→ node")
        help_bits.extend(["letters jump", "esc back"])
        help_line = Text("  " + " · ".join(help_bits), style="dim")
        lines.append(help_line)

        if first_paint:
            first_paint = False
        else:
            clear_lines(drawn)
        for line in lines:
            console.print(line)
        drawn = len(lines)

        choice = getch()
        if choice == "\x03":
            raise KeyboardInterrupt
        if not choice:
            continue
        if choice == "\x1b":
            return "b"
        if choice in {"\r", "\n"}:
            return selectables[cursor][0]
        if choice == "UP":
            cursor = (cursor - 1) % len(selectables)
            continue
        if choice == "DOWN":
            cursor = (cursor + 1) % len(selectables)
            continue
        if choice == "LEFT" and has_siblings:
            return "LEFT"
        if choice == "RIGHT" and has_siblings:
            return "RIGHT"
        # Ignore vertical/horizontal arrows that don't apply (no scolding).
        if choice in {"LEFT", "RIGHT", "UP", "DOWN", "HOME", "END"}:
            continue
        if len(choice) == 1:
            key = choice.lower()
            if key in by_key:
                return key
            console.print(Text(f"{key!r} is not an option", style="yellow"))
            drawn += 1
            continue
        # Unknown multi-char: ignore.
        continue


def _confirm_reject_and_retry(project: str, node_id: str) -> int:
    """Record human rejection, return graph truth to ready, and retry the job."""
    node_cli = _import_module("node_cli")
    try:
        evidence = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
    except Exception as exc:
        console.print(Text(f"Could not load runtime evidence: {exc}", style="red"))
        return 1
    job_id = getattr(evidence, "job_id", None)
    queue_state = getattr(evidence, "queue_state", None)
    if not job_id or queue_state != "awaiting_review":
        console.print(
            Text(
                f"Reject + retry requires an awaiting-review job; current state is "
                f"{queue_state or 'missing'}.",
                style="yellow",
            )
        )
        return 1

    _clear_screen()
    console.rule(f"{project} / {node_id} · reject + retry", style="bold yellow")
    actions = {
        "y": ("yes", "reject this result and dispatch the next attempt"),
        "n": ("no", "leave graph and runtime state unchanged"),
    }
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    try:
        reason = Prompt.ask(Text("fix-list / reason", style="cyan")).strip()
    except EOFError:
        reason = ""
    if not reason:
        console.print(Text("Unchanged — a retry fix-list is required.", style="yellow"))
        return 1

    rc = node_cli.cmd_set_status(
        project=project,
        node_id=node_id,
        status="ready",
        yes=True,
        reason=reason,
    )
    if rc != 0:
        return rc
    _offer_publish_graph_status(project, node_id, "ready", reason)
    return run_runtime_jobs([
        "retry",
        str(job_id),
        "--reason",
        reason,
        "--yes",
    ])


def _node_review_menu(
    project: str,
    node_id: str,
    node_ids: list[str] | None = None,
    *,
    allow_batch: bool = False,
):
    """Review one node and optionally update its human-owned graph status.

    When ``node_ids`` is the project's ordered list:
      ←/→  previous / next sibling node
      ↑/↓  move action cursor; Enter opens the highlighted action
    Letter keys remain direct shortcuts.
    ``allow_batch`` adds ``s`` same-status for the current sibling set.
    """
    node_cli = _import_module("node_cli")
    siblings = list(node_ids) if node_ids else []
    if node_id not in siblings:
        siblings = [node_id, *[s for s in siblings if s != node_id]]

    while True:
        _clear_screen()
        position = ""
        if len(siblings) > 1:
            position = f" · {siblings.index(node_id) + 1}/{len(siblings)}"
        chip = ""
        try:
            ev = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
            chip = _verdict_chip(getattr(ev, "verdict", None))
        except Exception:
            chip = ""
        rule = f"{project} / {node_id}{position}"
        if chip:
            rule = f"{rule} · {chip}"
        rule_style = "bold green" if chip == "PASS" else (
            "bold red" if chip == "FAIL" else "dim"
        )
        console.rule(rule, style=rule_style)
        node_cli.cmd_show(
            project=project,
            node_id=node_id,
            trace=False,
            view="summary",
        )
        choice = _node_review_pick_action(
            has_siblings=len(siblings) > 1,
            allow_batch=allow_batch,
        )
        if choice == "LEFT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx - 1) % len(siblings)]
            continue
        if choice == "RIGHT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx + 1) % len(siblings)]
            continue
        if choice == "s" and allow_batch:
            outcome = _batch_node_status(project, siblings)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue
        if choice == "q":
            return _MENU_QUIT
        if choice == "p":
            return "projects"
        if choice == "b":
            return _MENU_BACK
        if choice == "e":
            _clear_screen()
            node_cli.cmd_show(
                project=project,
                node_id=node_id,
                trace=False,
                view="evaluation",
            )
            if _pause("u update · any other key returns to the node") != "u":
                continue
        elif choice == "v":
            _clear_screen()
            console.print(Text(f"evaluate · {project} / {node_id}", style="bold"))
            _run_live_eval(project, node_id)
            _pause()
            continue
        elif choice == "x":
            _confirm_reject_and_retry(project, node_id)
            _pause()
            continue
        elif choice == "m":
            more = {
                "c": ("contract", "intent, dependencies, acceptance criteria"),
                "d": ("diff", "what the attempt changed + merge state"),
                "t": ("trace", "full evaluator and job history"),
                "b": ("back", ""),
                "q": ("quit", ""),
            }
            _clear_screen()
            console.print(Text("more", style="bold").append(
                f"  ·  {node_id}", style="dim"
            ))
            more_choice = _menu_choice(more, default="c")
            if more_choice == "q":
                return _MENU_QUIT
            if more_choice == "b":
                continue
            _clear_screen()
            if more_choice == "c":
                node_cli.cmd_show(
                    project=project,
                    node_id=node_id,
                    trace=False,
                    view="contract",
                )
            elif more_choice == "t":
                node_cli.cmd_show(
                    project=project,
                    node_id=node_id,
                    trace=True,
                    view="evaluation",
                )
            else:
                _render_evaluation_and_diff(project, node_id)
            if _pause("u update · any other key returns to the node") != "u":
                continue
        elif choice != "u":
            continue

        ready, gate_reason = node_cli.node_completion_readiness(project, node_id)
        complete_hint = (
            "evaluator passed — your call"
            if ready
            else gate_reason
        )
        complete_desc: str | Text = (
            Text(complete_hint, style="bold green")
            if ready
            else Text(complete_hint, style="yellow")
        )
        status_actions: dict[str, tuple[str, str | Text]] = {
            "p": ("pending", ""),
            "r": ("ready", ""),
            "c": ("complete", complete_desc),
            "d": ("deferred", ""),
            "b": ("back", ""),
            "q": ("quit", ""),
        }
        _clear_screen()
        status_rule = f"{project} / {node_id}"
        if chip:
            status_rule = f"{status_rule} · {chip}"
        console.rule(
            status_rule,
            style=(
                "bold green" if chip == "PASS"
                else "bold red" if chip == "FAIL"
                else "dim"
            ),
        )
        console.print(Text("graph status", style="bold"))
        status_choice = _menu_choice(status_actions, default="b")
        if status_choice == "q":
            return _MENU_QUIT
        if status_choice == "b":
            continue
        target_status = status_actions[status_choice][0]
        if target_status == "complete":
            if not ready:
                _clear_screen()
                console.print(
                    Text("Not ready to mark complete yet", style="bold yellow")
                )
                console.print(gate_reason)
                console.print()
                node_cli.cmd_show(
                    project=project,
                    node_id=node_id,
                    trace=False,
                    view="evaluation",
                )
                override_actions = {
                    "o": (
                        "override",
                        "accept anyway after you've checked the gaps",
                    ),
                    "b": ("back", "leave graph status unchanged"),
                    "q": ("quit", ""),
                }
                override_choice = _menu_choice(override_actions, default="b")
                if override_choice == "q":
                    return _MENU_QUIT
                if override_choice == "b":
                    continue
        _confirm_status_change(
            project,
            node_id,
            target_status,
        )
        _pause()


def _node_status_label(doc: dict, entry: dict | None) -> str:
    """Show node/index disagreement instead of silently choosing one copy."""
    node_status = str(doc.get("status") or "").strip()
    index_status = str((entry or {}).get("status") or "").strip()
    if node_status and index_status and node_status != index_status:
        return f"DESYNC node={node_status} index={index_status}"
    return node_status or index_status or "?"


def interactive_nodes(project: str | None = None):
    """Project → node → review/update loop for canonical graph truth.

    Default path is the rich paged menu. ``f`` steps into fzf (filter/preview;
    tab multi on this list). Space / ``m`` checks rows; Enter with 2+ checked
    reviews that set (``s`` still does one status for all).
    """
    node_cli = _import_module("node_cli")
    fixed_project = project is not None
    while True:
        if not fixed_project:
            projects = node_cli.list_project_ids(ROOT)
            project_items = []
            for project_id in projects:
                try:
                    count = len(node_cli.iter_nodes(ROOT, project_id))
                    description = f"{count} node{'s' if count != 1 else ''}"
                except Exception as exc:
                    description = f"unavailable: {exc}"
                project_items.append((project_id, description))

            project = _pick_list(
                "projects",
                project_items,
                preview_cmd=_project_preview_cmd(),
                back_label="main menu",
                refreshable=True,
            )
            if project is _MENU_REFRESH:
                continue
            if project in {_MENU_BACK, _MENU_QUIT}:
                return project

        while True:
            try:
                nodes = node_cli.iter_nodes(ROOT, project)
            except Exception as exc:
                console.print(Text(f"Could not load {project}: {exc}", style="red"))
                if fixed_project:
                    _pause()
                    return _MENU_BACK
                break
            node_items = []
            for node_id, doc, entry in nodes:
                graph_status = _node_status_label(doc, entry)
                queue_state = "-"
                job_status = "-"
                verdict = "-"
                try:
                    ev = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
                    queue_state = getattr(ev, "queue_state", "-") or "-"
                    job_status = getattr(ev, "job_status", "-") or "-"
                    verdict = getattr(ev, "verdict", "-") or "-"
                except Exception:
                    pass
                title = str(doc.get("title") or (entry or {}).get("title") or "")
                node_items.append((
                    node_id,
                    _node_list_desc(
                        graph_status,
                        _runtime_label(queue_state, job_status),
                        title,
                        verdict,
                    ),
                ))

            picked = _pick_list(
                f"nodes · {project}",
                node_items,
                preview_cmd=_node_preview_cmd(project),
                multi=True,
                back_label="projects",
                refreshable=True,
            )
            if picked is _MENU_REFRESH:
                continue
            if picked is _MENU_QUIT:
                return _MENU_QUIT
            if picked is _MENU_BACK:
                if fixed_project:
                    return _MENU_BACK
                break
            ordered_ids = [nid for nid, _ in node_items]
            if isinstance(picked, list) and len(picked) > 1:
                outcome = _node_review_menu(
                    project,
                    picked[0],
                    node_ids=picked,
                    allow_batch=True,
                )
            else:
                node_id = picked[0] if isinstance(picked, list) else picked
                outcome = _node_review_menu(project, node_id, node_ids=ordered_ids)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            if outcome == "projects":
                if fixed_project:
                    return _MENU_BACK
                break


def cmd_node_browse(args):
    """Open the interactive node browser, optionally skipping project choice."""
    interactive_nodes(args.project)
    return 0


def cmd_node_new(args):
    new_node = _import_module("new_node")
    sys.exit(new_node.main())


def cmd_node_rapid(args):
    rapid = _import_module("rapid_add")
    sys.exit(rapid.main(
        project=args.project,
        repo=args.repo,
        project_name=args.project_name,
        llm_draft=args.llm_draft,
        dry_run=args.dry_run,
    ))


def cmd_node_batch(args):
    batch = _import_module("batch_fill")
    sys.exit(batch.main(project=args.project))


def cmd_node_import(args):
    import_node = _import_module("import_node")
    sys.exit(import_node.main(
        file_path=args.file,
        use_stdin=args.stdin,
        project=args.project,
        auto_approve=args.auto_approve,
        dry_run=args.dry_run,
        update=args.update,
    ))


def cmd_node_validate(args):
    validate = _import_module("validate")
    root = args.root or ROOT
    findings = validate.run(root, args.project)
    if args.json:
        print(validate.render_json(findings))
    elif args.quiet:
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if args.strict:
            errors += warnings
        print(f"errors={errors} warnings={warnings}")
    else:
        for f in findings:
            if f.severity == "error":
                sev = "ERROR"
            elif args.strict:
                sev = "ERROR*"
            else:
                sev = "WARN"
            loc = f.path if f.line == 0 else f"{f.path}:{f.line}"
            print(f"{loc} — {sev} — {f.rule} — {f.message}")
        if not findings:
            print("OK — all nodes valid")
        else:
            errors = sum(1 for f in findings if f.severity == "error")
            warnings = sum(1 for f in findings if f.severity == "warning")
            files = len({f.path for f in findings})
            print(f"\n{errors} error(s), {warnings} warning(s) across {files} file(s)")
    errors = sum(1 for f in findings if f.severity == "error")
    if args.strict:
        errors += sum(1 for f in findings if f.severity == "warning")
    sys.exit(1 if errors else 0)


def cmd_node_list(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_list(
        project=getattr(args, "project", None),
        status=getattr(args, "status", None),
        active=bool(getattr(args, "active", False)),
    ))


def cmd_node_show(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_show(
        project=args.project,
        node_id=args.node_id,
        trace=bool(getattr(args, "trace", False)),
        view=getattr(args, "view", "all"),
    ))


def cmd_node_status(args):
    show_status(getattr(args, "project", None))


def resolve_runtime_root() -> Path:
    """Resolve the runtime checkout that owns job and evaluator state."""
    configured = os.environ.get("GDDP_RUNTIME_ROOT")
    runtime_root = Path(configured).expanduser() if configured else ROOT.parent / "gddp-runtime"
    runtime_root = runtime_root.resolve()
    if not (runtime_root / "scripts" / "jobs_status.py").is_file():
        raise RuntimeError(
            f"gddp-runtime not found at {runtime_root}; set GDDP_RUNTIME_ROOT"
        )
    return runtime_root


def runtime_python(runtime_root: Path) -> str:
    """Prefer runtime's interpreter, with an explicit override for deployments."""
    configured = os.environ.get("GDDP_RUNTIME_PYTHON")
    if configured:
        return str(Path(configured).expanduser())
    runtime_venv = runtime_root / ".venv" / "bin" / "python"
    if runtime_venv.is_file() and os.access(runtime_venv, os.X_OK):
        return str(runtime_venv)
    return sys.executable


def run_runtime_jobs(argv: list[str]) -> int:
    """Delegate one jobs invocation through runtime's job-only CLI boundary."""
    if not argv or argv[0] not in _RUNTIME_JOB_COMMANDS:
        print(
            "ERROR: unsupported runtime jobs command.",
            file=sys.stderr,
        )
        return 2
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "jobs_status.py"),
        *argv,
    ]
    env = os.environ.copy()
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def run_graph_delivery(action: str, project: str, *, delete: bool = False) -> int:
    """Publish one graph's delivery commit, or list/retire its transport refs.

    Delegates to runtime's graph_delivery.py (never runs in-process —
    mutation stays behind the same subprocess boundary as jobs/verify).
    """
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "graph_delivery.py"),
        action,
        project,
        "--config-root", str(ROOT),
        *(["--delete"] if delete else []),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def load_runtime_jobs_module():
    """Load the job-only runtime backend used by the interactive menu."""
    runtime_root = resolve_runtime_root()
    path = runtime_root / "scripts" / "jobs_status.py"
    if not path.is_file():
        raise RuntimeError(f"runtime jobs backend not found at {path}")
    spec = importlib.util.spec_from_file_location("gddp_runtime_jobs_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load runtime jobs backend from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _confirm_job_state_change(ref: str, state: str) -> int:
    """Collect explicit menu confirmation and a durable reason, then write."""
    actions = {
        "y": ("yes", f"set {ref} to {state}"),
        "n": ("no", "leave runtime job state unchanged"),
    }
    console.print(
        f"Set [bold]{ref}[/bold] runtime job state to "
        f"[bold cyan]{state}[/bold cyan]?"
    )
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    try:
        reason = Prompt.ask(Text("reason", style="cyan")).strip()
    except EOFError:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not reason:
        console.print(Text("Unchanged — reason required.", style="yellow"))
        return 1
    try:
        jobs_status = load_runtime_jobs_module()
        return jobs_status.apply_state_change(ref=ref, state=state, reason=reason)
    except (RuntimeError, ValueError) as exc:
        console.print(Text(f"ERROR: {exc}", style="red"))
        return 1


def _evaluation_sources() -> tuple[Path | None, Path]:
    receipt_root = ROOT / "verification"
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError:
        return None, receipt_root
    db_path = runtime_root / "db" / "queue.db"
    return (db_path if db_path.is_file() else None), receipt_root


def interactive_evaluations():
    """Browse evaluator receipts as their own evidence stream."""
    evaluations = _import_module("evaluations")
    actions = {
        "r": ("refresh", "reload receipts"),
        "o": ("open", "open one evaluation"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("evaluations", style="bold").append(
            "  ·  evidence only — does not change graph status", style="dim"
        ))
        db_path, receipt_root = _evaluation_sources()
        rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
        if rows:
            for row in rows:
                print(evaluations.format_evaluation_row(row))
            print(f"\n{len(rows)} evaluation(s)")
        else:
            print("No evaluator receipts yet.")
        console.print()
        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "r":
            continue
        if not rows:
            _pause()
            continue
        items = [
            (str(index), evaluations.format_evaluation_row(row))
            for index, row in enumerate(rows)
        ]
        picked = _pick_list(
            "open evaluation",
            items,
            multi=False,
            back_label="evaluations",
        )
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        row = rows[int(picked)]
        _clear_screen()
        console.print(Text("evaluation", style="bold"))
        if row.get("job_id") and row.get("source") == "result":
            run_runtime_jobs(["show", str(row["job_id"])])
        else:
            evaluations.print_evaluation_detail(row)
        _pause()


def cmd_evaluations(_args) -> int:
    """Print the evaluator receipt list for non-interactive use and tests."""
    evaluations = _import_module("evaluations")
    db_path, receipt_root = _evaluation_sources()
    rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
    if not rows:
        print("No evaluator receipts yet.")
        return 0
    for row in rows:
        print(evaluations.format_evaluation_row(row))
    print(f"\n{len(rows)} evaluation(s)")
    return 0


def interactive_jobs(project: str | None = None):
    """Review and update runtime jobs inside the human-operated menu.

    open/update use the rich paged list; ``f`` filters via fzf, ``m`` multi-
    selects for batch queue-state changes. Empty queue falls back to typing an id.
    When ``project`` is set (graph hub), only that graph's jobs are shown.
    """
    state_filter: str | None = None
    back_name = "graph" if project else "graphs"
    actions = {
        "l": ("live", "running executors — refresh + events"),
        "r": ("refresh", "reload this job list"),
        "a": ("awaiting review", "human review queue"),
        "e": ("evaluations", "evaluator result summary"),
        "o": ("open", "pick a job (f = filter)"),
        "u": ("update", "set queue state (space checks)"),
        "b": (back_name, ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        if project and state_filter:
            heading = f"jobs · {project} · {state_filter}"
        elif project:
            heading = f"jobs · {project}"
        elif state_filter:
            heading = f"jobs · {state_filter}"
        else:
            heading = "jobs"
        console.print(Text(heading, style="bold"))
        try:
            listed = _runtime_job_items(state_filter, project=project)
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            listed = []
        if listed:
            for job_id, label in listed[:40]:
                state = label.split("  ", 1)[0]
                line = Text()
                line.append(f"{job_id}  ", style="dim")
                line.append(state, style=_graph_status_style(state))
                rest = label[len(state):]
                if rest:
                    line.append(rest)
                console.print(line)
            if len(listed) > 40:
                console.print(Text(f"  … {len(listed) - 40} more", style="dim"))
        else:
            console.print(Text("No jobs." + (
                f" (project={project})" if project else ""
            ), style="dim"))
        console.print()

        choice = _menu_choice(actions, default="l" if not state_filter else "r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "l":
            interactive_watch(project)
            continue
        if choice == "r":
            state_filter = None
            continue
        if choice == "a":
            state_filter = "awaiting_review"
            continue
        if choice == "e":
            _clear_screen()
            console.print(Text("evaluator results", style="bold"))
            run_runtime_jobs(["results"])
            _pause()
            continue

        try:
            job_items = _runtime_job_items(state_filter, project=project)
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            _pause()
            continue

        if choice == "o":
            if job_items:
                ref = _pick_list(
                    "open job",
                    job_items,
                    preview_cmd=_job_preview_cmd(),
                    multi=False,
                    back_label="jobs",
                )
                if ref is _MENU_QUIT:
                    return _MENU_QUIT
                if ref is _MENU_BACK:
                    continue
            else:
                try:
                    ref = Prompt.ask(Text("job or node ID", style="cyan")).strip()
                except EOFError:
                    continue
                if not ref:
                    continue
            _clear_screen()
            console.print(Text(f"job · {ref}", style="bold"))
            run_runtime_jobs(["show", ref])
            _pause()
            continue

        # update — paged list; space/m checks rows for batch queue state
        if not job_items:
            console.print(Text("No jobs to update.", style="yellow"))
            _pause()
            continue
        selected = _pick_list(
            "update jobs",
            job_items,
            preview_cmd=_job_preview_cmd(),
            multi=True,
            back_label="jobs",
        )
        if selected is _MENU_QUIT:
            return _MENU_QUIT
        if selected is _MENU_BACK:
            continue
        refs = selected if isinstance(selected, list) else [selected]

        try:
            jobs_status = load_runtime_jobs_module()
            states = []
            for state in jobs_status.QUEUE_STATES:
                label = Text(state.replace("_", " "), style=_graph_status_style(state))
                states.append((state, label))
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            _pause()
            continue

        if len(refs) > 1:
            outcome = _batch_job_state(refs, states)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue

        ref = refs[0]
        _clear_screen()
        console.print(Text(f"job · {ref}", style="bold"))
        run_runtime_jobs(["show", ref])
        state = _pick_list("job state", states, multi=False, back_label="jobs")
        if state is _MENU_QUIT:
            return _MENU_QUIT
        if state is _MENU_BACK:
            continue
        _clear_screen()
        console.rule(f"job · {ref}", style="dim")
        _confirm_job_state_change(ref, state)
        _pause()


def cmd_jobs(args):
    command = getattr(args, "jobs_command", None)
    if command == "live":
        # Same surface as `gddp watch` — packaged under jobs for discoverability.
        return cmd_watch(args)
    argv = []
    if command:
        argv.append(command)
    if command == "list" and args.state:
        argv.extend(["--state", args.state])
    elif command == "show":
        argv.append(args.ref)
        if args.full:
            argv.append("--full")
    elif command == "results" and args.all:
        argv.append("--all")
    elif command == "set":
        argv.extend([args.ref, args.state, "--reason", args.reason])
        if args.yes:
            argv.append("--yes")
    elif command == "retry":
        argv.extend([args.ref, "--reason", args.reason])
        if args.yes:
            argv.append("--yes")
    return run_runtime_jobs(argv)


def static_overview():
    """Render the unified command groups without blocking redirected output."""
    console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=False,
        pad_edge=False,
        padding=(0, 2, 0, 0),
    )
    table.add_column("group", style="bold cyan", no_wrap=True)
    table.add_column("owns")
    table.add_column("start with", style="dim", no_wrap=True)
    table.add_row("menu", "dispatch · graphs · live · heartbeat", "gddp")
    table.add_row("live", "running executors, diffs, events stream", "gddp watch / gddp jobs live")
    table.add_row("node", "graph truth, authoring, runtime/evaluator join", "gddp node list")
    table.add_row("jobs", "runtime queue, results, and audited state changes", "gddp jobs list")
    table.add_row("evaluations", "evaluator receipts, verdicts, and timing", "gddp evaluations")
    table.add_row("verify", "node evaluation", "gddp verify node")
    table.add_row("project", "project graph creation and validation", "gddp project -h")
    table.add_row("obsidian", "graph export", "gddp obsidian export")
    console.print(table)
    tty_bits = [
        f"{key} {name}" for key, (name, _desc) in _front_page_actions().items()
        if key != "q"
    ]
    console.print(Text(
        "TTY: " + " · ".join(tty_bits) + ". "
        "Shell: `gddp watch`, `gddp jobs live`, `gddp <group> -h`.",
        style="dim",
    ))


def _graph_more_menu(project: str):
    """Secondary graph tools — not on equal footing with nodes/dispatch/live."""
    actions = {
        "j": ("jobs", "runtime jobs for this graph"),
        "f": ("frontier", "ready / in flight / blocked"),
        "s": ("status", "completion + node phases"),
        "v": ("validate", "check this graph definition"),
        "e": ("evaluations", "evaluator receipts"),
        "d": ("deliver", "publish review branch / retire transport refs"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(
            Text("more", style="bold")
            .append(f"  ·  {project}", style="dim")
        )
        choice = _menu_choice(actions, default="j")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        try:
            if choice == "j":
                outcome = interactive_jobs(project)
            elif choice == "f":
                outcome = interactive_frontier(project)
            elif choice == "s":
                outcome = interactive_status(project)
            elif choice == "v":
                outcome = interactive_validate(project)
            elif choice == "e":
                outcome = interactive_evaluations()
            elif choice == "d":
                outcome = interactive_graph_delivery(project)
            else:
                outcome = _MENU_BACK
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
        except SystemExit:
            if choice == "v":
                _pause()
        except KeyboardInterrupt:
            return _MENU_BACK


def _graph_hub_actions() -> dict[str, tuple[str, str]]:
    return {
        "n": ("nodes", "review evidence and update graph truth"),
        "d": ("dispatch", "send ready work on this graph"),
        "w": ("live", "running executors for this graph"),
        "m": ("more", "jobs · frontier · status · validate · evaluations"),
        "b": ("graphs", ""),
        "q": ("quit", ""),
    }


def _graph_hub_handlers() -> dict[str, object]:
    return {
        "n": interactive_nodes,
        "d": interactive_dispatch,
        "w": interactive_watch,
        "m": _graph_more_menu,
    }


def interactive_graph_hub(project: str):
    """Primary work for one graph: nodes, dispatch, live. Rest under more."""
    actions = _graph_hub_actions()
    while True:
        _clear_screen()
        console.print(
            Text("graph", style="bold")
            .append(f"  ·  {project}", style="bold cyan")
        )
        try:
            choice = _menu_choice(actions, default="n")
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        try:
            if choice == "n":
                outcome = interactive_nodes(project)
            elif choice == "d":
                outcome = interactive_dispatch(project)
                if outcome is not _MENU_QUIT:
                    _pause()
            elif choice == "w":
                outcome = interactive_watch(project)
            elif choice == "m":
                outcome = _graph_more_menu(project)
            else:
                outcome = _MENU_BACK
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
        except SystemExit:
            pass
        except KeyboardInterrupt:
            return _MENU_BACK


def interactive_graphs():
    """Activity-sorted graphs; idle (>7d) live under archive, not the main list."""
    while True:
        picked = _pick_graph("graphs", back_label="main menu")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            return _MENU_BACK
        outcome = interactive_graph_hub(str(picked))
        if outcome is _MENU_QUIT:
            return _MENU_QUIT


def _heartbeat_loaded(label: str) -> bool:
    try:
        return subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
        ).returncode == 0
    except OSError:
        return False


def interactive_heartbeat():
    """Show control-plane state and offer the arm/disarm toggle."""
    kit = resolve_runtime_root() / "deploy" / "mini-heartbeat"
    labels = ("com.gddp.intake", "com.gddp.heartbeat")
    _clear_screen()
    loaded = {label: _heartbeat_loaded(label) for label in labels}
    for label, on in loaded.items():
        state = Text("ARMED", style="bold green") if on else Text("off", style="dim")
        console.print(f"  {label}  ", state)
    armed = any(loaded.values())
    verb = "disarm" if armed else "arm"
    script = "disarm.sh" if armed else "arm.sh"
    try:
        answer = Prompt.ask(
            f"[cyan]{verb} the control plane?[/] (enter = yes, b = back)", default=""
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return _MENU_BACK
    if answer in ("b", "back", "q"):
        return _MENU_BACK
    env = dict(os.environ)
    if not armed:
        env["MINI_HEARTBEAT_ARM"] = "1"
    subprocess.run(["bash", str(kit / "bin" / script)], env=env, check=False)
    _pause()
    return _MENU_BACK


def _front_page_actions() -> dict[str, tuple[str, str]]:
    return {
        "d": ("dispatch", "send ready work through the event pipeline"),
        "e": ("evaluate", "run the live judge on a node now"),
        "g": ("graphs", "active graphs first; archive for idle (>7d)"),
        "w": ("live", "running executors — fleet + drill-in"),
        "h": ("heartbeat", "arm/disarm the control plane (intake + heartbeat)"),
        "c": ("config", "executor & evaluator settings (runtime/settings.env)"),
        "q": ("quit", ""),
    }


def _front_page_handlers() -> dict[str, object]:
    return {
        "d": interactive_dispatch,
        "e": interactive_evaluate,
        "g": interactive_graphs,
        "w": interactive_watch,
        "h": interactive_heartbeat,
        "c": interactive_config,
    }


def interactive_evaluate():
    """Pick a graph → node → run the live judge → return to the menu."""
    while True:
        picked = _pick_graph("evaluate · graphs", back_label="main menu")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            return _MENU_BACK
        project = str(picked)
        try:
            nodes = list(_import_module("node_cli").iter_nodes(ROOT, project))
        except Exception as exc:
            console.print(Text(f"Could not load {project}: {exc}", style="red"))
            _pause()
            continue
        node_items = [(node_id, str(doc.get("title") or "")) for node_id, doc, _ in nodes]
        node_picked = _pick_list(
            f"evaluate · nodes · {project}",
            node_items,
            preview_cmd=_node_preview_cmd(project),
            back_label="graphs",
        )
        if node_picked is _MENU_QUIT:
            return _MENU_QUIT
        if node_picked is _MENU_BACK:
            continue
        node_id = node_picked[0] if isinstance(node_picked, list) else node_picked
        _clear_screen()
        console.print(Text(f"evaluate · {project} / {node_id}", style="bold"))
        _run_live_eval(project, node_id)
        _pause()
        return _MENU_BACK


def interactive_config():
    """Editor for executor & evaluator settings (runtime/settings.env)."""
    _clear_screen()
    console.print(Text("config · executor & evaluator settings", style="bold").append(
        f"  ·  {SETTINGS_FILE}", style="dim"
    ))
    console.print()
    console.print(Text("Values shown are in effect for subprocesses. Empty = default.", style="dim"))
    console.print()
    settings: dict[str, str] = {}
    for key, (label, hint) in SETTINGS_FIELDS.items():
        current = os.environ.get(key, "")
        console.print(Text(f"  {label}", style="bold cyan"))
        console.print(Text(f"    {hint}", style="dim"))
        try:
            answer = Prompt.ask(
                f"    [{key}] (enter = keep {current!r}, x = clear)",
                default=current,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if answer == "x":
            settings[key] = ""
        elif answer != current or answer:
            settings[key] = answer
        else:
            settings[key] = current
        console.print()
    _write_runtime_settings(settings)
    console.print(Text(f"  saved → {SETTINGS_FILE}", style="bold green"))
    _pause()
    return _MENU_BACK


def interactive_menu():
    """Front door: dispatch, graphs, live. Everything else is under a graph."""
    actions = _front_page_actions()
    while True:
        _clear_screen()
        console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
        try:
            choice = _menu_choice(actions, default="g")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if choice == "q":
            break
        try:
            if choice == "d":
                outcome = interactive_dispatch()
                if outcome is _MENU_QUIT:
                    break
                if outcome is not _MENU_BACK:
                    _pause()
            elif choice == "e":
                outcome = interactive_evaluate()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "g":
                outcome = interactive_graphs()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "w":
                interactive_watch()
            elif choice == "h":
                interactive_heartbeat()
            elif choice == "c":
                interactive_config()
        except SystemExit:
            pass
        except KeyboardInterrupt:
            break
    _clear_screen()
    console.print(Text("bye.", style="dim"))


# ---------------------------------------------------------------------------
# watch / steer — live observability + operator steering over the pi_rpc spool
# ---------------------------------------------------------------------------
# Read-only over filesystem truth: attempt dirs hold packet.json, pid,
# worktree_path, events.jsonl, result.json. watch never writes; steer appends
# one line to steer.jsonl, which the steer-aware supervisor drains.

def _spool_root(runtime_root: Path) -> Path:
    configured = os.environ.get("GDDP_PI_RPC_SPOOL_DIR") or os.environ.get(
        "GDDP_LOCAL_SUBPROCESS_SPOOL_DIR"
    )
    root = (
        Path(configured).expanduser()
        if configured
        else runtime_root / "jobs" / "local-subprocess-spool"
    )
    return root.resolve()


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


def _render_fleet(attempts: list[dict], now: float, *, running_only: bool) -> None:
    scope = "running" if running_only else "all"
    print(
        f"gddp watch · {scope} — {len(attempts)} attempt(s)  "
        f"({time.strftime('%H:%M:%S')})"
    )
    if not attempts:
        print("  (none live right now)")
        print("  tip: gddp watch --all   ·   gddp jobs live")
        return
    print(
        f"{'NODE':34} {'STATE':8} {'AGE':>7} {'DIFF':>22} {'QUIET':>6}  JOB"
    )
    for info in attempts:
        shortstat, untracked = _diff_summary(info["worktree"])
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
    print("  drill in:  gddp watch <node-id|job-id>")
    print("  events:    tail -F <spool>/…/events.jsonl  (path in single view)")


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
    print("\n  live stream:  tail -F " + str(info.get("events_path") or (info["dir"] / "events.jsonl")))


def cmd_watch(args) -> int:
    """Live execution view. Default fleet = running only (`--all` for history)."""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: live/watch unavailable: {exc}", file=sys.stderr)
        print("  Set GDDP_RUNTIME_ROOT to a gddp-runtime checkout.", file=sys.stderr)
        return 2
    spool = _spool_root(runtime_root)
    if not spool.is_dir():
        print(f"no spool at {spool}; nothing has run yet", file=sys.stderr)
        print("  live needs a local-subprocess spool from gddp-runtime.", file=sys.stderr)
        return 1
    tty = sys.stdout.isatty()
    running_only = not bool(getattr(args, "all", False))
    project = getattr(args, "project", None) or None
    try:
        while True:
            attempts = _scan_attempts(spool)
            if args.target:
                info = _find_attempt(attempts, args.target)
                if info is None:
                    # Retry against unfiltered spool names even if done.
                    info = _find_attempt(_scan_attempts(spool), args.target)
                if info is None:
                    print(f"no attempt matching {args.target!r}", file=sys.stderr)
                    return 1
            else:
                attempts = _filter_attempts(
                    attempts, running_only=running_only, project=project
                )
            if tty and not args.once:
                sys.stdout.write("\033[2J\033[H")
            now = time.time()
            if args.target:
                _render_single(info, now)
            else:
                _render_fleet(attempts, now, running_only=running_only)
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
    )
    try:
        rc = cmd_watch(ns)
    except KeyboardInterrupt:
        print()
        return _MENU_BACK
    except RuntimeError as exc:
        console.print(Text(f"ERROR: live/watch unavailable: {exc}", style="bold red"))
        console.print(Text("Set GDDP_RUNTIME_ROOT to a gddp-runtime checkout.", style="dim"))
        _pause()
        return _MENU_BACK
    if rc != 0:
        _pause("live/watch could not start — press any key to return")
    return _MENU_BACK


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
        shortstat, untracked = _diff_summary(info.get("worktree"))
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
    spool = _spool_root(runtime_root)
    if not spool.is_dir():
        print(f"no spool at {spool}; nothing has run yet", file=sys.stderr)
        return 1

    running_only = not bool(getattr(args, "all", False))
    project = getattr(args, "project", None) or None
    attempts = _filter_attempts(
        _scan_attempts(spool),
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
        events = info.get("events_path") or str(Path(attempt_dir) / "events.jsonl")
        print(f"tail -F {events}")
        try:
            os.execvp("tail", ["tail", "-F", events])
        except OSError as exc:
            print(f"could not exec tail: {exc}", file=sys.stderr)
            return 1
    if action in {"show", "job", "j"}:
        return run_runtime_jobs(["show", target])
    if action in {"path", "print"}:
        print(attempt_dir)
        print(info.get("events_path") or "")
        return 0

    # Default: enter live single-target watch (same as agent-runs → open).
    return cmd_watch(
        argparse.Namespace(
            target=target,
            interval=float(getattr(args, "interval", 2.0) or 2.0),
            once=bool(getattr(args, "once", False)),
            all=True,  # single target: allow done attempts too
            project=None,
        )
    )


def cmd_steer(args) -> int:
    runtime_root = resolve_runtime_root()
    attempts = _scan_attempts(_spool_root(runtime_root))
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
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "message": message}
    )
    with (info["dir"] / "steer.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(f"steer queued for {info['node_id'] or info['name']}: {message}")
    print("delivered on the supervisor's next read cycle (needs the steer-aware runtime)")
    return 0


def cmd_overview(_args):
    if sys.stdin.isatty() and sys.stdout.isatty():
        return interactive_menu()
    static_overview()
    return 0


def cmd_receipt(args) -> int:
    """Delegate mission worker receipt writes to runtime's receipt CLI."""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    script = runtime_root / "scripts" / "gddp_node_receipt.py"
    if not script.is_file():
        print(f"ERROR: receipt backend not found at {script}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(script),
        "--node-id",
        args.node_id,
        "--base",
        args.base,
        "--result",
        args.result,
    ]
    env = os.environ.copy()
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def cmd_verify_node(args):
    """Delegate node verification to the runtime evaluator — the single judge.

    Default runs the deterministic lane (offline, fast — the verb's original
    contract). --live runs the full two-lane evaluation (deterministic +
    semantic + integrity), the same judge the pipeline uses.
    """
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    node_yaml = ROOT / "graphs" / args.project / "nodes" / f"{args.node}.yaml"
    project_yaml = ROOT / "graphs" / args.project / "project.yaml"
    for path, label in ((node_yaml, "node yaml"), (project_yaml, "project yaml")):
        if not path.is_file():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            sys.exit(2)

    with open(project_yaml) as f:
        proj = yaml.safe_load(f) or {}
    repo_name = str(proj.get("repo", "")).split("/")[-1]
    repo = None
    candidates = []
    if args.repo_path:
        candidates.append(Path(args.repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for c in candidates:
        if c.is_dir():
            repo = c
            break
    if repo is None:
        print(f"ERROR: could not resolve repo checkout for '{proj.get('repo', '')}' "
              "(pass --repo-path)", file=sys.stderr)
        sys.exit(2)

    receipt_dir = ROOT / "verification"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    live = bool(getattr(args, "live", False))
    manual_job_id = "manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cmd = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "verification" / "cli.py"),
        "--node-yaml", str(node_yaml),
        "--project-yaml", str(project_yaml),
        "--repo", str(repo),
        "--config-root", str(ROOT),
        "--receipt-dir", str(receipt_dir),
        "--job-id", manual_job_id,
        "--attempt", "0",
        *(["--base", args.base] if getattr(args, "base", None) else []),
        "--semantic-mode", "live" if live else "offline",
        # --live must select the Pi harness explicitly: auto resolves to the
        # removed built-in runner and the evaluator refuses to start.
        *(["--semantic-harness", "pi"] if live else []),
        "--integrity", "on" if live else "off",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


def _resolve_repo_for_project(project: str, repo_path: str | None = None) -> Path | None:
    """Resolve a project's source checkout: --repo-path > env root > sibling."""
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    if not project_yaml.is_file():
        return None
    try:
        with open(project_yaml) as f:
            proj = yaml.safe_load(f) or {}
    except Exception:
        return None
    repo_name = str(proj.get("repo", "")).split("/")[-1]
    candidates: list[Path] = []
    if repo_path:
        candidates.append(Path(repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _auto_base_commit(repo: Path) -> str | None:
    """Best-effort base for subject-diff evidence: HEAD~1, else HEAD."""
    for ref in ("HEAD~1", "HEAD"):
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", ref],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None


_EVAL_PRESETS = {"cheap": "deepseek-v4-flash"}
_EVAL_LENSES = frozenset({"config", "instructions", "runs", "show"})


class EvalKnobError(ValueError):
    """Operator-facing failure resolving evaluator knobs."""


def _parse_semantic_flag(args_str: str, flag: str) -> str | None:
    try:
        tokens = shlex.split(args_str or "")
    except ValueError:
        return None
    try:
        idx = tokens.index(flag)
    except ValueError:
        return None
    if idx + 1 >= len(tokens):
        return None
    return tokens[idx + 1]


def _resolve_eval_knobs(
    *,
    model: str | None = None,
    thinking: str | None = None,
    integrity: str | None = None,
    lanes: str | None = None,
    base: str | None = None,
) -> dict:
    """Resolve evaluator knobs: explicit args → env/settings → defaults."""
    env_args = os.environ.get("GDDP_VERIFY_SEMANTIC_ARGS", DEFAULT_SEMANTIC_ARGS)
    env_model = (
        os.environ.get("GDDP_EVAL_MODEL_CHEAP")
        or _parse_semantic_flag(env_args, "--semantic-pi-model")
        or _EVAL_PRESETS["cheap"]
    )
    env_thinking = (
        os.environ.get("GDDP_SEMANTIC_THINKING")
        or os.environ.get("GDDP_EVAL_THINKING_DEFAULT")
        or _parse_semantic_flag(env_args, "--semantic-thinking")
        or "medium"
    )
    env_integrity = (os.environ.get("GDDP_INTEGRITY_MODE") or "on").strip().lower()
    env_lanes = (os.environ.get("GDDP_EVAL_LANES_DEFAULT") or "").strip().lower()
    if not env_lanes:
        mode = _parse_semantic_flag(env_args, "--semantic-mode")
        env_lanes = "deterministic" if mode == "offline" else "live"

    preset: str | None = None
    raw_model = (model or "").strip()
    if not raw_model:
        resolved_model = env_model
    elif raw_model == "cheap" or raw_model in _EVAL_PRESETS:
        preset = "cheap"
        resolved_model = (
            os.environ.get("GDDP_EVAL_MODEL_CHEAP") or _EVAL_PRESETS["cheap"]
        ).strip() or _EVAL_PRESETS["cheap"]
    elif raw_model == "expensive":
        preset = "expensive"
        resolved_model = (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip()
        if not resolved_model:
            raise EvalKnobError(
                "expensive preset is unset — set GDDP_EVAL_MODEL_EXPENSIVE"
            )
    else:
        resolved_model = raw_model

    resolved_thinking = (thinking or env_thinking).strip() or "medium"
    explicit_integrity = integrity is not None and str(integrity).strip() != ""
    resolved_integrity = (
        str(integrity).strip().lower() if explicit_integrity else env_integrity
    )
    if resolved_integrity not in {"on", "off"}:
        raise EvalKnobError(f"integrity must be on or off, got {resolved_integrity!r}")
    resolved_lanes = (lanes or env_lanes).strip().lower() or "live"
    if resolved_lanes not in {"live", "deterministic"}:
        raise EvalKnobError(
            f"lanes must be live or deterministic, got {resolved_lanes!r}"
        )
    if resolved_lanes == "deterministic" and not explicit_integrity:
        resolved_integrity = "off"

    if resolved_lanes == "deterministic":
        semantic_args = "--semantic-mode offline"
    else:
        semantic_args = (
            "--semantic-mode live --semantic-harness pi --semantic-provider deepseek "
            f"--semantic-pi-model {resolved_model} --semantic-thinking {resolved_thinking}"
        )
    return {
        "model": resolved_model,
        "preset": preset,
        "thinking": resolved_thinking,
        "integrity": resolved_integrity,
        "lanes": resolved_lanes,
        "semantic_args": semantic_args,
        "base": base,
    }


def _write_eval_knobs_sidecar(
    receipt_dir: Path,
    project: str,
    node_id: str,
    job_id: str,
    attempt: int,
    knobs: dict,
) -> Path | None:
    """Best-effort sidecar next to the receipt. Never fails the eval."""
    path = Path(receipt_dir) / project / node_id / f"{job_id}-attempt{attempt}.knobs.json"
    payload = {
        "model": knobs.get("model"),
        "preset": knobs.get("preset"),
        "thinking": knobs.get("thinking"),
        "integrity": knobs.get("integrity"),
        "lanes": knobs.get("lanes"),
        "base": knobs.get("base"),
        "semantic_args": knobs.get("semantic_args"),
        "job_id": job_id,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
    except OSError as exc:
        print(f"warning: could not write knobs sidecar {path}: {exc}", file=sys.stderr)
        return None


def _load_eval_knobs_sidecar(receipt_path: str | Path) -> dict:
    """Load sibling *.knobs.json next to a receipt; empty dict if missing."""
    sidecar = Path(receipt_path).with_suffix(".knobs.json")
    if not sidecar.is_file():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_live_eval(
    project: str,
    node_id: str,
    base: str | None = None,
    knobs: dict | None = None,
) -> str:
    """Run the live two-lane judge on one node; print a compact summary.

    Single code path for the interactive menu (`evaluate` front-page action,
    `v` in the node review menu) and the `gddp eval <node>` shell command.
    Auto-resolves the repo and base commit. Returns the verdict string
    ("pass"/"fail"/...) or "" on error.
    """
    try:
        resolved = knobs or _resolve_eval_knobs(base=base)
    except EvalKnobError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""
    node_yaml = ROOT / "graphs" / project / "nodes" / f"{node_id}.yaml"
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    for path, label in ((node_yaml, "node yaml"), (project_yaml, "project yaml")):
        if not path.is_file():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            return ""
    repo = _resolve_repo_for_project(project)
    if repo is None:
        print(
            f"ERROR: could not resolve repo checkout for project '{project}' "
            f"(pass --repo-path)",
            file=sys.stderr,
        )
        return ""
    base_sha = base or resolved.get("base") or _auto_base_commit(repo)
    resolved = {**resolved, "base": base_sha}
    receipt_dir = ROOT / "verification"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    job_id = "manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = 0

    cmd = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "verification" / "cli.py"),
        "--node-yaml", str(node_yaml),
        "--project-yaml", str(project_yaml),
        "--repo", str(repo),
        "--config-root", str(ROOT),
        "--receipt-dir", str(receipt_dir),
        "--job-id", job_id,
        "--attempt", str(attempt),
    ]
    if base_sha:
        cmd += ["--base", base_sha]
    cmd += shlex.split(str(resolved.get("semantic_args") or DEFAULT_SEMANTIC_ARGS))
    cmd += ["--integrity", "off" if str(resolved.get("integrity") or "on").lower() == "off" else "on"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)

    print(f"  evaluating {project}/{node_id}  (base {base_sha[:8] if base_sha else 'n/a'})")
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True, check=False)
    _write_eval_knobs_sidecar(receipt_dir, project, node_id, job_id, attempt, resolved)
    receipt_summary: dict = {}
    if proc.stdout.strip():
        try:
            receipt_summary = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            receipt_summary = {}
    if proc.returncode != 0 and not receipt_summary:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        return ""

    verdict = str(receipt_summary.get("verdict", ""))
    confidence = receipt_summary.get("criteria_confidence", "")
    action = receipt_summary.get("required_next_action", "")
    lane = receipt_summary.get("lane_status", {})
    print()
    chip = Text(f"  VERDICT  {verdict.upper()}", style=("bold green" if verdict == "pass" else "bold red"))
    console.print(chip)
    preset = resolved.get("preset")
    model = resolved.get("model") or "-"
    print(f"  model      : {preset}/{model}" if preset else f"  model      : {model}")
    if confidence:
        print(f"  confidence : {confidence}")
    if lane:
        crit = (lane.get("criteria") or "").replace("_", " ")
        integ = (lane.get("integrity") or "").replace("_", " ")
        print(f"  lanes     : criteria {crit} · integrity {integ}")
    if action:
        print(f"  next      : {action}")
    print(f"  receipts  : {ROOT / 'verification' / project / node_id}/")
    return verdict


def _resolve_eval_node(project: str | None, node_id: str) -> tuple[str, str] | int:
    """Fuzzy-resolve (project, node_id). Returns an exit code on failure."""
    def _match_in(proj_name: str) -> list[str]:
        nodes_dir = ROOT / "graphs" / proj_name / "nodes"
        if not nodes_dir.is_dir():
            return []
        return [
            f.stem for f in nodes_dir.glob("*.yaml")
            if f.stem == node_id or f.stem.startswith(f"{node_id}-") or node_id in f.stem
        ]

    if project:
        stems = _match_in(project)
        if len(stems) == 1:
            return project, stems[0]
        if len(stems) > 1:
            print(f"Ambiguous node '{node_id}' in project '{project}' — matches: {stems}", file=sys.stderr)
            return 2
        print(f"ERROR: node '{node_id}' not found in graph '{project}'", file=sys.stderr)
        return 2
    matches = []
    graphs = ROOT / "graphs"
    if graphs.is_dir():
        for proj_dir in graphs.iterdir():
            if not proj_dir.is_dir() or proj_dir.name.startswith(("_", ".")):
                continue
            for stem in _match_in(proj_dir.name):
                matches.append((proj_dir.name, stem))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous node '{node_id}' — matches:", file=sys.stderr)
        for proj_name, stem in matches:
            print(f"  {proj_name}/{stem}", file=sys.stderr)
        print("Pass --project <id>", file=sys.stderr)
        return 2
    print(f"ERROR: node '{node_id}' not found in any graph", file=sys.stderr)
    return 2


def cmd_eval(args):
    """Human-friendly live evaluation: gddp eval <node> [--project p].

    First token in {config,instructions,runs,show} is a lens; otherwise a node
    id. Auto-resolves project/node, repo, and base commit.
    """
    token = getattr(args, "node", None)
    if token in _EVAL_LENSES:
        handler = globals().get(f"cmd_eval_{token}")
        if handler is None:
            print(f"ERROR: eval {token} is not available", file=sys.stderr)
            return 2
        return handler(args)
    if not token:
        print("ERROR: gddp eval needs a node id (or config|instructions|runs|show)", file=sys.stderr)
        return 2
    resolved = _resolve_eval_node(getattr(args, "project", None), token)
    if isinstance(resolved, int):
        return resolved
    project, node_id = resolved
    try:
        knobs = _resolve_eval_knobs(
            model=getattr(args, "model", None),
            thinking=getattr(args, "thinking", None),
            integrity=getattr(args, "integrity", None),
            lanes=getattr(args, "lanes", None),
            base=getattr(args, "base", None),
        )
    except EvalKnobError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    verdict = _run_live_eval(project, node_id, base=knobs.get("base"), knobs=knobs)
    if not verdict:
        return 1
    return 0


def cmd_obsidian_export(args):
    obsidian_export = _import_module("obsidian_export")
    argv = ["--project", args.project]
    if args.vault:
        argv += ["--vault", str(args.vault)]
    if args.dry_run:
        argv.append("--dry-run")
    sys.exit(obsidian_export.main(argv))


def cmd_deliver(args):
    """Publish a graph's delivery commit, or list/retire its transport refs.

    Scriptable counterpart to the `deliver` action in the graph hub `more`
    menu — same run_graph_delivery boundary, no in-process mutation either way.
    """
    sys.exit(run_graph_delivery(
        args.subcommand, args.project, delete=getattr(args, "delete", False)
    ))


def cmd_project_new(args):
    if args.from_outline:
        outline = _import_module("outline_to_nodes")
        sys.exit(outline.main(
            outline_path=args.from_outline,
            project_id=args.project_id,
            repo=args.repo,
            project_name=args.project_name,
            dry_run=args.dry_run,
            force=args.force,
        ))
    elif args.from_graphify:
        graphify = _import_module("graphify_to_nodes")
        sys.argv = [
            "graphify_to_nodes",
            "--input", str(args.from_graphify),
            "--project-id", args.project_id,
            "--repo", args.repo or "",
        ]
        if args.project_name:
            sys.argv.extend(["--project-name", args.project_name])
        if args.dry_run:
            sys.argv.append("--dry-run")
        if args.force:
            sys.argv.append("--force")
        sys.exit(graphify.main())
    else:
        rapid = _import_module("rapid_add")
        rapid.ensure_project_shell(ROOT, args.project_id, args.repo, args.project_name)
        print(f"Created empty project: graphs/{args.project_id}/")
        print(f"Next: gddp node rapid --project {args.project_id} --repo {args.repo}")


def cmd_project_validate(args):
    validate_project(args.project)


def _list_status_projects() -> list[str]:
    graphs = ROOT / "graphs"
    if not graphs.exists():
        return []
    return sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )


def _load_project_doc(project_id: str) -> dict:
    with open(ROOT / "graphs" / project_id / "project.yaml") as f:
        return yaml.safe_load(f) or {}


def _graph_status_counts(nodes: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        s = str(n.get("status") or "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


def _pct_style(pct: int) -> str:
    if pct >= 100:
        return "bold green"
    if pct > 0:
        return "bold yellow"
    return "dim"


def _status_counts_text(counts: dict[str, int]) -> Text:
    out = Text()
    for i, (status, count) in enumerate(sorted(counts.items())):
        if i:
            out.append(", ", style="dim")
        out.append(status, style=_graph_status_style(status))
        out.append(f"={count}")
    return out


def _print_status_project_row(project_id: str, nodes: list, *, indent: str = "") -> tuple[int, int]:
    """Print one project summary line. Returns (complete, total)."""
    counts = _graph_status_counts(nodes)
    total = sum(counts.values())
    complete = counts.get("complete", 0)
    pct = int(complete / total * 100) if total else 0
    row = Text(indent)
    row.append(f"{project_id:<25}", style="bold")
    row.append(f" {total:>3} nodes  ", style="dim")
    row.append(f"{pct:>3}% done", style=_pct_style(pct))
    row.append("  (", style="dim")
    row.append_text(_status_counts_text(counts))
    row.append(")", style="dim")
    console.print(row)
    return complete, total


def show_status(project_id: str | None = None) -> None:
    """Rich graph completion summary — all projects or one project with nodes."""
    projects = _list_status_projects()
    if not projects:
        console.print(Text("No graphs/ directory found", style="yellow"))
        return
    if project_id:
        if project_id not in projects:
            console.print(Text(f"Project '{project_id}' not found", style="red"))
            return
        _render_project_status_detail(project_id)
        return

    console.print(Text("status · all projects", style="bold"))
    total_complete = 0
    grand = 0
    for pid in projects:
        proj = _load_project_doc(pid)
        complete, total = _print_status_project_row(pid, proj.get("nodes") or [])
        total_complete += complete
        grand += total
    gpct = int(total_complete / grand * 100) if grand else 0
    footer = Text()
    footer.append(f"{'TOTAL':<25}", style="bold")
    footer.append(f" {grand:>3} nodes  ", style="dim")
    footer.append(f"{gpct:>3}% done", style=_pct_style(gpct))
    console.print()
    console.print(footer)


def _render_project_status_detail(project_id: str) -> None:
    """One project: colored counts + each node with runtime phase."""
    node_cli = _import_module("node_cli")
    proj = _load_project_doc(project_id)
    nodes_index = proj.get("nodes") or []
    console.print(Text(f"status · {project_id}", style="bold"))
    _print_status_project_row(project_id, nodes_index)
    console.print()

    try:
        node_rows = node_cli.iter_nodes(ROOT, project_id)
    except Exception as exc:
        console.print(Text(f"Could not load nodes: {exc}", style="red"))
        return
    if not node_rows:
        console.print(Text("(no nodes)", style="dim"))
        return

    phase_counts: dict[str, int] = {}
    verdict_counts: dict[str, int] = {}
    for node_id, doc, entry in node_rows:
        graph_status = _node_status_label(doc, entry)
        queue_state = "-"
        job_status = "-"
        verdict = "-"
        try:
            ev = node_cli.fetch_runtime_evidence(ROOT, project_id, node_id)
            queue_state = getattr(ev, "queue_state", "-") or "-"
            job_status = getattr(ev, "job_status", "-") or "-"
            verdict = getattr(ev, "verdict", "-") or "-"
        except Exception:
            pass
        phase = _node_menu_phase(graph_status, queue_state, job_status)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        chip = _verdict_chip(verdict)
        if chip:
            key = chip.lower()
            verdict_counts[key] = verdict_counts.get(key, 0) + 1
        title = str(doc.get("title") or (entry or {}).get("title") or "")
        line = Text()
        line.append(f"  {node_id:<36}", style="bold")
        line.append_text(_format_node_columns(
            graph=graph_status,
            runtime=_runtime_label(queue_state, job_status),
            verdict=verdict,
            title=title,
            room=max(24, (console.width or 80) - 40),
        ))
        console.print(line)

    console.print()
    scan = Text("  operator scan  ")
    scan.append_text(_status_counts_text(phase_counts))
    console.print(scan)
    if verdict_counts:
        ev_scan = Text("  evaluator       ")
        ev_scan.append_text(_status_counts_text(verdict_counts))
        console.print(ev_scan)


def interactive_graph_delivery(project: str):
    """Publish this graph's delivery commit, or retire its transport refs.

    Both mutate origin. Neither runs without this explicit confirmation —
    publish and cleanup are never triggered as a side effect of any other
    graph action (dispatch, node review, etc.).
    """
    actions = {
        "p": ("publish", f"push the delivery commit to review/{project}"),
        "c": ("cleanup", "list, then optionally delete, transport refs"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    confirm = {"y": ("yes", ""), "n": ("no", "")}
    while True:
        _clear_screen()
        console.print(Text("deliver", style="bold").append(f"  ·  {project}", style="dim"))
        choice = _menu_choice(actions, default="p")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "p":
            console.print(
                f"Publish [bold]{project}[/bold]'s delivery commit to "
                f"[bold cyan]review/{project}[/bold cyan]?"
            )
            if _menu_choice(confirm, default="n") == "y":
                run_graph_delivery("publish", project)
            _pause()
        elif choice == "c":
            console.print(Text("dry run — nothing deleted yet:", style="dim"))
            run_graph_delivery("cleanup", project)
            console.print("Delete the ref(s) listed above?")
            if _menu_choice(confirm, default="n") == "y":
                run_graph_delivery("cleanup", project, delete=True)
            _pause()


def interactive_status(project: str | None = None):
    """Status for one graph, or all/one picker when no project is fixed."""
    if project:
        _clear_screen()
        show_status(project)
        _pause()
        return _MENU_BACK
    actions = {
        "a": ("all", "every project completion summary"),
        "o": ("one", "pick one project — counts + node phases"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("status", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            show_status()
            _pause()
            continue
        picked = _pick_graph("status · graphs", back_label="status")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        _clear_screen()
        show_status(str(picked))
        _pause()


def interactive_validate(project: str | None = None):
    """Validate one graph, or all/one picker when no project is fixed."""
    if project:
        _clear_screen()
        validate_project(project)
        _pause()
        return _MENU_BACK
    actions = {
        "a": ("all", "validate every project"),
        "o": ("one", "pick one project"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("validate", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            validate_project(None)
            _pause()
            continue
        picked = _pick_graph("validate · graphs", back_label="validate")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        _clear_screen()
        validate_project(str(picked))
        _pause()


def validate_project(project_id: str | None):
    graphs = ROOT / "graphs"
    if not graphs.exists():
        console.print(Text("No graphs/ directory found", style="yellow"))
        return

    projects = _list_status_projects()
    if project_id:
        if project_id not in projects:
            console.print(Text(f"Project '{project_id}' not found", style="red"))
            return
        projects = [project_id]

    errors = 0
    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}

        pid_errors = []

        if proj.get("schema_version") != "1.0":
            pid_errors.append("schema_version != 1.0")
        if not proj.get("project_id"):
            pid_errors.append("missing project_id")
        if proj.get("project_id") != pid:
            pid_errors.append(f"project_id '{proj.get('project_id')}' != directory '{pid}'")
        if not proj.get("repo"):
            pid_errors.append("missing repo")
        nodes = proj.get("nodes")
        if not isinstance(nodes, list):
            pid_errors.append("nodes is not a list")
        else:
            node_ids = set()
            for n in nodes:
                if not isinstance(n, dict):
                    pid_errors.append(f"nodes entry is not a dict: {n}")
                    continue
                nid = n.get("id")
                if not nid:
                    pid_errors.append("nodes entry missing id")
                    continue
                if nid in node_ids:
                    pid_errors.append(f"duplicate node id in project.yaml: {nid}")
                node_ids.add(nid)

            nodes_dir = graphs / pid / "nodes"
            yaml_ids = set()
            if nodes_dir.exists():
                yaml_ids = {p.stem for p in nodes_dir.glob("*.yaml")}

            missing_yaml = node_ids - yaml_ids
            orphan_yaml = yaml_ids - node_ids
            if missing_yaml:
                for nid in sorted(missing_yaml):
                    pid_errors.append(f"project.yaml lists {nid} but no nodes/{nid}.yaml exists")
            if orphan_yaml:
                for nid in sorted(orphan_yaml):
                    pid_errors.append(f"nodes/{nid}.yaml exists but not listed in project.yaml")

        if pid_errors:
            console.print(Text(pid, style="bold red"))
            for e in pid_errors:
                console.print(Text(f"  ERROR: {e}", style="red"))
            errors += len(pid_errors)
        else:
            line = Text()
            line.append(pid, style="bold green")
            line.append(" OK", style="green")
            console.print(line)

    summary = Text()
    summary.append(f"\n{errors} error(s)", style="bold red" if errors else "bold green")
    summary.append(f" across {len(projects)} project(s)", style="dim")
    console.print(summary)
    return 1 if errors else 0


def main(argv=None):
    _load_runtime_settings()
    argv = list(sys.argv[1:] if argv is None else argv)
    # Positional dispatch: gddp <graph|node> [executor] [--yes]. Anything that
    # is not a known subcommand is an exact graph or node target.
    if argv and argv[0] not in _CLI_COMMANDS and not argv[0].startswith("-"):
        return cmd_dispatch(argv)
    parser = argparse.ArgumentParser(
        description="gddp — graph truth and runtime evidence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=cmd_overview)
    sub = parser.add_subparsers(dest="command")

    node_p = sub.add_parser("node", help="Node operations")
    node_sub = node_p.add_subparsers(dest="subcommand")

    node_browse = node_sub.add_parser(
        "browse", help="Interactive node review and graph-status menu")
    node_browse.add_argument(
        "--project", default=None, help="Open this project directly")
    node_browse.set_defaults(func=cmd_node_browse)

    node_new = node_sub.add_parser("new", help="Interactive TUI node scaffold (full editor)")
    node_new.set_defaults(func=cmd_node_new)

    node_rapid = node_sub.add_parser("rapid", help="Minimal-keystroke rapid node adder")
    node_rapid.add_argument("--project", required=True, help="Project ID")
    node_rapid.add_argument("--repo", default="")
    node_rapid.add_argument("--project-name", default=None)
    node_rapid.add_argument("--llm-draft", action="store_true",
                            help="Use LLM to draft why/acceptance/constraints")
    node_rapid.add_argument("--dry-run", action="store_true")
    node_rapid.set_defaults(func=cmd_node_rapid)

    node_batch = node_sub.add_parser("batch", help="Walk through REPLACE_ME nodes in a project")
    node_batch.add_argument("--project", required=True, help="Project ID")
    node_batch.set_defaults(func=cmd_node_batch)

    node_import = node_sub.add_parser("import", help="Import node YAML from file or stdin")
    node_import.add_argument("--file", type=Path, default=None, help="YAML file to import")
    node_import.add_argument("--stdin", action="store_true", help="Read YAML from stdin")
    node_import.add_argument("--project", required=True, help="Project ID")
    node_import.add_argument("--auto-approve", action="store_true")
    node_import.add_argument("--dry-run", action="store_true")
    node_import.add_argument(
        "--update", action="store_true",
        help="Replace an existing node; preserve its status",
    )
    node_import.set_defaults(func=cmd_node_import)

    node_val = node_sub.add_parser("validate", help="Validate nodes")
    node_val.add_argument("--project", default=None, help="Only check this project")
    node_val.add_argument("--json", action="store_true", help="Machine-readable output")
    node_val.add_argument("--strict", action="store_true", help="Warnings count as errors")
    node_val.add_argument("--quiet", action="store_true", help="Only summary line")
    node_val.add_argument("--root", type=Path, default=None)
    node_val.set_defaults(func=cmd_node_validate)

    node_list = node_sub.add_parser(
        "list", help="List nodes (ID | GRAPH | RUNTIME | VERDICT)")
    node_list.add_argument("--project", default=None, help="Project ID (omit for all)")
    node_list.add_argument("--status", default=None, help="Filter by graph status")
    node_list.add_argument(
        "--active", action="store_true",
        help="Only graph status pending or ready",
    )
    node_list.set_defaults(func=cmd_node_list)

    node_show = node_sub.add_parser(
        "show", help="Show one node + evaluator summary")
    node_show.add_argument("--project", required=True, help="Project ID")
    node_show.add_argument("node_id", help="Node ID")
    node_show.add_argument(
        "--trace", action="store_true",
        help="Expand tool traces and result/job history",
    )
    node_show.add_argument(
        "--view",
        choices=("all", "summary", "evaluation", "contract"),
        default="all",
        help="Limit output to one operator view",
    )
    node_show.set_defaults(func=cmd_node_show)

    node_status = node_sub.add_parser(
        "status", help="Status summary (all projects, or one with --project)"
    )
    node_status.add_argument(
        "--project", default=None, help="One project — counts + node phases"
    )
    node_status.set_defaults(func=cmd_node_status)

    evals_p = sub.add_parser(
        "evaluations",
        help="List evaluator receipts with verdict and timing",
    )
    evals_p.set_defaults(func=cmd_evaluations)

    jobs_p = sub.add_parser("jobs", help="Runtime jobs and evaluator evidence")
    jobs_p.set_defaults(func=cmd_jobs)

    watch_p = sub.add_parser(
        "watch",
        help="Live running executors (default: running only; drill-in by node/job)",
    )
    watch_p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="node id, job id, or attempt-dir prefix; omit for fleet",
    )
    watch_p.add_argument(
        "--interval", type=float, default=2.0, help="refresh seconds (default 2)"
    )
    watch_p.add_argument("--once", action="store_true", help="render once and exit")
    watch_p.add_argument(
        "--all",
        action="store_true",
        help="include done/dead spool history (default: running only)",
    )
    watch_p.add_argument(
        "--project", default=None, help="limit fleet to one graph/project id"
    )
    watch_p.set_defaults(func=cmd_watch)

    runs_p = sub.add_parser(
        "runs",
        help="fzf picker over attempts (agent-runs style); Enter → gddp watch",
    )
    runs_p.add_argument(
        "--all",
        action="store_true",
        help="include done/dead history (default: running only)",
    )
    runs_p.add_argument(
        "--project", default=None, help="limit to one graph/project id"
    )
    runs_p.add_argument(
        "--list", action="store_true", help="print catalog (no fzf)"
    )
    runs_p.add_argument(
        "--preview",
        default=None,
        metavar="DIR",
        help=argparse.SUPPRESS,  # fzf --preview callback
    )
    runs_p.add_argument(
        "--action",
        default="watch",
        choices=("watch", "events", "show", "path"),
        help="after pick: watch (default), events (tail -F), show (jobs show), path",
    )
    runs_p.add_argument(
        "--once", action="store_true", help="with action=watch: one frame then exit"
    )
    runs_p.add_argument(
        "--interval", type=float, default=2.0, help="watch refresh seconds"
    )
    runs_p.add_argument(
        "--height", default="90%", help="fzf height (default 90%%)"
    )
    runs_p.set_defaults(func=cmd_runs)

    steer_p = sub.add_parser(
        "steer", help="Send an operator message into a running attempt's session"
    )
    steer_p.add_argument("target", help="node id, job id, or attempt-dir prefix")
    steer_p.add_argument("message", nargs="+", help="message text")
    steer_p.set_defaults(func=cmd_steer)
    jobs_sub = jobs_p.add_subparsers(dest="jobs_command")

    jobs_list = jobs_sub.add_parser("list", help="List jobs and queue states")
    jobs_list.add_argument("--state", default=None, help="Filter by queue state")
    jobs_list.set_defaults(func=cmd_jobs)

    jobs_show = jobs_sub.add_parser("show", help="Show one job by job ID or node ID")
    jobs_show.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_show.add_argument(
        "--full", action="store_true", help="Include criterion-level reasoning"
    )
    jobs_show.set_defaults(func=cmd_jobs)

    jobs_live = jobs_sub.add_parser(
        "live",
        help="Live running executors (alias for gddp watch)",
    )
    jobs_live.add_argument(
        "target",
        nargs="?",
        default=None,
        help="node id, job id, or attempt prefix; omit for fleet",
    )
    jobs_live.add_argument(
        "--interval", type=float, default=2.0, help="refresh seconds (default 2)"
    )
    jobs_live.add_argument("--once", action="store_true", help="render once and exit")
    jobs_live.add_argument(
        "--all", action="store_true", help="include done/dead history"
    )
    jobs_live.add_argument(
        "--project", default=None, help="limit fleet to one graph/project id"
    )
    jobs_live.set_defaults(func=cmd_jobs, jobs_command="live")

    jobs_results = jobs_sub.add_parser("results", help="Summarize evaluator output")
    jobs_results.add_argument("--all", action="store_true", help="List every result row")
    jobs_results.set_defaults(func=cmd_jobs)

    jobs_set = jobs_sub.add_parser("set", help="Change runtime job state")
    jobs_set.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_set.add_argument("state", help="New runtime job state")
    jobs_set.add_argument(
        "--reason",
        required=True,
        help="Why; stored in the runtime audit row",
    )
    jobs_set.add_argument("--yes", action="store_true", help="Skip confirmation")
    jobs_set.set_defaults(func=cmd_jobs)

    jobs_retry = jobs_sub.add_parser(
        "retry", help="Reject a reviewed result and retry the same node"
    )
    jobs_retry.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_retry.add_argument(
        "--reason", required=True, help="Human fix-list injected into the retry"
    )
    jobs_retry.add_argument("--yes", action="store_true", help="Skip confirmation")
    jobs_retry.set_defaults(func=cmd_jobs)

    receipt_p = sub.add_parser(
        "receipt",
        help="Append a mission worker node receipt (requires GDDP_RECEIPTS_PATH)",
    )
    receipt_p.add_argument("--node-id", required=True, help="Graph/feature node id")
    receipt_p.add_argument("--base", required=True, help="Starting commit SHA")
    receipt_p.add_argument("--result", required=True, help="Result commit SHA")
    receipt_p.set_defaults(func=cmd_receipt)

    verify_p = sub.add_parser("verify", help="Node evaluation harness")
    verify_sub = verify_p.add_subparsers(dest="subcommand")

    verify_node = verify_sub.add_parser(
        "node", help="Run the runtime evaluator on a node; emit a receipt")
    verify_node.add_argument("--project", required=True, help="Project ID")
    verify_node.add_argument("--node", required=True, help="Node ID")
    verify_node.add_argument("--repo-path", default=None,
                             help="Path to the source repo checkout "
                                  "(overrides auto-resolve)")
    verify_node.add_argument("--live", action="store_true",
                             help="Full two-lane evaluation (deterministic + semantic + integrity); default is the fast deterministic lane")
    verify_node.add_argument("--base", default=None,
                             help="Base commit the subject was built on; enables "
                                  "subject-diff evidence (pipeline runs get this "
                                  "from the session row automatically)")
    verify_node.set_defaults(func=cmd_verify_node)

    eval_p = sub.add_parser(
        "eval", help="Live two-lane evaluation on a node (human-friendly)")
    eval_p.add_argument(
        "node",
        nargs="?",
        help="Node ID, or a lens: config | instructions | runs | show",
    )
    eval_p.add_argument(
        "lens_node",
        nargs="?",
        default=None,
        help="Node ID when the first token is a lens",
    )
    eval_p.add_argument("--project", default=None,
                        help="Project ID (auto-resolved when unambiguous)")
    eval_p.add_argument("--base", default=None,
                        help="Base commit for subject-diff evidence "
                             "(default: HEAD~1)")
    eval_p.add_argument("--model", default=None,
                        help="Preset (cheap|expensive) or raw model id")
    eval_p.add_argument("--thinking", default=None,
                        help="Semantic thinking level (e.g. medium, high)")
    eval_p.add_argument("--integrity", choices=("on", "off"), default=None,
                        help="Integrity lane (default: on for live)")
    eval_p.add_argument("--lanes", choices=("live", "deterministic"), default=None,
                        help="Evaluator lanes (default: live)")
    eval_p.add_argument("--run", default=None,
                        help="Receipt job_id for instructions/show")
    eval_p.add_argument("--preflight", action="store_true",
                        help="Instructions lens: offered pointers only, no receipt")
    eval_p.set_defaults(func=cmd_eval)

    review_p = sub.add_parser(
        "review",
        help="Human-gate review surface: latest verdict, subject diff, merge state",
    )
    review_p.add_argument("--project", required=True, help="Project ID")
    review_p.add_argument("--node", required=True, help="Node ID")
    review_p.add_argument("--repo-path", default=None,
                          help="Path to the source repo checkout (overrides auto-resolve)")
    review_p.add_argument("--full", action="store_true",
                          help="Full patch instead of --stat")
    review_p.set_defaults(func=cmd_review)

    obs_p = sub.add_parser("obsidian", help="Obsidian vault export")
    obs_sub = obs_p.add_subparsers(dest="subcommand")

    obs_export = obs_sub.add_parser(
        "export", help="Export one graph to an Obsidian vault folder")
    obs_export.add_argument("--project", required=True,
                            help="Graph to export (graphs/<project>/)")
    obs_export.add_argument("--vault", type=Path, default=None,
                            help="Destination vault (default: ~/Obsidian/gdd-<project>)")
    obs_export.add_argument("--dry-run", action="store_true")
    obs_export.set_defaults(func=cmd_obsidian_export)

    deliver_p = sub.add_parser(
        "deliver", help="Publish a graph's delivery commit / retire transport refs")
    deliver_sub = deliver_p.add_subparsers(dest="subcommand")

    deliver_publish = deliver_sub.add_parser(
        "publish", help="Push the graph's unique delivery commit to review/<project>")
    deliver_publish.add_argument("project", help="Project ID")
    deliver_publish.set_defaults(func=cmd_deliver)

    deliver_cleanup = deliver_sub.add_parser(
        "cleanup", help="List (default) or delete this graph's gddp/attempt-*/result-* refs")
    deliver_cleanup.add_argument("project", help="Project ID")
    deliver_cleanup.add_argument(
        "--delete", action="store_true",
        help="Actually delete the refs (default: dry run, list only)",
    )
    deliver_cleanup.set_defaults(func=cmd_deliver)

    proj_p = sub.add_parser("project", help="Project operations")
    proj_sub = proj_p.add_subparsers(dest="subcommand")

    proj_new = proj_sub.add_parser("new", help="Create project skeleton")
    proj_new.add_argument("--project-id", required=True, help="kebab-case project id")
    proj_new.add_argument("--project-name", default=None, help="Display name")
    proj_new.add_argument("--repo", default="")
    source = proj_new.add_mutually_exclusive_group(required=False)
    source.add_argument("--from-outline", type=Path, default=None, help="Markdown outline file")
    source.add_argument("--from-graphify", type=Path, default=None, help="graphify-out/graph.json file")
    proj_new.add_argument("--dry-run", action="store_true")
    proj_new.add_argument("--force", action="store_true")
    proj_new.set_defaults(func=cmd_project_new)

    proj_val = proj_sub.add_parser("validate", help="Validate project.yaml files")
    proj_val.add_argument("--project", default=None, help="Project ID (omit for all)")
    proj_val.set_defaults(func=cmd_project_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
