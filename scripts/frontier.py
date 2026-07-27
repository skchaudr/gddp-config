"""frontier.py — Derived operating frontier (read-only).

Answers, from the same surfaces the loop already uses: which nodes are ready
now, which are already moving (never offered for duplicate dispatch), which
incomplete dependencies block the rest, and what each human acceptance would
unlock. Status comes from project.yaml node summaries (the contract
GraphReader reads); dependencies and routing come from node YAMLs; motion
comes from jobs + executor_sessions + results.

Rules that keep the view honest:
- Graph complete/deferred is authoritative: accepted nodes keep their review
  evidence (jobs/results rows stay) but are no longer motion or unlocks.
- A graph-ready node with incomplete deps is dependency-blocked drift, never
  "ready now (dispatchable)".
- Runtime read failures surface as an explicit unavailable state, never as a
  silently empty runtime.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import yaml

ACTIVE_JOB_STATES = frozenset({
    "ready", "running", "awaiting_result", "awaiting_review", "dispatching",
})
# Terminal graph statuses: suppress the NODE ITSELF (motion/unlocks) — a
# deferred node is settled human business, never again in motion.
TERMINAL_NODE_STATUSES = frozenset({"complete", "deferred"})
# Dependency satisfaction: exactly "complete". Live truth —
# scope_checker.py rejects any dep whose status != complete, and
# dispatch_next.py eligibility requires deps in complete_ids. A deferred
# dependency still blocks; only the node it belongs to is settled.
SATISFIED_DEP_STATUSES = frozenset({"complete"})

_SESSION_PHASES = {
    "dispatched": "dispatching",
    "running": "executing",
    "needs_operator": "needs operator",
    "collected": "evaluating",
}


class FrontierUnavailable(Exception):
    """Runtime state could not be read; never silently treated as empty."""


def connect_readonly(db_path: Path):
    """Open the live WAL DB read-only. Raises FrontierUnavailable instead of
    falling back to a stale-immutable or empty view."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FrontierUnavailable(f"runtime DB not found at {db_path}")
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        con.execute("SELECT 1 FROM jobs LIMIT 1")
    except sqlite3.OperationalError as exc:
        raise FrontierUnavailable(f"runtime DB unavailable at {db_path}: {exc}") from exc
    return con


def project_ids(config_root: Path) -> list[str]:
    graphs = Path(config_root) / "graphs"
    if not graphs.is_dir():
        return []
    return sorted(
        d.name for d in graphs.iterdir()
        if d.is_dir() and (d / "project.yaml").is_file()
    )


