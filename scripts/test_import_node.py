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
            project = root / "graphs" / "demo"
            (project / "nodes").mkdir(parents=True)
            (project / "project.yaml").write_text(
                "project_id: demo\nrepo: org/demo\nnodes: []\n",
                encoding="utf-8",
            )
            buf = StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                rc = import_node.import_node(
                    _valid_doc(priority="normal"), "demo", root, dry_run=False
                )
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            written = yaml.safe_load(
                (project / "nodes" / "import-fixture.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(written["priority"], "medium")
            result = json.loads(buf.getvalue())
            self.assertEqual(result["status"], "imported")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
