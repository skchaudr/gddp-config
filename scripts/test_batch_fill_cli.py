#!/usr/bin/env python3
"""End-to-end CLI test for batch_fill.py driven through a pseudo-terminal.

batch_fill.py reads keystrokes from /dev/tty (see terminal.getch/getline), so a
plain stdin pipe is ignored. This test allocates a pty, makes it the child's
controlling terminal via pty.fork, and feeds keystrokes to it — the faithful
"piped input" path for an interactive TUI.

Covers:
    VAL-CLI-001  empty acceptance => no file written, acceptance error printed
    VAL-CLI-002  validation findings printed after a successful write
    VAL-CLI-010  a node written by batch_fill passes validate.py, no REPLACE_ME

Run:  .venv/bin/python scripts/test_batch_fill_cli.py
"""

from __future__ import annotations

import fcntl
import json
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = str(REPO / ".venv" / "bin" / "python")
BATCH = str(REPO / "scripts" / "batch_fill.py")
VALIDATE = str(REPO / "scripts" / "validate.py")

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b[()][AB012]|\x1b[=>]")

TOKEN_DELAY = 0.45
LAUNCH_DELAY = 0.7


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text).replace("\x1b", "")


def make_placeholder_yaml(node_id: str, *, empty_acceptance: bool) -> str:
    acceptance = "acceptance: []" if empty_acceptance else (
        "acceptance:\n  - id: replace-me\n    criterion: REPLACE_ME"
    )
    return (
        'schema_version: "1.0"\n'
        "schema_type: node\n"
        f"node_id: {node_id}\n"
        "title: Test Batch Node\n"
        "type: capability\n"
        "why: REPLACE_ME\n"
        "depends_on: []\n"
        f"{acceptance}\n"
        "constraints:\n  - REPLACE_ME\n"
        "allowed_execution_modes:\n  - jules\n"
        "required_artifacts:\n  - decision.md\n  - result-summary.md\n"
        "status: pending\n"
        "priority: medium\n"
        "unlocks: []\n"
    )


def make_project(project: str, node_id: str, *, empty_acceptance: bool) -> Path:
    nodes_dir = REPO / "graphs" / project / "nodes"
    if nodes_dir.parent.exists():
        shutil.rmtree(nodes_dir.parent)
    nodes_dir.mkdir(parents=True)
    (nodes_dir / f"{node_id}.yaml").write_text(
        make_placeholder_yaml(node_id, empty_acceptance=empty_acceptance),
        encoding="utf-8",
    )
    return REPO / "graphs" / project


def drive(project: str, tokens: list[str], timeout: float = 40.0) -> str:
    """Run batch_fill.py under a pty, feed tokens, return ANSI-stripped output."""
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.environ["COLUMNS"] = "200"
        os.environ["LINES"] = "60"
        os.environ["TERM"] = "dumb"
        os.execv(PY, [PY, BATCH, "--project", project])
        os._exit(127)  # unreachable

    # parent
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 60, 200, 0, 0))
    output = bytearray()

    def drain(budget: float) -> None:
        end = time.time() + budget
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], max(0.0, end - time.time()))
            if not r:
                return
            try:
                data = os.read(fd, 65536)
            except OSError:
                return
            if not data:
                return
            output.extend(data)

    time.sleep(LAUNCH_DELAY)
    drain(0.3)
    for tok in tokens:
        try:
            os.write(fd, tok.encode())
        except OSError:
            break
        drain(TOKEN_DELAY)

    start = time.time()
    while time.time() - start < timeout:
        try:
            r, _, _ = select.select([fd], [], [], 0.3)
        except OSError:
            break
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            output.extend(data)
            continue
        wpid, _ = os.waitpid(pid, os.WNOHANG)
        if wpid != 0:
            break

    try:
        os.waitpid(pid, 0)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
    return strip_ansi(output.decode(errors="replace"))


def validate_project(project: str) -> tuple[int, int]:
    """Return (exit_code, error_count) for `validate.py --project <p> --json`."""
    proc = subprocess.run(
        [PY, VALIDATE, "--project", project, "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    try:
        errors = json.loads(proc.stdout)["summary"]["errors"]
    except (ValueError, KeyError):
        errors = -1
    return proc.returncode, errors


# Keystroke sequences -------------------------------------------------------

# Fill why (multi-line), acceptance (add one manual), constraints (add one manual):
FILL_TOKENS = [
    "\n",                              # node card: proceed
    "Why this node must exist.\n",     # why: line 1 (getline)
    "\n",                              # why: blank line ends multi-line entry
    "a", "m", "The output is verifiable.\n", "\n",   # acceptance: add manual, done
    "a", "m", "Use only the standard library.\n", "\n",  # constraints: add manual, done
    "y",                               # review: write
]

# Skip acceptance entirely (Enter on empty list editor), then try to write:
SKIP_ACCEPTANCE_TOKENS = [
    "\n",                              # node card: proceed
    "Why this node must exist.\n",     # why: line 1
    "\n",                              # why: end
    "\n",                              # acceptance: Enter on empty list -> []
    "a", "m", "Use only the standard library.\n", "\n",  # constraints: add manual
    "y",                               # review: attempt write (should be refused)
]


def test_filled_node_passes_validation() -> None:
    """VAL-CLI-002 + VAL-CLI-010 via the real CLI."""
    project = "zztest-batchfill-happy"
    node_id = "happy-node"
    make_project(project, node_id, empty_acceptance=False)
    try:
        out = drive(project, FILL_TOKENS)
        node_path = REPO / "graphs" / project / "nodes" / f"{node_id}.yaml"

        assert node_path.exists(), f"node was not written. CLI output:\n{out}"
        content = node_path.read_text()
        assert "REPLACE_ME" not in content, "written node still contains REPLACE_ME"

        assert "WROTE" in out, f"expected WROTE line in output:\n{out}"
        assert ("OK" in out) or ("WARN" in out) or ("ERROR" in out), (
            f"expected validation findings after write:\n{out}"
        )

        code, errors = validate_project(project)
        assert code == 0, f"validate.py --project {project} exited {code}"
        assert errors == 0, f"expected 0 errors, got {errors}"
    finally:
        shutil.rmtree(REPO / "graphs" / project, ignore_errors=True)


def test_refuses_empty_acceptance() -> None:
    """VAL-CLI-001 via the real CLI."""
    project = "zztest-batchfill-empty"
    node_id = "empty-node"
    make_project(project, node_id, empty_acceptance=True)
    try:
        out = drive(project, SKIP_ACCEPTANCE_TOKENS)
        node_path = REPO / "graphs" / project / "nodes" / f"{node_id}.yaml"

        # The placeholder pre-exists on disk; the refusal means write_text was
        # never called, so the file must remain the untouched placeholder.
        content = node_path.read_text()
        assert "REPLACE_ME" in content, (
            f"placeholder was overwritten despite empty acceptance:\n{content}"
        )
        assert "Why this node must exist." not in content, (
            f"node was written with filled content despite empty acceptance:\n{content}"
        )
        assert "acceptance" in out.lower() and "refusing to write" in out.lower(), (
            f"expected an acceptance-related refusal message:\n{out}"
        )
    finally:
        shutil.rmtree(REPO / "graphs" / project, ignore_errors=True)


def main() -> int:
    tests = [
        ("test_filled_node_passes_validation", test_filled_node_passes_validation),
        ("test_refuses_empty_acceptance", test_refuses_empty_acceptance),
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
