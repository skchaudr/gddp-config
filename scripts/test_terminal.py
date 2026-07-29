"""Focused tests for terminal key decoding."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import terminal


class TerminalDecodeTests(unittest.TestCase):
    def test_bare_escape_is_preserved(self):
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: None), "\x1b"
        )

    def test_arrow_escape_sequence_is_decoded(self):
        values = iter(["[", "C"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values)),
            "RIGHT",
        )

    def test_unknown_escape_sequence_falls_back_to_escape(self):
        values = iter(["[", "Z"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values)),
            "\x1b",
        )
