"""gddp gdad — thin entry to the runtime GDAD executor."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime_root() -> Path:
    env = os.environ.get("GDDP_RUNTIME_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    parts = ROOT.parts
    if ".worktrees" in parts:
        name = parts[parts.index(".worktrees") + 1]
        candidate = Path.home() / "gddp-runtime" / ".worktrees" / name
        if (candidate / "scripts" / "gdad_run.py").is_file():
            return candidate
    sibling = ROOT.parent / "gddp-runtime"
    if (sibling / "scripts" / "gdad_run.py").is_file():
        return sibling
    return Path.home() / "gddp-runtime"


def cmd_gdad(args) -> int:
    runtime = runtime_root()
    script = runtime / "scripts" / "gdad_run.py"
    if not script.is_file():
        print(f"ERROR: gdad executor not found at {script}", file=sys.stderr)
        return 2
    os.environ.setdefault("GDDP_RUNTIME_ROOT", str(runtime))
    os.environ.setdefault("GDDP_CONFIG_PATH", str(ROOT))
    os.environ.setdefault("GDAD_GATE_REPO", str(ROOT))
    spec = importlib.util.spec_from_file_location("gdad_run", script)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot load {script}", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = list(getattr(args, "gdad_args", None) or [])
    if argv and argv[0] == "--":
        argv = argv[1:]
    return int(module.main(argv))
