"""Evaluator knobs, live eval, and gddp eval* subcommands."""

from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.text import Text

import graph_io

DEFAULT_SEMANTIC_ARGS = (
    "--semantic-mode live --semantic-harness pi --semantic-provider deepseek "
    "--semantic-pi-model deepseek-v4-flash --semantic-thinking medium"
)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent


def _import_module(name: str):
    import gddp
    return gddp._import_module(name)


def resolve_runtime_root() -> Path:
    import gddp
    return gddp.resolve_runtime_root()


def runtime_python(runtime_root: Path) -> str:
    import gddp
    return gddp.runtime_python(runtime_root)


import gddp as _gddp_host

os = _gddp_host.os
subprocess = _gddp_host.subprocess
sys = _gddp_host.sys

from gddp_proxy import console


def _render_eval_config() -> None:
    import gddp
    gddp._render_eval_config()


def _render_eval_instructions(*args, **kwargs) -> None:
    import gddp
    return gddp._render_eval_instructions(*args, **kwargs)


def _render_eval_show(row: dict) -> None:
    import gddp
    gddp._render_eval_show(row)


def _load_receipts_for_node(project: str, node_id: str) -> list[dict]:
    import gddp
    return gddp._load_receipts_for_node(project, node_id)


def _hydrate_eval_row(row: dict) -> dict:
    import gddp
    return gddp._hydrate_eval_row(row)


def _evaluation_sources():
    import gddp
    return gddp._evaluation_sources()

_EVAL_PRESETS = {"cheap": "deepseek-v4-flash"}

_EVAL_LENSES = frozenset({"config", "instructions", "runs", "show"})

class EvalKnobError(ValueError):
    """Operator-facing failure resolving evaluator knobs."""

def _parse_semantic_flag(args_str: str, flag: str) -> str | None:
    try:
        tokens = shlex.split(args_str or "")
    except ValueError:
        return None
    try:
        idx = tokens.index(flag)
    except ValueError:
        return None
    if idx + 1 >= len(tokens):
        return None
    return tokens[idx + 1]

