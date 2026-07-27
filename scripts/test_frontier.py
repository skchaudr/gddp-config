"""test_frontier.py — Derived operating frontier (read-only view).

Covers the four graph-frontier-operations criteria: ready + exact blocking
dependencies, no duplicate dispatch offers, downstream impact of acceptance,
and recomputation after a human acceptance. Deferred deps count as satisfied.
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
    })
    _write_node(nodes, "base", "complete", modes=["local_subprocess"])
    _write_node(nodes, "retired", "deferred")
    _write_node(nodes, "work", "ready", modes=["jules_api"])
    _write_node(nodes, "child", "pending", deps=["base", "retired"])
    _write_node(nodes, "grandchild", "pending", deps=["work"])
    _write_node(nodes, "blocked", "pending", deps=["base", "ghost", "work"])
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
        "received_at TEXT)"
    )
    return c


def _job(con, job_id, node_id, status, ts="2026-07-26T10:00"):
    con.execute(
        "INSERT INTO jobs VALUES (?, ?, 'g', ?, ?, ?)",
        (job_id, node_id, status, status, ts),
    )


def _graph(config_root):
    return frontier.load_graph(config_root, "g")


# --- ready + blocked visibility -------------------------------------------- #

def test_ready_and_blocked_with_exact_deps(config_root, con):
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert derived["ready"] == [("work", "jules_api", [])]
    blocked = dict(derived["blocked"])
    assert blocked["blocked"] == [("ghost", "missing"), ("work", "ready")]
    assert blocked["child"] == []  # complete + deferred deps are satisfied
    assert blocked["grandchild"] == [("work", "ready")]


def test_ready_node_with_incomplete_dep_is_annotated(config_root, con):
    nodes_dir = config_root / "graphs" / "g" / "nodes"
    _write_node(nodes_dir, "child", "ready", deps=["work"])
    proj = config_root / "graphs" / "g" / "project.yaml"
    proj.write_text(proj.read_text().replace("id: child\n    status: pending",
                                             "id: child\n    status: ready"))
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    ready = {n: u for n, _, u in derived["ready"]}
    assert ready["child"] == ["work"]
    text = frontier.render_text("g", derived)
    assert "child  (dep not complete: work)" in text


def test_render_marks_deps_satisfied_but_pending(config_root, con):
    text = frontier.render_text("g", frontier.derive(
        _graph(config_root), frontier.load_runtime(con, "g")))
    assert "child  ← deps satisfied; graph status still pending" in text


# --- no duplicate dispatch -------------------------------------------------- #

def test_in_flight_phases_exclude_from_ready(config_root, con):
    _job(con, "j1", "work", "running")
    con.execute(
        "INSERT INTO executor_sessions VALUES ('s1', 'j1', 'collected', '2026-07-26T10:05')"
    )
    _job(con, "j2", "base", "awaiting_review", ts="2026-07-26T11:00")
    con.execute(
        "INSERT INTO results VALUES ('r1', 'j2', 'pass', '2026-07-26T11:09')"
    )
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert derived["ready"] == []  # work is moving → not offered again
    phases = {n: m["phase"] for n, m in derived["in_flight"]}
    assert phases == {"work": "evaluating", "base": "awaiting review"}
    verdicts = {n: m["verdict"] for n, m in derived["in_flight"]}
    assert verdicts["base"] == "pass"


def test_failed_latest_job_shows_awaiting_correction(config_root, con):
    _job(con, "j1", "work", "failed")
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert derived["ready"] == []
    assert derived["in_flight"] == [
        ("work", {"phase": "failed — awaiting correction", "job_id": "j1", "verdict": None})
    ]


def test_superseded_old_job_does_not_haunt(config_root, con):
    _job(con, "j_old", "work", "failed", ts="2026-07-26T08:00")
    _job(con, "j_new", "work", "awaiting_review", ts="2026-07-26T09:00")
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert [n for n, _ in derived["in_flight"]] == ["work"]
    assert derived["in_flight"][0][1]["phase"] == "awaiting review"


# --- downstream impact ------------------------------------------------------- #

def test_unlocks_only_when_other_deps_satisfied(config_root, con):
    _job(con, "j1", "work", "awaiting_review")
    derived = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert derived["unlocks"] == [("work", ["grandchild"])]
    # "blocked" also depends on ghost → must NOT appear as an unlock
    assert "blocked" not in [d for _, ds in derived["unlocks"] for d in ds]


# --- acceptance advances the frontier ---------------------------------------- #

def test_recompute_after_acceptance(config_root, con):
    _job(con, "j1", "work", "awaiting_review")
    before = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert [n for n, _ in before["ready"]] == []

    # Human accepts: job leaves the active set, graph truth flips to complete.
    con.execute("DELETE FROM jobs WHERE job_id = 'j1'")
    nodes_dir = config_root / "graphs" / "g" / "nodes"
    _write_node(nodes_dir, "work", "complete", modes=["jules_api"])
    proj = config_root / "graphs" / "g" / "project.yaml"
    proj.write_text(proj.read_text().replace("id: work\n    status: ready",
                                             "id: work\n    status: complete"))

    after = frontier.derive(_graph(config_root), frontier.load_runtime(con, "g"))
    assert after["in_flight"] == []
    assert after["unlocks"] == []
    blocked = dict(after["blocked"])
    assert blocked["grandchild"] == []  # now derivable; awaits human ready toggle
    text = frontier.render_text("g", after)
    assert "grandchild  ← deps satisfied; graph status still pending" in text
