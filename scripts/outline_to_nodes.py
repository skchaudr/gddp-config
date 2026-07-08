#!/usr/bin/env python3
"""outline_to_nodes.py — convert a markdown outline into GDDP project skeleton.

Takes a simple markdown outline with node names and dependency edges,
produces a graphs/<project-id>/ skeleton with project.yaml + node YAMLs.

Outline format:
    # my-app

    ## Phase 1: Foundation

    - [ ] scan-vault-core
    - [ ] find-duplicates -> scan-vault-core
    - [ ] find-stale-todos -> scan-vault-core
    - [ ] check-performance -> scan-vault-core

    ## Phase 2: Surface

    - [ ] performance-dashboard -> check-performance
    - [ ] triage-cli-core -> find-duplicates, find-stale-todos, check-performance

    - [x] already-done-node

Rules:
    - `- [ ] node-name` creates a pending node (title derived from kebab-case)
    - `- [x] node-name` creates a complete node
    - `-> dep1, dep2` after node name declares depends_on (kebab-case, comma-separated)
    - `## heading` sections are purely organizational (not nodes)
    - `# heading` is the project name (optional, falls back to --project-id)
    - `- node-name` (no checkbox) also works, treated as pending
    - Indentation is ignored
    - Lines that don't start with - are ignored (comments, blank, etc.)

Self-contained — schema constants inline.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Install: pip install pyyaml")
    sys.exit(1)


KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
DEFAULT_ARTIFACTS = ["decision.md", "result-summary.md", "graph-update.yaml"]

ITEM_RE = re.compile(
    r"^\s*-"
    r"\s*\[(?P<checkbox>[ xX])\]?"
    r"\s*(?P<id>[a-zA-Z][a-zA-Z0-9_-]*)"
    r"(?:\s*->\s*(?P<deps>[a-zA-Z][a-zA-Z0-9_\-,\s]*))?"
    r"\s*$"
)

PROJECT_RE = re.compile(r"^#\s+(?P<name>.+)")


def kebab_to_title(node_id: str) -> str:
    return node_id.replace("-", " ").title()


def parse_outline(text: str) -> dict:
    """Parse outline markdown into structured data.

    Returns:
        {
            "project_name": str or None,
            "nodes": [
                {"id": str, "title": str, "status": str, "depends_on": [str]},
                ...
            ]
        }
    """
    project_name = None
    nodes = []
    seen_ids = set()

    for line in text.splitlines():
        stripped = line.strip()

        proj_match = PROJECT_RE.match(stripped)
        if proj_match:
            project_name = proj_match.group("name").strip()
            continue

        item_match = ITEM_RE.match(stripped)
        if not item_match:
            continue

        nid = item_match.group("id").lower().strip()
        if not KEBAB_RE.match(nid):
            print(f"WARN: skipping non-kebab-case id: {nid!r}", file=sys.stderr)
            continue

        if nid in seen_ids:
            print(f"WARN: duplicate node id: {nid!r}", file=sys.stderr)
            continue
        seen_ids.add(nid)

        checkbox = item_match.group("checkbox")
        status = "complete" if checkbox and checkbox.lower() == "x" else "pending"

        deps_str = item_match.group("deps") or ""
        deps = [d.strip().lower() for d in deps_str.split(",") if d.strip()]

        nodes.append({
            "id": nid,
            "title": kebab_to_title(nid),
            "status": status,
            "depends_on": deps,
        })

    return {"project_name": project_name, "nodes": nodes}


def make_node_dict(node: dict, deps_resolved: list[str]) -> dict:
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node["id"],
        "title": node["title"],
        "type": "capability",
        "why": "REPLACE_ME",
        "depends_on": deps_resolved,
        "acceptance_criteria": ["REPLACE_ME"],
        "constraints": ["REPLACE_ME"],
        "allowed_execution_modes": ["jules"],
        "required_artifacts": list(DEFAULT_ARTIFACTS),
        "status": node["status"],
        "priority": "medium",
        "unlocks": [],
    }


def render_node_yaml(node: dict) -> str:
    field_order = [
        "schema_version", "schema_type",
        "node_id", "title", "type", "why",
        "depends_on", "acceptance_criteria", "constraints",
        "allowed_execution_modes", "required_artifacts",
        "status", "priority", "unlocks",
    ]
    ordered = {k: node[k] for k in field_order if k in node}
    return yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)


def render_project_yaml(project_id: str, project_name: str, repo: str,
                         node_index: list[dict]) -> str:
    today = datetime.date.today().isoformat()
    project = {
        "schema_version": "1.0",
        "schema_type": "project_graph",
        "project_id": project_id,
        "project_name": project_name or project_id,
        "description": "REPLACE_ME",
        "repo": repo or "REPLACE_ME",
        "blueprint": {
            "vision": "REPLACE_ME",
            "architecture_notes": "REPLACE_ME",
            "major_capabilities": ["REPLACE_ME"],
        },
        "graph_version": "1.0",
        "created_at": today,
        "last_updated": today,
        "nodes_dir": "nodes/",
        "nodes": node_index,
        "execution_policy": {
            "default_executor": "jules",
            "max_concurrent_jobs": 1,
            "require_human_review_before_overnight": True,
            "artifact_gate_enforced": True,
        },
    }
    return yaml.dump(project, default_flow_style=False, sort_keys=False, allow_unicode=True)


def resolve_deps(nodes: list[dict]) -> dict[str, list[str]]:
    """Validate and return node_id -> [depends_on] using only known node ids."""
    known = {n["id"] for n in nodes}
    result = {}
    for n in nodes:
        valid = [d for d in n["depends_on"] if d in known]
        missing = set(n["depends_on"]) - known
        if missing:
            print(f"WARN: {n['id']} depends on unknown: {missing}", file=sys.stderr)
        result[n["id"]] = valid
    return result


def main(outline_path=None, project_id=None, repo=None, project_name=None,
         dry_run=False, force=False, root=None) -> int:
    if outline_path and isinstance(outline_path, Path):
        path = outline_path
    else:
        path = Path(outline_path) if outline_path else None

    if not path or not path.exists():
        print(f"ERROR: outline file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    parsed = parse_outline(text)

    if not parsed["nodes"]:
        print("ERROR: no nodes found in outline", file=sys.stderr)
        return 1

    proj_name = project_name or parsed["project_name"] or project_id

    deps_map = resolve_deps(parsed["nodes"])
    root = root or Path(__file__).resolve().parent.parent
    project_dir = root / "graphs" / project_id

    if dry_run:
        print(f"=== DRY RUN · project={project_id} ===")
        print(f"Nodes: {len(parsed['nodes'])}")
        print(f"Target: {project_dir}/")
        print()
        for n in parsed["nodes"]:
            deps = deps_map.get(n["id"], [])
            status_marker = "[x]" if n["status"] == "complete" else "[ ]"
            print(f"  {status_marker} {n['id']:<40} {n['title']}")
            if deps:
                print(f"       depends_on: {deps}")
        print(f"\nTo write: re-run without --dry-run")
        return 0

    if project_dir.exists() and any(project_dir.iterdir()):
        if not force:
            print(f"ERROR: {project_dir} exists and is non-empty.", file=sys.stderr)
            print("       Use --force to overwrite.", file=sys.stderr)
            return 1

    nodes_dir = project_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    node_index = []
    for n in parsed["nodes"]:
        deps = deps_map.get(n["id"], [])
        node_dict = make_node_dict(n, deps)
        (nodes_dir / f"{n['id']}.yaml").write_text(
            render_node_yaml(node_dict), encoding="utf-8"
        )
        node_index.append({
            "id": n["id"],
            "title": n["title"],
            "status": n["status"],
            "type": "capability",
        })

    proj_yaml_text = render_project_yaml(project_id, proj_name, repo, node_index)
    (project_dir / "project.yaml").write_text(proj_yaml_text, encoding="utf-8")

    print(f"WROTE {project_dir.relative_to(root)}/")
    print(f"  project.yaml")
    print(f"  nodes/  ({len(node_index)} nodes)")
    replace_me_count = sum(1 for n in parsed["nodes"] if n["status"] != "complete")
    print(f"  {replace_me_count} node(s) need human fields (why, acceptance, constraints)")
    print()
    print("Next steps:")
    print(f"  1. python3 scripts/gddp.py node batch --project {project_id}")
    print(f"  2. python3 scripts/gddp.py node validate --project {project_id}")
    print(f"  3. python3 scripts/gddp.py project validate --project {project_id}")

    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("outline_path", type=Path, help="Markdown outline file")
    p.add_argument("--project-id", required=True)
    p.add_argument("--project-name", default=None)
    p.add_argument("--repo", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    sys.exit(main(
        outline_path=args.outline_path,
        project_id=args.project_id,
        project_name=args.project_name,
        repo=args.repo,
        dry_run=args.dry_run,
        force=args.force,
    ))
