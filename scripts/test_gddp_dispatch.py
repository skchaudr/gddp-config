"""test_gddp_dispatch.py — Positional operator dispatch (gddp <graph|node> [executor]).

Covers exact-target resolution (graph-first), validation refusals, configured
routing defaults, event insert shape, and the single preview/confirm gate.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gddp  # noqa: E402


_EVENTS_SCHEMA = """
CREATE TABLE events (
    event_id                TEXT PRIMARY KEY,
    schema_version          TEXT NOT NULL DEFAULT '1.0',
    received_at             TEXT NOT NULL,
    source                  TEXT NOT NULL,
    event_type              TEXT NOT NULL,
    actor                   TEXT,
    branch                  TEXT,
    base_branch             TEXT,
    pr_number               INTEGER,
    issue_number            INTEGER,
    commit_sha              TEXT,
    url                     TEXT,
    project_id              TEXT,
    project_node_candidates TEXT,
    scope_status            TEXT DEFAULT 'pending',
    priority                TEXT DEFAULT 'pending',
    risk_level              TEXT DEFAULT 'pending',
    raw_payload_path        TEXT,
    normalized_payload_path TEXT,
    classification          TEXT,
    routing                 TEXT,
    status                  TEXT DEFAULT 'received',
    claimed_at              TEXT,
    repo TEXT
);
"""

_JOBS_SCHEMA = """
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    node_id TEXT,
    project_id TEXT,
    status TEXT,
    queue_state TEXT,
    created_at TEXT
);
"""


def _write_node(nodes_dir: Path, node_id: str, status: str, modes: list[str], deps: list[str] | None = None):
    deps_yaml = "depends_on: []\n" if not deps else "depends_on:\n" + "".join(f"  - {d}\n" for d in deps)
    (nodes_dir / f"{node_id}.yaml").write_text(
        f"schema_version: '1.0'\n"
        f"schema_type: node\n"
        f"node_id: {node_id}\n"
        f"title: t\n"
        f"status: {status}\n"
        f"{deps_yaml}"
        f"allowed_execution_modes: {json.dumps(modes)}\n"
    )


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / "config"
    for project, repo in (("proj-a", "org/a"), ("proj-b", "org/b")):
        nodes = root / "graphs" / project / "nodes"
        nodes.mkdir(parents=True)
        (root / "graphs" / project / "project.yaml").write_text(
            f"project_id: {project}\nrepo: {repo}\n"
            "execution_policy:\n  default_executor: jules_api\n"
        )
    a = root / "graphs" / "proj-a" / "nodes"
    _write_node(a, "alpha", "ready", ["local_subprocess"])
    _write_node(a, "beta", "ready", ["jules_api", "local_subprocess"])
    _write_node(a, "gamma", "pending", ["local_subprocess"])
    b = root / "graphs" / "proj-b" / "nodes"
    _write_node(b, "shared", "ready", ["local_subprocess"])
    _write_node(a, "shared", "ready", ["local_subprocess"])
    # A node whose id collides with a graph name: graph must win.
    _write_node(b, "proj-a", "ready", ["local_subprocess"])
    return root


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(_EVENTS_SCHEMA)
    c.execute(_JOBS_SCHEMA)
    return c


# --- resolution + validation ---------------------------------------------- #

def test_graph_frontier_uses_configured_routing(config_root):
    plan = gddp.build_dispatch_plan(config_root, "proj-a", None)
    assert plan["project_id"] == "proj-a"
    assert plan["repo"] == "org/a"
    assert plan["executor_explicit"] is False
    assert {i["node_id"]: i["executor"] for i in plan["items"]} == {
        "alpha": "local_subprocess",
        "beta": "jules_api",
        "shared": "local_subprocess",
    }


def test_graph_named_executor_applies_to_all(config_root):
    plan = gddp.build_dispatch_plan(config_root, "proj-a", "local_subprocess")
    assert plan["executor_explicit"] is True
    assert {i["executor"] for i in plan["items"]} == {"local_subprocess"}


def test_graph_named_executor_conflict_refuses(config_root):
    with pytest.raises(gddp.DispatchError, match="alpha"):
        gddp.build_dispatch_plan(config_root, "proj-a", "jules_api")


def test_graph_wins_over_same_named_node(config_root):
    plan = gddp.build_dispatch_plan(config_root, "proj-a", None)
    assert plan["project_id"] == "proj-a"
    assert len(plan["items"]) == 3  # the frontier, not proj-b's proj-a node


def test_node_default_and_named_executor(config_root):
    plan = gddp.build_dispatch_plan(config_root, "beta", "local_subprocess")
    assert plan["items"] == [{"node_id": "beta", "executor": "local_subprocess"}]
    with pytest.raises(gddp.DispatchError, match="allowed_execution_modes"):
        gddp.build_dispatch_plan(config_root, "alpha", "jules_api")


def test_ambiguous_node_refuses(config_root):
    with pytest.raises(gddp.DispatchError, match="multiple graphs"):
        gddp.build_dispatch_plan(config_root, "shared", None)


def test_project_hint_qualifies_ambiguous_node(config_root):
    plan = gddp.build_dispatch_plan(config_root, "shared", None, project_hint="proj-b")
    assert plan["project_id"] == "proj-b"
    assert plan["items"] == [{"node_id": "shared", "executor": "local_subprocess"}]
    with pytest.raises(gddp.DispatchError, match="no graph or node"):
        gddp.build_dispatch_plan(config_root, "alpha", None, project_hint="proj-b")


def test_unknown_target_and_not_ready_refuse(config_root):
    with pytest.raises(gddp.DispatchError, match="no graph or node"):
        gddp.build_dispatch_plan(config_root, "nope", None)
    with pytest.raises(gddp.DispatchError, match="'pending', not ready"):
        gddp.build_dispatch_plan(config_root, "gamma", None)


# --- insert shape ---------------------------------------------------------- #

def test_insert_event_shape(con):
    items = [{"node_id": "alpha", "executor": "local_subprocess"}]
    ids = gddp.insert_dispatch_events(
        con, "proj-a", "org/a", items, executor_explicit=True, actor="sab"
    )
    row = con.execute("SELECT * FROM events WHERE event_id = ?", ids).fetchone()
    assert row["status"] == "received"
    assert row["source"] == "manual_inject"
    assert row["event_type"] == "issue.opened"
    assert row["actor"] == "sab"
    assert row["project_id"] == "proj-a"
    assert row["repo"] == "org/a"
    assert "node: alpha" in row["url"]  # classifier tag source
    assert json.loads(row["project_node_candidates"]) == ["alpha"]
    assert json.loads(row["routing"]) == {"selected_executor": "local_subprocess"}


def test_insert_without_named_executor_leaves_routing_null(con):
    items = [{"node_id": "beta", "executor": "jules_api"}]
    ids = gddp.insert_dispatch_events(
        con, "proj-a", "org/a", items, executor_explicit=False
    )
    row = con.execute("SELECT routing FROM events WHERE event_id = ?", ids).fetchone()
    assert row["routing"] is None


# --- preview / confirm gate ------------------------------------------------- #

def test_abort_inserts_nothing(con, config_root, monkeypatch):
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "n")
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 1
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0


def test_confirm_inserts_frontier(con, config_root, monkeypatch):
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 0
    rows = con.execute("SELECT * FROM events ORDER BY event_id").fetchall()
    assert len(rows) == 3
    assert {r["status"] for r in rows} == {"received"}


def test_in_flight_node_refused_zero_events(con, config_root, monkeypatch):
    con.execute(
        "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, '2026-07-26T10:00')",
        ("job_1", "alpha", "proj-a", "running", "running"),
    )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "alpha", None)
    assert rc == 2
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0


def test_graph_dispatch_excludes_in_flight_inserts_rest(con, config_root, monkeypatch):
    con.execute(
        "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, '2026-07-26T10:00')",
        ("job_1", "alpha", "proj-a", "awaiting_review", "awaiting_review"),
    )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 0
    urls = [r["url"] for r in con.execute("SELECT url FROM events").fetchall()]
    assert len(urls) == 2
    assert all("node: alpha" not in u for u in urls)


def test_all_in_flight_refuses_whole_dispatch(con, config_root, monkeypatch):
    for index, node in enumerate(("alpha", "beta", "shared")):
        con.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)",
            (f"job_{index}", node, "proj-a", "running", "running",
             f"2026-07-26T10:0{index}"),
        )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 2
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0


def test_dep_blocked_exact_node_refused_zero_events(con, config_root, monkeypatch):
    # guard depends on work (ready, not complete) — the harness→guard case.
    _write_node(
        config_root / "graphs" / "proj-a" / "nodes",
        "depkid", "ready", ["local_subprocess"], deps=["alpha"],
    )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "depkid", None)
    assert rc == 2
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0


def test_graph_dispatch_excludes_dep_blocked_inserts_rest(con, config_root, monkeypatch):
    _write_node(
        config_root / "graphs" / "proj-a" / "nodes",
        "depkid", "ready", ["local_subprocess"], deps=["alpha"],
    )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 0
    urls = [r["url"] for r in con.execute("SELECT url FROM events").fetchall()]
    assert len(urls) == 3
    assert all("node: depkid" not in u for u in urls)


def test_failed_latest_job_stays_dispatchable(con, config_root, monkeypatch):
    con.execute(
        "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, '2026-07-26T10:00')",
        ("job_1", "alpha", "proj-a", "failed", "failed"),
    )
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp._dispatch_flow(con, config_root, "alpha", None)
    assert rc == 0
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 1


# --- argv shim -------------------------------------------------------------- #

def test_main_positional_routes_to_dispatch(config_root, tmp_path, monkeypatch):
    db = tmp_path / "db" / "queue.db"
    db.parent.mkdir()
    c = sqlite3.connect(db)
    c.execute(_EVENTS_SCHEMA)
    c.execute(_JOBS_SCHEMA)
    c.commit()
    c.close()
    monkeypatch.setattr(gddp, "ROOT", config_root)
    monkeypatch.setattr(gddp, "resolve_runtime_root", lambda: tmp_path)
    monkeypatch.setattr(gddp.Prompt, "ask", lambda *a, **k: "y")
    rc = gddp.main(["beta"])
    assert rc == 0
    check = sqlite3.connect(db)
    check.row_factory = sqlite3.Row
    rows = check.execute("SELECT * FROM events").fetchall()
    assert len(rows) == 1
    assert "node: beta" in rows[0]["url"]
    check.close()


def test_eof_at_confirm_aborts_cleanly(con, config_root, monkeypatch):
    def _eof(*a, **k):
        raise EOFError
    monkeypatch.setattr(gddp.Prompt, "ask", _eof)
    rc = gddp._dispatch_flow(con, config_root, "proj-a", None)
    assert rc == 1
    assert con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0


def test_main_known_commands_still_parse(monkeypatch):
    monkeypatch.setattr(
        gddp, "cmd_overview", lambda _args: 0
    )
    assert gddp.main([]) == 0
