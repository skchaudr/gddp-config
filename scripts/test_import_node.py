#!/usr/bin/env python3
"""Tests for scripts/import_node.py agent-pipeline import."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import import_node
import yaml


def _valid_doc(**overrides) -> dict:
    doc = {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": "import-fixture",
        "title": "Import fixture",
        "type": "capability",
        "why": "exercise the import pipeline",
        "depends_on": [],
        "acceptance_criteria": [{"id": "ok", "criterion": "something holds"}],
        "constraints": [],
        "allowed_execution_modes": ["local_subprocess"],
        "required_artifacts": ["docs/decision.md"],
        "status": "pending",
        "priority": "medium",
        "unlocks": [],
    }
    doc.update(overrides)
    return doc


def _project(root: Path, project_id: str = "demo") -> Path:
    project = root / "graphs" / project_id
    (project / "nodes").mkdir(parents=True)
    (project / "project.yaml").write_text(
        f"project_id: {project_id}\nrepo: org/{project_id}\nnodes: []\n",
        encoding="utf-8",
    )
    return project


def _run_import(doc: dict, root: Path, **kwargs) -> tuple[int, dict]:
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = import_node.import_node(doc, "demo", root, **kwargs)
    finally:
        sys.stdout = old
    return rc, json.loads(buf.getvalue())


class PriorityEnumTests(unittest.TestCase):
    def test_normal_is_normalized_to_medium(self):
        doc = _valid_doc(priority="normal")
        findings = import_node.validate_node_yaml(doc)
        self.assertEqual(doc["priority"], "medium")
        self.assertFalse([f for f in findings if f["rule"] == "priority_enum"])

    def test_unknown_priority_lists_valid_values(self):
        findings = import_node.validate_node_yaml(_valid_doc(priority="urgent"))
        hits = [f for f in findings if f["rule"] == "priority_enum"]
        self.assertEqual(len(hits), 1)
        message = hits[0]["message"]
        for value in ("critical", "high", "low", "medium"):
            self.assertIn(value, message)
        self.assertIn("urgent", message)

    def test_import_writes_normalized_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _project(root)
            rc, result = _run_import(_valid_doc(priority="normal"), root)
            self.assertEqual(rc, 0)
            written = yaml.safe_load(
                (project / "nodes" / "import-fixture.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(written["priority"], "medium")
            self.assertEqual(result["status"], "imported")


class UpdatePathTests(unittest.TestCase):
    def test_reimport_without_update_still_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            first_rc, _ = _run_import(_valid_doc(title="first"), root)
            self.assertEqual(first_rc, 0)
            rc, result = _run_import(_valid_doc(title="second"), root)
            self.assertEqual(rc, 1)
            self.assertEqual(result["status"], "rejected")
            rules = {f["rule"] for f in result["errors"]}
            self.assertIn("node_exists", rules)
            self.assertIn("node_in_index", rules)

    def test_update_replaces_fields_and_preserves_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _project(root)
            first_rc, _ = _run_import(
                _valid_doc(title="first", status="ready", priority="high"),
                root,
            )
            self.assertEqual(first_rc, 0)
            rc, result = _run_import(
                _valid_doc(
                    title="corrected title",
                    status="pending",
                    priority="low",
                    why="corrected why",
                ),
                root,
                update=True,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(result["status"], "updated")
            written = yaml.safe_load(
                (project / "nodes" / "import-fixture.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(written["title"], "corrected title")
            self.assertEqual(written["why"], "corrected why")
            self.assertEqual(written["priority"], "low")
            self.assertEqual(written["status"], "ready")
            index = yaml.safe_load((project / "project.yaml").read_text(encoding="utf-8"))
            entry = next(n for n in index["nodes"] if n["id"] == "import-fixture")
            self.assertEqual(entry["title"], "corrected title")
            self.assertEqual(entry["status"], "ready")
            self.assertEqual(len(index["nodes"]), 1)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
