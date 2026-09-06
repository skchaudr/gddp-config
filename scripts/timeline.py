"""gddp timeline — what actually happened to a project, in order, in words.

Read-only. Merges every evidence source the operator otherwise has to hunt
for by hand, then says plainly where they disagree:

  graph file          graphs/<project>/nodes/<node>.yaml status + git authorship
  status ledger       <runtime>/node_status_history/<project>/<node>.jsonl
  runtime jobs        <runtime>/db/queue.db jobs (this host only)
  heartbeat events    <runtime>/db/queue.db events (dispatch requests)
  executor attempts   spool dirs (packet/events/result) — passed in by caller
  evaluator receipts  verification/<project>/evaluations.yaml
  target repo         commits on the project's repo main branch; agent
                      co-authored commits with no GDDP attempt ref are
                      flagged as work that happened outside GDDP
  heartbeat health    systemd (Linux) / launchd (macOS) last tick on this host

Nothing here writes. Nothing here changes graph or runtime state.
"""

from __future__ import annotations

import json
import os
import platform
import re
import socket
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - gddp.py already enforces deps
    yaml = None

AGENT_MARKERS = (
    "cursor", "grok", "claude", "codex", "jules", "copilot", "gpt", "gemini",
    "composer", "openai", "anthropic", "google-labs", "devin", "droid", "aider",
)
GOVERNED_COMMIT_RE = re.compile(r"result\(job=job_|accept\([^)]+\): human-approved result|^gddp-", re.MULTILINE)
UNGOVERNED_LIST_CAP = 5
ACTIVE_JOB_STATES = {"queued", "dispatched", "running", "awaiting_result", "awaiting_review"}
DEFAULT_REPO_WINDOW = timedelta(days=14)
SYSTEMD_UNIT = "gddp-heartbeat.service"
LAUNCHD_LABEL = "com.gddp.heartbeat"


@dataclass(order=True)
class Entry:
    ts: datetime
    who: str = field(compare=False)
    text: str = field(compare=False)
    node: str | None = field(default=None, compare=False)

    def as_dict(self) -> dict:
        return {"ts": self.ts.isoformat(), "who": self.who, "node": self.node, "text": self.text}


@dataclass
class Timeline:
    project_id: str
    node_id: str | None
    host: str
    entries: list[Entry]
    warnings: list[str]
    notes: list[str]

    def as_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "node_id": self.node_id,
            "host": self.host,
            "entries": [e.as_dict() for e in self.entries],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------- time

