#!/usr/bin/env python3
"""gddp — unified CLI for graph truth and runtime evidence.

Subcommands:
    node new          Interactive TUI node scaffold (full field editor)
    node rapid        Minimal-keystroke rapid node adder
    node batch        Walk through pending/REPLACE_ME nodes in a project
    node import       Import a node YAML from file or stdin (agent pipeline)
    node validate     Validate all nodes (or one project)
    node list         List nodes (ID | GRAPH | RUNTIME | VERDICT)
    node show         Show one node + evaluator summary (read-only runtime)
    node set-status   Set graph status on node YAML + project.yaml
    node status       Show status summary for all projects

    jobs list         List runtime jobs and queue states
    jobs show         Show one runtime job and its evidence
    jobs results      Summarize evaluator output
    jobs set          Change runtime queue state with an audit reason

    verify node       Run deterministic node evaluation; emit a receipt

    obsidian export   Export one graph to ~/Obsidian/gdd-<project>/

    project new       Create project skeleton (from graphify, outline, or empty shell)
    project validate  Validate project.yaml structure

Usage:
    python3 scripts/gddp.py node rapid --project my-app --repo org/repo
    python3 scripts/gddp.py node validate --project vault-doctor
    python3 scripts/gddp.py node import --file draft.yaml --project my-app
    python3 scripts/gddp.py node batch --project my-greenfield
    python3 scripts/gddp.py node list --project gddp-runtime --active
    python3 scripts/gddp.py node show --project gddp-runtime canary-retry-proof
    python3 scripts/gddp.py node set-status --project gddp-runtime canary-retry-proof ready --yes
    python3 scripts/gddp.py jobs list --state awaiting_review
    python3 scripts/gddp.py jobs show <job-id> --full
    python3 scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import yaml
    from rich import box
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Install deps:  pip install pyyaml rich")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
_PIPE_WIDTH = None if sys.stdout.isatty() else 120
console = Console(soft_wrap=True, highlight=False, width=_PIPE_WIDTH)


def _import_module(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    return __import__(name)


def cmd_node_new(args):
    new_node = _import_module("new_node")
    sys.exit(new_node.main())


def cmd_node_rapid(args):
    rapid = _import_module("rapid_add")
    sys.exit(rapid.main(
        project=args.project,
        repo=args.repo,
        project_name=args.project_name,
        llm_draft=args.llm_draft,
        dry_run=args.dry_run,
    ))


def cmd_node_batch(args):
    batch = _import_module("batch_fill")
    sys.exit(batch.main(project=args.project))


def cmd_node_import(args):
    import_node = _import_module("import_node")
    sys.exit(import_node.main(
        file_path=args.file,
        use_stdin=args.stdin,
        project=args.project,
        auto_approve=args.auto_approve,
        dry_run=args.dry_run,
    ))


def cmd_node_validate(args):
    validate = _import_module("validate")
    root = args.root or ROOT
    findings = validate.run(root, args.project)
    if args.json:
        print(validate.render_json(findings))
    elif args.quiet:
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if args.strict:
            errors += warnings
        print(f"errors={errors} warnings={warnings}")
    else:
        for f in findings:
            if f.severity == "error":
                sev = "ERROR"
            elif args.strict:
                sev = "ERROR*"
            else:
                sev = "WARN"
            loc = f.path if f.line == 0 else f"{f.path}:{f.line}"
            print(f"{loc} — {sev} — {f.rule} — {f.message}")
        if not findings:
            print("OK — all nodes valid")
        else:
            errors = sum(1 for f in findings if f.severity == "error")
            warnings = sum(1 for f in findings if f.severity == "warning")
            files = len({f.path for f in findings})
            print(f"\n{errors} error(s), {warnings} warning(s) across {files} file(s)")
    errors = sum(1 for f in findings if f.severity == "error")
    if args.strict:
        errors += sum(1 for f in findings if f.severity == "warning")
    sys.exit(1 if errors else 0)


def cmd_node_list(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_list(
        project=getattr(args, "project", None),
        status=getattr(args, "status", None),
        active=bool(getattr(args, "active", False)),
    ))


def cmd_node_show(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_show(
        project=args.project,
        node_id=args.node_id,
        trace=bool(getattr(args, "trace", False)),
    ))


def cmd_node_set_status(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_set_status(
        project=args.project,
        node_id=args.node_id,
        status=args.status,
        yes=bool(getattr(args, "yes", False)),
        reason=getattr(args, "reason", None),
    ))


def cmd_node_status(args):
    show_status()


def resolve_runtime_root() -> Path:
    """Resolve the runtime checkout that owns job and evaluator state."""
    configured = os.environ.get("GDDP_RUNTIME_ROOT")
    runtime_root = Path(configured).expanduser() if configured else ROOT.parent / "gddp-runtime"
    runtime_root = runtime_root.resolve()
    if not (runtime_root / "scripts" / "node_status.py").is_file():
        raise RuntimeError(
            f"gddp-runtime not found at {runtime_root}; set GDDP_RUNTIME_ROOT"
        )
    return runtime_root


def runtime_python(runtime_root: Path) -> str:
    """Prefer runtime's interpreter, with an explicit override for deployments."""
    configured = os.environ.get("GDDP_RUNTIME_PYTHON")
    if configured:
        return str(Path(configured).expanduser())
    runtime_venv = runtime_root / ".venv" / "bin" / "python"
    if runtime_venv.is_file() and os.access(runtime_venv, os.X_OK):
        return str(runtime_venv)
    return sys.executable


