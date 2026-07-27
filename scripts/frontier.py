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

ACTIVE_JOB_STATES = frozenset({"ready", "running", "awaiting_review", "dispatching"})
SATISFIED_DEP_STATUSES = frozenset({"complete", "deferred"})

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
    """node_id -> {status, depends_on, executor} for one graph."""
    config_root = Path(config_root)
    project_doc = yaml.safe_load(
        (config_root / "graphs" / project_id / "project.yaml").read_text()
    ) or {}
    nodes = {
        n["id"]: {"status": n.get("status"), "depends_on": [], "executor": None}
        for n in project_doc.get("nodes", [])
        if n.get("id")
    }
    nodes_dir = config_root / "graphs" / project_id / "nodes"
    for path in sorted(nodes_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        node_id = data.get("node_id") or path.stem
        entry = nodes.setdefault(node_id, {"status": None, "depends_on": [], "executor": None})
        if entry["status"] is None:
            entry["status"] = data.get("status")
        entry["depends_on"] = list(data.get("depends_on") or [])
        modes = data.get("allowed_execution_modes") or []
        entry["executor"] = modes[0] if modes else None
    return nodes


def _latest_job_per_node(con, project_id: str):
    rows = con.execute(
        "SELECT job_id, node_id, status, queue_state, created_at "
        "FROM jobs WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    latest = {}
    for row in rows:  # DESC → first row per node is its latest job
        latest.setdefault(row["node_id"], row)
    return latest


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
    """node_id -> {phase, job_id, result} for nodes whose latest job is open."""
    active = {}
    for node_id, job in _latest_job_per_node(con, project_id).items():
        state = job["status"] or job["queue_state"]
        if state == "awaiting_review":
            phase = "awaiting review"
        elif state == "failed":
            phase = "failed — awaiting correction"
        elif state in ACTIVE_JOB_STATES:
            phase = _SESSION_PHASES.get(
                _latest_session_state(con, job["job_id"]), "queued"
            )
        else:
            continue
        active[node_id] = {
            "phase": phase,
            "job_id": job["job_id"],
            "result": _latest_result_label(con, job["job_id"]),
        }
    return active


def dispatch_blockers(con, project_id: str) -> set[str]:
    """Nodes that must not be offered for dispatch: latest job is executing,
    being evaluated, or awaiting review. A failed latest job (awaiting
    correction) is NOT a blocker — redispatch after correction is the
    operator's recovery path."""
    return {
        node_id
        for node_id, job in _latest_job_per_node(con, project_id).items()
        if (job["status"] or job["queue_state"]) in ACTIVE_JOB_STATES
    }


def _unsatisfied_deps(graph: dict, info: dict) -> list:
    return [
        (
            dep,
            (graph.get(dep) or {}).get("status") or "missing",
        )
        for dep in info["depends_on"]
        if (graph.get(dep) or {}).get("status") not in SATISFIED_DEP_STATUSES
    ]


def derive(graph: dict, runtime: dict) -> dict:
    """Split the graph into ready / in-flight / blocked / unlocks."""
    ready, in_flight, blocked = [], [], []
    for node_id, info in sorted(graph.items()):
        if info["status"] in SATISFIED_DEP_STATUSES:
            continue  # accepted/deferred: evidence retained, no longer motion
        motion = runtime.get(node_id)
        if motion is not None:
            in_flight.append((node_id, motion))
            continue
        unsatisfied = _unsatisfied_deps(graph, info)
        if info["status"] == "ready" and not unsatisfied:
            ready.append((node_id, info["executor"]))
        elif info["status"] in {"ready", "pending"}:
            blocked.append((node_id, info["status"], unsatisfied))

    unlocks = []
    for node_id, motion in sorted(runtime.items()):
        if motion["phase"] != "awaiting review":
            continue
        if (graph.get(node_id) or {}).get("status") in SATISFIED_DEP_STATUSES:
            continue  # already accepted; retained evidence is not an unlock
        downstream = []
        for cand, info in sorted(graph.items()):
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
        "blocked": blocked,
        "unlocks": unlocks,
    }


def render_text(project_id: str, derived: dict, runtime_note: str | None = None) -> str:
    lines = [f"frontier: {project_id}"]
    if runtime_note:
        lines.append(f"  runtime: UNAVAILABLE — {runtime_note}")
    lines.append(
        f"  {len(derived['ready'])} ready · "
        f"{len(derived['in_flight'])} in flight · "
        f"{len(derived['blocked'])} blocked · "
        f"{len(derived['unlocks'])} acceptance unlocks"
    )

    lines.append("\nready now (dispatchable):")
    if derived["ready"]:
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

    lines.append("\nunlocks on acceptance:")
    if runtime_note:
        lines.append("  (unknown — runtime unavailable)")
    elif derived["unlocks"]:
        for node_id, downstream in derived["unlocks"]:
            lines.append(f"  accept {node_id} → {', '.join(downstream)}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)
