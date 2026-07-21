#!/usr/bin/env python3
"""Focused unittest coverage for Stage 1 node CLI (list/show/set-status).

Run:
  /Users/sab-mini/repos/gddp-config/.venv/bin/python scripts/test_node_cli.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import node_cli  # noqa: E402

PROJECT = "demo-proj"
PROJECT2 = "other-proj"
NODE_A = "alpha-node"
NODE_B = "beta-node"
NODE_C = "gamma-node"


def _valid_node(node_id: str, status: str = "pending", **overrides) -> dict:
    doc = {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node_id,
        "title": f"Title for {node_id}",
        "type": "capability",
        "why": "Because the graph needs this capability.",
        "depends_on": [],
        "acceptance_criteria": [
            {"id": "ac-1", "criterion": "thing exists"},
        ],
        "constraints": ["do not rewrite unrelated files"],
        "allowed_execution_modes": ["jules"],
        "required_artifacts": ["decision.md", "result-summary.md"],
        "status": status,
        "priority": "medium",
        "unlocks": [],
    }
    doc.update(overrides)
    return doc


def _write_yaml(path: Path, doc: dict) -> None:
    if path.name == "project.yaml":
        nodes = doc.get("nodes") or []
        lines = [
            'schema_version: "1.0"',
            "schema_type: project_graph",
            "",
            f"project_id: {doc['project_id']}",
            f"project_name: {doc.get('project_name', doc['project_id'])}",
            "repo: org/demo",
            "",
            "nodes_dir: nodes/",
            "",
            "nodes:",
        ]
        for n in nodes:
            lines.append(f"  - id: {n['id']}")
            lines.append(f"    title: {n.get('title', '')}")
            lines.append(f"    status: {n.get('status', 'pending')}")
            lines.append(f"    type: {n.get('type', 'capability')}")
            lines.append("")
        text = "\n".join(lines) + "\n"
    else:
        ac_lines = []
        for item in doc["acceptance_criteria"]:
            ac_lines.append(f"  - id: {item['id']}")
            ac_lines.append(f"    criterion: {item['criterion']}")
        text = "\n".join([
            'schema_version: "1.0"',
            "schema_type: node",
            "",
            f"node_id: {doc['node_id']}",
            f"title: {doc['title']}",
            f"type: {doc['type']}",
            "",
            "why: |",
            f"  {doc['why']}",
            "",
            "depends_on: []",
            "",
            "acceptance_criteria:",
            *ac_lines,
            "",
            "constraints:",
            *[f"  - {c}" for c in doc["constraints"]],
            "",
            "allowed_execution_modes:",
            *[f"  - {m}" for m in doc["allowed_execution_modes"]],
            "",
            "required_artifacts:",
            *[f"  - {a}" for a in doc["required_artifacts"]],
            "",
            f"status: {doc['status']}",
            f"priority: {doc['priority']}",
            "",
            "unlocks: []",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_fixture_root(two_projects: bool = False) -> Path:
    root = Path(tempfile.mkdtemp(prefix="node-cli-test-"))
    for pid, nodes in (
        (PROJECT, [
            _valid_node(NODE_A, status="pending"),
            _valid_node(NODE_B, status="ready"),
        ]),
        *([(PROJECT2, [_valid_node(NODE_C, status="complete", type="milestone",
                                    title="Gamma title")])] if two_projects else []),
    ):
        graphs = root / "graphs" / pid / "nodes"
        graphs.mkdir(parents=True)
        entries = []
        for doc in nodes:
            _write_yaml(graphs / f"{doc['node_id']}.yaml", doc)
            entries.append({
                "id": doc["node_id"],
                "title": doc["title"],
                "status": doc["status"],
                "type": doc["type"],
            })
        _write_yaml(
            root / "graphs" / pid / "project.yaml",
            {"project_id": pid, "project_name": pid, "nodes": entries},
        )
    return root


def make_db(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            project_id TEXT,
            node_id TEXT,
            queue_state TEXT,
            status TEXT,
            created_at TEXT
        );
        CREATE TABLE results (
            result_id TEXT PRIMARY KEY,
            job_id TEXT,
            outcome TEXT,
            status TEXT,
            received_at TEXT,
            acceptance_check TEXT
        );
        """
    )
    for r in rows:
        con.execute(
            "INSERT INTO jobs (job_id, project_id, node_id, queue_state, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                r["job_id"],
                r.get("project_id", PROJECT),
                r["node_id"],
                r.get("queue_state", "awaiting_review"),
                r.get("status", "awaiting_review"),
                r.get("created_at", "2026-07-01T00:00:00Z"),
            ),
        )
        if "acceptance_check" in r:
            con.execute(
                "INSERT INTO results "
                "(result_id, job_id, outcome, status, received_at, acceptance_check) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    r.get("result_id", "res_" + r["job_id"]),
                    r["job_id"],
                    r.get("outcome", "success"),
                    r.get("result_status", "needs_review"),
                    r.get("received_at", "2026-07-02T00:00:00Z"),
                    json.dumps(r["acceptance_check"]),
                ),
            )
    con.commit()
    con.close()
    return path


