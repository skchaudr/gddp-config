"""Focused tests for the config-owned gddp command boundary."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        (scripts / "jobs_status.py").write_text("print('fake runtime')\n")

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
            str(self.runtime_root.resolve() / "scripts" / "jobs_status.py"),
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
        args = unittest.mock.Mock(
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

    def test_jobs_set_remains_a_shell_subcommand(self):
        with patch.object(gddp, "run_runtime_jobs", return_value=0) as run:
            rc = gddp.main([
                "jobs",
                "set",
                "job-1",
                "failed",
                "--reason",
                "executor failed",
                "--yes",
            ])
        self.assertEqual(rc, 0)
        run.assert_called_once_with([
            "set",
            "job-1",
            "failed",
            "--reason",
            "executor failed",
            "--yes",
        ])

    def test_jobs_retry_forwards_reason_to_runtime_boundary(self):
        with patch.object(gddp, "run_runtime_jobs", return_value=0) as run:
            rc = gddp.main([
                "jobs",
                "retry",
                "job-1",
                "--reason",
                "new clean user is ready",
                "--yes",
            ])
        self.assertEqual(rc, 0)
        run.assert_called_once_with([
            "retry",
            "job-1",
            "--reason",
            "new clean user is ready",
            "--yes",
        ])

    def test_node_set_status_is_not_a_shell_subcommand(self):
        with patch.object(gddp.sys, "stderr", StringIO()), \
                self.assertRaises(SystemExit) as exit_context:
            gddp.main(["node", "set-status", "node-1", "complete"])
        self.assertEqual(exit_context.exception.code, 2)

    def test_missing_runtime_reports_configuration_error(self):
        missing = Path(self.tempdir.name) / "missing"
        with patch.dict(os.environ, {"GDDP_RUNTIME_ROOT": str(missing)}, clear=False):
            self.assertEqual(gddp.run_runtime_jobs(["list"]), 2)


class OverviewTests(unittest.TestCase):
    def test_node_browse_can_open_one_project_directly(self):
        with patch.object(
            gddp, "interactive_nodes", return_value=gddp._MENU_BACK
        ) as browse:
            rc = gddp.main([
                "node", "browse", "--project", "gddp-runtime",
            ])

        self.assertEqual(rc, 0)
        browse.assert_called_once_with("gddp-runtime")

    def _menu_terminal(self, getch):
        return SimpleNamespace(getch=getch, clear_lines=lambda n: None)

    def test_menu_choice_uses_one_keypress_without_enter(self):
        terminal = self._menu_terminal(lambda: "j")
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "j")

    def test_menu_choice_keeps_enter_as_the_default_shortcut(self):
        terminal = self._menu_terminal(lambda: "\r")
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "n")

    def test_menu_choice_maps_escape_to_back(self):
        terminal = self._menu_terminal(lambda: "\x1b")
        actions = {
            "b": ("back", ""),
            "q": ("quit", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="b"), "b")

    def test_menu_choice_keeps_ctrl_c_as_quit_signal(self):
        terminal = self._menu_terminal(lambda: "\x03")
        actions = {"b": ("back", ""), "q": ("quit", "")}
        with patch.object(gddp, "_import_module", return_value=terminal):
            with self.assertRaises(KeyboardInterrupt):
                gddp._menu_choice(actions, default="b")

    def test_menu_choice_accepts_named_arrow_keys(self):
        terminal = self._menu_terminal(lambda: "RIGHT")
        actions = {
            "LEFT": ("prev", ""),
            "RIGHT": ("next", ""),
            "b": ("back", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="b"), "RIGHT")

    def test_menu_choice_ignores_incomplete_escape(self):
        """Failed CSI decode must not act as Escape/back or spam an error."""
        keys = iter(["", "j"])
        terminal = self._menu_terminal(lambda: next(keys))
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
            "b": ("back", ""),
        }
        output = StringIO()
        test_console = Console(file=output, width=80, color_system=None)
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "j")
        self.assertNotIn("is not an option", output.getvalue())

    def test_menu_choice_ignores_unregistered_horizontal_arrows(self):
        keys = iter(["LEFT", "b"])
        terminal = self._menu_terminal(lambda: next(keys))
        actions = {"b": ("back", ""), "q": ("quit", "")}
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="b"), "b")

    def test_menu_choice_arrows_move_cursor_then_enter(self):
        keys = iter(["DOWN", "\r"])
        terminal = self._menu_terminal(lambda: next(keys))
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
            "q": ("quit", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "j")

    def test_menu_choice_number_picks_by_position(self):
        terminal = self._menu_terminal(lambda: "2")
        actions = {
            "n": ("nodes", ""),
            "j": ("jobs", ""),
            "q": ("quit", ""),
        }
        with patch.object(gddp, "_import_module", return_value=terminal):
            self.assertEqual(gddp._menu_choice(actions, default="n"), "j")

    def test_menu_choice_enter_uses_default_when_not_first(self):
        """Confirm menus put the safe default mid-list; Enter lands there."""
        terminal = self._menu_terminal(lambda: "\r")
        actions = {
            "y": ("yes", ""),
            "n": ("no", ""),
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

    def _paged_terminal(self, getch):
        return SimpleNamespace(getch=getch, clear_lines=lambda n: None)

    def test_paged_menu_selects_numbered_item_with_one_keypress(self):
        terminal = self._paged_terminal(lambda: "2")
        with patch.object(gddp, "_import_module", return_value=terminal):
            selected = gddp._paged_menu(
                "projects",
                [("first", "1 node"), ("second", "2 nodes")],
            )
        self.assertEqual(selected, "second")

    def test_paged_menu_refresh_has_chrome_and_returns_reload_signal(self):
        terminal = self._paged_terminal(lambda: "r")
        output = StringIO()
        test_console = Console(file=output, width=100, color_system=None)
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            selected = gddp._paged_menu(
                "projects",
                [("demo", "1 node")],
                refreshable=True,
            )
        self.assertIs(selected, gddp._MENU_REFRESH)
        self.assertIn("r refresh", output.getvalue())

    def test_paged_menu_labels_pages_and_cycles_both_directions(self):
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 12)]
        keys = iter(["p", "n", "n", "1"])
        terminal = self._paged_terminal(lambda: next(keys))
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
        self.assertIn("nodes · demo  ·  1/2", rendered)
        self.assertIn("nodes · demo  ·  2/2", rendered)
        self.assertIn("←/→ page", rendered)
        self.assertIn("b projects", rendered)

    def test_paged_menu_full_clear_only_on_first_paint(self):
        """Arrow/page moves redraw in place — no full clear per keypress."""
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 12)]
        keys = iter(["n", "DOWN", "\r"])
        clear_lines_calls = []
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: clear_lines_calls.append(n),
        )

        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "_clear_screen") as clear:
            selected = gddp._paged_menu("nodes", items)

        self.assertEqual(selected, "node-11")
        self.assertEqual(clear.call_count, 1)
        self.assertEqual(len(clear_lines_calls), 2)

    def test_paged_menu_left_right_change_pages(self):
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 12)]
        keys = iter(["RIGHT", "LEFT", "RIGHT", "1"])
        terminal = self._paged_terminal(lambda: next(keys))
        with patch.object(gddp, "_import_module", return_value=terminal):
            selected = gddp._paged_menu("nodes", items)

        self.assertEqual(selected, "node-10")

    def test_paged_menu_up_down_moves_highlighted_item(self):
        items = [(f"node-{i}", f"Node {i}") for i in range(1, 4)]
        keys = iter(["DOWN", "DOWN", "UP", "\r"])
        terminal = self._paged_terminal(lambda: next(keys))
        with patch.object(gddp, "_import_module", return_value=terminal):
            selected = gddp._paged_menu("nodes", items)

        self.assertEqual(selected, "node-2")

    def test_paged_menu_space_toggles_native_multi(self):
        items = [("n1", "a"), ("n2", "b"), ("n3", "c")]
        keys = iter([" ", "DOWN", " ", "\r"])
        terminal = self._paged_terminal(lambda: next(keys))
        output = StringIO()
        test_console = Console(file=output, width=80, color_system=None)
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            selected = gddp._paged_menu("nodes", items, fzf_multi=True)
        self.assertEqual(selected, ["n1", "n2"])
        rendered = output.getvalue()
        self.assertIn("2 selected", rendered)
        self.assertIn("✓", rendered)
        self.assertIn("space", rendered)

    def test_paged_menu_m_toggles_without_opening_fzf(self):
        items = [("n1", "a"), ("n2", "b")]
        keys = iter(["m", "DOWN", "m", "\r"])
        terminal = self._paged_terminal(lambda: next(keys))
        fzf = SimpleNamespace(
            available=lambda: True,
            pick=lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("fzf multi must stay closed")
            ),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module):
            selected = gddp._paged_menu("nodes", items, fzf_multi=True)
        self.assertEqual(selected, ["n1", "n2"])

    def test_paged_menu_enter_with_no_checks_opens_current(self):
        items = [("n1", "a"), ("n2", "b")]
        keys = iter(["DOWN", "\r"])
        terminal = self._paged_terminal(lambda: next(keys))
        with patch.object(gddp, "_import_module", return_value=terminal):
            selected = gddp._paged_menu("nodes", items, fzf_multi=True)
        self.assertEqual(selected, "n2")

    def test_paged_menu_f_passes_multi_and_returns_fzf_set(self):
        items = [("n1", "a"), ("n2", "b"), ("n3", "c")]
        keys = iter(["f"])
        terminal = self._paged_terminal(lambda: next(keys))
        fzf = SimpleNamespace(
            available=lambda: True,
            pick=Mock(return_value=["n3", "n1"]),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module):
            selected = gddp._paged_menu("nodes", items, fzf_multi=True)

        self.assertEqual(selected, ["n1", "n3"])
        self.assertTrue(fzf.pick.call_args.kwargs["multi"])

    def test_paged_menu_f_stays_single_when_not_multi(self):
        items = [("n1", "a"), ("n2", "b")]
        keys = iter(["f"])
        terminal = self._paged_terminal(lambda: next(keys))
        fzf = SimpleNamespace(
            available=lambda: True,
            pick=Mock(return_value=["n1", "n2"]),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module):
            selected = gddp._paged_menu("nodes", items, fzf_multi=False)

        self.assertEqual(selected, "n1")
        self.assertFalse(fzf.pick.call_args.kwargs["multi"])

    def test_interactive_jobs_starts_with_real_list_command(self):
        terminal = SimpleNamespace(getch=lambda: "b")
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(
                    gddp,
                    "_runtime_job_items",
                    return_value=[("job-1", "ready  node-a  2026-01-01")],
                ) as listed, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_jobs()

        self.assertIs(outcome, gddp._MENU_BACK)
        listed.assert_called_with(None, project=None)

    def test_interactive_jobs_can_filter_review_queue(self):
        keys = iter(["a", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        fzf = SimpleNamespace(available=lambda: False, pick=lambda *a, **k: None)

        def import_module(name):
            return terminal if name == "terminal" else fzf

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(
                    gddp,
                    "_runtime_job_items",
                    return_value=[],
                ) as listed, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_jobs()

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertEqual(
            listed.call_args_list,
            [
                unittest.mock.call(None, project=None),
                unittest.mock.call("awaiting_review", project=None),
            ],
        )

    def test_job_workflow_updates_only_through_menu(self):
        # u → paged pick job-1 → state 1 → y → reason → b
        keys = iter(["u", "1", "1", "y", "x", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        fzf = SimpleNamespace(available=lambda: False, pick=lambda *a, **k: None)
        row = {"job_id": "job-1", "node_id": "node-a", "queue_state": "ready", "created_at": "2026-01-01"}

        class _Cur:
            def fetchall(self):
                return [row]

        class _Con:
            def execute(self, *a, **k):
                return _Cur()

            def close(self):
                return None

        operator = SimpleNamespace(
            QUEUE_STATES=("ready",),
            connect=lambda: _Con(),
            apply_state_change=unittest.mock.Mock(return_value=0),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return terminal

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "run_runtime_jobs", return_value=0) as run, \
                patch.object(gddp, "load_runtime_jobs_module", return_value=operator), \
                patch.object(
                    gddp.Prompt,
                    "ask",
                    return_value="operator reviewed recovery",
                ), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_jobs()

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertIn(unittest.mock.call(["show", "job-1"]), run.call_args_list)
        operator.apply_state_change.assert_called_once_with(
            ref="job-1",
            state="ready",
            reason="operator reviewed recovery",
        )

    def test_main_menu_opens_graphs_submenu(self):
        with patch.object(gddp, "_menu_choice", side_effect=["g", "q"]), \
                patch.object(
                    gddp, "interactive_graphs", return_value=gddp._MENU_BACK
                ) as graphs, \
                patch.object(gddp, "_clear_screen"):
            gddp.interactive_menu()

        graphs.assert_called_once_with()

    def test_main_menu_opens_dispatch(self):
        with patch.object(gddp, "_menu_choice", side_effect=["d", "q"]), \
                patch.object(
                    gddp, "interactive_dispatch", return_value=gddp._MENU_BACK
                ) as dispatch, \
                patch.object(gddp, "_clear_screen"):
            gddp.interactive_menu()

        dispatch.assert_called_once_with()

    def test_main_menu_opens_live_watch(self):
        with patch.object(gddp, "_menu_choice", side_effect=["w", "q"]), \
                patch.object(
                    gddp, "interactive_watch", return_value=gddp._MENU_BACK
                ) as live, \
                patch.object(gddp, "_clear_screen"):
            gddp.interactive_menu()
        live.assert_called_once_with()

    def test_jobs_live_routes_to_watch(self):
        with patch.object(gddp, "cmd_watch", return_value=0) as watch:
            rc = gddp.main(["jobs", "live", "--once"])
        self.assertEqual(rc, 0)
        watch.assert_called_once()
        ns = watch.call_args[0][0]
        self.assertTrue(ns.once)
        self.assertIsNone(ns.target)

    def test_filter_attempts_running_only(self):
        attempts = [
            {"state": "running", "job_id": "j1", "node_id": "a", "project_id": "p"},
            {"state": "done", "job_id": "j2", "node_id": "b", "project_id": "p"},
            {"state": "dead", "job_id": "j3", "node_id": "c", "project_id": "q"},
        ]
        live = gddp._filter_attempts(attempts, running_only=True)
        self.assertEqual([a["job_id"] for a in live], ["j1"])
        all_a = gddp._filter_attempts(attempts, running_only=False)
        self.assertEqual(len(all_a), 3)

    def test_runs_list_uses_catalog(self):
        with patch.object(gddp, "resolve_runtime_root", return_value=Path("/tmp")), \
                patch.object(
                    gddp,
                    "_spool_root",
                    return_value=Path("/tmp/spool"),
                ), \
                patch.object(Path, "is_dir", return_value=True), \
                patch.object(
                    gddp,
                    "_scan_attempts",
                    return_value=[{
                        "dir": Path("/tmp/spool/a"),
                        "name": "a",
                        "job_id": "job-1",
                        "node_id": "node-x",
                        "project_id": "p",
                        "state": "running",
                        "worktree": None,
                        "last_write": 100.0,
                        "created": 90.0,
                        "events_path": "/tmp/spool/a/events.jsonl",
                        "pid": 1,
                    }],
                ), \
                patch.object(gddp, "_diff_summary", return_value=("0f +0/-0", 0)), \
                patch("sys.stdout", new_callable=StringIO) as out:
            rc = gddp.cmd_runs(argparse.Namespace(
                all=False, project=None, list=True, preview=None,
                action="watch", once=False, interval=2.0, height="90%",
            ))
        self.assertEqual(rc, 0)
        self.assertIn("node-x", out.getvalue())
        self.assertIn("job-1", out.getvalue())

    def test_main_menu_exits_on_ctrl_c(self):
        with patch.object(gddp, "_menu_choice", side_effect=KeyboardInterrupt), \
                patch.object(gddp, "_clear_screen"):
            gddp.interactive_menu()

    def test_partition_graphs_by_activity_archives_idle(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        job_times = {
            "hot": now - timedelta(days=1),
            "cold": now - timedelta(days=10),
        }
        with patch.object(gddp, "_graph_file_activity", return_value=now - timedelta(days=30)):
            active, archive = gddp.partition_graphs_by_activity(
                ["hot", "cold", "files-only"],
                now=now,
                job_times=job_times,
            )
        self.assertEqual([p for p, _ in active], ["hot"])
        self.assertEqual([p for p, _ in archive], ["cold", "files-only"])
        # newest first within archive
        self.assertEqual(archive[0][0], "cold")

    def test_graph_picker_refresh_requeries_activity(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        snapshots = [
            ([('old', now)], []),
            ([('new', now)], []),
        ]
        with patch.object(
            gddp, "partition_graphs_by_activity", side_effect=snapshots
        ) as partitioned, patch.object(
            gddp,
            "_graph_pick_items",
            side_effect=lambda rows, now=None: [(pid, "") for pid, _ in rows],
        ), patch.object(
            gddp,
            "_pick_list",
            side_effect=[gddp._MENU_REFRESH, "new"],
        ) as picked:
            result = gddp._pick_graph("graphs")

        self.assertEqual(result, "new")
        self.assertEqual(partitioned.call_count, 2)
        self.assertTrue(picked.call_args_list[0].kwargs["refreshable"])

    def test_interactive_graph_hub_routes_nodes(self):
        with patch.object(gddp, "_menu_choice", side_effect=["n", "b"]), \
                patch.object(
                    gddp, "interactive_nodes", return_value=gddp._MENU_BACK
                ) as nodes, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_graph_hub("demo")
        self.assertIs(outcome, gddp._MENU_BACK)
        nodes.assert_called_once_with("demo")

    def test_interactive_graph_hub_w_opens_live_watch(self):
        with patch.object(gddp, "_menu_choice", side_effect=["w", "b"]), \
                patch.object(
                    gddp, "interactive_watch", return_value=gddp._MENU_BACK
                ) as live, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_graph_hub("demo")
        self.assertIs(outcome, gddp._MENU_BACK)
        live.assert_called_once_with("demo")

    def test_node_status_label_exposes_node_index_desync(self):
        self.assertEqual(
            gddp._node_status_label(
                {"status": "pending"},
                {"status": "complete"},
            ),
            "DESYNC node=pending index=complete",
        )

    def test_node_menu_phase_distinguishes_review_from_ready(self):
        self.assertEqual(
            gddp._node_menu_phase("ready", "awaiting_review", "awaiting_review"),
            "awaiting review",
        )
        self.assertEqual(gddp._node_menu_phase("ready", "-", "-"), "ready")
        self.assertEqual(
            gddp._node_menu_phase("ready", "running", "running"),
            "running",
        )
        self.assertEqual(
            gddp._node_menu_phase("complete", "awaiting_review", "awaiting_review"),
            "complete",
        )
        self.assertNotEqual(
            gddp._graph_status_style("ready"),
            gddp._graph_status_style("awaiting review"),
        )

    def test_verdict_chip_and_pass_style_are_distinct(self):
        self.assertEqual(gddp._verdict_chip("pass"), "PASS")
        self.assertEqual(gddp._verdict_chip("failed"), "FAIL")
        self.assertEqual(gddp._verdict_chip("-"), "")
        self.assertEqual(gddp._graph_status_style("pass"), "bold green")
        self.assertNotEqual(
            gddp._graph_status_style("pass"),
            gddp._graph_status_style("awaiting review"),
        )

    def test_node_row_puts_pass_verdict_first(self):
        text = gddp._node_row_description("awaiting review", "Title", "pass")
        self.assertEqual(text.plain, "PASS · awaiting review · Title")
        self.assertEqual(text.spans[0].style, "bold green")
        none = gddp._node_row_description("ready", "Title", "-")
        self.assertEqual(none.plain, "ready · Title")

    def test_front_page_displayed_letters_are_handled(self):
        displayed = gddp._letter_keys(gddp._front_page_actions())
        handled = gddp._handled_letter_keys(
            gddp._front_page_actions(), gddp._front_page_handlers()
        )
        self.assertIn("w", displayed)
        self.assertEqual(set(displayed), set(handled))
        self.assertEqual(set(displayed), {"d", "e", "g", "w", "h", "c", "q"})
        self.assertTrue(
            {"d", "g", "w", "h"}.issubset(gddp._front_page_handlers())
        )

    def test_graph_hub_displayed_letters_are_handled(self):
        displayed = gddp._letter_keys(gddp._graph_hub_actions())
        handled = gddp._handled_letter_keys(
            gddp._graph_hub_actions(), gddp._graph_hub_handlers()
        )
        self.assertIn("w", displayed)
        self.assertEqual(set(displayed), set(handled))
        self.assertTrue(
            {"n", "d", "w", "m"}.issubset(gddp._graph_hub_handlers())
        )

    def test_paged_help_letters_stay_in_handled_set(self):
        help_bits, displayed = gddp._paged_menu_key_spec(
            page_count=2,
            fzf_ok=True,
            refreshable=True,
            fzf_multi=True,
            back_label="projects",
        )
        chrome = " ".join(help_bits)
        for letter in displayed:
            if letter.isdigit() or letter == " ":
                continue
            self.assertIn(letter, chrome)
        self.assertTrue({"f", "r", "b", "q", "p", "n"}.issubset(displayed))
        self.assertIn("f filter", chrome)
        self.assertIn("r refresh", chrome)
        self.assertIn("space", chrome)

    def test_interactive_watch_invokes_cmd_watch_boundary(self):
        with patch.object(gddp, "_clear_screen"), \
                patch.object(gddp, "cmd_watch", return_value=0) as watch:
            outcome = gddp.interactive_watch()
        self.assertIs(outcome, gddp._MENU_BACK)
        watch.assert_called_once()
        ns = watch.call_args[0][0]
        self.assertIsNone(ns.target)
        self.assertFalse(ns.once)
        self.assertFalse(ns.all)
        self.assertIsNone(ns.project)

    def test_interactive_watch_keeps_failure_visible(self):
        with patch.object(gddp, "_clear_screen"), \
                patch.object(
                    gddp,
                    "cmd_watch",
                    side_effect=RuntimeError("gddp-runtime not found at /missing"),
                ), \
                patch.object(gddp, "_pause", return_value="x") as pause, \
                patch.object(gddp.console, "print") as printed:
            outcome = gddp.interactive_watch("demo")
        self.assertIs(outcome, gddp._MENU_BACK)
        pause.assert_called_once()
        joined = " ".join(
            str(getattr(c.args[0], "plain", c.args[0]))
            for c in printed.call_args_list if c.args
        )
        self.assertIn("live/watch unavailable", joined)
        self.assertIn("GDDP_RUNTIME_ROOT", joined)

    def test_cmd_watch_reports_missing_runtime(self):
        missing = Path(tempfile.mkdtemp()) / "missing-runtime"
        ns = argparse.Namespace(
            target=None, interval=2.0, once=True, all=False, project=None,
        )
        err = StringIO()
        with patch.dict(os.environ, {"GDDP_RUNTIME_ROOT": str(missing)}, clear=False), \
                patch.object(gddp.sys, "stderr", err):
            rc = gddp.cmd_watch(ns)
        self.assertEqual(rc, 2)
        self.assertIn("live/watch unavailable", err.getvalue())
        self.assertIn("GDDP_RUNTIME_ROOT", err.getvalue())

    def test_node_columns_align_and_mark_running(self):
        ready = gddp._format_node_columns(
            graph="ready",
            runtime="-",
            verdict="-",
            title="Short",
            room=64,
        )
        running = gddp._format_node_columns(
            graph="ready",
            runtime="running",
            verdict="-",
            title="Preserve run evidence",
            room=64,
        )
        review = gddp._format_node_columns(
            graph="provisional",
            runtime="awaiting_review",
            verdict="pass",
            title="Validate",
            room=64,
        )
        self.assertTrue(running.plain.startswith("ready"))
        self.assertEqual(ready.plain[:18], running.plain[:18])
        self.assertIn("▶running", running.plain)
        self.assertNotIn("▶", ready.plain)
        self.assertIn("reverse", " ".join(
            str(span.style) for span in running.spans if span.style
        ))
        self.assertIn("awaiting review", review.plain)
        self.assertIn("PASS", review.plain)
        mark_at = running.plain.index("▶")
        self.assertEqual(ready.plain[mark_at], " ")
        self.assertEqual(ready.plain[:mark_at], running.plain[:mark_at])

    def test_paged_menu_node_rows_align_at_representative_widths(self):
        items = [
            ("n", gddp._node_list_desc("ready", "-", "Tiny id", "-")),
            (
                "node-05-validate-decision-set",
                gddp._node_list_desc(
                    "provisional", "awaiting_review", "Validate", "pass",
                ),
            ),
            (
                "node-13-preserve-results",
                gddp._node_list_desc(
                    "ready", "running", "Preserve run evidence", "-",
                ),
            ),
        ]
        for width in (80, 120, 200):
            output = StringIO()
            test_console = Console(
                file=output, width=width, color_system=None, highlight=False,
            )
            terminal = self._paged_terminal(lambda: "q")
            with patch.object(gddp, "_import_module", return_value=terminal), \
                    patch.object(gddp, "console", test_console):
                selected = gddp._paged_menu(
                    "nodes · demo", items, back_label="projects",
                )
            self.assertIs(selected, gddp._MENU_QUIT)
            lines = [
                ln.rstrip()
                for ln in output.getvalue().splitlines()
                if ln.strip() and not ln.startswith("nodes")
                and "↑/↓" not in ln and "GRAPH" not in ln
            ]
            self.assertGreaterEqual(len(lines), 3)
            prefixes = [ln[:6] for ln in lines]
            self.assertTrue(all(p[0] in {" ", "›"} for p in prefixes))
            id_cols = [ln[4:34] for ln in lines]
            self.assertTrue(all(len(col) == len(id_cols[0]) for col in id_cols))
            self.assertIn("▶running", output.getvalue())
            if width >= 80:
                self.assertIn("GRAPH", output.getvalue())
                self.assertIn("RUNTIME", output.getvalue())

    def test_interactive_status_all_and_one(self):
        keys = iter(["a", "x", "o", "x", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        fzf = SimpleNamespace(available=lambda: False, pick=lambda *a, **k: None)
        node_cli = SimpleNamespace(
            iter_nodes=lambda root, project: [
                (
                    "alpha",
                    {"title": "Alpha", "status": "ready"},
                    {"status": "ready"},
                )
            ],
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(
                queue_state="awaiting_review",
                job_status="awaiting_review",
                verdict="pass",
            ),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(
                    gddp, "_list_status_projects", return_value=["demo"]
                ), \
                patch.object(
                    gddp,
                    "_load_project_doc",
                    return_value={
                        "nodes": [{"id": "alpha", "status": "ready"}],
                    },
                ), \
                patch.object(gddp, "_pick_graph", return_value="demo"), \
                patch.object(gddp, "_clear_screen"), \
                patch.object(gddp.console, "print") as printed:
            outcome = gddp.interactive_status()

        self.assertIs(outcome, gddp._MENU_BACK)
        rendered = " ".join(
            str(getattr(c.args[0], "plain", c.args[0]))
            for c in printed.call_args_list
            if c.args
        )
        self.assertIn("status · all projects", rendered)
        self.assertIn("awaiting review", rendered)
        self.assertIn("PASS", rendered)

    def test_show_status_all_uses_rich_counts(self):
        with patch.object(
            gddp, "_list_status_projects", return_value=["demo"]
        ), patch.object(
            gddp,
            "_load_project_doc",
            return_value={"nodes": [
                {"id": "a", "status": "complete"},
                {"id": "b", "status": "ready"},
            ]},
        ), patch.object(gddp.console, "print") as printed:
            gddp.show_status()
        texts = [
            c.args[0]
            for c in printed.call_args_list
            if c.args and hasattr(c.args[0], "plain")
        ]
        joined = " ".join(t.plain for t in texts)
        self.assertIn("demo", joined)
        self.assertIn("complete=1", joined)
        self.assertIn("ready=1", joined)
        # colored spans present for status tokens
        styles = {span.style for t in texts for span in t.spans}
        self.assertTrue(any(s and "green" in str(s) for s in styles))
        self.assertTrue(any(s and "cyan" in str(s) for s in styles))

    def test_node_picker_refresh_requeries_runtime_evidence(self):
        snapshots = [
            [("alpha", {"title": "Alpha", "status": "running"}, {"status": "running"})],
            [("alpha", {"title": "Alpha", "status": "complete"}, {"status": "complete"})],
        ]
        node_cli = SimpleNamespace(
            iter_nodes=Mock(side_effect=snapshots),
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(
                queue_state="-", job_status="-", verdict="-"
            ),
        )
        with patch.object(gddp, "_import_module", return_value=node_cli), \
                patch.object(
                    gddp,
                    "_pick_list",
                    side_effect=[gddp._MENU_REFRESH, gddp._MENU_BACK],
                ) as picked:
            result = gddp.interactive_nodes("demo")

        self.assertIs(result, gddp._MENU_BACK)
        self.assertEqual(node_cli.iter_nodes.call_count, 2)
        self.assertTrue(picked.call_args_list[0].kwargs["refreshable"])

    def test_multi_pick_reviews_selected_set_not_batch(self):
        node_cli = SimpleNamespace(
            iter_nodes=lambda root, project: [
                ("alpha", {"title": "A", "status": "ready"}, {"status": "ready"}),
                ("beta", {"title": "B", "status": "ready"}, {"status": "ready"}),
                ("gamma", {"title": "C", "status": "ready"}, {"status": "ready"}),
            ],
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(
                queue_state="-", job_status="-", verdict="-"
            ),
        )
        with patch.object(gddp, "_import_module", return_value=node_cli), \
                patch.object(
                    gddp,
                    "_pick_list",
                    side_effect=[["beta", "gamma"], gddp._MENU_BACK],
                ), \
                patch.object(
                    gddp, "_node_review_menu", return_value=gddp._MENU_BACK
                ) as review, \
                patch.object(gddp, "_batch_node_status") as batch:
            result = gddp.interactive_nodes("demo")

        self.assertIs(result, gddp._MENU_BACK)
        review.assert_called_once_with(
            "demo",
            "beta",
            node_ids=["beta", "gamma"],
            allow_batch=True,
        )
        batch.assert_not_called()

    def test_review_same_status_key_opens_batch(self):
        keys = iter(["s", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        node_cli = SimpleNamespace(
            cmd_show=lambda **kwargs: 0,
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(verdict="-"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(
                    gddp, "_batch_node_status", return_value=gddp._MENU_BACK
                ) as batch, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu(
                "demo",
                "beta",
                node_ids=["beta", "gamma"],
                allow_batch=True,
            )

        self.assertIs(outcome, gddp._MENU_BACK)
        batch.assert_called_once_with("demo", ["beta", "gamma"])

    def test_node_workflow_reviews_and_updates_entirely_in_menu(self):
        # paged: project 1 → node 1 → update → complete → confirm → back out
        keys = iter(["1", "1", "u", "c", "y", "x", "b", "b", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        fzf = SimpleNamespace(available=lambda: False, pick=lambda *a, **k: None)
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
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(
                queue_state="-", job_status="-"
            ),
            node_completion_readiness=lambda project, node_id: (
                True,
                "evaluator passed (criteria + integrity) — your acceptance sets graph status",
            ),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp.Prompt, "ask", return_value="accepted after review"), \
                patch.object(node_cli, "cmd_show", wraps=node_cli.cmd_show) as show, \
                patch.object(
                    node_cli, "cmd_set_status", wraps=node_cli.cmd_set_status
                ) as set_status, \
                patch.object(gddp, "_dirty_graph_status_paths", return_value=[]), \
                patch.object(gddp, "_offer_acceptance_merge", return_value=True):
            outcome = gddp.interactive_nodes()

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertGreaterEqual(show.call_count, 1)
        show.assert_called_with(
            project="demo",
            node_id="alpha",
            trace=False,
            view="summary",
        )
        set_status.assert_called_once_with(
            project="demo",
            node_id="alpha",
            status="complete",
            yes=True,
            reason="accepted after review",
        )

    def test_update_key_after_evaluation_opens_status_menu(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80)
        keys = iter(["e", "u", "b", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        node_cli = SimpleNamespace(
            cmd_show=lambda **kwargs: 0,
            node_completion_readiness=lambda project, node_id: (
                True,
                "evaluator passed (criteria + integrity) — your acceptance sets graph status",
            ),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "console", test_console), \
                patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu("demo", "alpha")

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertRegex(output.getvalue(), r"(?m)^graph status$")
        self.assertIn("evaluator passed", output.getvalue())

    def test_node_review_offers_reject_and_retry_action(self):
        terminal = SimpleNamespace(
            getch=lambda: "x",
            clear_lines=lambda n: None,
        )
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=100)
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            choice = gddp._node_review_pick_action(has_siblings=False)

        self.assertEqual(choice, "x")
        self.assertIn("reject + retry", output.getvalue())

    def test_reject_and_retry_returns_graph_ready_then_retries_job(self):
        node_cli = SimpleNamespace(
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(
                job_id="job-1", queue_state="awaiting_review"
            ),
            cmd_set_status=Mock(return_value=0),
        )
        with patch.object(gddp, "_import_module", return_value=node_cli), \
                patch.object(gddp, "_menu_choice", return_value="y"), \
                patch.object(gddp.Prompt, "ask", return_value="new clean user"), \
                patch.object(gddp, "_offer_publish_graph_status") as publish, \
                patch.object(gddp, "run_runtime_jobs", return_value=0) as retry, \
                patch.object(gddp, "_clear_screen"):
            rc = gddp._confirm_reject_and_retry("demo", "node-1")

        self.assertEqual(rc, 0)
        node_cli.cmd_set_status.assert_called_once_with(
            project="demo",
            node_id="node-1",
            status="ready",
            yes=True,
            reason="new clean user",
        )
        publish.assert_called_once_with("demo", "node-1", "ready", "new clean user")
        retry.assert_called_once_with([
            "retry",
            "job-1",
            "--reason",
            "new clean user",
            "--yes",
        ])

    def test_node_review_left_right_move_to_sibling_nodes(self):
        """←/→ on the node view jumps prev/next without returning to the list."""
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80)
        keys = iter(["RIGHT", "LEFT", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        shown: list[str] = []

        def cmd_show(**kwargs):
            if kwargs.get("view") == "summary":
                shown.append(kwargs["node_id"])
            return 0

        node_cli = SimpleNamespace(
            cmd_show=cmd_show,
            node_completion_readiness=lambda project, node_id: (False, "n/a"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "console", test_console), \
                patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu(
                "demo",
                "alpha",
                node_ids=["alpha", "beta", "gamma"],
            )

        self.assertIs(outcome, gddp._MENU_BACK)
        # start alpha → RIGHT beta → LEFT alpha → b
        self.assertEqual(shown, ["alpha", "beta", "alpha"])
        self.assertIn("1/3", output.getvalue())
        self.assertIn("prev", output.getvalue())
        self.assertIn("next", output.getvalue())
        self.assertIn("↑/↓ move", output.getvalue())

    def test_node_review_up_down_enter_opens_update(self):
        """↑/↓ walk the action menu; Enter opens the highlighted action."""
        views: list[tuple[str, str]] = []
        # default cursor is evaluation (e); two DOWN → skip evaluator hub → update
        keys = iter(["DOWN", "DOWN", "\r", "b", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )

        def cmd_show(**kwargs):
            views.append((kwargs.get("node_id", ""), kwargs.get("view", "")))
            return 0

        node_cli = SimpleNamespace(
            cmd_show=cmd_show,
            node_completion_readiness=lambda project, node_id: (False, "n/a"),
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(verdict="-"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu(
                "demo",
                "alpha",
                node_ids=["alpha"],
            )

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertIn(("alpha", "summary"), views)

    def test_node_review_more_opens_contract(self):
        views: list[tuple[str, str]] = []
        # m → c → pause → b
        keys = iter(["m", "c", "x", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )

        def cmd_show(**kwargs):
            views.append((kwargs.get("node_id", ""), kwargs.get("view", "")))
            return 0

        node_cli = SimpleNamespace(
            cmd_show=cmd_show,
            node_completion_readiness=lambda project, node_id: (False, "n/a"),
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(verdict="-"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu(
                "demo",
                "alpha",
                node_ids=["alpha"],
            )

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertIn(("alpha", "contract"), views)

    def test_node_review_up_from_top_wraps_to_quit_then_enter(self):
        """↑ from the default evaluation row wraps to quit."""
        keys = iter(["UP", "\r"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        node_cli = SimpleNamespace(
            cmd_show=lambda **kwargs: 0,
            node_completion_readiness=lambda project, node_id: (False, "n/a"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu("demo", "alpha", node_ids=["alpha"])

        self.assertIs(outcome, gddp._MENU_QUIT)

    def test_node_review_arrows_wrap_at_list_ends(self):
        keys = iter(["LEFT", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        shown: list[str] = []

        def cmd_show(**kwargs):
            if kwargs.get("view") == "summary":
                shown.append(kwargs["node_id"])
            return 0

        node_cli = SimpleNamespace(
            cmd_show=cmd_show,
            node_completion_readiness=lambda project, node_id: (False, "n/a"),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp._node_review_menu(
                "demo",
                "alpha",
                node_ids=["alpha", "beta", "gamma"],
            )

        self.assertIs(outcome, gddp._MENU_BACK)
        self.assertEqual(shown, ["alpha", "gamma"])

    def test_node_workflow_blocks_complete_without_current_evaluation(self):
        keys = iter(["u", "c", "b", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        node_cli = SimpleNamespace(
            cmd_show=lambda **kwargs: 0,
            cmd_set_status=lambda **kwargs: 0,
            node_completion_readiness=lambda project, node_id: (
                False,
                "no evaluator result yet for job job-1",
            ),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"), \
                patch.object(node_cli, "cmd_show", wraps=node_cli.cmd_show) as show, \
                patch.object(node_cli, "cmd_set_status") as set_status:
            outcome = gddp._node_review_menu("demo", "alpha")

        self.assertIs(outcome, gddp._MENU_BACK)
        set_status.assert_not_called()
        self.assertTrue(
            any(
                call.kwargs.get("view") == "evaluation"
                for call in show.call_args_list
            )
        )

    def test_node_workflow_allows_explicit_menu_override(self):
        keys = iter(["u", "c", "o", "y", "x", "b"])
        terminal = SimpleNamespace(getch=lambda: next(keys))
        node_cli = SimpleNamespace(
            cmd_show=lambda **kwargs: 0,
            cmd_set_status=lambda **kwargs: 0,
            node_completion_readiness=lambda project, node_id: (
                False,
                "no evaluator result yet for job job-1",
            ),
        )

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(
                    gddp.Prompt,
                    "ask",
                    return_value="operator reviewed missing evidence",
                ), \
                patch.object(gddp, "_clear_screen"), \
                patch.object(node_cli, "cmd_set_status") as set_status:
            outcome = gddp._node_review_menu("demo", "alpha")

        self.assertIs(outcome, gddp._MENU_BACK)
        set_status.assert_called_once_with(
            project="demo",
            node_id="alpha",
            status="complete",
            yes=True,
            reason="operator reviewed missing evidence",
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

    def test_complete_abort_on_pending_merge_skips_writer(self):
        """After reason, declining the merge prompt must not write graph status."""
        terminal = SimpleNamespace(getch=lambda: "y")  # confirm set complete
        node_cli = SimpleNamespace(cmd_set_status=lambda **kwargs: 0)

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp.Prompt, "ask", return_value="looks good"), \
                patch.object(gddp, "_offer_acceptance_merge", return_value=False), \
                patch.object(node_cli, "cmd_set_status") as set_status:
            rc = gddp._confirm_status_change("demo", "alpha", "complete")

        self.assertEqual(rc, 1)
        set_status.assert_not_called()

    def test_acceptance_merge_skip_allows_complete(self):
        terminal = SimpleNamespace(getch=lambda: "s")
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(
                    gddp,
                    "_latest_receipt",
                    return_value={
                        "merge_commit_sha": "abc123def456",
                        "evaluated_commit_sha": "abc123def456",
                    },
                ), \
                patch.object(
                    gddp, "_resolve_project_repo", return_value=Path("/tmp/repo")
                ), \
                patch.object(gddp, "_acceptance_merge_state", return_value="pending"), \
                patch.object(gddp, "_default_branch", return_value="main"), \
                patch.object(
                    gddp.subprocess,
                    "run",
                    return_value=SimpleNamespace(
                        returncode=0, stdout="abc123d tip\n", stderr=""
                    ),
                ):
            self.assertTrue(
                gddp._offer_acceptance_merge("demo", "alpha")
            )

    def test_successful_status_change_offers_publish(self):
        terminal = SimpleNamespace(getch=lambda: "y")
        node_cli = SimpleNamespace(cmd_set_status=lambda **kwargs: 0)

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp.Prompt, "ask", return_value="ship it"), \
                patch.object(
                    gddp, "_offer_publish_graph_status"
                ) as publish, \
                patch.object(node_cli, "cmd_set_status", return_value=0) as set_status:
            rc = gddp._confirm_status_change("demo", "alpha", "ready")

        self.assertEqual(rc, 0)
        set_status.assert_called_once()
        publish.assert_called_once_with("demo", "alpha", "ready", "ship it")

    def test_publish_commit_push_stages_only_graph_paths(self):
        calls: list[tuple] = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[:2] == ("status", "--porcelain"):
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        " M graphs/demo/nodes/alpha.yaml\n"
                        " M graphs/demo/project.yaml\n"
                    ),
                    stderr="",
                )
            if args[0] == "diff":
                return SimpleNamespace(returncode=0, stdout=" 2 files changed\n", stderr="")
            if args[0] == "rev-parse":
                return SimpleNamespace(returncode=0, stdout="abc1234\n", stderr="")
            if args[0] == "branch":
                return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        terminal = SimpleNamespace(getch=lambda: "p")
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "_config_git", side_effect=fake_git):
            gddp._offer_publish_graph_status(
                "demo", "alpha", "complete", "looks good"
            )

        self.assertIn(
            ("add", "--", "graphs/demo/nodes/alpha.yaml", "graphs/demo/project.yaml"),
            calls,
        )
        commit_calls = [c for c in calls if c and c[0] == "commit"]
        self.assertEqual(len(commit_calls), 1)
        self.assertIn("graph(demo): alpha → complete", commit_calls[0][2])
        self.assertIn(("push",), calls)

    def test_publish_skip_does_not_git_write(self):
        calls: list[tuple] = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[:2] == ("status", "--porcelain"):
                return SimpleNamespace(
                    returncode=0,
                    stdout=" M graphs/demo/nodes/alpha.yaml\n",
                    stderr="",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        terminal = SimpleNamespace(getch=lambda: "s")
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "_config_git", side_effect=fake_git):
            gddp._offer_publish_graph_status("demo", "alpha", "ready", "x")

        self.assertFalse(any(c and c[0] in {"add", "commit", "push"} for c in calls))

    def test_status_confirmation_shows_yes_no_before_reading_key(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80)
        terminal = SimpleNamespace(getch=lambda: "n")
        node_cli = SimpleNamespace(cmd_set_status=lambda **kwargs: 0)

        def import_module(name):
            return terminal if name == "terminal" else node_cli

        with patch.object(gddp, "console", test_console), \
                patch.object(gddp, "_import_module", side_effect=import_module):
            rc = gddp._confirm_status_change("demo", "alpha", "ready")

        rendered = output.getvalue()
        self.assertEqual(rc, 1)
        # Cursor starts on default ``n``; both options paint before any key.
        self.assertRegex(rendered, r"(?m)^  y\s+yes\s+set alpha to ready\s*$")
        self.assertRegex(
            rendered,
            r"(?m)^› n\s+no\s+leave graph truth unchanged\s*$",
        )
        self.assertIn("↑/↓ move", rendered)
        self.assertLess(rendered.index("yes"), rendered.index("Unchanged"))

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


class ReviewSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def _write_receipt(self, node_dir: Path, name: str, **fields):
        import json as _json

        node_dir.mkdir(parents=True, exist_ok=True)
        payload = {"verdict": "pass", "node_id": "n"}
        payload.update(fields)
        (node_dir / name).write_text(_json.dumps(payload))

    def test_latest_receipt_picks_newest_and_skips_bad_json(self):
        node_dir = Path(self.tempdir.name) / "verification" / "p" / "n"
        self._write_receipt(node_dir, "a.json", verdict="fail")
        self._write_receipt(node_dir, "b.json", verdict="pass")
        (node_dir / "broken.json").write_text("{not json")
        with patch.object(gddp, "ROOT", Path(self.tempdir.name)):
            receipt = gddp._latest_receipt("p", "n")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["verdict"], "pass")
        self.assertTrue(receipt["_receipt_path"].endswith("broken.json") is False)

    def test_diff_view_styles_pass_verdict(self):
        node_dir = Path(self.tempdir.name) / "verification" / "p" / "n"
        self._write_receipt(node_dir, "r.json", verdict="pass", criteria_verdict="pass")
        output = StringIO()
        test_console = Console(file=output, force_terminal=True, width=80, color_system="truecolor")
        with patch.object(gddp, "ROOT", Path(self.tempdir.name)), \
                patch.object(gddp, "console", test_console), \
                patch.object(gddp, "_resolve_project_repo", return_value=None):
            gddp._render_evaluation_and_diff("p", "n")
        rendered = output.getvalue()
        self.assertIn("pass", rendered)
        self.assertIn("\x1b[", rendered)

    def test_latest_receipt_none_without_dir(self):
        with patch.object(gddp, "ROOT", Path(self.tempdir.name)):
            self.assertIsNone(gddp._latest_receipt("p", "n"))

    def _git_repo(self):
        import subprocess as sp
        repo = Path(self.tempdir.name) / "repo"
        repo.mkdir()
        def git(*args):
            proc = sp.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout.strip()
        sp.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (repo / "f.txt").write_text("one\n")
        git("add", "-A")
        git("commit", "-qm", "base")
        base = git("rev-parse", "HEAD")
        (repo / "f.txt").write_text("two\n")
        git("add", "-A")
        git("commit", "-qm", "result")
        tip = git("rev-parse", "HEAD")
        git("reset", "-q", "--hard", base)
        return repo, base, tip

    def test_merge_state_pending_then_merged(self):
        import subprocess as sp
        repo, base, tip = self._git_repo()
        self.assertEqual(gddp._acceptance_merge_state(repo, tip), "pending")
        proc = sp.run(["git", "-C", str(repo), "merge", "--ff-only", tip],
                      capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(gddp._acceptance_merge_state(repo, tip), "merged")

    def test_merge_state_unavailable_for_unknown_sha(self):
        repo, _, _ = self._git_repo()
        self.assertEqual(
            gddp._acceptance_merge_state(repo, "0" * 40), "unavailable")


class ReviewRoutingTests(unittest.TestCase):
    def test_review_routes_to_subcommand_not_positional_dispatch(self):
        with patch.object(gddp, "cmd_review", return_value=0) as review, patch.object(
            gddp, "cmd_dispatch"
        ) as dispatch:
            rc = gddp.main(["review", "--project", "p", "--node", "n"])
        self.assertEqual(rc, 0)
        review.assert_called_once()
        dispatch.assert_not_called()

    def test_cli_commands_cover_all_subcommands(self):
        # _CLI_COMMANDS gates positional dispatch; a subcommand missing here is
        # silently swallowed as a node id (shipped once with 'review').
        for name in (
            "node",
            "jobs",
            "evaluations",
            "verify",
            "review",
            "obsidian",
            "project",
        ):
            self.assertIn(name, gddp._CLI_COMMANDS)


class EvalWiringTests(unittest.TestCase):
    """Coverage for the evaluate/config menu surfaces and gddp eval command."""

    def test_node_review_offers_verify_now_action(self):
        terminal = SimpleNamespace(getch=lambda: "v", clear_lines=lambda n: None)
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=100)
        with patch.object(gddp, "_import_module", return_value=terminal), \
                patch.object(gddp, "console", test_console):
            choice = gddp._node_review_pick_action(has_siblings=False)
        self.assertEqual(choice, "v")
        self.assertIn("evaluator", output.getvalue())
        self.assertNotIn("verify now", output.getvalue())

    def _completed_eval(self):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "verdict": "pass",
                "criteria_confidence": 0.9,
                "lane_status": {"criteria": "completed", "integrity": "completed"},
                "required_next_action": "accept",
            }),
            stderr="",
        )

    def test_run_live_eval_builds_live_two_lane_command(self):
        fake_runtime = Path(tempfile.mkdtemp())
        with patch.object(gddp, "resolve_runtime_root", return_value=fake_runtime), \
                patch.object(gddp, "_auto_base_commit", return_value="abc1234"), \
                patch.object(gddp, "_write_eval_knobs_sidecar"), \
                patch.object(gddp.subprocess, "run", return_value=self._completed_eval()) as run:
            verdict = gddp._run_live_eval("myapi-part1", "node-05-validate-decision-set")
        self.assertEqual(verdict, "pass")
        cmd = run.call_args.args[0]
        cmd_str = " ".join(str(c) for c in cmd)
        self.assertIn("verification/cli.py", cmd_str)
        self.assertIn("--base abc1234", cmd_str)
        self.assertIn("--semantic-mode live", cmd_str)
        self.assertIn("--semantic-harness pi", cmd_str)
        self.assertIn("--integrity on", cmd_str)
        self.assertIn("--receipt-dir", cmd_str)
        self.assertTrue(any(str(c).startswith("manual-") for c in cmd))

    def test_run_live_eval_passes_model_override(self):
        fake_runtime = Path(tempfile.mkdtemp())
        knobs = gddp._resolve_eval_knobs(model="cheap")
        with patch.object(gddp, "resolve_runtime_root", return_value=fake_runtime), \
                patch.object(gddp, "_auto_base_commit", return_value="abc1234"), \
                patch.object(gddp, "_write_eval_knobs_sidecar") as sidecar, \
                patch.object(gddp.subprocess, "run", return_value=self._completed_eval()) as run:
            gddp._run_live_eval(
                "myapi-part1", "node-05-validate-decision-set", knobs=knobs,
            )
        cmd_str = " ".join(str(c) for c in run.call_args.args[0])
        self.assertIn("--semantic-pi-model deepseek-v4-flash", cmd_str)
        sidecar.assert_called_once()
        written = sidecar.call_args.args[5]
        self.assertEqual(written["preset"], "cheap")
        self.assertEqual(written["model"], "deepseek-v4-flash")

    def test_run_live_eval_passes_thinking_and_integrity_off(self):
        fake_runtime = Path(tempfile.mkdtemp())
        knobs = gddp._resolve_eval_knobs(thinking="high", integrity="off")
        with patch.object(gddp, "resolve_runtime_root", return_value=fake_runtime), \
                patch.object(gddp, "_auto_base_commit", return_value="abc1234"), \
                patch.object(gddp, "_write_eval_knobs_sidecar"), \
                patch.object(gddp.subprocess, "run", return_value=self._completed_eval()) as run:
            gddp._run_live_eval(
                "myapi-part1", "node-05-validate-decision-set", knobs=knobs,
            )
        cmd_str = " ".join(str(c) for c in run.call_args.args[0])
        self.assertIn("--semantic-thinking high", cmd_str)
        self.assertIn("--integrity off", cmd_str)

    def test_run_live_eval_lanes_deterministic(self):
        fake_runtime = Path(tempfile.mkdtemp())
        knobs = gddp._resolve_eval_knobs(lanes="deterministic")
        with patch.object(gddp, "resolve_runtime_root", return_value=fake_runtime), \
                patch.object(gddp, "_auto_base_commit", return_value="abc1234"), \
                patch.object(gddp, "_write_eval_knobs_sidecar"), \
                patch.object(gddp.subprocess, "run", return_value=self._completed_eval()) as run:
            gddp._run_live_eval(
                "myapi-part1", "node-05-validate-decision-set", knobs=knobs,
            )
        cmd = [str(c) for c in run.call_args.args[0]]
        cmd_str = " ".join(cmd)
        self.assertIn("--semantic-mode offline", cmd_str)
        self.assertNotIn("--semantic-harness", cmd_str)
        self.assertIn("--integrity off", cmd_str)
        self.assertEqual(knobs["integrity"], "off")

    def test_resolve_eval_knobs_preset_vs_raw_id(self):
        cheap = gddp._resolve_eval_knobs(model="cheap")
        self.assertEqual(cheap["preset"], "cheap")
        self.assertEqual(cheap["model"], "deepseek-v4-flash")
        raw = gddp._resolve_eval_knobs(model="openai/gpt-5.4")
        self.assertIsNone(raw["preset"])
        self.assertEqual(raw["model"], "openai/gpt-5.4")

    def test_cmd_eval_forwards_knob_flags(self):
        with patch.object(gddp, "_run_live_eval", return_value="pass") as live:
            rc = gddp.cmd_eval(SimpleNamespace(
                project="myapi-part1", node="node-05", base=None,
                model="cheap", thinking="high", integrity="off", lanes="live",
            ))
        self.assertEqual(rc, 0)
        kwargs = live.call_args.kwargs
        self.assertEqual(kwargs["knobs"]["preset"], "cheap")
        self.assertEqual(kwargs["knobs"]["thinking"], "high")
        self.assertEqual(kwargs["knobs"]["integrity"], "off")
        self.assertEqual(kwargs["knobs"]["lanes"], "live")

    def test_load_eval_knobs_sidecar_missing_is_empty(self):
        missing = Path(tempfile.mkdtemp()) / "no-such-receipt.json"
        self.assertEqual(gddp._load_eval_knobs_sidecar(missing), {})

    def test_cmd_eval_fuzzy_resolves_within_project(self):
        with patch.object(gddp, "_run_live_eval", return_value="pass") as live:
            rc = gddp.cmd_eval(SimpleNamespace(
                project="myapi-part1", node="node-05", base=None,
            ))
        self.assertEqual(rc, 0)
        self.assertEqual(
            live.call_args.args,
            ("myapi-part1", "node-05-validate-decision-set"),
        )

    def test_cmd_eval_ambiguous_without_project_exits_2(self):
        with patch.object(gddp, "_run_live_eval", return_value="pass") as live:
            rc = gddp.cmd_eval(SimpleNamespace(
                project=None, node="node-01", base=None,
            ))
        self.assertEqual(rc, 2)
        live.assert_not_called()

    def test_cmd_eval_unknown_node_exits_2(self):
        with patch.object(gddp, "_run_live_eval", return_value="pass") as live:
            rc = gddp.cmd_eval(SimpleNamespace(
                project="myapi-part1", node="node-99-does-not-exist", base=None,
            ))
        self.assertEqual(rc, 2)
        live.assert_not_called()

    def test_eval_hub_displayed_letters_are_handled(self):
        displayed = gddp._letter_keys(gddp._eval_hub_actions())
        handled = gddp._handled_letter_keys(
            gddp._eval_hub_actions(), gddp._eval_hub_handlers()
        )
        self.assertEqual(set(displayed), set(handled))
        self.assertEqual(set(displayed), {"r", "k", "c", "i", "h", "s", "b", "q"})
        self.assertTrue(
            {"r", "k", "c", "i", "h", "s"}.issubset(gddp._eval_hub_handlers())
        )

    def test_node_review_v_opens_hub(self):
        picks = iter(["v", "b"])
        node_cli = SimpleNamespace(
            fetch_runtime_evidence=lambda *a, **k: SimpleNamespace(verdict=None),
            cmd_show=Mock(),
        )
        with patch.object(gddp, "_import_module", return_value=node_cli), \
                patch.object(gddp, "_node_review_pick_action", side_effect=lambda **k: next(picks)), \
                patch.object(gddp, "interactive_eval_hub", return_value=gddp._MENU_BACK) as hub, \
                patch.object(gddp, "_run_live_eval") as live, \
                patch.object(gddp, "_clear_screen"), \
                patch.object(gddp, "console"):
            outcome = gddp._node_review_menu("demo", "alpha")
        hub.assert_called_once_with("demo", "alpha")
        live.assert_not_called()
        self.assertIs(outcome, gddp._MENU_BACK)

    def test_interactive_evaluate_opens_hub(self):
        node_cli = SimpleNamespace(
            iter_nodes=lambda *a, **k: [("node-05-validate-decision-set", {"title": "x"}, {})],
        )
        graphs = iter(["myapi-part1", gddp._MENU_BACK])
        nodes = iter(["node-05-validate-decision-set", gddp._MENU_BACK])
        with patch.object(gddp, "_pick_graph", side_effect=lambda *a, **k: next(graphs)), \
                patch.object(gddp, "_pick_list", side_effect=lambda *a, **k: next(nodes)), \
                patch.object(gddp, "_import_module", return_value=node_cli), \
                patch.object(gddp, "interactive_eval_hub", return_value=gddp._MENU_BACK) as hub, \
                patch.object(gddp, "_run_live_eval") as live, \
                patch.object(gddp, "_clear_screen"):
            outcome = gddp.interactive_evaluate()
        hub.assert_called_once_with("myapi-part1", "node-05-validate-decision-set")
        live.assert_not_called()
        self.assertIs(outcome, gddp._MENU_BACK)

    def test_eval_hub_getch_run_then_back(self):
        keys = iter(["r", "b"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_load_receipts_for_node", return_value=[]), \
                patch.object(gddp, "_run_live_eval") as live, \
                patch.object(gddp, "_pause") as pause, \
                patch.object(gddp, "_clear_screen"), \
                patch.object(gddp, "console"):
            outcome = gddp.interactive_eval_hub("demo", "alpha")
        live.assert_called_once()
        self.assertEqual(live.call_args.args[:2], ("demo", "alpha"))
        pause.assert_called()
        self.assertIs(outcome, gddp._MENU_BACK)

    def test_offered_vs_read_formats_lane_files(self):
        canonical = {
            "readme": "/var/folders/xx/gddp-eval-wt-abc/README.md",
            "project_brief": "/var/folders/xx/gddp-eval-wt-abc/PROJECT-BRIEF.md",
            "neighbor:node-04-normalize-decisions": (
                "/Users/sab-mini/repos/gddp-config/graphs/myapi-part1/nodes/"
                "node-04-normalize-decisions.yaml"
            ),
        }
        coverage = {
            "criteria": {
                "rating": "medium",
                "accessed_paths": [
                    "/var/folders/xx/gddp-eval-wt-abc/README.md",
                    "/var/folders/xx/gddp-eval-wt-abc/PROJECT-BRIEF.md",
                ],
                "not_observed_paths": [
                    "/Users/sab-mini/repos/gddp-config/graphs/myapi-part1/nodes/"
                    "node-04-normalize-decisions.yaml",
                ],
            },
            "integrity": {
                "rating": "none",
                "accessed_paths": [],
                "not_observed_paths": [],
            },
            "overall": "low",
        }
        lines = gddp._offered_vs_read_lines(canonical, coverage)
        blob = "\n".join(lines)
        self.assertIn("README.md", blob)
        self.assertIn("PROJECT-BRIEF.md", blob)
        self.assertIn("README.md  (worktree) ✓", blob)
        self.assertIn("PROJECT-BRIEF.md  (worktree) ✓", blob)
        self.assertIn(
            "neighbor:node-04-normalize-decisions=node-04-normalize-decisions.yaml",
            blob,
        )
        self.assertIn("node-04-normalize-decisions.yaml ✗", blob)
        self.assertIn("Read (integrity): — (none)", blob)
        self.assertNotIn("/var/folders", blob)

    def test_offered_vs_read_handles_criteria_not_run(self):
        lines = gddp._offered_vs_read_lines({}, {"criteria": "not_run", "integrity": {}})
        blob = "\n".join(lines)
        self.assertIn("Read (criteria): not run", blob)

    def test_load_receipts_for_node_joins_sidecar(self):
        tmp = Path(tempfile.mkdtemp())
        rec_dir = tmp / "demo" / "alpha"
        rec_dir.mkdir(parents=True)
        rec = rec_dir / "manual-1-attempt0.json"
        rec.write_text(json.dumps({
            "verdict": "pass",
            "project_id": "demo",
            "node_id": "alpha",
            "job_id": "manual-1",
            "generated_at": "2026-01-01T00:00:00Z",
        }), encoding="utf-8")
        rec.with_suffix(".knobs.json").write_text(
            json.dumps({"model": "deepseek-v4-flash", "preset": "cheap"}),
            encoding="utf-8",
        )
        with patch.object(gddp, "_evaluation_sources", return_value=(None, tmp)):
            rows = gddp._load_receipts_for_node("demo", "alpha")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["knobs"]["model"], "deepseek-v4-flash")

    def test_load_receipts_for_node_hydrates_db_summary(self):
        tmp = Path(tempfile.mkdtemp())
        rec_dir = tmp / "demo" / "alpha"
        rec_dir.mkdir(parents=True)
        rec = rec_dir / "job-1-attempt0.json"
        rec.write_text(json.dumps({
            "verdict": "pass",
            "project_id": "demo",
            "node_id": "alpha",
            "job_id": "job-1",
            "canonical_context": {"readme": str(tmp / "README.md")},
            "context_coverage": {"overall": "low"},
        }), encoding="utf-8")
        summary = {
            "project_id": "demo",
            "node_id": "alpha",
            "job_id": "job-1",
            "verdict": "pass",
            "receipt_path": str(rec),
            "check": {"verdict": "pass", "receipt_path": str(rec)},
            "knobs": {},
        }
        with patch.object(gddp, "_evaluation_sources", return_value=(None, tmp)), \
                patch.object(gddp, "_import_module", side_effect=lambda name: __import__(name)):
            # Bypass evaluations walker: feed a DB-shaped summary through hydrate.
            hydrated = gddp._hydrate_eval_row(summary)
        self.assertEqual(
            hydrated["check"]["canonical_context"]["readme"],
            str(tmp / "README.md"),
        )

    def test_render_eval_show_empty_knobs_prints_dash(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)
        row = {
            "project_id": "demo",
            "node_id": "alpha",
            "job_id": "manual-1",
            "verdict": "pass",
            "sort_at": "2026-01-01T00:00:00Z",
            "check": {},
            "knobs": {},
        }
        with patch.object(gddp, "console", test_console):
            gddp._render_eval_show(row)
        self.assertIn("model             : -", output.getvalue())
        self.assertIn("tools             : c=0 i=0", output.getvalue())

    def test_cmd_eval_runs_empty_knobs_prints_dash(self):
        rows = [{
            "project_id": "myapi-part1",
            "node_id": "node-05-validate-decision-set",
            "verdict": "pass",
            "job_id": "manual-1",
            "sort_at": "2026-01-02T00:00:00Z",
            "knobs": {},
            "check": {},
        }]
        with patch.object(gddp, "_load_receipts_for_node", return_value=rows), \
                patch("sys.stdout", new_callable=StringIO) as out:
            rc = gddp.cmd_eval_runs(SimpleNamespace(
                project="myapi-part1", lens_node="node-05",
            ))
        self.assertEqual(rc, 0)
        self.assertRegex(out.getvalue(), r"pass\s+-\s+")

    def test_cmd_verify_node_live_delegates_to_run_live_eval(self):
        args = SimpleNamespace(
            project="myapi-part1",
            node="node-05-validate-decision-set",
            live=True,
            base="abc1234",
            repo_path=None,
        )
        with patch.object(gddp, "_run_live_eval", return_value="pass") as live:
            with self.assertRaises(SystemExit) as ctx:
                gddp.cmd_verify_node(args)
        live.assert_called_once_with(
            "myapi-part1", "node-05-validate-decision-set", base="abc1234",
        )
        self.assertEqual(ctx.exception.code, 0)

    def test_cmd_eval_instructions_without_receipt_is_preflight(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=100)
        with patch.object(gddp, "console", test_console):
            rc = gddp.cmd_eval_instructions(SimpleNamespace(
                project="myapi-part1",
                lens_node="node-05-validate-decision-set",
                preflight=True,
                run=None,
            ))
        self.assertEqual(rc, 0)
        text = output.getvalue()
        self.assertIn("preflight — offered only", text)
        self.assertNotIn("accessed_paths", text)
        self.assertNotIn("Read (criteria)", text)

    def test_cmd_eval_runs_filters_to_node(self):
        rows = [
            {"project_id": "myapi-part1", "node_id": "node-05-validate-decision-set",
             "verdict": "pass", "job_id": "manual-keep", "sort_at": "2026-01-02",
             "knobs": {"model": "deepseek-v4-flash"}},
            {"project_id": "myapi-part1", "node_id": "other",
             "verdict": "fail", "job_id": "manual-skip", "sort_at": "2026-01-01",
             "knobs": {}},
        ]
        with patch.object(gddp, "_load_receipts_for_node", return_value=rows[:1]) as load:
            rc = gddp.cmd_eval_runs(SimpleNamespace(
                project="myapi-part1", lens_node="node-05",
            ))
        self.assertEqual(rc, 0)
        load.assert_called_once()
        self.assertEqual(load.call_args.args[0], "myapi-part1")
        self.assertEqual(load.call_args.args[1], "node-05-validate-decision-set")

    def test_cmd_eval_config_prints_resolved_model(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)
        with patch.object(gddp, "console", test_console):
            rc = gddp.cmd_eval_config(SimpleNamespace())
        self.assertEqual(rc, 0)
        self.assertIn("deepseek-v4-flash", output.getvalue())

    def test_resolve_eval_knobs_expensive_unset_errors(self):
        env = {k: v for k, v in os.environ.items() if k != "GDDP_EVAL_MODEL_EXPENSIVE"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(gddp.EvalKnobError) as ctx:
                gddp._resolve_eval_knobs(model="expensive")
        self.assertIn("unset", str(ctx.exception))

    def test_resolve_eval_knobs_reads_settings_file(self):
        settings = Path(tempfile.mkdtemp()) / "settings.env"
        settings.write_text("GDDP_EVAL_MODEL_CHEAP=custom-cheap\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "GDDP_EVAL_MODEL_CHEAP"}
        with patch.object(gddp, "SETTINGS_FILE", settings), \
                patch.dict(os.environ, env, clear=True):
            gddp._load_runtime_settings()
            knobs = gddp._resolve_eval_knobs(model="cheap")
        self.assertEqual(knobs["model"], "custom-cheap")
        self.assertEqual(knobs["preset"], "cheap")

    def test_front_page_config_still_lists_new_keys(self):
        self.assertIn("GDDP_EVAL_MODEL_CHEAP", gddp.SETTINGS_FIELDS)
        self.assertIn("GDDP_EVAL_MODEL_EXPENSIVE", gddp.SETTINGS_FIELDS)


if __name__ == "__main__":
    unittest.main()
