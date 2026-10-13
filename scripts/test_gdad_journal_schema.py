"""Validate GDAD demo journal lines against journal.schema.json."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class GdadJournalSchemaTests(unittest.TestCase):
    def test_demo_dispatch_line_matches_schema(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas" / "gdad" / "journal.schema.json").read_text(encoding="utf-8"))
        allowed = set(schema["properties"])
        required = set(schema["required"])
        line = {
            "v": 1,
            "ts": "2026-10-13T12:00:00Z",
            "type": "dispatch",
            "who": "gdad-executor",
            "state": "running",
            "run_id": "line-pair-1",
            "artifacts": [],
            "request_id": "line-pair-1",
            "wid": "wid-demo",
        }
        self.assertTrue(required <= set(line))
        self.assertTrue(set(line) <= allowed)


if __name__ == "__main__":
    unittest.main()