def _resolve_eval_knobs(
    *,
    model: str | None = None,
    thinking: str | None = None,
    integrity: str | None = None,
    lanes: str | None = None,
    base: str | None = None,
) -> dict:
    """Resolve evaluator knobs: explicit args → env/settings → defaults."""
    env_args = os.environ.get("GDDP_VERIFY_SEMANTIC_ARGS", DEFAULT_SEMANTIC_ARGS)
    env_model = (
        os.environ.get("GDDP_EVAL_MODEL_CHEAP")
        or _parse_semantic_flag(env_args, "--semantic-pi-model")
        or _EVAL_PRESETS["cheap"]
    )
    env_thinking = (
        os.environ.get("GDDP_SEMANTIC_THINKING")
        or os.environ.get("GDDP_EVAL_THINKING_DEFAULT")
        or _parse_semantic_flag(env_args, "--semantic-thinking")
        or "medium"
    )
    env_integrity = (os.environ.get("GDDP_INTEGRITY_MODE") or "on").strip().lower()
    env_lanes = (os.environ.get("GDDP_EVAL_LANES_DEFAULT") or "").strip().lower()
    if not env_lanes:
        mode = _parse_semantic_flag(env_args, "--semantic-mode")
        env_lanes = "deterministic" if mode == "offline" else "live"

    preset: str | None = None
    raw_model = (model or "").strip()
    if not raw_model:
        resolved_model = env_model
    elif raw_model == "cheap" or raw_model in _EVAL_PRESETS:
        preset = "cheap"
        resolved_model = (
            os.environ.get("GDDP_EVAL_MODEL_CHEAP") or _EVAL_PRESETS["cheap"]
        ).strip() or _EVAL_PRESETS["cheap"]
    elif raw_model == "expensive":
        preset = "expensive"
        resolved_model = (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip()
        if not resolved_model:
            raise EvalKnobError(
                "expensive preset is unset — set GDDP_EVAL_MODEL_EXPENSIVE"
            )
    else:
        resolved_model = raw_model

    resolved_thinking = (thinking or env_thinking).strip() or "medium"
    explicit_integrity = integrity is not None and str(integrity).strip() != ""
    resolved_integrity = (
        str(integrity).strip().lower() if explicit_integrity else env_integrity
    )
    if resolved_integrity not in {"on", "off"}:
        raise EvalKnobError(f"integrity must be on or off, got {resolved_integrity!r}")
    resolved_lanes = (lanes or env_lanes).strip().lower() or "live"
    if resolved_lanes not in {"live", "deterministic"}:
        raise EvalKnobError(
            f"lanes must be live or deterministic, got {resolved_lanes!r}"
        )
    if resolved_lanes == "deterministic" and not explicit_integrity:
        resolved_integrity = "off"

    if resolved_lanes == "deterministic":
        semantic_args = "--semantic-mode offline"
    else:
        semantic_args = (
            "--semantic-mode live --semantic-harness pi --semantic-provider deepseek "
            f"--semantic-pi-model {resolved_model} --semantic-thinking {resolved_thinking}"
        )
    return {
        "model": resolved_model,
        "preset": preset,
        "thinking": resolved_thinking,
        "integrity": resolved_integrity,
        "lanes": resolved_lanes,
        "semantic_args": semantic_args,
        "base": base,
    }

def _write_eval_knobs_sidecar(
    receipt_dir: Path,
    project: str,
    node_id: str,
    job_id: str,
    attempt: int,
    knobs: dict,
) -> Path | None:
    """Best-effort sidecar next to the receipt. Never fails the eval."""
    path = Path(receipt_dir) / project / node_id / f"{job_id}-attempt{attempt}.knobs.json"
    payload = {
        "model": knobs.get("model"),
        "preset": knobs.get("preset"),
        "thinking": knobs.get("thinking"),
        "integrity": knobs.get("integrity"),
        "lanes": knobs.get("lanes"),
        "base": knobs.get("base"),
        "semantic_args": knobs.get("semantic_args"),
        "job_id": job_id,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
    except OSError as exc:
        print(f"warning: could not write knobs sidecar {path}: {exc}", file=sys.stderr)
        return None

def _load_eval_knobs_sidecar(receipt_path: str | Path) -> dict:
    """Load sibling *.knobs.json next to a receipt; empty dict if missing."""
    sidecar = Path(receipt_path).with_suffix(".knobs.json")
    if not sidecar.is_file():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}

def _run_live_eval(
    project: str,
    node_id: str,
    base: str | None = None,
    knobs: dict | None = None,
) -> str:
    """Run the live two-lane judge on one node; print a compact summary.

    Single code path for the interactive menu (`evaluate` front-page action,
    `v` in the node review menu) and the `gddp eval <node>` shell command.
    Auto-resolves the repo and base commit. Returns the verdict string
    ("pass"/"fail"/...) or "" on error.
    """
    try:
        resolved = knobs or _resolve_eval_knobs(base=base)
    except EvalKnobError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""
    node_yaml = ROOT / "graphs" / project / "nodes" / f"{node_id}.yaml"
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    for path, label in ((node_yaml, "node yaml"), (project_yaml, "project yaml")):
        if not path.is_file():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            return ""
    import gddp
    repo = gddp._resolve_repo_for_project(project)
    if repo is None:
        print(
            f"ERROR: could not resolve repo checkout for project '{project}' "
            f"(pass --repo-path)",
            file=sys.stderr,
        )
        return ""
    base_sha = base or resolved.get("base") or gddp._auto_base_commit(repo)
    resolved = {**resolved, "base": base_sha}
    receipt_dir = ROOT / "verification"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    job_id = "manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = 0

    cmd = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "verification" / "cli.py"),
        "--node-yaml", str(node_yaml),
        "--project-yaml", str(project_yaml),
        "--repo", str(repo),
        "--config-root", str(ROOT),
        "--receipt-dir", str(receipt_dir),
        "--job-id", job_id,
        "--attempt", str(attempt),
    ]
    if base_sha:
        cmd += ["--base", base_sha]
    cmd += shlex.split(str(resolved.get("semantic_args") or DEFAULT_SEMANTIC_ARGS))
    cmd += ["--integrity", "off" if str(resolved.get("integrity") or "on").lower() == "off" else "on"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)

    print(f"  evaluating {project}/{node_id}  (base {base_sha[:8] if base_sha else 'n/a'})")
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True, check=False)
    import gddp
    gddp._write_eval_knobs_sidecar(receipt_dir, project, node_id, job_id, attempt, resolved)
    receipt_summary: dict = {}
    if proc.stdout.strip():
        try:
            receipt_summary = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            receipt_summary = {}
    if proc.returncode != 0 and not receipt_summary:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        return ""

    verdict = str(receipt_summary.get("verdict", ""))
    confidence = receipt_summary.get("criteria_confidence", "")
    action = receipt_summary.get("required_next_action", "")
    lane = receipt_summary.get("lane_status", {})
    print()
    chip = Text(f"  VERDICT  {verdict.upper()}", style=("bold green" if verdict == "pass" else "bold red"))
    console.print(chip)
    preset = resolved.get("preset")
    model = resolved.get("model") or "-"
    print(f"  model      : {preset}/{model}" if preset else f"  model      : {model}")
    if confidence:
        print(f"  confidence : {confidence}")
    if lane:
        crit = (lane.get("criteria") or "").replace("_", " ")
        integ = (lane.get("integrity") or "").replace("_", " ")
        print(f"  lanes     : criteria {crit} · integrity {integ}")
    if action:
        print(f"  next      : {action}")
    print(f"  receipts  : {ROOT / 'verification' / project / node_id}/")
    return verdict