def parse_ts(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    text = str(raw).strip()
    if text == "":
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


def _short(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%MZ")


def _short_id(value: str | None) -> str:
    if value is None:
        return "?"
    value = str(value)
    return value if len(value) <= 12 else "…" + value[-8:]


def _run(cmd: list[str], cwd: Path | None = None, timeout: float = 10.0) -> str:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


# --------------------------------------------------------------------------- graph

def read_graph(config_root: Path, project_id: str) -> dict:
    """Return {"repo": str, "nodes": {node_id: {"status", "title", "path"}}}."""
    project_dir = Path(config_root) / "graphs" / project_id
    project_yaml = project_dir / "project.yaml"
    if yaml is None or project_yaml.is_file() is False:
        raise FileNotFoundError(f"no project.yaml under {project_dir}")
    with open(project_yaml, encoding="utf-8") as handle:
        project = yaml.safe_load(handle) or {}
    nodes: dict[str, dict] = {}
    nodes_dir = project_dir / "nodes"
    if nodes_dir.is_dir():
        for path in sorted(nodes_dir.glob("*.yaml")):
            with open(path, encoding="utf-8") as handle:
                doc = yaml.safe_load(handle) or {}
            node_id = str(doc.get("id") or path.stem)
            nodes[node_id] = {
                "status": str(doc.get("status") or "?"),
                "title": str(doc.get("title") or ""),
                "path": path,
            }
    return {"repo": str(project.get("repo") or ""), "nodes": nodes, "project_yaml": project_yaml}


def project_authored_at(config_root: Path, graph: dict) -> datetime | None:
    """When project.yaml first entered git; the natural start of the story."""
    rel = os.path.relpath(graph["project_yaml"], config_root)
    log = _run(
        ["git", "log", "--diff-filter=A", "--format=%aI", "--", rel], cwd=Path(config_root)
    ).strip().splitlines()
    return parse_ts(log[-1]) if log else None


def graph_entries(config_root: Path, graph: dict, node_filter: str | None) -> tuple[list[Entry], list[str]]:
    entries: list[Entry] = []
    warnings: list[str] = []
    for node_id, info in graph["nodes"].items():
        if node_filter and node_id != node_filter:
            continue
        rel = os.path.relpath(info["path"], config_root)
        log = _run(
            ["git", "log", "--diff-filter=A", "--format=%aI%x1f%an%x1f%s", "--", rel],
            cwd=Path(config_root),
        ).strip().splitlines()
        if log:
            ts_raw, author, subject = (log[-1].split("\x1f") + ["", ""])[:3]
            ts = parse_ts(ts_raw)
            if ts:
                entries.append(Entry(ts, "graph", f"node {node_id} authored by {author} — \"{subject}\"", node_id))
        dirty = _run(["git", "status", "--porcelain", "--", rel], cwd=Path(config_root)).strip()
        if dirty:
            warnings.append(
                f"{node_id}: the node file has edits that are uncommitted; "
                f"other hosts see a different graph status than this one."
            )
    return entries, warnings


# --------------------------------------------------------------------------- ledger

def read_ledger(runtime_root: Path, project_id: str, node_id: str) -> list[dict]:
    path = Path(runtime_root) / "node_status_history" / project_id / f"{node_id}.jsonl"
    records: list[dict] = []
    if path.is_file() is False:
        return records
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line == "":
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def ledger_entries(runtime_root: Path, graph: dict, node_filter: str | None) -> tuple[list[Entry], list[str]]:
    entries: list[Entry] = []
    warnings: list[str] = []
    for node_id, info in graph["nodes"].items():
        if node_filter and node_id != node_filter:
            continue
        records = read_ledger(runtime_root, graph["project_id"], node_id)
        last_to = None
        for rec in records:
            ts = parse_ts(rec.get("ts"))
            if ts is None:
                continue
            who = "you" if "operator" in str(rec.get("source", "")) else str(rec.get("source") or "ledger")
            reason = rec.get("reason") or "(no reason)"
            entries.append(Entry(
                ts, who,
                f"set {node_id} {rec.get('from_status')} → {rec.get('to_status')} — \"{reason}\"",
                node_id,
            ))
            last_to = rec.get("to_status")
        if last_to is not None and last_to != info["status"]:
            warnings.append(
                f"{node_id}: graph file says '{info['status']}' but the last recorded change "
                f"ended at '{last_to}'. The file was edited by hand with no reason recorded."
            )
    return entries, warnings


# --------------------------------------------------------------------------- runtime db

def open_runtime_db(runtime_root: Path):
    path = Path(runtime_root) / "db" / "queue.db"
    if path.is_file() is False:
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("SELECT 1 FROM jobs LIMIT 1")
    except sqlite3.Error:
        return None
    return con


def _columns(con, table: str) -> set[str]:
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def runtime_entries(con, project_id: str, node_filter: str | None) -> tuple[list[Entry], list[str], int]:
    """Jobs + heartbeat dispatch events from this host's queue.db."""
    entries: list[Entry] = []
    warnings: list[str] = []
    if con is None:
        return entries, warnings, 0
    jobs_by_node: dict[str, list] = {}
    try:
        rows = con.execute(
            "SELECT job_id, node_id, executor, status, queue_state, attempt, created_at "
            "FROM jobs WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
    except sqlite3.Error:
        rows = []
    for row in rows:
        node_id = str(row["node_id"] or "?")
        if node_filter and node_id != node_filter:
            continue
        jobs_by_node.setdefault(node_id, []).append(row)
        ts = parse_ts(row["created_at"])
        if ts is None:
            continue
        state = row["status"]
        if row["queue_state"] and row["queue_state"] != row["status"]:
            state = f"{row['status']} (queue says {row['queue_state']})"
            warnings.append(
                f"{node_id}: job {_short_id(row['job_id'])} has two different states "
                f"recorded: status '{row['status']}', queue '{row['queue_state']}'."
            )
        entries.append(Entry(
            ts, "runtime",
            f"job {_short_id(row['job_id'])} created for {node_id} on {row['executor'] or '?'}"
            f" (attempt {row['attempt']}); now {state}",
            node_id,
        ))

    event_cols = _columns(con, "events")
    if "project_id" in event_cols:
        try:
            ev_rows = con.execute(
                "SELECT event_id, received_at, source, status, claimed_at, "
                "project_node_candidates, routing FROM events WHERE project_id = ? "
                "ORDER BY received_at",
                (project_id,),
            ).fetchall()
        except sqlite3.Error:
            ev_rows = []
        for row in ev_rows:
            try:
                candidates = json.loads(row["project_node_candidates"] or "[]")
            except json.JSONDecodeError:
                candidates = []
            node_id = str(candidates[0]) if candidates else "?"
            if node_filter and node_id != node_filter:
                continue
            ts = parse_ts(row["received_at"])
            if ts is None:
                continue
            executor = ""
            try:
                routing = json.loads(row["routing"] or "{}")
                executor = str(routing.get("selected_executor") or "")
            except json.JSONDecodeError:
                pass
            status = str(row["status"] or "?")
            claimed = parse_ts(row["claimed_at"])
            state_text = f"request {status}"
            if claimed:
                state_text += f" at {_short(claimed)}"
            entries.append(Entry(
                ts, "heartbeat",
                f"asked to dispatch {node_id}" + (f" on {executor}" if executor else "")
                + f" ({row['source']}); {state_text}",
                node_id,
            ))
            has_job_after = any(
                (parse_ts(j["created_at"]) or ts) >= ts for j in jobs_by_node.get(node_id, [])
            )
            if status in {"claimed", "pending", "received"} and has_job_after is False:
                warnings.append(
                    f"{node_id}: the heartbeat requested a dispatch at {_short(ts)} "
                    f"and the request is '{status}', but no job exists for it on this host. "
                    f"The tick most likely died after claiming it — see heartbeat health."
                )
    return entries, warnings, len(rows)


# --------------------------------------------------------------------------- attempts

def attempt_entries(
    attempts: list[dict], project_id: str, graph_node_ids: set[str], node_filter: str | None
) -> list[Entry]:
    """attempts: dicts from gddp._discover_attempts (created, node_id, project_id, state, dir, name).

    A packet with no project_id belongs here only when its node is in this graph.
    """
    entries: list[Entry] = []
    for info in attempts:
        proj = str(info.get("project_id") or "")
        node_id = info.get("node_id") or None
        if proj and proj != project_id:
            continue
        if proj == "" and node_id not in graph_node_ids:
            continue
        if node_filter and node_id != node_filter:
            continue
        ts = parse_ts(info.get("created"))
        if ts is None:
            continue
        entries.append(Entry(
            ts, "executor",
            f"attempt {info.get('name') or _short_id(str(info.get('dir')))} for {node_id or '?'}: {info.get('state')}",
            node_id,
        ))
    return entries


# --------------------------------------------------------------------------- receipts

def receipt_entries(config_root: Path, project_id: str, node_filter: str | None) -> list[Entry]:
    path = Path(config_root) / "verification" / project_id / "evaluations.yaml"
    entries: list[Entry] = []
    if yaml is None or path.is_file() is False:
        return entries
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    for node_id, rec in (doc.get("evaluations") or {}).items():
        if node_filter and node_id != node_filter:
            continue
        if isinstance(rec, dict) is False:
            continue
        ts = parse_ts(rec.get("evaluated_at"))
        if ts is None:
            continue
        entries.append(Entry(
            ts, "evaluator",
            f"verdict on {node_id}: {rec.get('verdict')} (job {_short_id(rec.get('job_id'))}, "
            f"{rec.get('executor') or '?'}) — evidence for review, never acceptance",
            str(node_id),
        ))
    return entries


# --------------------------------------------------------------------------- repo

def _looks_agent_authored(message: str, author: str) -> bool:
    haystack = (message + "\n" + author).lower()
    return any(marker in haystack for marker in AGENT_MARKERS)


def repo_entries(repo_path: Path | None, repo_label: str, since: datetime) -> tuple[list[Entry], list[str], list[str]]:
    """Agent-co-authored commits on main that live on no GDDP attempt/result ref."""
    entries: list[Entry] = []
    warnings: list[str] = []
    notes: list[str] = []
    if repo_path is None or Path(repo_path).is_dir() is False:
        notes.append(f"repo {repo_label or '?'}: no local checkout found on this host; repo activity is invisible from here.")
        return entries, warnings, notes
    repo_path = Path(repo_path)
    branch = "main"
    if _run(["git", "rev-parse", "--verify", "--quiet", "origin/main"], cwd=repo_path).strip():
        branch = "origin/main"
    log = _run(
        ["git", "log", branch, f"--since={since.isoformat()}", "--format=%H%x1f%aI%x1f%an%x1f%s%x1f%b%x1e"],
        cwd=repo_path,
    )
    ungoverned: list[str] = []
    other = 0
    for chunk in log.split("\x1e"):
        chunk = chunk.strip("\n")
        if chunk == "":
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 4:
            continue
        sha, ts_raw, author, subject = parts[:4]
        body = parts[4] if len(parts) > 4 else ""
        ts = parse_ts(ts_raw)
        if ts is None:
            continue
        message = subject + "\n" + body
        governed = GOVERNED_COMMIT_RE.search(message + "\n" + author) is not None
        if governed:
            entries.append(Entry(ts, "repo", f"{repo_label}: \"{subject}\" — via GDDP", None))
            continue
        if _looks_agent_authored(message, author) is False:
            other += 1
            continue
        coauthors = re.findall(r"Co-authored-by:\s*([^<\n]+)", body)
        by = ", ".join(c.strip() for c in coauthors) if coauthors else author
        entries.append(Entry(ts, "repo", f"{repo_label}: \"{subject}\" by {by} — OUTSIDE GDDP", None))
        ungoverned.append(f"\"{subject}\" ({_short(ts)})")
    if ungoverned:
        shown = ungoverned[:UNGOVERNED_LIST_CAP]
        more = len(ungoverned) - len(shown)
        tail = f"; and {more} more (see the timeline above)" if more > 0 else ""
        warnings.append(
            f"{len(ungoverned)} agent-authored commit(s) landed on {repo_label} {branch} since "
            f"{_short(since)} without passing through GDDP: " + "; ".join(shown) + tail
            + ". The graph has no record of this work."
        )
    if other:
        notes.append(f"repo {repo_label}: {other} other commit(s) on {branch} since {_short(since)} (human-authored, shown only in git log).")
    return entries, warnings, notes


# --------------------------------------------------------------------------- heartbeat health

def heartbeat_health() -> tuple[list[str], list[str]]:
    """Return (warnings, notes) about the heartbeat on this host. Read-only."""
    system = platform.system()
    if system == "Linux":
        show = _run(["systemctl", "--user", "show", SYSTEMD_UNIT, "-p", "Result", "-p", "ExecMainExitTimestamp", "-p", "ExecMainStatus"])
        if show.strip() == "":
            return [], ["heartbeat: no systemd user unit named " + SYSTEMD_UNIT + " on this host."]
        fields = dict(line.split("=", 1) for line in show.strip().splitlines() if "=" in line)
        when = fields.get("ExecMainExitTimestamp", "").strip() or "unknown time"
        if fields.get("Result", "").strip() == "success":
            return [], [f"heartbeat on this host: last tick succeeded ({when})."]
        journal = _run(["journalctl", "--user", "-u", SYSTEMD_UNIT, "-n", "120", "--no-pager", "-o", "cat"])
        error_line = ""
        for line in reversed(journal.splitlines()):
            if re.search(r"Error|error:|Exception", line):
                error_line = line.strip()
                break
        return [f"heartbeat on this host: last tick FAILED ({when}). {error_line}".rstrip()], []
    if system == "Darwin":
        out = _run(["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"])
        if out.strip() == "":
            return [], [f"heartbeat: launchd agent {LAUNCHD_LABEL} is absent on this host (disarmed)."]
        exit_match = re.search(r"last exit code = (-?\d+)", out)
        runs_match = re.search(r"runs = (\d+)", out)
        last_exit = int(exit_match.group(1)) if exit_match else None
        runs = int(runs_match.group(1)) if runs_match else 0
        if last_exit == 0:
            return [], [f"heartbeat on this host: armed via launchd, {runs} run(s), last exit 0."]
        return [f"heartbeat on this host: armed via launchd, {runs} run(s), last exit code {last_exit}."], []
    return [], [f"heartbeat: health check has no reader for {system}."]


# --------------------------------------------------------------------------- assemble

def build(
    project_id: str,
    node_id: str | None,
    *,
    config_root: Path,
    runtime_root: Path | None,
    repo_path: Path | None,
    attempts: list[dict] | None = None,
    include_heartbeat: bool = True,
    host: str | None = None,
) -> Timeline:
    config_root = Path(config_root)
    graph = read_graph(config_root, project_id)
    graph["project_id"] = project_id
    if node_id and node_id not in graph["nodes"]:
        raise KeyError(f"node {node_id!r} is absent from graph {project_id}")
    host = host or socket.gethostname()
    entries: list[Entry] = []
    warnings: list[str] = []
    notes: list[str] = []

    g_entries, g_warn = graph_entries(config_root, graph, node_id)
    entries += g_entries
    warnings += g_warn

    if runtime_root is not None:
        l_entries, l_warn = ledger_entries(runtime_root, graph, node_id)
        entries += l_entries
        warnings += l_warn
        con = open_runtime_db(runtime_root)
        try:
            r_entries, r_warn, job_count = runtime_entries(con, project_id, node_id)
        finally:
            if con is not None:
                con.close()
        entries += r_entries
        warnings += r_warn
        if con is None:
            notes.append(f"runtime db absent or unreadable under {runtime_root}; jobs and events are invisible from here.")
        elif job_count == 0:
            active = [n for n, i in graph["nodes"].items() if i["status"] != "pending"]
            if active or l_entries:
                notes.append(
                    f"this host ({host}) has no runtime jobs for {project_id}. Work dispatched from another "
                    f"host lives in that host's db/queue.db and is invisible from here."
                )
    else:
        notes.append("GDDP_RUNTIME_ROOT unset; ledger, jobs, and events are invisible.")

    entries += attempt_entries(attempts or [], project_id, set(graph["nodes"]), node_id)
    entries += receipt_entries(config_root, project_id, node_id)

    since = project_authored_at(config_root, graph) or (datetime.now(timezone.utc) - DEFAULT_REPO_WINDOW)
    repo_label = graph["repo"].split("/")[-1] or graph["repo"]
    rp_entries, rp_warn, rp_notes = repo_entries(repo_path, repo_label, since)
    entries += rp_entries
    warnings += rp_warn
    notes += rp_notes

    if include_heartbeat:
        hb_warn, hb_notes = heartbeat_health()
        warnings += hb_warn
        notes += hb_notes

    entries.sort()
    return Timeline(project_id, node_id, host, entries, warnings, notes)


def render_text(tl: Timeline, graph_nodes: dict | None = None) -> str:
    lines: list[str] = []
    head = f"timeline: {tl.project_id}"
    if tl.node_id:
        head += f" · {tl.node_id}"
    lines.append(head + f"   (host {tl.host}, times UTC)")
    if graph_nodes:
        lines.append("graph says now:")
        for nid, info in graph_nodes.items():
            if tl.node_id and nid != tl.node_id:
                continue
            title = f"  {info['title']}" if info.get("title") else ""
            lines.append(f"  {nid:<32} {info['status']:<12}{title}")
    lines.append("")
    if tl.entries:
        for e in tl.entries:
            lines.append(f"  {_short(e.ts)}  {e.who:<10} {e.text}")
    else:
        lines.append("  (no recorded activity anywhere this host can see)")
    lines.append("")
    if tl.warnings:
        lines.append(f"what is wrong ({len(tl.warnings)}):")
        for w in tl.warnings:
            lines.append(f"  ! {w}")
    else:
        lines.append("what is wrong: nothing detected from this host")
    if tl.notes:
        lines.append("")
        lines.append("what this host cannot see:")
        for n in tl.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)
