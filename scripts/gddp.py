#!/usr/bin/env python3
"""gddp — unified CLI for gddp-config graph node management.

Subcommands:
    node new          Interactive TUI node scaffold (full field editor)
    node rapid        Minimal-keystroke rapid node adder
    node batch        Walk through pending/REPLACE_ME nodes in a project
    node import       Import a node YAML from file or stdin (agent pipeline)
    node validate     Validate all nodes (or one project)
    node list         List nodes in a project
    node status       Show status summary for all projects

    verify node       Run deterministic node evaluation; emit a receipt

    project new       Create project skeleton (from graphify, outline, or empty shell)
    project validate  Validate project.yaml structure

Usage:
    python3 scripts/gddp.py node rapid --project my-app --repo org/repo
    python3 scripts/gddp.py node validate --project vault-doctor
    python3 scripts/gddp.py node import --file draft.yaml --project my-app
    python3 scripts/gddp.py node batch --project my-greenfield
    python3 scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Install deps:  pip install pyyaml rich")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent


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
    list_nodes(args.project)


def cmd_node_status(args):
    show_status()


def cmd_verify_node(args):
    verify_node = _import_module("verify_node")
    argv = ["node", "--project", args.project, "--node", args.node]
    if args.repo_path:
        argv += ["--repo-path", args.repo_path]
    if args.json:
        argv += ["--json"]
    sys.exit(verify_node.main(argv))


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


def list_nodes(project_id: str | None):
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
            print(f"Project '{project_id}' not found. Available: {', '.join(projects)}")
            return
        projects = [project_id]

    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}
        nodes = proj.get("nodes", [])
        name = proj.get("project_name", pid)
        print(f"\n[bold cyan]{pid}[/bold cyan] ({name}) — {len(nodes)} nodes")
        if not nodes:
            print("  (none)")
            continue
        for n in nodes:
            nid = n.get("id", "?")
            title = n.get("title", "")
            status = n.get("status", "?")
            ntype = n.get("type", "")
            print(f"  [{status:<10}] {nid:<40} {ntype}  {title}")


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


def main():
    parser = argparse.ArgumentParser(
        description="gddp — graph node management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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

    node_list = node_sub.add_parser("list", help="List nodes in a project")
    node_list.add_argument("--project", default=None, help="Project ID (omit for all)")
    node_list.set_defaults(func=cmd_node_list)

    node_status = node_sub.add_parser("status", help="Status summary for all projects")
    node_status.set_defaults(func=cmd_node_status)

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

    args = parser.parse_args()

    if not args.command or not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