def run_runtime_jobs(argv: list[str]) -> int:
    """Delegate one jobs invocation through runtime's supported CLI boundary."""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "node_status.py"),
        *argv,
    ]
    env = os.environ.copy()
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def cmd_jobs(args):
    argv = []
    command = getattr(args, "jobs_command", None)
    if command:
        argv.append(command)
    if command == "list" and args.state:
        argv.extend(["--state", args.state])
    elif command == "show":
        argv.append(args.ref)
        if args.full:
            argv.append("--full")
    elif command == "results" and args.all:
        argv.append("--all")
    elif command == "set":
        argv.extend([args.ref, args.state, "--reason", args.reason])
        if args.yes:
            argv.append("--yes")
    return run_runtime_jobs(argv)


def static_overview():
    """Render the unified command groups without blocking redirected output."""
    console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=False,
        pad_edge=False,
        padding=(0, 2, 0, 0),
    )
    table.add_column("group", style="bold cyan", no_wrap=True)
    table.add_column("owns")
    table.add_column("start with", style="dim", no_wrap=True)
    table.add_row("node", "graph truth, authoring, runtime/evaluator join", "gddp node list")
    table.add_row("jobs", "runtime queue, results, and audited state changes", "gddp jobs list")
    table.add_row("verify", "node evaluation", "gddp verify node")
    table.add_row("project", "project graph creation and validation", "gddp project -h")
    table.add_row("obsidian", "graph export", "gddp obsidian export")
    console.print(table)
    console.print(Text("Run `gddp` in a terminal for the menu; use `gddp <group> -h` for commands.", style="dim"))


def interactive_menu():
    """Keep graph control in config while delegating the jobs section to runtime."""
    console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
    actions = {
        "n": ("nodes", "list graph truth with runtime/evaluator evidence"),
        "j": ("jobs", "open runtime jobs, results, and queue controls"),
        "s": ("status", "summarize graph completion"),
        "v": ("validate", "validate graph definitions"),
        "q": ("quit", ""),
    }
    while True:
        menu = Table(box=None, padding=(0, 2, 0, 1), pad_edge=False, show_header=False)
        menu.add_column(style="bold cyan", no_wrap=True)
        menu.add_column(style="bold", no_wrap=True)
        menu.add_column(style="dim")
        for key, (name, description) in actions.items():
            menu.add_row(key, name, description)
        console.print(menu)
        try:
            choice = Prompt.ask("select", choices=list(actions), default="n")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        console.rule(style="dim")
        if choice == "q":
            break
        try:
            if choice == "n":
                cmd_node_list(argparse.Namespace(project=None, status=None, active=False))
            elif choice == "j":
                run_runtime_jobs([])
            elif choice == "s":
                show_status()
            elif choice == "v":
                cmd_node_validate(argparse.Namespace(
                    root=None, project=None, json=False, quiet=False, strict=False
                ))
        except SystemExit:
            # Existing command handlers use SystemExit; one menu action should
            # return to the control-plane menu instead of closing the CLI.
            pass
        console.rule(style="dim")
    console.print(Text("bye.", style="dim"))