class FixtureCase(unittest.TestCase):
    two_projects = False

    def setUp(self):
        self.root = make_fixture_root(two_projects=self.two_projects)
        self.addCleanup(shutil.rmtree, self.root, True)


class ListFiltersTests(FixtureCase):
    two_projects = True

    def setUp(self):
        super().setUp()
        self.db = make_db(
            self.root / "rt" / "db" / "queue.db",
            [
                {
                    "job_id": "job_a",
                    "node_id": NODE_A,
                    "queue_state": "running",
                    "status": "running",
                    "created_at": "2026-07-10T00:00:00Z",
                    "acceptance_check": {"verdict": "fail"},
                    "received_at": "2026-07-10T01:00:00Z",
                },
                {
                    "job_id": "job_b",
                    "node_id": NODE_B,
                    "queue_state": "awaiting_review",
                    "created_at": "2026-07-11T00:00:00Z",
                    "acceptance_check": {"verdict": "pass"},
                    "received_at": "2026-07-11T01:00:00Z",
                },
            ],
        )

    def _list(self, **kwargs) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(root=self.root, db_path=self.db, **kwargs)
        self.assertEqual(rc, 0)
        return buf.getvalue()

    def test_id_first_columns_and_type_title(self):
        # Wide layout: single-line table with ID | GRAPH | RUNTIME | VERDICT | TYPE | TITLE
        out = self._list(project=PROJECT, width=120)
        header_line = next(
            ln for ln in out.splitlines() if ln.startswith("ID")
        )
        cols = header_line.split()
        self.assertEqual(cols[:6], ["ID", "GRAPH", "RUNTIME", "VERDICT", "TYPE", "TITLE"])
        data = next(ln for ln in out.splitlines() if ln.startswith(NODE_A))
        self.assertTrue(data.startswith(NODE_A))
        self.assertIn("capability", data)
        self.assertIn("Title for alpha-node", data)

    def test_all_project_headings(self):
        out = self._list()
        self.assertIn(f"# {PROJECT}", out)
        self.assertIn(f"# {PROJECT2}", out)
        self.assertIn(NODE_A, out)
        self.assertIn(NODE_C, out)

    def test_status_filter(self):
        out = self._list(project=PROJECT, status="ready")
        self.assertIn(NODE_B, out)
        self.assertNotIn(NODE_A, out)

    def test_active_filter(self):
        out = self._list(project=PROJECT, active=True)
        self.assertIn(NODE_A, out)
        self.assertIn(NODE_B, out)
        self.assertNotIn(NODE_C, out)

    def test_list_keeps_project_index_as_status_source(self):
        project_path = self.root / "graphs" / PROJECT / "project.yaml"
        project_path.write_text(
            project_path.read_text(encoding="utf-8").replace(
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: pending",
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: complete",
            ),
            encoding="utf-8",
        )

        out = self._list(project=PROJECT, active=True)

        self.assertNotIn(NODE_A, out)
        self.assertIn(NODE_B, out)

    def test_no_match_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(
                project=PROJECT, status="deferred", root=self.root, db_path=self.db
            )
        self.assertEqual(rc, 0)
        self.assertIn("No nodes matched the given filters.", buf.getvalue())

    def test_invalid_status_filter(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(
                project=PROJECT, status="running", root=self.root, db_path=self.db
            )
        self.assertEqual(rc, 2)
        self.assertIn("Invalid --status", buf.getvalue())


class ListResponsiveLayoutTests(ListFiltersTests):
    """Stage-1 UX: COLUMNS-aware list; exact ID; width caps; signal separation."""

    def _list_w(self, width: int, **kwargs) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(
                root=self.root, db_path=self.db, width=width, **kwargs
            )
        self.assertEqual(rc, 0)
        return buf.getvalue()

    def test_columns_80_exact_id_line_and_max_width(self):
        out = self._list_w(80, project=PROJECT)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        # exact node id alone on its own line (copyable)
        self.assertIn(NODE_A, lines)
        id_line = next(ln for ln in lines if ln == NODE_A)
        self.assertEqual(id_line, NODE_A)
        # meta line carries distinct signals
        meta = next(
            ln for ln in lines
            if "GRAPH" in ln and "RUNTIME" in ln and "VERDICT" in ln
        )
        self.assertIn("GRAPH pending", meta)
        self.assertIn("RUNTIME running", meta)
        self.assertIn("VERDICT fail", meta)
        # no emitted content line exceeds width (project header "# pid" short)
        for ln in out.splitlines():
            self.assertLessEqual(len(ln), 80, msg=repr(ln))

    def test_columns_120_table_id_first_title_truncatable(self):
        long_title = "T" * 200
        # stretch title on NODE_B via node yaml
        npath = self.root / "graphs" / PROJECT / "nodes" / f"{NODE_B}.yaml"
        text = npath.read_text(encoding="utf-8")
        npath.write_text(
            text.replace(f"title: Title for {NODE_B}", f"title: {long_title}"),
            encoding="utf-8",
        )
        out = self._list_w(120, project=PROJECT, status="ready")
        header = next(ln for ln in out.splitlines() if ln.startswith("ID"))
        self.assertIn("GRAPH", header)
        self.assertIn("VERDICT", header)
        data = next(ln for ln in out.splitlines() if ln.startswith(NODE_B))
        self.assertTrue(data.startswith(NODE_B))
        self.assertLessEqual(len(data), 120)
        # title ellipsized — full 200 T's must not appear
        self.assertNotIn(long_title, data)
        self.assertIn("…", data)

    def test_format_list_lines_unit_narrow_vs_wide(self):
        rows = [
            (
                "very-long-node-id-for-copy",
                "ready",
                "awaiting_review",
                "pass",
                "capability",
                "A fairly long title that would smash columns on narrow terminals",
            )
        ]
        narrow = node_cli.format_list_lines(rows, 80)
        self.assertEqual(narrow[0], "very-long-node-id-for-copy")
        self.assertTrue(any("GRAPH ready" in ln for ln in narrow))
        self.assertTrue(any("VERDICT pass" in ln for ln in narrow))
        self.assertTrue(any("RUNTIME awaiting_review" in ln for ln in narrow))
        for ln in narrow:
            self.assertLessEqual(len(ln), 80)

        wide = node_cli.format_list_lines(rows, 120)
        self.assertTrue(wide[0].startswith("ID"))
        data = wide[1]
        self.assertTrue(data.startswith("very-long-node-id-for-copy"))
        self.assertIn("pass", data)
        self.assertLessEqual(len(data), 120)

    def test_columns_env_respected_by_terminal_width(self):
        old = os.environ.get("COLUMNS")
        try:
            os.environ["COLUMNS"] = "80"
            self.assertEqual(node_cli.terminal_width(), 80)
            os.environ["COLUMNS"] = "120"
            self.assertEqual(node_cli.terminal_width(), 120)
        finally:
            if old is None:
                os.environ.pop("COLUMNS", None)
            else:
                os.environ["COLUMNS"] = old

    def test_evaluator_distinction_narrow(self):
        out = self._list_w(80, project=PROJECT)
        # NODE_A fail vs NODE_B pass stay distinct from graph status
        self.assertIn("VERDICT fail", out)
        self.assertIn("VERDICT pass", out)
        self.assertIn("GRAPH pending", out)
        self.assertIn("GRAPH ready", out)


class ShowTests(FixtureCase):
    def test_show_desync_and_no_evidence(self):
        ppath = self.root / "graphs" / PROJECT / "project.yaml"
        ppath.write_text(
            ppath.read_text().replace(
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: pending",
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: ready",
            ),
            encoding="utf-8",
        )
        db = make_db(self.root / "rt" / "db" / "queue.db", [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_show(
                project=PROJECT, node_id=NODE_A, root=self.root, db_path=db
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("DESYNC", out)
        self.assertIn("no evaluation evidence", out)
        self.assertRegex(out, r"graph status:\s+pending")
        self.assertRegex(out, r"evaluator verdict:\s+-")

    def test_missing_index_warning(self):
        ppath = self.root / "graphs" / PROJECT / "project.yaml"
        # Drop NODE_A from index only
        text = ppath.read_text()
        block = (
            f"  - id: {NODE_A}\n"
            f"    title: Title for {NODE_A}\n"
            f"    status: pending\n"
            f"    type: capability\n\n"
        )
        ppath.write_text(text.replace(block, ""), encoding="utf-8")
        db = make_db(self.root / "rt" / "db" / "queue.db", [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_show(
                project=PROJECT, node_id=NODE_A, root=self.root, db_path=db
            )
        self.assertEqual(rc, 0)
        self.assertIn("WARNING: project.yaml has no nodes entry", buf.getvalue())

    def test_runtime_without_evaluator(self):
        db = make_db(
            self.root / "rt" / "db" / "queue.db",
            [
                {
                    "job_id": "job_only",
                    "node_id": NODE_A,
                    "queue_state": "running",
                    "status": "running",
                    "created_at": "2026-07-10T00:00:00Z",
                    # no acceptance_check / result row
                }
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_show(
                project=PROJECT, node_id=NODE_A, root=self.root, db_path=db
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("runtime state:     running", out)
        self.assertIn("no evaluation evidence", out)
        self.assertRegex(out, r"evaluator verdict:\s+-")


class SetStatusTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.npath = self.root / "graphs" / PROJECT / "nodes" / f"{NODE_A}.yaml"
        self.ppath = self.root / "graphs" / PROJECT / "project.yaml"
        self.node_orig = self.npath.read_bytes()
        self.proj_orig = self.ppath.read_bytes()

    def test_dual_update_preserves_formatting(self):
        before_node = self.npath.read_text(encoding="utf-8")
        before_proj = self.ppath.read_text(encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_set_status(
                project=PROJECT,
                node_id=NODE_A,
                status="ready",
                yes=True,
                root=self.root,
            )
        self.assertEqual(rc, 0, buf.getvalue())
        after_node = self.npath.read_text(encoding="utf-8")
        after_proj = self.ppath.read_text(encoding="utf-8")
        self.assertEqual(
            before_node.replace("status: pending", "status: ready"),
            after_node,
        )
        self.assertEqual(
            before_proj.replace(
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: pending",
                f"  - id: {NODE_A}\n    title: Title for {NODE_A}\n    status: ready",
            ),
            after_proj,
        )

    def test_noop_does_not_rewrite(self):
        content_n = self.npath.read_bytes()
        content_p = self.ppath.read_bytes()
        mtime_n = self.npath.stat().st_mtime_ns
        mtime_p = self.ppath.stat().st_mtime_ns
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_set_status(
                project=PROJECT,
                node_id=NODE_A,
                status="pending",
                yes=True,
                root=self.root,
            )
        self.assertEqual(rc, 0)
        self.assertIn("No-op", buf.getvalue())
        self.assertEqual(self.npath.read_bytes(), content_n)
        self.assertEqual(self.ppath.read_bytes(), content_p)
        self.assertEqual(self.npath.stat().st_mtime_ns, mtime_n)
        self.assertEqual(self.ppath.stat().st_mtime_ns, mtime_p)

    def test_abort_without_yes(self):
        buf = io.StringIO()
        with mock.patch("builtins.input", return_value="n"):
            with redirect_stdout(buf):
                rc = node_cli.cmd_set_status(
                    project=PROJECT,
                    node_id=NODE_A,
                    status="ready",
                    yes=False,
                    root=self.root,
                )
        self.assertEqual(rc, 1)
        self.assertIn("Aborted", buf.getvalue())
        self.assertEqual(self.npath.read_bytes(), self.node_orig)
        self.assertEqual(self.ppath.read_bytes(), self.proj_orig)

    def test_rollback_on_post_write_validation_failure(self):
        buf = io.StringIO()
        with mock.patch.object(
            node_cli,
            "validate_status_change_docs",
            return_value=["injected validation failure"],
        ):
            with redirect_stdout(buf):
                rc = node_cli.cmd_set_status(
                    project=PROJECT,
                    node_id=NODE_A,
                    status="ready",
                    yes=True,
                    root=self.root,
                )
        self.assertEqual(rc, 1)
        self.assertIn("rolled back", buf.getvalue())
        self.assertEqual(self.npath.read_bytes(), self.node_orig)
        self.assertEqual(self.ppath.read_bytes(), self.proj_orig)

    def test_invalid_status_rejected(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_set_status(
                project=PROJECT,
                node_id=NODE_A,
                status="running",
                yes=True,
                root=self.root,
            )
        self.assertEqual(rc, 2)
        self.assertEqual(self.npath.read_bytes(), self.node_orig)

    def test_candidate_rejection_before_writes(self):
        buf = io.StringIO()
        with mock.patch.object(
            node_cli,
            "verify_candidates",
            return_value=["candidate node status is wrong"],
        ):
            with redirect_stdout(buf):
                rc = node_cli.cmd_set_status(
                    project=PROJECT,
                    node_id=NODE_A,
                    status="ready",
                    yes=True,
                    root=self.root,
                )
        self.assertEqual(rc, 1)
        self.assertIn("No files written", buf.getvalue())
        self.assertEqual(self.npath.read_bytes(), self.node_orig)
        self.assertEqual(self.ppath.read_bytes(), self.proj_orig)

    def test_baseline_failure_before_writes(self):
        buf = io.StringIO()
        with mock.patch.object(
            node_cli,
            "baseline_error_keys",
            side_effect=RuntimeError("validate blew up"),
        ):
            with redirect_stdout(buf):
                rc = node_cli.cmd_set_status(
                    project=PROJECT,
                    node_id=NODE_A,
                    status="ready",
                    yes=True,
                    root=self.root,
                )
        self.assertEqual(rc, 1)
        self.assertIn("baseline failed before write", buf.getvalue())
        self.assertIn("No files written", buf.getvalue())
        self.assertEqual(self.npath.read_bytes(), self.node_orig)

    def test_project_status_boundary_missing_entry_status(self):
        # Entry for NODE_A has no status; later top-level/other entry has status
        text = (
            'schema_version: "1.0"\n'
            "schema_type: project_graph\n"
            f"project_id: {PROJECT}\n"
            "nodes:\n"
            f"  - id: {NODE_A}\n"
            f"    title: Title for {NODE_A}\n"
            "    type: capability\n"
            "\n"
            f"  - id: {NODE_B}\n"
            f"    title: Title for {NODE_B}\n"
            "    status: ready\n"
            "    type: capability\n"
        )
        self.ppath.write_text(text, encoding="utf-8")
        before = self.ppath.read_text()
        with self.assertRaises(ValueError) as ctx:
            node_cli.replace_project_index_status(before, NODE_A, "complete")
        self.assertIn("status field not found", str(ctx.exception))
        # NODE_B status untouched
        self.assertEqual(self.ppath.read_text(), before)
        self.assertIn("status: ready", before)


class RuntimeEvidenceTests(FixtureCase):
    def test_latest_result_and_receipt_path(self):
        receipt = {
            "project_id": PROJECT,
            "node_id": NODE_A,
            "verdict": "pass",
            "criteria_verdict": "pass",
            "criteria_confidence": 0.9,
            "integrity": {
                "verdict": "pass",
                "confidence": 0.8,
                "findings": [],
                "graph_observations": [
                    {
                        "severity": "medium",
                        "summary": "watch frontier",
                        "affected_node_ids": [],
                    }
                ],
                "lane_status": "completed",
                "tool_trace": [{"tool": "read", "path": "x.py"}],
            },
            "semantic": {
                "judgments": [],
                "overall_reasoning": "fine",
                "risks": None,
                "followup_candidates": None,
                "budget_exhausted": False,
                "lane_status": "completed",
                "tool_trace": [{"tool": "grep"}],
            },
            "evaluated_commit_sha": "abc",
            "merge_commit_sha": "abc",
            "context_coverage": {
                "criteria": {"rating": "high"},
                "integrity": {"rating": "medium"},
                "overall": "high",
            },
        }
        rpath = self.root / "receipts" / "alpha.json"
        rpath.parent.mkdir(parents=True)
        rpath.write_text(json.dumps(receipt), encoding="utf-8")

        db = make_db(
            self.root / "rt" / "db" / "queue.db",
            [
                {
                    "job_id": "job_old",
                    "node_id": NODE_A,
                    "queue_state": "failed",
                    "created_at": "2026-07-01T00:00:00Z",
                    "acceptance_check": {"verdict": "fail"},
                    "received_at": "2026-07-01T01:00:00Z",
                },
                {
                    "job_id": "job_new",
                    "node_id": NODE_A,
                    "queue_state": "awaiting_review",
                    "created_at": "2026-07-12T00:00:00Z",
                    "acceptance_check": {
                        "verdict": "pass",
                        "criteria_verdict": "pass",
                        "criteria_confidence": 0.9,
                        "receipt_path": str(rpath),
                        "integrity": {
                            "verdict": "pass",
                            "confidence": 0.8,
                            "findings": [],
                        },
                    },
                    "received_at": "2026-07-12T01:00:00Z",
                },
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_show(
                project=PROJECT,
                node_id=NODE_A,
                root=self.root,
                db_path=db,
                trace=True,
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("awaiting_review", out)
        self.assertRegex(out, r"evaluator verdict:\s*pass")
        self.assertIn("criteria:  verdict=pass", out)
        self.assertIn("watch frontier", out)
        self.assertIn(str(rpath), out)
        self.assertIn("job_new", out)

    def test_receipt_fallback_live_path(self):
        live = self.root / "verification-runtime-live" / PROJECT / f"{NODE_A}.json"
        live.parent.mkdir(parents=True)
        live.write_text(
            json.dumps({
                "verdict": "needs-more-evidence",
                "criteria_verdict": "needs-more-evidence",
                "criteria_confidence": 0.1,
                "integrity": {"verdict": "unknown", "confidence": 0.0, "findings": []},
                "lane_status": {"criteria": "completed", "integrity": "not_run"},
                "harness_error": {"criteria": None, "integrity": None},
            }),
            encoding="utf-8",
        )
        db = make_db(self.root / "rt" / "db" / "queue.db", [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_show(
                project=PROJECT, node_id=NODE_A, root=self.root, db_path=db
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("needs-more-evidence", out)
        self.assertIn("lane=completed", out)
        self.assertIn(str(live), out)

    def test_malformed_evidence_is_normal(self):
        db_path = self.root / "rt" / "db" / "queue.db"
        db_path.parent.mkdir(parents=True)
        con = sqlite3.connect(db_path)
        con.execute(
            "CREATE TABLE jobs (job_id TEXT, project_id TEXT, node_id TEXT, "
            "queue_state TEXT, status TEXT, created_at TEXT)"
        )
        con.execute(
            "CREATE TABLE results (result_id TEXT, job_id TEXT, outcome TEXT, "
            "status TEXT, received_at TEXT, acceptance_check TEXT)"
        )
        con.execute(
            "INSERT INTO jobs VALUES (?,?,?,?,?,?)",
            ("j1", PROJECT, NODE_A, "running", "running", "2026-07-01T00:00:00Z"),
        )
        con.execute(
            "INSERT INTO results VALUES (?,?,?,?,?,?)",
            ("r1", "j1", "success", "needs_review", "2026-07-01T01:00:00Z", "NOT JSON{{{"),
        )
        con.commit()
        con.close()
        live = self.root / "verification-runtime-live" / PROJECT / f"{NODE_A}.json"
        live.parent.mkdir(parents=True)
        live.write_text("{broken", encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(project=PROJECT, root=self.root, db_path=db_path)
        self.assertEqual(rc, 0)
        self.assertIn("running", buf.getvalue())

        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            rc2 = node_cli.cmd_show(
                project=PROJECT, node_id=NODE_A, root=self.root, db_path=db_path
            )
        self.assertEqual(rc2, 0)
        self.assertIn("no evaluation evidence", buf2.getvalue())

    def test_missing_db_exits_zero(self):
        missing = self.root / "nope" / "queue.db"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = node_cli.cmd_list(project=PROJECT, root=self.root, db_path=missing)
        self.assertEqual(rc, 0)
        self.assertIn("-", buf.getvalue())


class NormalizeShapeTests(unittest.TestCase):
    def test_full_vs_summary_lane_shapes(self):
        full = {
            "semantic": {"lane_status": "crashed", "harness_error": "boom"},
            "integrity": {"lane_status": "timed-out", "harness_error": "slow"},
        }
        lane, harness = node_cli._lane_fields(full, {})
        self.assertEqual(lane["criteria"], "crashed")
        self.assertEqual(lane["integrity"], "timed-out")
        self.assertEqual(harness["criteria"], "boom")
        self.assertEqual(harness["integrity"], "slow")

        summary = {
            "lane_status": {"criteria": "completed", "integrity": "completed"},
            "harness_error": {"criteria": None, "integrity": None},
        }
        lane2, harness2 = node_cli._lane_fields(summary, summary)
        self.assertEqual(lane2["criteria"], "completed")
        self.assertIsNone(harness2["criteria"])


class ReplaceHelpersTests(unittest.TestCase):
    def test_replace_node_status_only_toplevel(self):
        text = "node_id: x\nstatus: pending\npriority: high\n"
        new, old = node_cli.replace_node_status(text, "complete")
        self.assertEqual(old, "pending")
        self.assertEqual(new, "node_id: x\nstatus: complete\npriority: high\n")


class LauncherTests(unittest.TestCase):
    def test_launcher_help_smoke(self):
        launcher = REPO_ROOT / "bin" / "gddp"
        self.assertTrue(launcher.is_file())
        self.assertTrue(os.access(launcher, os.X_OK))
        env = os.environ.copy()
        env["GDDP_CONFIG_PATH"] = str(REPO_ROOT)
        # Prefer shared venv python via the launcher path when present
        proc = subprocess.run(
            [str(launcher), "--help"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("graph node management", proc.stdout.lower() + proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
