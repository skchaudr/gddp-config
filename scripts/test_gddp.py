"""Focused tests for the config-owned gddp command boundary."""

from __future__ import annotations

import argparse
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
        # default cursor is evaluation (e); one DOWN → update; Enter → status menu → back
        keys = iter(["DOWN", "\r", "b", "b"])
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


if __name__ == "__main__":
    unittest.main()
