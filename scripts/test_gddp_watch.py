"""Watch → Layer 1 wiring, including a real feed smoke test when installed."""

import argparse
import json
import os
import selectors
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gddp


@pytest.fixture
def attempt(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "scripts").mkdir(parents=True)
    (runtime / "scripts/jobs_status.py").write_text("# discovery marker\n")
    spool = runtime / "jobs/local-subprocess-spool"
    directory = spool / "job-one-attempt-2"
    directory.mkdir(parents=True)
    (directory / "packet.json").write_text(json.dumps({
        "job_id": "job-one", "node_id": "node-one",
        "execution_attempt_id": "job-one:attempt:2",
    }))
    (directory / "worktree_path").write_text(str(tmp_path / "gddp-agent-wt-one"))
    monkeypatch.setenv("GDDP_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("GDDP_ATTEMPT_SPOOL_DIR", str(spool))
    monkeypatch.delenv("GDDP_LOCAL_SUBPROCESS_SPOOL_DIR", raising=False)
    monkeypatch.setenv("GDDP_WORKTREE_MAP_PATH", str(tmp_path / "map.ndjson"))
    monkeypatch.setenv("AGENT_OBS_DB", str(tmp_path / "obs.db"))
    return gddp._attempt_info(directory)


@pytest.fixture
def index(attempt):
    path = Path(os.environ["AGENT_OBS_DB"])
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT)")
        con.execute("INSERT INTO sessions VALUES (?, ?)", ("session-one", attempt["worktree"]))
    return path


def test_session_uses_exact_path_and_preserves_execution_attempt(attempt, index):
    assert attempt["execution_attempt_id"] == "job-one:attempt:2"
    with sqlite3.connect(index) as con:
        con.execute("INSERT INTO sessions VALUES ('other', '/other/gddp-agent-wt-one')")
    assert gddp._agent_obs_session(attempt, index) == "session-one"


@pytest.mark.parametrize("mapped", [False, True])
def test_pruned_macos_worktree_alias_and_map_retry_binding(attempt, index, mapped):
    attempt["worktree"] = None if mapped else "/var/folders/tmp/gddp-agent-wt-one"
    Path(os.environ["GDDP_WORKTREE_MAP_PATH"]).write_text("\n".join([
        json.dumps({"job_id": "job-one", "execution_attempt_id": "job-one:attempt:1",
                    "worktree_path": "/tmp/gddp-agent-wt-previous"}),
        "null", "[]", "{partial",
        json.dumps({"job_id": "job-one", "execution_attempt_id": "job-one:attempt:2",
                    "worktree_path": "/var/folders/tmp/gddp-agent-wt-one"}),
        json.dumps({"job_id": "unrelated", "worktree_path": "/tmp/other"}),
    ]))
    with sqlite3.connect(index) as con:
        con.execute("UPDATE sessions SET cwd = '/private/var/folders/tmp/gddp-agent-wt-one'")
        con.execute("INSERT INTO sessions VALUES ('old-session', '/tmp/gddp-agent-wt-previous')")
    assert gddp._agent_obs_session(attempt, index) == "session-one"


def test_symlink_worktree_path(attempt, index, tmp_path):
    target = Path(attempt["worktree"])
    target.mkdir()
    alias = tmp_path / "linked-tree"
    alias.symlink_to(target, target_is_directory=True)
    attempt["worktree"] = str(alias)
    assert gddp._agent_obs_session(attempt, index) == "session-one"


