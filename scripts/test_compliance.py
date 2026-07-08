#!/usr/bin/env python3
"""Tests for the batch_fill.py bug fixes.

Exercises the fixed review_and_write/fill_node_fields functions with simulated
keypresses and verifies schema compliance via validate.run().

Run:  .venv/bin/python scripts/test_compliance.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import batch_fill
from acceptance_items import normalize_acceptance_items
from batch_fill import console
from validate import run as validate_run

PROJECT = "testproj"


class FakeInput:
    """Replaces terminal.getch/getline with scripted queues."""

    def __init__(self) -> None:
        self.ch: list[str] = []
        self.line: list[str] = []

    def set(self, ch=None, line=None) -> None:
        self.ch = list(ch or [])
        self.line = list(line or [])

    def getch(self) -> str:
        if not self.ch:
            raise AssertionError("getch queue exhausted")
        return self.ch.pop(0)

    def getline(self, prompt: str = "") -> str:
        if not self.line:
            raise AssertionError("getline queue exhausted")
        return self.line.pop(0)


KEYS = FakeInput()
batch_fill.getch = KEYS.getch
batch_fill.getline = lambda prompt="": KEYS.getline(prompt)


def tmp_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="batchfill-test-"))
    (root / "graphs" / PROJECT / "nodes").mkdir(parents=True)
    return root


def make_placeholder_node(node_id: str) -> dict:
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node_id,
        "title": "Test node",
        "type": "capability",
        "why": "REPLACE_ME",
        "depends_on": [],
        "acceptance_criteria": normalize_acceptance_items(["REPLACE_ME"]),
        "constraints": ["REPLACE_ME"],
        "allowed_execution_modes": ["jules"],
        "required_artifacts": ["decision.md", "result-summary.md"],
        "status": "pending",
        "priority": "medium",
        "unlocks": [],
    }


def make_valid_node(node_id: str) -> dict:
    node = make_placeholder_node(node_id)
    node["why"] = "This capability must exist for testing purposes."
    node["acceptance_criteria"] = normalize_acceptance_items(["The function returns a dict"])
    node["constraints"] = ["use only stdlib"]
    return node


def node_errors(root: Path) -> list:
    return [f for f in validate_run(root, PROJECT) if f.severity == "error"]


def test_refuses_empty_acceptance() -> None:
    """VAL-CLI-001: empty acceptance => no file written, error printed, returns False."""
    root = tmp_root()
    node = make_valid_node("empty-acc")
    node["acceptance_criteria"] = []
    KEYS.set(ch=["y"], line=[])
    with console.capture() as cap:
        result = batch_fill.review_and_write(node, root, PROJECT)
    out = cap.get()
    assert result is False, "expected review_and_write to return False on empty acceptance"
    written = root / "graphs" / PROJECT / "nodes" / "empty-acc.yaml"
    assert not written.exists(), "node file must NOT be written when acceptance is empty"
    assert "acceptance_criteria" in out.lower(), f"expected error message about acceptance, got: {out!r}"


def test_prints_validation_findings() -> None:
    """VAL-CLI-002: validation findings printed after a successful write."""
    root = tmp_root()
    node = make_valid_node("print-find")
    KEYS.set(ch=["y"], line=[])
    with console.capture() as cap:
        result = batch_fill.review_and_write(node, root, PROJECT)
    out = cap.get()
    assert result is True, "expected successful write"
    assert ("OK" in out) or ("ERROR" in out) or ("WARN" in out), (
        f"expected validation output (OK/ERROR/WARN) after write, got: {out!r}"
    )


def test_edit_handler_scopes_single_field() -> None:
    """VAL-CLI-003: 'e' handler edits only the named field, preserving the others."""
    root = tmp_root()
    node = make_valid_node("edit-one")
    node["why"] = "original why"
    node["acceptance_criteria"] = normalize_acceptance_items(["original acceptance criterion"])
    node["constraints"] = ["original constraint"]
    orig_acceptance = [dict(x) for x in node["acceptance_criteria"]]

    # 'e' -> edit "why"; manual multi-line entry "new why text" then blank;
    # then 'q' on the re-shown review to stop.
    KEYS.set(ch=["e", "q"], line=["why", "new why text", ""])
    batch_fill.review_and_write(node, root, PROJECT)

    assert node["why"] == "new why text", f"why should be updated, got {node['why']!r}"
    assert node["acceptance_criteria"] == orig_acceptance, "acceptance must be preserved, not reset"
    assert node["constraints"] == ["original constraint"], "constraints must be preserved, not reset"
    assert "REPLACE_ME" not in str(node["acceptance_criteria"]), "acceptance must not be reset to REPLACE_ME"
    assert "REPLACE_ME" not in str(node["constraints"]), "constraints must not be reset to REPLACE_ME"


def test_filled_node_passes_validation() -> None:
    """VAL-CLI-010: a node filled + written via batch_fill passes validate.py with 0 errors."""
    root = tmp_root()
    node = make_placeholder_node("filled-node")

    # fill_node_fields: why (multi-line), acceptance (add manual), constraints (add manual)
    KEYS.set(
        ch=["a", "m", "\r", "a", "m", "\r"],
        line=["Why this node exists", "", "The function returns a dict", "use only stdlib"],
    )
    filled = batch_fill.fill_node_fields(dict(node), root, PROJECT)
    assert filled["why"] == "Why this node exists"
    assert filled["acceptance_criteria"] and isinstance(filled["acceptance_criteria"][0], dict)
    assert "id" in filled["acceptance_criteria"][0] and "criterion" in filled["acceptance_criteria"][0]
    assert filled["constraints"] == ["use only stdlib"]

    KEYS.set(ch=["y"], line=[])
    result = batch_fill.review_and_write(filled, root, PROJECT)
    assert result is True
    path = root / "graphs" / PROJECT / "nodes" / "filled-node.yaml"
    assert path.exists(), "filled node should be written"

    errors = node_errors(root)
    assert errors == [], f"filled node must pass validate.py with 0 errors, got: {errors}"


def main() -> int:
    tests = [
        ("test_refuses_empty_acceptance", test_refuses_empty_acceptance),
        ("test_prints_validation_findings", test_prints_validation_findings),
        ("test_edit_handler_scopes_single_field", test_edit_handler_scopes_single_field),
        ("test_filled_node_passes_validation", test_filled_node_passes_validation),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    total = len(tests)
    print(f"\n{total - failed}/{total} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
