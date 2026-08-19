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
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "RIGHT",
        )

    def test_unknown_escape_sequence_is_ignored(self):
        values = iter(["[", "Z"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "",
        )

    def test_modified_arrow_csi_is_decoded(self):
        values = iter(["[", "1", ";", "3", "A"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "UP",
        )

    def test_focus_event_is_not_escape(self):
        values = iter(["[", "I"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "",
        )

    def test_incomplete_csi_is_not_escape(self):
        values = iter(["["])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "",
        )

    def test_ss3_arrow_is_decoded(self):
        values = iter(["O", "B"])
        self.assertEqual(
            terminal._decode_escape_sequence("\x1b", lambda: next(values, None)),
            "DOWN",
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
            # Give the child time to enter cbreak: bytes written while the
            # line discipline is still canonical echo into the pending line
            # and get stranded when ICANON flips off (BSD/macOS behavior).
            time.sleep(0.2)
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

    def test_getch_decodes_modified_arrow_csi(self):
        """Ghostty/tmux send ESC[1;3A for alt-up; that must be UP, not Escape."""
        pid, fd = pty.fork()
        if pid == 0:
            sys.stdin = open(0, encoding="utf-8", closefd=False)
            os.write(1, b"READY\n")
            os.write(1, f"KEY={terminal.getch()!r}\n".encode())
            os._exit(0)

        output = bytearray()
        try:
            deadline = time.monotonic() + 2
            while b"READY" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    output.extend(os.read(fd, 4096))

            self.assertIn(b"READY", output)
            # Give the child time to enter cbreak: bytes written while the
            # line discipline is still canonical echo into the pending line
            # and get stranded when ICANON flips off (BSD/macOS behavior).
            time.sleep(0.2)
            os.write(fd, b"\x1b[1;3A")

            deadline = time.monotonic() + 2
            while b"KEY=" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    try:
                        output.extend(os.read(fd, 4096))
                    except OSError:
                        break
            self.assertIn(b"KEY='UP'", output)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass


class CbreakTypeaheadTests(unittest.TestCase):
    """Held cbreak keeps typeahead queued during redraws from being stranded."""

    def test_typeahead_sent_while_busy_survives(self):
        pid, fd = pty.fork()
        if pid == 0:
            sys.stdin = open(0, encoding="utf-8", closefd=False)
            with terminal.cbreak() as key_fd:
                os.write(1, b"READY\n")
                time.sleep(0.6)  # parent types ahead during this window
                first = terminal.read_key(key_fd)
                second = terminal.read_key(key_fd)
            os.write(1, f"PAIR={first!r},{second!r}\n".encode())
            os._exit(0)

        output = bytearray()
        try:
            deadline = time.monotonic() + 2
            while b"READY" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    output.extend(os.read(fd, 4096))
            self.assertIn(b"READY", output)
            os.write(fd, b"aj")  # typed while the "pager" is busy redrawing
            deadline = time.monotonic() + 2
            while b"PAIR=" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    try:
                        output.extend(os.read(fd, 4096))
                    except OSError:
                        break
            self.assertIn(b"PAIR='a','j'", output)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass

    def test_read_key_decodes_page_down(self):
        pid, fd = pty.fork()
        if pid == 0:
            sys.stdin = open(0, encoding="utf-8", closefd=False)
            with terminal.cbreak() as key_fd:
                os.write(1, b"READY\n")
                key = terminal.read_key(key_fd)
            os.write(1, f"KEY={key!r}\n".encode())
            os._exit(0)

        output = bytearray()
        try:
            deadline = time.monotonic() + 2
            while b"READY" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    output.extend(os.read(fd, 4096))
            self.assertIn(b"READY", output)
            os.write(fd, b"\x1b[6~")
            deadline = time.monotonic() + 2
            while b"KEY=" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if readable:
                    try:
                        output.extend(os.read(fd, 4096))
                    except OSError:
                        break
            self.assertIn(b"KEY='PAGE_DOWN'", output)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass


if __name__ == "__main__":
    unittest.main()
