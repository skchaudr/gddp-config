"""test_timeline.py — read-only project timeline assembly."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import timeline  # noqa: E402

GRAPH_DATE = "2026-09-05T09:44:00+00:00"
HUMAN_COMMIT_DATE = "2026-09-05T11:26:00+00:00"
AGENT_COMMIT_DATE = "2026-09-05T11:44:00+00:00"
GOVERNED_COMMIT_DATE = "2026-09-05T12:00:00+00:00"
PROJECT_ID = "demo-proj"
NODE_ID = "node-a"


def _git(cwd: Path, *args, env: dict | None = None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env=merged,
    )


def _git_commit(cwd: Path, message: str, date_iso: str, body: str = ""):
    full = message + (f"\n\n{body}" if body else "")
    env = {"GIT_AUTHOR_DATE": date_iso, "GIT_COMMITTER_DATE": date_iso}
    _git(cwd, "add", "-A")
    _git(
        cwd,
        "-c", "user.name=t",
        "-c", "user.email=t@t",
        "commit", "-q", "-m", full,
        env=env,
    )


def _write_graph(config_root: Path, project_id: str, node_id: str, node_status: str, node_title: str = "Test node"):
    project_dir = config_root / "graphs" / project_id
    nodes_dir = project_dir / "nodes"
    nodes_dir.mkdir(parents=True)
    (project_dir / "project.yaml").write_text(
        f"project_id: {project_id}\nrepo: org/demo-repo\n",
        encoding="utf-8",
    )
    (nodes_dir / f"{node_id}.yaml").write_text(
        f"id: {node_id}\ntitle: {node_title}\nstatus: {node_status}\n",
        encoding="utf-8",
    )


def _init_config_git(config_root: Path, date_iso: str = GRAPH_DATE):
    _git(config_root, "init", "-q")
    _git_commit(config_root, "add graph", date_iso)


def _write_ledger(runtime_root: Path, project_id: str, node_id: str, records: list[dict]):
    ledger_dir = runtime_root / "node_status_history" / project_id
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{node_id}.jsonl"
    lines = [json.dumps(rec) for rec in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _create_runtime_db(runtime_root: Path, jobs: list[tuple] = (), events: list[tuple] = ()):
    db_dir = runtime_root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "queue.db"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE jobs (job_id TEXT, project_id TEXT, node_id TEXT, executor TEXT, "
        "status TEXT, queue_state TEXT, attempt INTEGER, created_at TEXT)"
    )
    con.execute(
        "CREATE TABLE events (event_id TEXT, received_at TEXT, source TEXT, status TEXT, "
        "claimed_at TEXT, project_id TEXT, project_node_candidates TEXT, routing TEXT)"
    )
    for row in jobs:
        con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", row)
    for row in events:
        con.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)", row)
    con.commit()
    con.close()
    return db_path


def _init_target_repo(repo_path: Path):
    repo_path.mkdir(parents=True)
    _git(repo_path, "init", "-q")
    (repo_path / "README.md").write_text("demo\n", encoding="utf-8")
    _git_commit(repo_path, "human work", HUMAN_COMMIT_DATE)
    _git(repo_path, "branch", "-M", "main")
    (repo_path / "agent.txt").write_text("agent\n", encoding="utf-8")
    _git_commit(
        repo_path,
        "agent-side edit",
        AGENT_COMMIT_DATE,
        body="Co-authored-by: Grok 4.6 <grok@cursor.com>",
    )
    (repo_path / "governed.txt").write_text("governed\n", encoding="utf-8")
    _git_commit(
        repo_path,
        "result(job=job_20260905T1, attempt=job_20260905T1:attempt:0)",
        GOVERNED_COMMIT_DATE,
    )


def _build(
    config_root: Path,
    runtime_root: Path | None = None,
    repo_path: Path | None = None,
    node_id: str | None = None,
    project_id: str = PROJECT_ID,
):
    return timeline.build(
        project_id,
        node_id,
        config_root=config_root,
        runtime_root=runtime_root,
        repo_path=repo_path,
        include_heartbeat=False,
        host="testhost",
    )


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    _write_graph(root, PROJECT_ID, NODE_ID, "ready")
    _init_config_git(root)
    return root


@pytest.fixture
def runtime_root(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    return root


@pytest.fixture
def target_repo(tmp_path):
    repo = tmp_path / "demo-repo"
    _init_target_repo(repo)
    return repo


def test_graph_authorship_entry(config_root):
    tl = _build(config_root)
    graph_entries = [e for e in tl.entries if e.who == "graph"]
    assert graph_entries
    text = graph_entries[0].text
    assert NODE_ID in text
    assert "authored by" in text


def test_ledger_entry_and_hand_edit_warning(config_root, runtime_root):
    _write_ledger(runtime_root, PROJECT_ID, NODE_ID, [
        {
            "ts": "2026-09-05T11:33:11+00:00",
            "project_id": PROJECT_ID,
            "node_id": NODE_ID,
            "from_status": "ready",
            "to_status": "pending",
            "reason": "infra failure",
            "kind": "graph",
            "source": "gddp operator menu",
        },
    ])
    _create_runtime_db(runtime_root)
    tl = _build(config_root, runtime_root=runtime_root)
    you_entries = [e for e in tl.entries if e.who == "you"]
    assert you_entries
    assert "ready → pending" in you_entries[0].text
    assert "infra failure" in you_entries[0].text
    assert any("graph file says 'ready'" in w and "ended at 'pending'" in w for w in tl.warnings)

    nodes_path = config_root / "graphs" / PROJECT_ID / "nodes" / f"{NODE_ID}.yaml"
    nodes_path.write_text(
        nodes_path.read_text().replace("status: ready", "status: pending"),
        encoding="utf-8",
    )
    tl2 = _build(config_root, runtime_root=runtime_root)
    assert any(
        "graph file says" in w and "ended at" in w for w in tl2.warnings
    ) is False


def test_claimed_event_without_job_warns(config_root, runtime_root):
    _create_runtime_db(
        runtime_root,
        events=[(
            "ev1",
            "2026-09-05T11:50:00+00:00",
            "heartbeat",
            "claimed",
            "2026-09-05T11:50:01+00:00",
            PROJECT_ID,
            json.dumps([NODE_ID]),
            json.dumps({"selected_executor": "cursor_cli"}),
        )],
    )
    tl = _build(config_root, runtime_root=runtime_root)
    hb = [e for e in tl.entries if e.who == "heartbeat"]
    assert hb
    assert f"asked to dispatch {NODE_ID} on cursor_cli" in hb[0].text
    assert any("no job exists for it on this host" in w for w in tl.warnings)

    _create_runtime_db(
        runtime_root,
        jobs=[(
            "job_1",
            PROJECT_ID,
            NODE_ID,
            "cursor_cli",
            "queued",
            "queued",
            0,
            "2026-09-05T11:50:02+00:00",
        )],
        events=[(
            "ev1",
            "2026-09-05T11:50:00+00:00",
            "heartbeat",
            "claimed",
            "2026-09-05T11:50:01+00:00",
            PROJECT_ID,
            json.dumps([NODE_ID]),
            json.dumps({"selected_executor": "cursor_cli"}),
        )],
    )
    tl2 = _build(config_root, runtime_root=runtime_root)
    assert any("no job exists for it on this host" in w for w in tl2.warnings) is False


def test_job_state_disagreement_warns(config_root, runtime_root):
    _create_runtime_db(
        runtime_root,
        jobs=[(
            "job_drift",
            PROJECT_ID,
            NODE_ID,
            "cursor_cli",
            "running",
            "cancelled",
            0,
            "2026-09-05T11:55:00+00:00",
        )],
    )
    tl = _build(config_root, runtime_root=runtime_root)
    assert any("two different states" in w for w in tl.warnings)


def test_repo_flags_outside_gddp_and_recognizes_governed(config_root, target_repo):
    tl = _build(config_root, repo_path=target_repo)
    texts = [e.text for e in tl.entries if e.who == "repo"]
    agent_line = next(t for t in texts if "OUTSIDE GDDP" in t)
    assert "Grok 4.6" in agent_line
    governed_line = next(t for t in texts if "via GDDP" in t)
    assert governed_line
    assert governed_line in texts
    agent_warnings = [w for w in tl.warnings if "agent-authored commit(s)" in w]
    assert len(agent_warnings) == 1
    assert "1 agent-authored" in agent_warnings[0]
    assert any("other commit(s)" in n for n in tl.notes)


def test_missing_repo_checkout_is_a_note(config_root):
    tl = _build(config_root, repo_path=None)
    assert any("no local checkout" in n for n in tl.notes)


def test_no_jobs_on_host_note(config_root, runtime_root):
    _create_runtime_db(runtime_root)
    tl = _build(config_root, runtime_root=runtime_root)
    assert any("has no runtime jobs" in n for n in tl.notes)


def test_node_filter_and_unknown_node(config_root, runtime_root, target_repo):
    nodes_dir = config_root / "graphs" / PROJECT_ID / "nodes"
    (nodes_dir / "node-b.yaml").write_text(
        "id: node-b\ntitle: Other\nstatus: pending\n",
        encoding="utf-8",
    )
    _git_commit(config_root, "add node-b", "2026-09-05T09:45:00+00:00")
    _write_ledger(runtime_root, PROJECT_ID, NODE_ID, [{
        "ts": "2026-09-05T11:33:11+00:00",
        "project_id": PROJECT_ID,
        "node_id": NODE_ID,
        "from_status": "pending",
        "to_status": "ready",
        "reason": "accepted",
        "source": "gddp operator menu",
    }])
    _write_ledger(runtime_root, PROJECT_ID, "node-b", [{
        "ts": "2026-09-05T11:34:00+00:00",
        "project_id": PROJECT_ID,
        "node_id": "node-b",
        "from_status": "pending",
        "to_status": "ready",
        "reason": "accepted",
        "source": "gddp operator menu",
    }])
    _create_runtime_db(runtime_root)
    tl = _build(config_root, runtime_root=runtime_root, repo_path=target_repo, node_id=NODE_ID)
    for entry in tl.entries:
        assert entry.node in (NODE_ID, None)
    with pytest.raises(KeyError, match="absent from graph"):
        _build(config_root, node_id="ghost-node")
    with pytest.raises(FileNotFoundError):
        _build(config_root / "missing", project_id="nope")


def test_attempt_entries_filter():
    attempts = [
        {
            "project_id": "",
            "node_id": "node-a",
            "created": 1757000000,
            "state": "done",
            "name": "x",
            "dir": "/tmp/x",
        },
        {
            "project_id": "other",
            "node_id": "node-a",
            "created": 1757000000,
            "state": "done",
            "name": "y",
            "dir": "/tmp/y",
        },
        {
            "project_id": "",
            "node_id": "node-zzz",
            "created": 1757000000,
            "state": "done",
            "name": "z",
            "dir": "/tmp/z",
        },
    ]
    result = timeline.attempt_entries(attempts, "proj", {"node-a"}, None)
    assert len(result) == 1
    assert result[0].node == "node-a"
    assert result[0].text.startswith("attempt x")


def test_render_text_sections(config_root):
    tl = _build(config_root)
    graph = timeline.read_graph(config_root, PROJECT_ID)
    text = timeline.render_text(tl, graph["nodes"])
    assert f"timeline: {PROJECT_ID}" in text
    assert "graph says now:" in text
    assert "what is wrong" in text
    assert "nothing detected from this host" in text


def test_json_roundtrip(config_root):
    tl = _build(config_root)
    payload = tl.as_dict()
    serialized = json.dumps(payload)
    assert serialized
    for key in ("project_id", "node_id", "host", "entries", "warnings", "notes"):
        assert key in payload