def _resolve_eval_node(project: str | None, node_id: str) -> tuple[str, str] | int:
    """Fuzzy-resolve (project, node_id). Returns an exit code on failure."""
    def _match_in(proj_name: str) -> list[str]:
        nodes_dir = ROOT / "graphs" / proj_name / "nodes"
        if not nodes_dir.is_dir():
            return []
        return [
            f.stem for f in nodes_dir.glob("*.yaml")
            if f.stem == node_id or f.stem.startswith(f"{node_id}-") or node_id in f.stem
        ]

    if project:
        stems = _match_in(project)
        if len(stems) == 1:
            return project, stems[0]
        if len(stems) > 1:
            print(f"Ambiguous node '{node_id}' in project '{project}' — matches: {stems}", file=sys.stderr)
            return 2
        print(f"ERROR: node '{node_id}' not found in graph '{project}'", file=sys.stderr)
        return 2
    matches = []
    graphs = ROOT / "graphs"
    if graphs.is_dir():
        for proj_dir in graphs.iterdir():
            if not proj_dir.is_dir() or proj_dir.name.startswith(("_", ".")):
                continue
            for stem in _match_in(proj_dir.name):
                matches.append((proj_dir.name, stem))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous node '{node_id}' — matches:", file=sys.stderr)
        for proj_name, stem in matches:
            print(f"  {proj_name}/{stem}", file=sys.stderr)
        print("Pass --project <id>", file=sys.stderr)
        return 2
    print(f"ERROR: node '{node_id}' not found in any graph", file=sys.stderr)
    return 2

def cmd_eval(args):
    """Human-friendly live evaluation: gddp eval <node> [--project p].

    First token in {config,instructions,runs,show} is a lens; otherwise a node
    id. Auto-resolves project/node, repo, and base commit.
    """
    token = getattr(args, "node", None)
    if token in _EVAL_LENSES:
        handler = globals().get(f"cmd_eval_{token}")
        if handler is None:
            print(f"ERROR: eval {token} is not available", file=sys.stderr)
            return 2
        return handler(args)
    if not token:
        print("ERROR: gddp eval needs a node id (or config|instructions|runs|show)", file=sys.stderr)
        return 2
    resolved = _resolve_eval_node(getattr(args, "project", None), token)
    if isinstance(resolved, int):
        return resolved
    project, node_id = resolved
    try:
        knobs = _resolve_eval_knobs(
            model=getattr(args, "model", None),
            thinking=getattr(args, "thinking", None),
            integrity=getattr(args, "integrity", None),
            lanes=getattr(args, "lanes", None),
            base=getattr(args, "base", None),
        )
    except EvalKnobError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    import gddp
    verdict = gddp._run_live_eval(project, node_id, base=knobs.get("base"), knobs=knobs)
    if not verdict:
        return 1
    return 0

def _eval_lens_node(args) -> tuple[str, str] | int:
    token = getattr(args, "lens_node", None)
    if not token:
        print("ERROR: this eval lens needs a node id", file=sys.stderr)
        return 2
    return _resolve_eval_node(getattr(args, "project", None), token)

def cmd_eval_config(_args) -> int:
    import gddp
    gddp._render_eval_config()
    return 0

def cmd_eval_instructions(args) -> int:
    resolved = _eval_lens_node(args)
    if isinstance(resolved, int):
        return resolved
    project, node_id = resolved
    receipt = None
    if not getattr(args, "preflight", False):
        rows = _load_receipts_for_node(project, node_id)
        run_id = getattr(args, "run", None)
        if run_id:
            rows = [row for row in rows if row.get("job_id") == run_id]
        if rows:
            receipt = rows[0].get("check") if isinstance(rows[0].get("check"), dict) else None
    _render_eval_instructions(project, node_id, receipt=receipt)
    return 0

