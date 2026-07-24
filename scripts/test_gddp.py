"""Focused tests for the config-owned gddp command boundary."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console

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

    def test_paged_menu_selects_numbered_item_with_one_keypress(self):
        terminal = SimpleNamespace(getch=lambda: "2")
        with patch.object(gddp, "_import_module", return_value=terminal):
            selected = gddp._paged_menu(
                "projects",
                [("first", "1 node"), ("second", "2 nodes")],
            )
        self.assertEqual(selected, "second")

    def test_paged_menu_labels_pages_and_cycles_both_directions(self):
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 12)]
        keys = iter(["p", "n", "n", "1"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        output = StringIO()
        test_console = Console(file=output, width=120, color_system=None)

        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            selected = gddp._paged_menu(
                "nodes · demo",
                items,
                back_label="projects",
            )

        self.assertEqual(selected, "node-10")
        rendered = output.getvalue()
        self.assertIn("nodes · demo · page 1 of 2", rendered)
        self.assertIn("nodes · demo · page 2 of 2", rendered)
        self.assertIn("previous page", rendered)
        self.assertIn("next page", rendered)
        self.assertRegex(rendered, r"b\s+projects")

    def test_paged_menu_redraws_each_page(self):
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 12)]
        keys = iter(["n", "1"])
        terminal = SimpleNamespace(getch=lambda: next(keys))

        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "_clear_screen") as clear:
            selected = gddp._paged_menu("nodes", items)

        self.assertEqual(selected, "node-10")
        self.assertEqual(clear.call_count, 2)

    def test_interactive_jobs_starts_with_real_list_command(self):
        terminal = SimpleNamespace(getch=lambda: "b")
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "run_runtime_jobs", return_value=0) as run, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_jobs()

        self.assertIs(outcome, gddp._MENU_BACK)
        run.assert_called_once_with(["list"])

    def test_interactive_jobs_can_filter_review_queue(self):
        keys = iter(["a", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "run_runtime_jobs", return_value=0) as run, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_jobs()

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertEqual(
            run.call_args_list,
            [
                unittest.mock.call(["list"]),
                unittest.mock.call(["list", "--state", "awaiting_review"]),
            ],
        )

    def test_main_menu_opens_jobs_submenu(self):
        with patch.object(gddp, "_menu_choice", side_effect=["j", "q"]), \
                patch.object(
                    gddp, "interactive_jobs", return_value=gddp._MENU_BACK
                ) as jobs, \
                patch.object(gddp, "_clear_screen"):
            gddp.interactive_menu()

        jobs.assert_called_once_with()

    def test_node_status_label_exposes_node_index_desync(self):
        self.assertEqual(
            gddp._node_status_label(
                {"status": "pending"},
                {"status": "complete"},
            ),
            "DESYNC node=pending index=complete",
        )

    def test_node_workflow_reviews_and_updates_entirely_in_menu(self):
        keys = iter(["1", "1", "u", "c", "y", "x", "b", "b", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        node_cli = SimpleNamespace(
            list_project_ids=lambda root: ["demo"],
            iter_nodes=lambda root, project: [
                (
                    "alpha",
                    {"title": "Alpha node", "status": "pending"},
                    {"status": "pending"},
                )
            ],
            cmd_show=lambda **kwargs: 0,
            cmd_set_status=lambda **kwargs: 0,
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp.Prompt, "ask", return_value="accepted after review"), \
                patch.object(node_cli, "cmd_show", wraps=node_cli.cmd_show) as show, \
                patch.object(
                    node_cli, "cmd_set_status", wraps=node_cli.cmd_set_status
                ) as set_status:
            outcome = gddp.interactive_nodes()

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertEqual(show.call_count, 2)
        show.assert_called_with(project="demo", node_id="alpha", trace=False)
        set_status.assert_called_once_with(
            project="demo",
            node_id="alpha",
            status="complete",
            yes=True,
            reason="accepted after review",
        )

    def test_declined_status_change_never_calls_writer(self):
        terminal = SimpleNamespace(getch=lambda: "n")
        node_cli = SimpleNamespace(cmd_set_status=lambda **kwargs: 0)

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(node_cli, "cmd_set_status") as set_status:
            rc = gddp._confirm_status_change("demo", "alpha", "ready")

        self.assertEqual(rc, 1)
        set_status.assert_not_called()

    def test_empty_interactive_reason_never_calls_writer(self):
        terminal = SimpleNamespace(getch=lambda: "y")
        node_cli = SimpleNamespace(cmd_set_status=lambda **kwargs: 0)

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp.Prompt, "ask", return_value="  "), \
                patch.object(node_cli, "cmd_set_status") as set_status:
            rc = gddp._confirm_status_change("demo", "alpha", "deferred")

        self.assertEqual(rc, 1)
        set_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
