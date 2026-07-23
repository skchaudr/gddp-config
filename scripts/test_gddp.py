"""Focused tests for the config-owned gddp command boundary."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gddp


class RuntimeJobsForwardingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self.tempdir.name) / "gddp-runtime"
        scripts = self.runtime_root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "node_status.py").write_text("print('fake runtime')\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_run_runtime_jobs_uses_runtime_boundary_and_environment(self):
        completed = SimpleNamespace(returncode=7)
        with patch.dict(os.environ, {
            "GDDP_RUNTIME_ROOT": str(self.runtime_root),
            "GDDP_RUNTIME_PYTHON": sys.executable,
        }, clear=False), patch.object(gddp.subprocess, "run", return_value=completed) as run:
            rc = gddp.run_runtime_jobs(["list", "--state", "ready"])

        self.assertEqual(rc, 7)
        command = run.call_args.args[0]
        self.assertEqual(command, [
            sys.executable,
            str(self.runtime_root.resolve() / "scripts" / "node_status.py"),
            "list",
            "--state",
            "ready",
        ])
        self.assertEqual(
            run.call_args.kwargs["env"]["GDDP_RUNTIME_ROOT"],
            str(self.runtime_root.resolve()),
        )
        self.assertFalse(run.call_args.kwargs["check"])

    def test_jobs_set_preserves_reason_as_one_argument(self):
        args = argparse.Namespace(
            jobs_command="set",
            ref="job-1",
            state="awaiting_review",
            reason="human review requested",
            yes=True,
        )
        with patch.object(gddp, "run_runtime_jobs", return_value=0) as run:
            rc = gddp.cmd_jobs(args)
        self.assertEqual(rc, 0)
        run.assert_called_once_with([
            "set",
            "job-1",
            "awaiting_review",
            "--reason",
            "human review requested",
            "--yes",
        ])

    def test_main_parses_jobs_show_as_real_subcommand(self):
        with patch.object(gddp, "run_runtime_jobs", return_value=0) as run:
            rc = gddp.main(["jobs", "show", "node-1", "--full"])
        self.assertEqual(rc, 0)
        run.assert_called_once_with(["show", "node-1", "--full"])

    def test_missing_runtime_reports_configuration_error(self):
        missing = Path(self.tempdir.name) / "missing"
        with patch.dict(os.environ, {"GDDP_RUNTIME_ROOT": str(missing)}, clear=False):
            self.assertEqual(gddp.run_runtime_jobs(["list"]), 2)


class OverviewTests(unittest.TestCase):
    def test_menu_choice_uses_one_keypress_without_enter(self):
        terminal = SimpleNamespace(getch=lambda: "j")
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "j")

    def test_menu_choice_keeps_enter_as_the_default_shortcut(self):
        terminal = SimpleNamespace(getch=lambda: "\r")
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "n")

    def test_redirected_bare_command_uses_static_overview(self):
        fake_in = SimpleNamespace(isatty=lambda: False)
        fake_out = SimpleNamespace(isatty=lambda: False)
        with patch.object(gddp.sys, "stdin", fake_in), \
                patch.object(gddp.sys, "stdout", fake_out), \
                patch.object(gddp, "static_overview") as overview:
            rc = gddp.cmd_overview(None)
        self.assertEqual(rc, 0)
        overview.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