@pytest.mark.parametrize("case, message", [
    ("missing-db", "could not read agent-obs index"),
    ("bad-schema", "could not read agent-obs index"),
    ("empty-index", "no agent-obs session"),
    ("ambiguous", "multiple agent-obs sessions"),
    ("ordinary-basename", "no agent-obs session"),
    ("missing-worktree", "missing worktree"),
    ("wrong-retry", "missing worktree"),
    ("ambiguous-map", "ambiguous worktree"),
])
def test_lookup_failures_are_explicit(attempt, index, tmp_path, case, message):
    if case == "missing-db":
        index = tmp_path / "absent.db"
    elif case == "bad-schema":
        with sqlite3.connect(index) as con:
            con.execute("ALTER TABLE sessions RENAME TO unrelated")
    elif case == "empty-index":
        with sqlite3.connect(index) as con:
            con.execute("UPDATE sessions SET cwd = '/unrelated'")
    elif case == "ambiguous":
        with sqlite3.connect(index) as con:
            con.execute("INSERT INTO sessions VALUES ('second', ?)", (attempt["worktree"],))
    elif case == "ordinary-basename":
        attempt["worktree"] = "/one/repo"
        with sqlite3.connect(index) as con:
            con.execute("UPDATE sessions SET cwd = '/two/repo'")
    else:
        attempt["worktree"] = None
        if case in {"wrong-retry", "ambiguous-map"}:
            rows = [{"job_id": "job-one", "execution_attempt_id": "job-one:attempt:1",
                     "worktree_path": "/tmp/gddp-agent-wt-old"}]
            if case == "ambiguous-map":
                attempt["execution_attempt_id"] = ""  # legacy packet cannot distinguish retries
                rows.append({"job_id": "job-one", "worktree_path": "/tmp/gddp-agent-wt-new"})
            Path(os.environ["GDDP_WORKTREE_MAP_PATH"]).write_text(
                "\n".join(json.dumps(row) for row in rows))
    with pytest.raises(RuntimeError, match=message):
        gddp._agent_obs_session(attempt, index)
    if case == "missing-db":
        assert not index.exists()  # mode=ro must never manufacture an empty index


@pytest.mark.parametrize("route", ["path", "venv", "uv", "missing"])
def test_cli_resolution(tmp_path, monkeypatch, route):
    root = tmp_path / "agent obs"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "agent-obs"\n')
    monkeypatch.setenv("GDDP_AGENT_OBS_ROOT", str(root))
    monkeypatch.setattr(gddp.shutil, "which", lambda name: (
        "/bin/agent-obs" if route == "path" and name == "agent-obs" else
        "/bin/uv" if route == "uv" and name == "uv" else None))
    if route == "venv":
        cli = root / ".venv/bin/agent-obs"
        cli.parent.mkdir(parents=True)
        cli.write_text("#!/bin/sh\n")
        cli.chmod(0o755)
    if route == "missing":
        with pytest.raises(RuntimeError, match="GDDP_AGENT_OBS_ROOT"):
            gddp._agent_obs_command()
    else:
        expected = {"path": ["/bin/agent-obs"], "venv": [str(root / ".venv/bin/agent-obs")],
                    "uv": ["/bin/uv", "run", "--project", str(root), "agent-obs"]}
        assert gddp._agent_obs_command() == expected[route]


@pytest.mark.parametrize("target", ["job-one", "node-one", "job-one-attempt-2"])
@pytest.mark.parametrize("tty", [False, True])
def test_watch_execs_feed_even_when_piped(attempt, index, monkeypatch, target, tty):
    monkeypatch.setattr(gddp, "_agent_obs_command", lambda: ["/bin/agent-obs"])
    monkeypatch.setattr(gddp.sys.stdout, "isatty", lambda: tty)
    execute = Mock()
    monkeypatch.setattr(gddp.os, "execvp", execute)
    assert gddp.main(["watch", target]) == 0
    execute.assert_called_once_with("/bin/agent-obs", [
        "/bin/agent-obs", "--db", str(index), "feed", "--watch", "session-one"])


def test_xdg_index_matches_feed_db(attempt, index, tmp_path, monkeypatch):
    xdg = tmp_path / "data"
    target = xdg / "agent-obs/agent-obs.db"
    target.parent.mkdir(parents=True)
    target.write_bytes(index.read_bytes())
    monkeypatch.delenv("AGENT_OBS_DB")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    monkeypatch.setattr(gddp, "_agent_obs_command", lambda: ["agent-obs"])
    execute = Mock()
    monkeypatch.setattr(gddp.os, "execvp", execute)
    assert gddp._watch_agent_events(attempt) == 0
    assert execute.call_args.args[1] == ["agent-obs", "--db", str(target), "feed", "--watch", "session-one"]