def load_graph(config_root: Path, project_id: str) -> dict:
    """Preserve project-summary and node-YAML status for one graph."""
    config_root = Path(config_root)
    project_doc = yaml.safe_load(
        (config_root / "graphs" / project_id / "project.yaml").read_text()
    ) or {}
    nodes = {
        n["id"]: {
            "status": n.get("status"),
            "summary_status": n.get("status"),
            "yaml_status": None,
            "depends_on": [],
            "executor": None,
        }
        for n in project_doc.get("nodes", [])
        if n.get("id")
    }
    nodes_dir = config_root / "graphs" / project_id / "nodes"
    for path in sorted(nodes_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        node_id = data.get("node_id") or path.stem
        entry = nodes.setdefault(node_id, {
            "status": data.get("status"),
            "summary_status": None,
            "yaml_status": None,
            "depends_on": [],
            "executor": None,
        })
        yaml_status = data.get("status")
        entry["yaml_status"] = yaml_status
        entry["depends_on"] = list(data.get("depends_on") or [])
        modes = data.get("allowed_execution_modes") or []
        entry["executor"] = modes[0] if modes else None
    return nodes


def _status_drift_detail(info: dict) -> str | None:
    summary, node_yaml = info.get("summary_status"), info.get("yaml_status")
    if summary is None:
        return f"status drift: summary missing / yaml {node_yaml or 'missing'}"
    if node_yaml is None:
        return f"status drift: summary {summary} / yaml missing"
    if summary != node_yaml:
        return f"status drift: summary {summary} / yaml {node_yaml}"
    return None


def _status_surfaces_agree(info: dict) -> bool:
    return _status_drift_detail(info) is None


def _latest_session_state(con, job_id: str):
    row = con.execute(
        "SELECT state FROM executor_sessions WHERE job_id = ? "
        "ORDER BY updated_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    return row["state"] if row else None


def _latest_result_label(con, job_id: str):
    """Canonical verdict from acceptance_check when present, else raw outcome."""
    row = con.execute(
        "SELECT outcome, acceptance_check FROM results WHERE job_id = ? "
        "ORDER BY received_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    if row["acceptance_check"]:
        try:
            verdict = json.loads(row["acceptance_check"]).get("verdict")
        except ValueError:
            verdict = None
        if verdict:
            return ("verdict", verdict)
    return ("outcome", row["outcome"])


def load_runtime(con, project_id: str) -> dict:
    """node_id -> {phase, job_id, result, disagreement} for nodes with motion.

    Motion selection mirrors the dispatch safety rule: ANY job active in
    either state column takes precedence (most recent active job wins); only
    when nothing is active does the latest settled job's failure render as
    awaiting correction. status/queue_state disagreement is surfaced, never
    coalesced away.
    """
    rows = con.execute(
        "SELECT job_id, node_id, status, queue_state, created_at "
        "FROM jobs WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    by_node: dict[str, list] = {}
    for row in rows:  # DESC → per-node lists stay newest-first
        by_node.setdefault(row["node_id"], []).append(row)
    active = {}
    for node_id, jobs in by_node.items():
        current = next(
            (
                job for job in jobs
                if job["status"] in ACTIVE_JOB_STATES
                or job["queue_state"] in ACTIVE_JOB_STATES
            ),
            None,
        )
        if current is None:
            latest = jobs[0]
            if "failed" in {latest["status"], latest["queue_state"]}:
                active[node_id] = {
                    "phase": "failed — awaiting correction",
                    "job_id": latest["job_id"],
                    "result": _latest_result_label(con, latest["job_id"]),
                    "disagreement": None,
                }
            continue
        status, queue = current["status"], current["queue_state"]
        state = status if status in ACTIVE_JOB_STATES else queue
        if state == "awaiting_review":
            phase = "awaiting review"
        elif state == "awaiting_result":
            phase = "awaiting result"
        else:
            phase = _SESSION_PHASES.get(
                _latest_session_state(con, current["job_id"]), "queued"
            )
        active[node_id] = {
            "phase": phase,
            "job_id": current["job_id"],
            "result": _latest_result_label(con, current["job_id"]),
            "disagreement": (f"{status}/{queue}" if status != queue else None),
        }
    return active


def dispatch_blockers(con, project_id: str) -> set[str]:
    """Nodes that must not be offered for dispatch: ANY job (not just the
    latest) still executing, being evaluated, or awaiting review, in either
    state column — status=failed/queue_state=running drift still blocks.
    Failed-and-settled jobs are NOT blockers: redispatch after correction is
    the operator's recovery path."""
    states = sorted(ACTIVE_JOB_STATES)
    rows = con.execute(
        f"SELECT DISTINCT node_id FROM jobs WHERE project_id = ? "
        f"AND (status IN ({','.join('?' * len(states))}) "
        f"OR queue_state IN ({','.join('?' * len(states))}))",
        (project_id, *states, *states),
    ).fetchall()
    return {row["node_id"] for row in rows}


def _unsatisfied_deps(graph: dict, info: dict) -> list:
    return [
        (
            dep,
            (graph.get(dep) or {}).get("status") or "missing",
        )
        for dep in info["depends_on"]
        if (graph.get(dep) or {}).get("status") not in SATISFIED_DEP_STATUSES
    ]


def unsatisfied_deps(graph: dict, node_id: str) -> list:
    """Public dependency-readiness check for one node (dispatch gating)."""
    info = graph.get(node_id)
    if info is None:
        return []
    return _unsatisfied_deps(graph, info)


def derive(graph: dict, runtime: dict) -> dict:
    """Split the graph into ready / in-flight / correction / blocked / unlocks
    / drift. Failed-latest is correction (may be redispatched), never
    'not offered'; complete/deferred suppresses retained review evidence but
    never hides genuinely active motion — that is runtime/graph drift."""
    ready, in_flight, correction, blocked, drift = [], [], [], [], []
    for node_id, info in sorted(graph.items()):
        motion = runtime.get(node_id)
        status_drift = _status_drift_detail(info)
        if status_drift:
            drift.append((node_id, status_drift))
        if info["status"] in TERMINAL_NODE_STATUSES:
            if motion is not None and motion["phase"] not in {
                "awaiting review",
                "failed — awaiting correction",
            }:
                drift.append((node_id, f"graph {info['status']} but runtime {motion['phase']}"))
            continue  # accepted/deferred: evidence retained, no longer motion
        if motion is not None:
            if motion["phase"] == "failed — awaiting correction":
                correction.append((node_id, motion))
            else:
                in_flight.append((node_id, motion))
            continue
        unsatisfied = _unsatisfied_deps(graph, info)
        if status_drift:
            continue  # both status surfaces must exist and agree
        if info["status"] == "ready" and not unsatisfied:
            ready.append((node_id, info["executor"]))
        elif info["status"] in {"ready", "pending"}:
            blocked.append((node_id, info["status"], unsatisfied))

    unlocks = []
    for node_id, motion in sorted(runtime.items()):
        if motion["phase"] != "awaiting review":
            continue
        source = graph.get(node_id) or {}
        if not _status_surfaces_agree(source):
            continue
        if source.get("status") in TERMINAL_NODE_STATUSES:
            continue  # already accepted; retained evidence is not an unlock
        downstream = []
        for cand, info in sorted(graph.items()):
            if not _status_surfaces_agree(info):
                continue
            if info["status"] not in {"pending", "ready"} or cand in runtime:
                continue
            if node_id not in info["depends_on"]:
                continue
            others = [d for d in info["depends_on"] if d != node_id]
            if all(
                (graph.get(d) or {}).get("status") in SATISFIED_DEP_STATUSES
                for d in others
            ):
                downstream.append(cand)
        if downstream:
            unlocks.append((node_id, downstream))

    return {
        "ready": ready,
        "in_flight": in_flight,
        "correction": correction,
        "blocked": blocked,
        "unlocks": unlocks,
        "drift": drift,
    }


def render_text(project_id: str, derived: dict, runtime_note: str | None = None) -> str:
    lines = [f"frontier: {project_id}"]
    if runtime_note:
        lines.append(f"  runtime: UNAVAILABLE — {runtime_note}")
        lines.append(
            f"  ready unknown · in flight unknown · awaiting correction unknown · "
            f"{len(derived['blocked'])} blocked · unlocks unknown"
        )
    else:
        lines.append(
            f"  {len(derived['ready'])} ready · "
            f"{len(derived['in_flight'])} in flight · "
            f"{len(derived['correction'])} awaiting correction · "
            f"{len(derived['blocked'])} blocked · "
            f"{len(derived['unlocks'])} acceptance unlocks"
        )

    lines.append("\nready now (dispatchable):")
    if runtime_note:
        lines.append("  (unknown — runtime unavailable)")
    elif derived["ready"]:
        for node_id, executor in derived["ready"]:
            lines.append(f"  {node_id}" + (f"  [{executor}]" if executor else ""))
    else:
        lines.append("  (none)")

    lines.append("\nin flight (not offered for dispatch):")
    if runtime_note:
        lines.append("  (unknown — runtime unavailable)")
    elif derived["in_flight"]:
        for node_id, motion in derived["in_flight"]:
            result = ""
            if motion["result"]:
                result = f"  {motion['result'][0]}: {motion['result'][1]}"
            drift = (
                f" (status/queue: {motion['disagreement']})"
                if motion.get("disagreement") else ""
            )
            lines.append(f"  {node_id}  — {motion['phase']}{drift}{result}")
    else:
        lines.append("  (none)")

    lines.append("\nawaiting correction (may be redispatched):")
    if runtime_note:
        lines.append("  (unknown — runtime unavailable)")
    elif derived["correction"]:
        for node_id, motion in derived["correction"]:
            result = ""
            if motion["result"]:
                result = f"  {motion['result'][0]}: {motion['result'][1]}"
            lines.append(f"  {node_id}  — {motion['phase']}{result}")
    else:
        lines.append("  (none)")

    lines.append("\nblocked (incomplete dependencies):")
    if derived["blocked"]:
        for node_id, status, unsatisfied in derived["blocked"]:
            drift = "  (graph status ready — dependency drift)" if status == "ready" else ""
            if unsatisfied:
                detail = ", ".join(f"{dep} [{s}]" for dep, s in unsatisfied)
                lines.append(f"  {node_id}  ← {detail}{drift}")
            else:
                lines.append(f"  {node_id}  ← deps satisfied; graph status still pending")
    else:
        lines.append("  (none)")

    lines.append("\nruntime/graph drift:")
    if derived["drift"]:
        for node_id, detail in derived["drift"]:
            lines.append(f"  {node_id}  — {detail}")
    else:
        lines.append("  (none)")

    lines.append("\nunlocks on acceptance:")
    if runtime_note:
        lines.append("  (unknown — runtime unavailable)")
    elif derived["unlocks"]:
        for node_id, downstream in derived["unlocks"]:
            lines.append(f"  accept {node_id} → {', '.join(downstream)}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)
