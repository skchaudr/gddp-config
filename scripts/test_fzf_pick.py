"""Unit tests for scripts/fzf_pick.py (mocked fzf subprocess)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fzf_pick


class FzfPickTests(unittest.TestCase):
    def test_empty_items_returns_none(self):
        self.assertIsNone(fzf_pick.pick([]))

    def test_missing_binary_returns_none(self):
        with patch.object(fzf_pick.shutil, "which", return_value=None):
            self.assertIsNone(
                fzf_pick.pick([("a", "A")], fzf_bin=None)
            )

    def test_pick_returns_values_from_stdout(self):
        completed = SimpleNamespace(returncode=0, stdout="node-1\nnode-3\n", stderr="")
        with patch.object(fzf_pick.subprocess, "run", return_value=completed) as run:
            result = fzf_pick.pick(
                [("node-1", "ready one"), ("node-2", "ready two"), ("node-3", "done")],
                multi=True,
                fzf_bin="/usr/bin/fzf",
            )
        self.assertEqual(result, ["node-1", "node-3"])
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "/usr/bin/fzf")
        self.assertIn("--multi", cmd)
        self.assertIn("--accept-nth=1", cmd)
        self.assertIn("node-1\tready one\n", run.call_args.kwargs["input"])

    def test_cancel_returncode_returns_none(self):
        completed = SimpleNamespace(returncode=130, stdout="", stderr="")
        with patch.object(fzf_pick.subprocess, "run", return_value=completed):
            self.assertIsNone(
                fzf_pick.pick([("a", "A")], fzf_bin="/usr/bin/fzf")
            )

    def test_fzf_pick_single_helper(self):
        completed = SimpleNamespace(returncode=0, stdout="only\n", stderr="")
        with patch.object(fzf_pick.subprocess, "run", return_value=completed):
            self.assertEqual(
                fzf_pick.fzf_pick([("only", "label")], fzf_bin="/usr/bin/fzf"),
                "only",
            )

    def test_preview_flag_passed(self):
        completed = SimpleNamespace(returncode=0, stdout="a\n", stderr="")
        with patch.object(fzf_pick.subprocess, "run", return_value=completed) as run:
            fzf_pick.pick(
                [("a", "A")],
                preview_cmd="cat {1}.yaml",
                fzf_bin="/usr/bin/fzf",
            )
        cmd = run.call_args.args[0]
        self.assertIn("--preview", cmd)
        self.assertIn("cat {1}.yaml", cmd)

    def test_full_line_stdout_still_extracts_value(self):
        # Older fzf without accept-nth may echo value\\tlabel.
        completed = SimpleNamespace(
            returncode=0, stdout="job-9\tready  node-x\n", stderr=""
        )
        with patch.object(fzf_pick.subprocess, "run", return_value=completed):
            self.assertEqual(
                fzf_pick.pick(
                    [("job-9", "ready  node-x")],
                    fzf_bin="/usr/bin/fzf",
                ),
                ["job-9"],
            )


class GddpPickListFallbackTests(unittest.TestCase):
    def test_pick_list_defaults_to_paged_menu(self):
        import gddp

        items = [("p1", "one"), ("p2", "two")]
        with patch.object(gddp, "_paged_menu", return_value="p2") as paged:
            result = gddp._pick_list(
                "projects",
                items,
                multi=False,
                preview_cmd="echo {1}",
            )
        self.assertEqual(result, "p2")
        paged.assert_called_once()
        kwargs = paged.call_args.kwargs
        self.assertEqual(kwargs.get("fzf_preview_cmd"), "echo {1}")
        self.assertFalse(kwargs.get("fzf_multi"))

    def test_paged_menu_f_steps_into_fzf(self):
        import gddp

        keys = iter(["f"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        fzf = SimpleNamespace(
            available=lambda: True,
            pick=lambda *a, **k: ["chosen"],
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            result = gddp._paged_menu(
                "projects",
                [("a", "one"), ("chosen", "two")],
                fzf_preview_cmd="echo {1}",
            )
        self.assertEqual(result, "chosen")

    def test_paged_menu_m_toggles_native_checks(self):
        import gddp

        keys = iter(["m", "DOWN", "m", "\r"])
        terminal = SimpleNamespace(
            getch=lambda: next(keys),
            clear_lines=lambda n: None,
        )
        fzf = SimpleNamespace(
            available=lambda: True,
            pick=lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("native multi must not open fzf")
            ),
        )

        def import_module(name):
            if name == "terminal":
                return terminal
            if name == "fzf_pick":
                return fzf
            return __import__(name)

        with patch.object(gddp, "_import_module", side_effect=import_module), \
                patch.object(gddp, "_clear_screen"):
            result = gddp._paged_menu(
                "nodes",
                [("n1", "a"), ("n2", "b")],
                fzf_multi=True,
            )
        self.assertEqual(result, ["n1", "n2"])

    def test_preview_cmds_do_not_double_quote_fzf_placeholders(self):
        """Regression: quoted \"...{1}...\" becomes graphs/'id'/… and 404s."""
        import gddp

        project_cmd = gddp._project_preview_cmd()
        node_cmd = gddp._node_preview_cmd("gddp-runtime")
        job_cmd = gddp._job_preview_cmd()
        # Bug form embeds fzf's shell quotes inside a double-quoted path.
        self.assertNotIn(
            f'"{gddp.ROOT}/graphs/{{1}}/project.yaml"',
            project_cmd,
        )
        self.assertIn(f"{gddp.ROOT}/graphs/{{1}}/project.yaml", project_cmd)
        self.assertNotIn(
            f'"{gddp.ROOT}/graphs/gddp-runtime/nodes/{{1}}.yaml"',
            node_cmd,
        )
        self.assertIn(
            f"{gddp.ROOT}/graphs/gddp-runtime/nodes/{{1}}.yaml",
            node_cmd,
        )
        self.assertIn("show {1}", job_cmd)


if __name__ == "__main__":
    unittest.main()
