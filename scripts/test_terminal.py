"""Focused tests for terminal key decoding."""

from __future__ import annotations

import os
import pty
import select
import sys
import time
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

    def test_getch_decodes_arrow_split_across_pty_reads(self):
        """A terminal multiplexer may split ESC [ C across several reads."""
        pid, fd = pty.fork()
        if pid == 0:
            # pytest replaces sys.stdin with a non-tty capture object; getch
            # needs a real tty. After pty.fork() fd 0 IS the slave, so point
            # sys.stdin at it. Bypass sys.stdout for writes (pytest capture
            # does not reach the pty master).
            sys.stdin = open(0, encoding="utf-8", closefd=False)
            os.write(1, b"READY\n")
            os.write(1, f"KEY={terminal.getch()}\n".encode())
            os._exit(0)

        output = bytearray()
        try:
            deadline = time.monotonic() + 2
            while b"READY" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    output.extend(os.read(fd, 4096))

            self.assertIn(b"READY", output)
            os.write(fd, b"\x1b")
            time.sleep(0.08)
            os.write(fd, b"[C")

            deadline = time.monotonic() + 2
            while b"KEY=" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    try:
                        output.extend(os.read(fd, 4096))
                    except OSError:
                        break
            self.assertIn(b"KEY=RIGHT", output)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
