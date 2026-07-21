#!/usr/bin/env python3
"""Focused tests for Stage-1 node list / show / set-status (node_ops).

Run with shared config venv:
  /Users/sab-mini/repos/gddp-config/.venv/bin/python scripts/test_node_ops.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import node_ops  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PROJECT_YAML = """\
schema_version: "1.0"
schema_type: project_graph

project_id: demo
project_name: Demo
repo: org/demo

nodes:
  - id: alpha-node
    title: Alpha
    status: pending
    type: capability
  - id: beta-node
    title: Beta
    status: ready
    type: capability
  - id: done-node
    title: Done
    status: complete
    type: capability
"""

NODE_ALPHA = """\
schema_version: "1.0"
schema_type: node

node_id: alpha-node
title: Alpha
type: capability

why: |
  Keep intent visible.

depends_on: []

acceptance_criteria:
  - id: a1
    criterion: something works

constraints:
  - do not expand scope

allowed_execution_modes:
  - human

required_artifacts:
  - decision.md

status: pending
priority: medium
unlocks: []
"""

NODE_BETA = NODE_ALPHA.replace("alpha-node", "beta-node").replace(
    "title: Alpha", "title: Beta"
).replace("status: pending", "status: ready")

NODE_DONE = NODE_ALPHA.replace("alpha-node", "done-node").replace(
    "title: Alpha", "title: Done"
).replace("status: pending", "status: complete")


class NodeOpsCoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        g = self.root / "graphs" / "demo" / "nodes"
        _write(self.root / "graphs" / "demo" / "project.yaml", PROJECT_YAML)
        _write(g / "alpha-node.yaml", NODE_ALPHA)
        _write(g / "beta-node.yaml", NODE_BETA)
        _write(g / "done-node.yaml", NODE_DONE)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_active_filter_excludes_complete(self) -> None:
        rows = node_ops.iter_index_nodes(self.root, "demo", active=True)
        ids = [e["id"] for _, e in rows]
        self.assertEqual(ids, ["alpha-node", "beta-node"])

    def test_status_filter(self) -> None:
        rows = node_ops.iter_index_nodes(self.root, "demo", status="ready")
        self.assertEqual([e["id"] for _, e in rows], ["beta-node"])

    def test_list_id_first_columns(self) -> None:
        line = node_ops.format_list_line(
            "neutral-executor-contract", "ready", "awaiting_review", "pass"
        )
        self.assertTrue(line.startswith("neutral-executor-contract"))
        self.assertIn("ready", line)
        self.assertIn("awaiting_review", line)
        self.assertIn("pass", line)

    def test_set_status_dual_write_preserves_surrounding_text(self) -> None:
        node_path = self.root / "graphs" / "demo" / "nodes" / "alpha-node.yaml"
        before = node_path.read_text(encoding="utf-8")
        marker = "Keep intent visible."
        self.assertIn(marker, before)

        result = node_ops.set_graph_status(self.root, "demo", "alpha-node", "ready")
        self.assertFalse(result.get("noop"))
        after_node = node_path.read_text(encoding="utf-8")
        after_proj = (self.root / "graphs" / "demo" / "project.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn(marker, after_node)
        self.assertRegex(after_node, r"(?m)^status: ready\s*$")
        # project index for alpha-node is ready; others unchanged
        self.assertIn("status: ready", after_proj)
        self.assertIn("id: done-node", after_proj)
        self.assertIn("status: complete", after_proj)

        # re-load validates
        node = node_ops.load_node_yaml(self.root, "demo", "alpha-node")
        proj = node_ops.load_project(self.root, "demo")
        entry = node_ops.project_node_entry(proj, "alpha-node")
        self.assertEqual(node["status"], "ready")
        self.assertEqual(entry["status"], "ready")

    def test_set_status_noop_no_rewrite(self) -> None:
        node_path = self.root / "graphs" / "demo" / "nodes" / "beta-node.yaml"
        proj_path = self.root / "graphs" / "demo" / "project.yaml"
        n0 = node_path.read_text(encoding="utf-8")
        p0 = proj_path.read_text(encoding="utf-8")
        result = node_ops.set_graph_status(self.root, "demo", "beta-node", "ready")
        self.assertTrue(result.get("noop"))
        self.assertEqual(node_path.read_text(encoding="utf-8"), n0)
        self.assertEqual(proj_path.read_text(encoding="utf-8"), p0)

    def test_set_status_invalid(self) -> None:
        with self.assertRaises(ValueError):
            node_ops.set_graph_status(self.root, "demo", "alpha-node", "running")

    def test_show_desync_warning(self) -> None:
        # break sync intentionally
        node_path = self.root / "graphs" / "demo" / "nodes" / "alpha-node.yaml"
        text = node_path.read_text(encoding="utf-8")
        node_path.write_text(
            text.replace("status: pending", "status: ready"), encoding="utf-8"
        )
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            code = node_ops.cmd_show(
                self.root,
                project_id="demo",
                node_id="alpha-node",
                runtime_root=self.root / "no-runtime",
                trace=False,
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("WARN: status desync", out)
        self.assertIn("graph_status:", out)


class NodeOpsEvalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        g = self.root / "graphs" / "demo" / "nodes"
        _write(self.root / "graphs" / "demo" / "project.yaml", PROJECT_YAML)
        _write(g / "alpha-node.yaml", NODE_ALPHA)
        _write(g / "beta-node.yaml", NODE_BETA)
        _write(g / "done-node.yaml", NODE_DONE)

        # runtime DB with one job + result
        self.runtime = self.root / "runtime"
        db_path = self.runtime / "db" / "queue.db"
        db_path.parent.mkdir(parents=True)
        con = sqlite3.connect(db_path)
        con.executescript(
            """
            CREATE TABLE jobs (
              job_id TEXT PRIMARY KEY,
              project_id TEXT,
              node_id TEXT NOT NULL,
              queue_state TEXT,
              status TEXT,
              attempt INTEGER,
              max_attempts INTEGER,
              executor TEXT,
              created_at TEXT,
              job_type TEXT DEFAULT 'implementation',
              title TEXT DEFAULT '',
              goal TEXT DEFAULT ''
            );
            CREATE TABLE results (
              result_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              executor TEXT,
              received_at TEXT,
              outcome TEXT,
              status TEXT,
              acceptance_check TEXT
            );
            """
        )
        check = {
            "verdict": "pass",
            "criteria_verdict": "pass",
            "criteria_confidence": 0.9,
            "integrity": {"verdict": "pass", "confidence": 0.8, "findings": []},
            "lane_status": {"criteria": "ok", "integrity": "ok"},
            "harness_error": {},
            "evaluated_commit_sha": "abc",
            "merge_commit_sha": "abc",
            "criteria_findings": [
                {"criterion_id": "a1", "judgment": "pass"}
            ],
            "context_coverage": {
                "criteria": {"rating": "high"},
                "integrity": {"rating": "medium"},
                "overall": "high",
            },
            "receipt_path": "/tmp/receipt.json",
        }
        con.execute(
            "INSERT INTO jobs (job_id, project_id, node_id, queue_state, status, "
            "attempt, max_attempts, executor, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "job_1",
                "demo",
                "alpha-node",
                "awaiting_review",
                "awaiting_review",
                1,
                3,
                "jules",
                "2026-07-21T00:00:00Z",
            ),
        )
        con.execute(
            "INSERT INTO results (result_id, job_id, executor, received_at, outcome, "
            "status, acceptance_check) VALUES (?,?,?,?,?,?,?)",
            (
                "res_1",
                "job_1",
                "jules",
                "2026-07-21T01:00:00Z",
                "success",
                "needs_review",
                json.dumps(check),
            ),
        )
        con.commit()
        con.close()
        self.db_path = db_path

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_join_latest_verdict(self) -> None:
        ev = node_ops.fetch_runtime_evidence(
            self.db_path, "demo", "alpha-node", config_root=self.root
        )
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.queue_state, "awaiting_review")
        self.assertEqual(ev.eval_verdict, "pass")

    def test_missing_db_is_not_error(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            code = node_ops.cmd_list(
                self.root,
                project_id="demo",
                status=None,
                active=True,
                runtime_root=self.root / "missing-runtime",
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("alpha-node", out)
        # runtime and verdict columns should show dashes
        self.assertIn("  -  ", out.replace("\n", " "))

    def test_show_evaluator_section(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            code = node_ops.cmd_show(
                self.root,
                project_id="demo",
                node_id="alpha-node",
                runtime_root=self.runtime,
                trace=True,
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("graph_status:", out)
        self.assertIn("runtime_state: awaiting_review", out)
        self.assertIn("overall_verdict: pass", out)
        self.assertIn("criteria:", out)
        self.assertIn("integrity:", out)
        self.assertIn("provenance:", out)
        self.assertIn("receipt_path:", out)
        self.assertIn("Evaluator trace", out)

    def test_live_receipt_fallback(self) -> None:
        live = (
            self.root
            / "verification-runtime-live"
            / "demo"
            / "beta-node.json"
        )
        _write(
            live,
            json.dumps(
                {
                    "verdict": "fail",
                    "criteria_verdict": "fail",
                    "criteria_confidence": 0.2,
                    "integrity": {"verdict": "indeterminate", "confidence": 0.1},
                    "lane_status": {"criteria": "ok", "integrity": "error"},
                }
            ),
        )
        ev = node_ops.fetch_runtime_evidence(
            None, "demo", "beta-node", config_root=self.root
        )
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.eval_verdict, "fail")
        self.assertIsNone(ev.job_id)


if __name__ == "__main__":
    # Prefer shared venv if invoked oddly; tests are stdlib unittest.
    raise SystemExit(unittest.main(verbosity=2))