def cmd_eval_runs(args) -> int:
    resolved = _eval_lens_node(args)
    if isinstance(resolved, int):
        return resolved
    project, node_id = resolved
    rows = _load_receipts_for_node(project, node_id)
    if not rows:
        print(f"No evaluator receipts for {project}/{node_id}")
        return 0
    for row in rows:
        model = ((row.get("knobs") or {}).get("model") or "-")
        when = str(row.get("sort_at") or "-")[:19].replace("T", " ")
        check = row.get("check") if isinstance(row.get("check"), dict) else {}
        timing = check.get("evaluation_timing") if isinstance(check.get("evaluation_timing"), dict) else {}
        crit = timing.get("criteria") if isinstance(timing.get("criteria"), dict) else {}
        integ = timing.get("integrity") if isinstance(timing.get("integrity"), dict) else {}
        tools = f"c={crit.get('tool_calls', 0)} i={integ.get('tool_calls', 0)}"
        print(
            f"{when}  {row.get('verdict') or '-':<8}  {model:<22}  {tools:<14}  "
            f"{project}/{node_id}  {row.get('job_id') or '-'}"
        )
    print(f"{len(rows)} run(s)")
    return 0

def cmd_eval_show(args) -> int:
    token = getattr(args, "lens_node", None) or getattr(args, "run", None)
    if not token:
        print("ERROR: gddp eval show needs a job id or receipt path", file=sys.stderr)
        return 2
    path = Path(token).expanduser()
    if path.is_file():
        try:
            check = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: could not read {path}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(check, dict):
            print(f"ERROR: {path} is not a receipt object", file=sys.stderr)
            return 2
        row = {
            "project_id": check.get("project_id"),
            "node_id": check.get("node_id"),
            "job_id": check.get("job_id"),
            "verdict": check.get("verdict"),
            "sort_at": (check.get("evaluation_timing") or {}).get("finished_at")
            if isinstance(check.get("evaluation_timing"), dict) else check.get("generated_at"),
            "receipt_path": str(path),
            "check": check,
            "knobs": _load_eval_knobs_sidecar(path),
        }
        _render_eval_show(row)
        return 0
    evaluations = _import_module("evaluations")
    db_path, receipt_root = _evaluation_sources()
    rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
    matches = [row for row in rows if row.get("job_id") == token]
    if not matches:
        print(f"ERROR: no receipt with job_id {token!r}", file=sys.stderr)
        return 2
    row = matches[0]
    receipt_path = row.get("receipt_path")
    row = {**row, "knobs": _load_eval_knobs_sidecar(receipt_path) if receipt_path else {}}
    _render_eval_show(_hydrate_eval_row(row))
    return 0

def cmd_verify_node(args):
    """Delegate node verification to the runtime evaluator — the single judge.

    Default runs the deterministic lane (offline, fast — the verb's original
    contract). --live delegates to `_run_live_eval` so knobs and the sidecar
    match `gddp eval`.
    """
    if bool(getattr(args, "live", False)):
        import gddp
        verdict = gddp._run_live_eval(
            args.project,
            args.node,
            base=getattr(args, "base", None),
        )
        sys.exit(0 if verdict else 1)
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    node_yaml = ROOT / "graphs" / args.project / "nodes" / f"{args.node}.yaml"
    project_yaml = ROOT / "graphs" / args.project / "project.yaml"
    for path, label in ((node_yaml, "node yaml"), (project_yaml, "project yaml")):
        if not path.is_file():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            sys.exit(2)

    with open(project_yaml) as f:
        proj = yaml.safe_load(f) or {}
    repo_name = str(proj.get("repo", "")).split("/")[-1]
    repo = None
    candidates = []
    if args.repo_path:
        candidates.append(Path(args.repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for c in candidates:
        if c.is_dir():
            repo = c
            break
    if repo is None:
        print(f"ERROR: could not resolve repo checkout for '{proj.get('repo', '')}' "
              "(pass --repo-path)", file=sys.stderr)
        sys.exit(2)

    receipt_dir = ROOT / "verification"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    live = bool(getattr(args, "live", False))
    manual_job_id = "manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cmd = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "verification" / "cli.py"),
        "--node-yaml", str(node_yaml),
        "--project-yaml", str(project_yaml),
        "--repo", str(repo),
        "--config-root", str(ROOT),
        "--receipt-dir", str(receipt_dir),
        "--job-id", manual_job_id,
        "--attempt", "0",
        *(["--base", args.base] if getattr(args, "base", None) else []),
        "--semantic-mode", "live" if live else "offline",
        # --live must select the Pi harness explicitly: auto resolves to the
        # removed built-in runner and the evaluator refuses to start.
        *(["--semantic-harness", "pi"] if live else []),
        "--integrity", "on" if live else "off",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    sys.exit(subprocess.run(cmd, env=env, check=False).returncode)