def cmd_overview(_args):
    if sys.stdin.isatty() and sys.stdout.isatty():
        return interactive_menu()
    static_overview()
    return 0


def cmd_verify_node(args):
    verify_node = _import_module("verify_node")
    argv = ["node", "--project", args.project, "--node", args.node]
    if args.repo_path:
        argv += ["--repo-path", args.repo_path]
    if args.json:
        argv += ["--json"]
    sys.exit(verify_node.main(argv))


def cmd_obsidian_export(args):
    obsidian_export = _import_module("obsidian_export")
    argv = ["--project", args.project]
    if args.vault:
        argv += ["--vault", str(args.vault)]
    if args.dry_run:
        argv.append("--dry-run")
    sys.exit(obsidian_export.main(argv))


def cmd_project_new(args):
    if args.from_outline:
        outline = _import_module("outline_to_nodes")
        sys.exit(outline.main(
            outline_path=args.from_outline,
            project_id=args.project_id,
            repo=args.repo,
            project_name=args.project_name,
            dry_run=args.dry_run,
            force=args.force,
        ))
    elif args.from_graphify:
        graphify = _import_module("graphify_to_nodes")
        sys.argv = [
            "graphify_to_nodes",
            "--input", str(args.from_graphify),
            "--project-id", args.project_id,
            "--repo", args.repo or "",
        ]
        if args.project_name:
            sys.argv.extend(["--project-name", args.project_name])
        if args.dry_run:
            sys.argv.append("--dry-run")
        if args.force:
            sys.argv.append("--force")
        sys.exit(graphify.main())
    else:
        rapid = _import_module("rapid_add")
        rapid.ensure_project_shell(ROOT, args.project_id, args.repo, args.project_name)
        print(f"Created empty project: graphs/{args.project_id}/")
        print(f"Next: gddp node rapid --project {args.project_id} --repo {args.repo}")


def cmd_project_validate(args):
    validate_project(args.project)


def show_status():
    graphs = ROOT / "graphs"
    if not graphs.exists():
        print("No graphs/ directory found")
        return

    projects = sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )

    total_complete = 0
    total_pending = 0
    total_other = 0

    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}
        nodes = proj.get("nodes", [])
        counts = {}
        for n in nodes:
            s = n.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
            if s == "complete":
                total_complete += 1
            elif s == "pending":
                total_pending += 1
            else:
                total_other += 1

        name = proj.get("project_name", pid)
        parts = [f"{s}={c}" for s, c in sorted(counts.items())]
        total = len(nodes)
        complete_count = counts.get("complete", 0)
        pct = int(complete_count / total * 100) if total else 0
        print(f"{pid:<25} {total:>3} nodes  {pct:>3}% done  ({', '.join(parts)})")

    grand = total_complete + total_pending + total_other
    gpct = int(total_complete / grand * 100) if grand else 0
    print(f"\n{'TOTAL':<25} {grand:>3} nodes  {gpct:>3}% done")


