"""test_frontier.py — Derived operating frontier (read-only view).

Regression coverage for the graph-frontier-operations criteria: ready + exact
blocking deps, no duplicate dispatch offers, downstream impact of acceptance,
recompute after acceptance with retained review evidence, drift demotion of
ready-but-dep-blocked nodes, explicit runtime-unavailable state, and honest
verdict/outcome labeling.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frontier  # noqa: E402


def _write_project(root: Path, statuses: dict):
    nodes_dir = root / "graphs" / "g" / "nodes"
    nodes_dir.mkdir(parents=True)
    summary = "\n".join(f"  - id: {n}\n    status: {s}" for n, s in statuses.items())
    (root / "graphs" / "g" / "project.yaml").write_text(
        f"project_id: g\nrepo: org/g\nnodes:\n{summary}\n"
    )
    return nodes_dir


def _write_node(nodes_dir: Path, node_id: str, status: str, deps=(), modes=()):
    deps_yaml = "\ndepends_on:\n" + "".join(f"  - {d}\n" for d in deps) if deps else "depends_on: []\n"
    (nodes_dir / f"{node_id}.yaml").write_text(
        f"node_id: {node_id}\nstatus: {status}\n{deps_yaml}"
        f"allowed_execution_modes: {json.dumps(list(modes))}\n"
    )


def _set_status(config_root: Path, nodes_dir: Path, node_id: str, old: str, new: str, deps=(), modes=()):
    """Mimic the real acceptance path: YAML + project summary flip; jobs stay."""
    _write_node(nodes_dir, node_id, new, deps=deps, modes=modes)
    proj = config_root / "graphs" / "g" / "project.yaml"
    proj.write_text(proj.read_text().replace(
        f"id: {node_id}\n    status: {old}", f"id: {node_id}\n    status: {new}"))


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / "config"
    nodes = _write_project(root, {
        "base": "complete",
        "retired": "deferred",
        "work": "ready",
        "child": "pending",
        "grandchild": "pending",
        "blocked": "pending",
        "guard": "ready",
    })
    _write_node(nodes, "base", "complete", modes=["local_subprocess"])
    _write_node(nodes, "retired", "deferred")
    _write_node(nodes, "work", "ready", modes=["jules_api"])
    _write_node(nodes, "child", "pending", deps=["base", "retired"])
    _write_node(nodes, "grandchild", "pending", deps=["work"])
    _write_node(nodes, "blocked", "pending", deps=["base", "ghost", "work"])
    _write_node(nodes, "guard", "ready", deps=["work"], modes=["jules"])
    return root


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE jobs (job_id TEXT, node_id TEXT, project_id TEXT, "
        "status TEXT, queue_state TEXT, created_at TEXT)"
    )
    c.execute(
        "CREATE TABLE executor_sessions (session_db_id TEXT, job_id TEXT, "
        "state TEXT, updated_at TEXT)"
    )
    c.execute(
        "CREATE TABLE results (result_id TEXT, job_id TEXT, outcome TEXT, "
        "acceptance_check TEXT, received_at TEXT)"
    )
    return c


def _job(con, job_id, node_id, status, ts="2026-07-26T10:00"):
    con.execute(
        "INSERT INTO jobs VALUES (?, ?, 'g', ?, ?, ?)",
        (job_id, node_id, status, status, ts),
    )


def _graph(config_root):
    return frontier.load_graph(config_root, "g")


def _derive(config_root, con):
    return frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))


# --- ready + blocked visibility -------------------------------------------- #

def test_ready_and_blocked_with_exact_deps(config_root, con):
    derived = _derive(config_root, con)
    assert derived["ready"] == [("work", "jules_api")]
    blocked = {n: (s, u) for n, s, u in derived["blocked"]}
    assert blocked["blocked"] == ("pending", [("ghost", "missing"), ("work", "ready")])
    assert blocked["child"] == ("pending", [])  # complete + deferred satisfied
    assert blocked["grandchild"] == ("pending", [("work", "ready")])


def test_ready_dep_blocked_is_drift_never_dispatchable(config_root, con):
    # guard is graph-ready but depends on work (not complete): the harness→guard case.
    derived = _derive(config_root, con)
    assert [n for n, _ in derived["ready"]] == ["work"]
    blocked = {n: (s, u) for n, s, u in derived["blocked"]}
    assert blocked["guard"] == ("ready", [("work", "ready")])
    text = frontier.render_text("g", derived)
    assert "guard  ← work [ready]  (graph status ready — dependency drift)" in text
    ready_section = text.split("ready now (dispatchable):")[1].split("in flight")[0]
    assert "guard" not in ready_section


# --- no duplicate dispatch -------------------------------------------------- #

def test_in_flight_phases_and_result_labels(config_root, con):
    _job(con, "j1", "work", "running")
    con.execute("INSERT INTO executor_sessions VALUES ('s1', 'j1', 'collected', '2026-07-26T10:05')")
    _job(con, "j2", "child", "awaiting_review", ts="2026-07-26T11:00")
    con.execute(
        "INSERT INTO results VALUES ('r1', 'j2', 'ok', ?, '2026-07-26T11:09')",
        (json.dumps({"verdict": "pass"}),),
    )
    _job(con, "j3", "grandchild", "awaiting_review", ts="2026-07-26T11:30")
    con.execute("INSERT INTO results VALUES ('r2', 'j3', 'success', NULL, '2026-07-26T11:40')")
    derived = _derive(config_root, con)
    assert derived["ready"] == []  # everything moving → nothing offered twice
    phases = {n: m["phase"] for n, m in derived["in_flight"]}
    assert phases == {
        "work": "evaluating",
        "child": "awaiting review",
        "grandchild": "awaiting review",
    }
    results = {n: m["result"] for n, m in derived["in_flight"]}
    assert results["child"] == ("verdict", "pass")       # canonical verdict read
    assert results["grandchild"] == ("outcome", "success")  # raw outcome labeled


def test_failed_latest_job_is_correction_not_in_flight(config_root, con):
    _job(con, "j1", "work", "failed")
    derived = _derive(config_root, con)
    assert derived["ready"] == []
    assert derived["in_flight"] == []  # failed is not 'not offered'
    assert derived["correction"][0][0] == "work"
    assert derived["correction"][0][1]["phase"] == "failed — awaiting correction"
    text = frontier.render_text("g", derived)
    assert "awaiting correction (may be redispatched):" in text
    in_flight_section = text.split("in flight (not offered for dispatch):")[1].split("awaiting correction")[0]
    assert "work" not in in_flight_section


def test_view_older_active_job_wins_over_newer_failed(config_root, con):
    _job(con, "j_old", "work", "running", ts="2026-07-26T08:00")
    _job(con, "j_new", "work", "failed", ts="2026-07-26T09:00")
    derived = _derive(config_root, con)
    assert derived["correction"] == []  # active truth wins; not 'may be redispatched'
    assert derived["in_flight"][0][0] == "work"
    assert derived["in_flight"][0][1]["phase"] == "queued"  # running, no session row


def test_view_failed_running_drift_is_active_and_marked(config_root, con):
    con.execute(
        "INSERT INTO jobs VALUES ('j_d', 'child', 'g', 'failed', 'running', '2026-07-26T10:00')"
    )
    derived = _derive(config_root, con)
    assert derived["correction"] == []
    motion = dict(derived["in_flight"])["child"]
    assert motion["phase"] == "queued"
    assert motion["disagreement"] == "failed/running"
    text = frontier.render_text("g", derived)
    assert "child  — queued (status/queue: failed/running)" in text


def test_superseded_old_job_does_not_haunt(config_root, con):
    _job(con, "j_old", "work", "failed", ts="2026-07-26T08:00")
    _job(con, "j_new", "work", "awaiting_review", ts="2026-07-26T09:00")
    derived = _derive(config_root, con)
    assert [n for n, _ in derived["in_flight"]] == ["work"]
    assert derived["in_flight"][0][1]["phase"] == "awaiting review"


def test_dispatch_blockers_semantics(config_root, con):
    _job(con, "j1", "work", "running")
    _job(con, "j2", "child", "awaiting_review", ts="2026-07-26T10:00")
    _job(con, "j3", "grandchild", "failed", ts="2026-07-26T10:00")
    _job(con, "j4", "guard", "failed", ts="2026-07-26T10:00")
    assert frontier.dispatch_blockers(con, "g") == {"work", "child"}


def test_dispatch_blockers_catch_older_active_and_drift(config_root, con):
    # Older job still active beneath an inactive latest job.
    _job(con, "j_old", "work", "running", ts="2026-07-26T08:00")
    _job(con, "j_new", "work", "failed", ts="2026-07-26T09:00")
    # status=failed / queue_state=running drift row.
    con.execute(
        "INSERT INTO jobs VALUES ('j_drift', 'child', 'g', 'failed', 'running', '2026-07-26T10:00')"
    )
    assert frontier.dispatch_blockers(con, "g") == {"work", "child"}


def test_complete_node_with_active_session_is_drift_not_hidden(config_root, con):
    _job(con, "j1", "base", "running")  # base is complete in graph
    con.execute("INSERT INTO executor_sessions VALUES ('s1', 'j1', 'running', '2026-07-26T10:05')")
    derived = _derive(config_root, con)
    assert derived["in_flight"] == []  # not ordinary motion…
    assert derived["drift"] == [("base", "complete", "executing")]  # …it is drift
    text = frontier.render_text("g", derived)
    assert "base  — graph complete but runtime executing" in text


def test_complete_node_with_retained_review_evidence_is_not_drift(config_root, con):
    _job(con, "j1", "base", "awaiting_review")
    derived = _derive(config_root, con)
    assert derived["drift"] == []
    assert derived["in_flight"] == []


# --- downstream impact ------------------------------------------------------- #

def test_unlocks_cover_pending_and_ready_dep_blocked(config_root, con):
    _job(con, "j1", "work", "awaiting_review")
    derived = _derive(config_root, con)
    # guard (ready but dep-blocked on work) and grandchild (pending) unlock;
    # child is not downstream of work; "blocked" never unlocks (ghost stays).
    assert derived["unlocks"] == [("work", ["grandchild", "guard"])]


# --- acceptance advances the frontier ---------------------------------------- #

def test_recompute_after_acceptance_with_retained_review_evidence(config_root, con):
    _job(con, "j1", "work", "awaiting_review")
    before = _derive(config_root, con)
    assert [n for n, _ in before["in_flight"]] == ["work"]
    assert before["unlocks"]

    # Real acceptance path (cmd_set_status): graph flips; the job row STAYS.
    nodes_dir = config_root / "graphs" / "g" / "nodes"
    _set_status(config_root, nodes_dir, "work", "ready", "complete", modes=["jules_api"])

    after = _derive(config_root, con)
    assert after["in_flight"] == []  # retained evidence is not motion
    assert after["unlocks"] == []    # already accepted → nothing left to unlock
    blocked = {n: (s, u) for n, s, u in after["blocked"]}
    assert blocked["grandchild"] == ("pending", [])
    assert ("guard", "jules") in after["ready"]  # dep-blocked drift graduated
    text = frontier.render_text("g", after)
    assert "grandchild  ← deps satisfied; graph status still pending" in text


# --- runtime availability ---------------------------------------------------- #

def test_connect_readonly_unavailable_and_enforced_ro(tmp_path):
    with pytest.raises(frontier.FrontierUnavailable, match="not found"):
        frontier.connect_readonly(tmp_path / "missing.db")
    db = tmp_path / "queue.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE jobs (job_id TEXT)")
    c.commit()
    c.close()
    con = frontier.connect_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("CREATE TABLE nope (x TEXT)")  # read-only is enforced
    con.close()


def test_render_marks_runtime_unavailable_explicitly(config_root, con):
    derived = frontier.derive(_graph(config_root), {})
    text = frontier.render_text("g", derived, runtime_note="database is locked")
    assert "runtime: UNAVAILABLE — database is locked" in text
    assert "in flight (not offered for dispatch):\n  (unknown — runtime unavailable)" in text
    assert "awaiting correction (may be redispatched):\n  (unknown — runtime unavailable)" in text
    assert "unlocks on acceptance:\n  (unknown — runtime unavailable)" in text
