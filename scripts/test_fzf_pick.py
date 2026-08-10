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
    def test_pick_list_falls_back_to_paged_when_fzf_unavailable(self):
        import gddp

        items = [("p1", "one"), ("p2", "two")]
        fake_fzf = SimpleNamespace(available=lambda: False, pick=lambda *a, **k: None)
        with patch.object(gddp, "_import_module", side_effect=lambda name: fake_fzf if name == "fzf_pick" else __import__(name)), \
             patch.object(gddp, "_paged_menu", return_value="p2") as paged:
            result = gddp._pick_list("projects", items, multi=False)
        self.assertEqual(result, "p2")
        paged.assert_called_once()

    def test_pick_list_uses_fzf_when_available(self):
        import gddp

        items = [("n1", "ready"), ("n2", "pending")]
        fake_fzf = SimpleNamespace(
            available=lambda: True,
            pick=lambda *a, **k: ["n1", "n2"],
        )
        with patch.object(gddp, "_import_module", return_value=fake_fzf):
            result = gddp._pick_list("nodes", items, multi=True, preview_cmd="echo {1}")
        self.assertEqual(result, ["n1", "n2"])


if __name__ == "__main__":
    unittest.main()