def validate_project(project_id: str | None):
    graphs = ROOT / "graphs"
    if not graphs.exists():
        print("No graphs/ directory found")
        return

    projects = sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )
    if project_id:
        if project_id not in projects:
            print(f"Project '{project_id}' not found")
            return
        projects = [project_id]

    errors = 0
    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}

        pid_errors = []

        if proj.get("schema_version") != "1.0":
            pid_errors.append("schema_version != 1.0")
        if not proj.get("project_id"):
            pid_errors.append("missing project_id")
        if proj.get("project_id") != pid:
            pid_errors.append(f"project_id '{proj.get('project_id')}' != directory '{pid}'")
        if not proj.get("repo"):
            pid_errors.append("missing repo")
        nodes = proj.get("nodes")
        if not isinstance(nodes, list):
            pid_errors.append("nodes is not a list")
        else:
            node_ids = set()
            for n in nodes:
                if not isinstance(n, dict):
                    pid_errors.append(f"nodes entry is not a dict: {n}")
                    continue
                nid = n.get("id")
                if not nid:
                    pid_errors.append("nodes entry missing id")
                    continue
                if nid in node_ids:
                    pid_errors.append(f"duplicate node id in project.yaml: {nid}")
                node_ids.add(nid)

            nodes_dir = graphs / pid / "nodes"
            yaml_ids = set()
            if nodes_dir.exists():
                yaml_ids = {p.stem for p in nodes_dir.glob("*.yaml")}

            missing_yaml = node_ids - yaml_ids
            orphan_yaml = yaml_ids - node_ids
            if missing_yaml:
                for nid in sorted(missing_yaml):
                    pid_errors.append(f"project.yaml lists {nid} but no nodes/{nid}.yaml exists")
            if orphan_yaml:
                for nid in sorted(orphan_yaml):
                    pid_errors.append(f"nodes/{nid}.yaml exists but not listed in project.yaml")

        if pid_errors:
            print(f"[red]{pid}[/red]")
            for e in pid_errors:
                print(f"  ERROR: {e}")
            errors += len(pid_errors)
        else:
            print(f"[green]{pid}[/green] OK")

    print(f"\n{errors} error(s) across {len(projects)} project(s)")
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="gddp — graph truth and runtime evidence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=cmd_overview)
    sub = parser.add_subparsers(dest="command")

    node_p = sub.add_parser("node", help="Node operations")
    node_sub = node_p.add_subparsers(dest="subcommand")

    node_new = node_sub.add_parser("new", help="Interactive TUI node scaffold (full editor)")
    node_new.set_defaults(func=cmd_node_new)

    node_rapid = node_sub.add_parser("rapid", help="Minimal-keystroke rapid node adder")
    node_rapid.add_argument("--project", required=True, help="Project ID")
    node_rapid.add_argument("--repo", default="")
    node_rapid.add_argument("--project-name", default=None)
    node_rapid.add_argument("--llm-draft", action="store_true",
                            help="Use LLM to draft why/acceptance/constraints")
    node_rapid.add_argument("--dry-run", action="store_true")
    node_rapid.set_defaults(func=cmd_node_rapid)

    node_batch = node_sub.add_parser("batch", help="Walk through REPLACE_ME nodes in a project")
    node_batch.add_argument("--project", required=True, help="Project ID")
    node_batch.set_defaults(func=cmd_node_batch)

    node_import = node_sub.add_parser("import", help="Import node YAML from file or stdin")
    node_import.add_argument("--file", type=Path, default=None, help="YAML file to import")
    node_import.add_argument("--stdin", action="store_true", help="Read YAML from stdin")
    node_import.add_argument("--project", required=True, help="Project ID")
    node_import.add_argument("--auto-approve", action="store_true")
    node_import.add_argument("--dry-run", action="store_true")
    node_import.set_defaults(func=cmd_node_import)

    node_val = node_sub.add_parser("validate", help="Validate nodes")
    node_val.add_argument("--project", default=None, help="Only check this project")
    node_val.add_argument("--json", action="store_true", help="Machine-readable output")
    node_val.add_argument("--strict", action="store_true", help="Warnings count as errors")
    node_val.add_argument("--quiet", action="store_true", help="Only summary line")
    node_val.add_argument("--root", type=Path, default=None)
    node_val.set_defaults(func=cmd_node_validate)

    node_list = node_sub.add_parser(
        "list", help="List nodes (ID | GRAPH | RUNTIME | VERDICT)")
    node_list.add_argument("--project", default=None, help="Project ID (omit for all)")
    node_list.add_argument("--status", default=None, help="Filter by graph status")
    node_list.add_argument(
        "--active", action="store_true",
        help="Only graph status pending or ready",
    )
    node_list.set_defaults(func=cmd_node_list)

    node_show = node_sub.add_parser(
        "show", help="Show one node + evaluator summary")
    node_show.add_argument("--project", required=True, help="Project ID")
    node_show.add_argument("node_id", help="Node ID")
    node_show.add_argument(
        "--trace", action="store_true",
        help="Expand tool traces and result/job history",
    )
    node_show.set_defaults(func=cmd_node_show)

    node_set = node_sub.add_parser(
        "set-status",
        help="Set graph status on node YAML + project.yaml (human-owned)",
    )
    node_set.add_argument("--project", required=True, help="Project ID")
    node_set.add_argument("node_id", help="Node ID")
    node_set.add_argument(
        "status", help="Graph status: pending | ready | complete | deferred")
    node_set.add_argument("--yes", action="store_true", help="Skip confirmation")
    node_set.add_argument("--reason", default=None, help="Reason (printed only)")
    node_set.set_defaults(func=cmd_node_set_status)

    node_status = node_sub.add_parser("status", help="Status summary for all projects")
    node_status.set_defaults(func=cmd_node_status)

    jobs_p = sub.add_parser("jobs", help="Runtime jobs and evaluator evidence")
    jobs_p.set_defaults(func=cmd_jobs)
    jobs_sub = jobs_p.add_subparsers(dest="jobs_command")

    jobs_list = jobs_sub.add_parser("list", help="List jobs and queue states")
    jobs_list.add_argument("--state", default=None, help="Filter by queue state")
    jobs_list.set_defaults(func=cmd_jobs)

    jobs_show = jobs_sub.add_parser("show", help="Show one job by job ID or node ID")
    jobs_show.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_show.add_argument("--full", action="store_true", help="Include full integrity reasoning")
    jobs_show.set_defaults(func=cmd_jobs)

    jobs_results = jobs_sub.add_parser("results", help="Summarize evaluator output")
    jobs_results.add_argument("--all", action="store_true", help="List every result row")
    jobs_results.set_defaults(func=cmd_jobs)

    jobs_set = jobs_sub.add_parser("set", help="Change runtime queue state")
    jobs_set.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_set.add_argument("state", help="New runtime queue state")
    jobs_set.add_argument("--reason", required=True, help="Why; stored in the runtime audit row")
    jobs_set.add_argument("--yes", action="store_true", help="Skip runtime confirmation")
    jobs_set.set_defaults(func=cmd_jobs)

    verify_p = sub.add_parser("verify", help="Node evaluation harness")
    verify_sub = verify_p.add_subparsers(dest="subcommand")

    verify_node = verify_sub.add_parser(
        "node", help="Run deterministic node evaluation; emit a receipt")
    verify_node.add_argument("--project", required=True, help="Project ID")
    verify_node.add_argument("--node", required=True, help="Node ID")
    verify_node.add_argument("--repo-path", default=None,
                             help="Path to the source repo checkout "
                                  "(overrides auto-resolve)")
    verify_node.add_argument("--json", action="store_true",
                             help="Print result.json to stdout")
    verify_node.set_defaults(func=cmd_verify_node)

    obs_p = sub.add_parser("obsidian", help="Obsidian vault export")
    obs_sub = obs_p.add_subparsers(dest="subcommand")

    obs_export = obs_sub.add_parser(
        "export", help="Export one graph to an Obsidian vault folder")
    obs_export.add_argument("--project", required=True,
                            help="Graph to export (graphs/<project>/)")
    obs_export.add_argument("--vault", type=Path, default=None,
                            help="Destination vault (default: ~/Obsidian/gdd-<project>)")
    obs_export.add_argument("--dry-run", action="store_true")
    obs_export.set_defaults(func=cmd_obsidian_export)

    proj_p = sub.add_parser("project", help="Project operations")
    proj_sub = proj_p.add_subparsers(dest="subcommand")

    proj_new = proj_sub.add_parser("new", help="Create project skeleton")
    proj_new.add_argument("--project-id", required=True, help="kebab-case project id")
    proj_new.add_argument("--project-name", default=None, help="Display name")
    proj_new.add_argument("--repo", default="")
    source = proj_new.add_mutually_exclusive_group(required=False)
    source.add_argument("--from-outline", type=Path, default=None, help="Markdown outline file")
    source.add_argument("--from-graphify", type=Path, default=None, help="graphify-out/graph.json file")
    proj_new.add_argument("--dry-run", action="store_true")
    proj_new.add_argument("--force", action="store_true")
    proj_new.set_defaults(func=cmd_project_new)

    proj_val = proj_sub.add_parser("validate", help="Validate project.yaml files")
    proj_val.add_argument("--project", default=None, help="Project ID (omit for all)")
    proj_val.set_defaults(func=cmd_project_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