def test_exec_failure_reports_error(attempt, index, monkeypatch, capsys):
    monkeypatch.setattr(gddp, "_agent_obs_command", lambda: ["agent-obs"])
    execute = Mock(side_effect=OSError("launch failed"))
    monkeypatch.setattr(gddp.os, "execvp", execute)
    assert gddp._watch_agent_events(attempt) == 1
    assert "launch failed" in capsys.readouterr().err
    assert execute.call_count == 1


def test_once_snapshot_works_without_layer_one(attempt, monkeypatch, capsys):
    monkeypatch.setattr(gddp, "_watch_agent_events", Mock(side_effect=AssertionError("live feed")))
    assert gddp.main(["watch", "job-one", "--once"]) == 0
    text = capsys.readouterr().out
    assert "diff vs HEAD" in text and "(agent-obs)" in text
    assert "tail -F" not in text


@pytest.mark.parametrize("action", ["watch", "events", "tail", "e"])
def test_picker_preserves_selected_retry(attempt, monkeypatch, action):
    other = dict(attempt, name="newer-attempt", dir=attempt["dir"].parent / "newer-attempt")
    monkeypatch.setattr(gddp, "_discover_attempts", lambda _root: [other, attempt])
    fzf = Mock()
    fzf.available.return_value = True
    fzf.pick.return_value = [str(attempt["dir"])]
    monkeypatch.setattr(gddp, "_import_module", lambda name: fzf)
    feed = Mock(return_value=0)
    monkeypatch.setattr(gddp, "_watch_agent_events", feed)
    assert gddp.main(["runs", "--all", "--action", action]) == 0
    feed.assert_called_once_with(attempt)


def test_real_agent_obs_feed_streams_appended_events(attempt, tmp_path, monkeypatch):
    """Real CLI + native Pi ingestion + live delta + Ctrl-C; isolated from user state."""
    try:
        agent_obs = gddp._agent_obs_command()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    monkeypatch.setenv("AGENT_OBS_FORWARD", "0")
    session_id = "gddp-watch-smoke"
    source = tmp_path / "pi-smoke.jsonl"
    source.write_text(json.dumps({
        "type": "session", "id": session_id, "cwd": attempt["worktree"], "version": 3,
    }) + "\n")

    def ingest_call(call_id):
        with source.open("a") as handle:
            handle.write(json.dumps({"type": "message", "id": f"msg-{call_id}", "message": {
                "role": "assistant", "content": [{"type": "toolCall", "id": call_id,
                "name": "read", "arguments": {"path": "README.md"}}],
            }}) + "\n")
        result = subprocess.run(agent_obs + ["ingest", "--path", str(source)],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr

    ingest_call("before-watch")
    # Exercise map-only recovery as well as the real exec boundary.
    (attempt["dir"] / "worktree_path").rename(attempt["dir"] / "worktree_path.saved")
    Path(os.environ["GDDP_WORKTREE_MAP_PATH"]).write_text(json.dumps({
        "job_id": attempt["job_id"], "execution_attempt_id": attempt["execution_attempt_id"],
        "worktree_path": attempt["worktree"],
    }) + "\n")
    proc = subprocess.Popen([sys.executable, str(Path(gddp.__file__).resolve()), "watch", "job-one"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            for call_id in ["before-watch", "after-watch"]:
                if call_id == "after-watch":
                    ingest_call(call_id)
                assert selector.select(timeout=15), "agent-obs feed produced no event"
                line = proc.stdout.readline()
                assert line, f"watch exited early: {proc.poll()}"
                event = json.loads(line)
                assert event["type"] == "tool/call"
                assert event["sessionId"] == session_id
                assert event["data"]["callId"] == call_id
                assert event["derived"] is True
        os.killpg(proc.pid, signal.SIGINT)
        assert proc.wait(timeout=10) == 0
        assert b"feed --watch gddp-watch-smoke" in proc.stderr.read()
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        proc.stdout.close()
        proc.stderr.close()
