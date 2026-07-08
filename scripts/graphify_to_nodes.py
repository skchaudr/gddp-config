#!/usr/bin/env python3
"""graphify_to_nodes.py — bootstrap a GDDP project skeleton from a graphify graph.json.

Takes any graphify-out/graph.json and emits a starter graphs/<project-id>/ with
project.yaml + nodes/*.yaml. Node edges (depends_on, unlocks) are lifted from
graphify's extracted edges; semantic fields (why, acceptance, constraints) are
left as REPLACE_ME placeholders for human authoring.

Why this exists: graphify extracts a graph skeleton from an existing codebase,
but cannot infer execution semantics (what counts as done, what's allowed).
This tool does the mechanical translation; the human does the meaning.

Self-contained — no imports from validate.py or new_node.py.

Usage:
    python3 scripts/graphify_to_nodes.py \\
        --input graphify-out/graph.json \\
        --project-id my-project \\
        --repo org/repo \\
        --dry-run

Filter modes:
    smart       (default) one node per source_file + concept nodes; drops
                rationale and intra-file symbols (functions/classes/methods)
    files       one node per source_file, no concepts
    documents   only graphify file_type=document
    all         every graphify node (will be noisy)
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Install: pip install pyyaml")
    sys.exit(1)


# ── Schema constants (mirror schemas/v1/node.yaml) ─────────────────────────

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

# Common graphify ID suffixes that describe the _kind_ of node, not its identity.
# Stripped during slugification.
ID_SUFFIXES_TO_STRIP = (
    "_node_file", "_project_file", "_schema_file", "_template_file",
    "_doc", "_doc_file", "_rules_doc",
    "_repo", "_path_env", "_root_env", "_token_env", "_url_env", "_env",
    "_concept", "_policy", "_system",
)

# graphify edge relations we recognize as project-level structure.
DEPENDS_ON_RELATIONS = {"depends_on"}
UNLOCKS_RELATIONS = {"unlocks"}
# All other relations (calls, references, contains, method, rationale_for,
# describes, defines, conceptually_related_to) are dropped — too granular or
# too inferential for a project node graph.


def slugify(graphify_id: str, label: str) -> str:
    """Convert a graphify node ID + label to a kebab-case node_id."""
    s = graphify_id
    for suffix in ID_SUFFIXES_TO_STRIP:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    s = s.replace("_", "-").lower()
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if s and KEBAB_RE.match(s):
        return s
    # Fallback: slugify the label
    fallback = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if fallback and KEBAB_RE.match(fallback):
        return fallback
    # Last resort
    return f"node-{hash(graphify_id) % 10000:04d}"


def representative_node_for_file(candidates: list[dict], source_file: str) -> dict:
    """When multiple graphify nodes share a source_file, pick the most file-like.

    Preference order:
      1. file_type=document (the doc itself)
      2. label matches the file's basename (e.g., "ag_natural_guard.py")
      3. file_type=code (the file as a whole, vs its inner symbols)
      4. first candidate (deterministic fallback)
    """
    basename = Path(source_file).name
    for n in candidates:
        if n.get("file_type") == "document":
            return n
    for n in candidates:
        if n.get("label") == basename:
            return n
    for n in candidates:
        if n.get("file_type") == "code":
            return n
    return candidates[0]


def filter_nodes(nodes: list[dict], mode: str, max_nodes: int) -> list[dict]:
    """Pick which graphify nodes become our nodes."""
    if mode == "all":
        result = list(nodes)
    elif mode == "documents":
        result = [n for n in nodes if n.get("file_type") == "document"]
    elif mode == "files":
        # Group by source_file, pick representative
        by_file: dict[str, list[dict]] = defaultdict(list)
        for n in nodes:
            sf = n.get("source_file")
            if sf:
                by_file[sf].append(n)
        result = [representative_node_for_file(group, sf) for sf, group in by_file.items()]
    else:  # "smart" (default)
        # Files (collapsed) + concept nodes; drop rationale entirely
        by_file: dict[str, list[dict]] = defaultdict(list)
        concepts = []
        for n in nodes:
            ft = n.get("file_type")
            if ft == "rationale":
                continue
            if ft == "concept":
                concepts.append(n)
                continue
            sf = n.get("source_file")
            if sf:
                by_file[sf].append(n)
        result = [representative_node_for_file(group, sf) for sf, group in by_file.items()]
        result.extend(concepts)

    if max_nodes and len(result) > max_nodes:
        result = result[:max_nodes]
    return result


def build_edge_maps(links: list[dict], included_ids: set[str]) -> tuple[dict, dict]:
    """Return (depends_on_map, unlocks_map): graphify_id -> list of graphify_ids.

    Only edges where BOTH endpoints are in included_ids are kept. Multiple edges
    between the same pair collapse to one (set semantics).
    """
    depends: dict[str, set[str]] = defaultdict(set)
    unlocks: dict[str, set[str]] = defaultdict(set)
    for link in links:
        rel = link.get("relation")
        src = link.get("source")
        tgt = link.get("target")
        if not src or not tgt:
            continue
        if src not in included_ids or tgt not in included_ids:
            continue
        if rel in DEPENDS_ON_RELATIONS:
            depends[src].add(tgt)
        elif rel in UNLOCKS_RELATIONS:
            unlocks[src].add(tgt)
    return (
        {k: sorted(v) for k, v in depends.items()},
        {k: sorted(v) for k, v in unlocks.items()},
    )


def make_node_dict(node_id: str, title: str,
                   depends_on: list[str], unlocks: list[str]) -> dict:
    """Build a node dict with REPLACE_ME placeholders for human-only fields."""
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node_id,
        "title": title,
        "type": "capability",
        "why": "REPLACE_ME",
        "depends_on": depends_on,
        "acceptance_criteria": ["REPLACE_ME"],
        "constraints": ["REPLACE_ME"],
        "allowed_execution_modes": ["jules"],
        "required_artifacts": ["decision.md", "result-summary.md", "graph-update.yaml"],
        "status": "pending",
        "priority": "medium",
        "unlocks": unlocks,
    }


def render_node_yaml(node: dict) -> str:
    """Mirror templates/node-template.yaml field order."""
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
        "project_name": project_name,
        "description": "REPLACE_ME — bootstrapped from graphify; needs human framing",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path, required=True,
                        help="Path to graphify-out/graph.json")
    parser.add_argument("--project-id", required=True,
                        help="kebab-case project id")
    parser.add_argument("--project-name", default=None,
                        help="Display name (default: same as --project-id)")
    parser.add_argument("--repo", default="",
                        help="org/repo (e.g., skchaudr/vault-doctor)")
    parser.add_argument("--filter", choices=["smart", "files", "documents", "all"],
                        default="smart",
                        help="Node selection heuristic (default: smart)")
    parser.add_argument("--max-nodes", type=int, default=0,
                        help="Cap on nodes emitted (0 = no cap)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created; don't write any files")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing project directory")
    parser.add_argument("--root", type=Path, default=None,
                        help="gddp-config root (default: parent of scripts/)")
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent

    # Load graphify graph
    try:
        graph = json.loads(args.input.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: {args.input} is not valid JSON: {e}", file=sys.stderr)
        return 1

    nodes = graph.get("nodes", [])
    links = graph.get("links", [])
    if not nodes:
        print(f"ERROR: no nodes found in {args.input}", file=sys.stderr)
        return 1

    # Filter
    included = filter_nodes(nodes, args.filter, args.max_nodes)
    included_ids = {n["id"] for n in included}

    # Build slug map (handle collisions with -2, -3, ...)
    slug_map: dict[str, str] = {}
    used_slugs: set[str] = set()
    for n in included:
        slug = slugify(n["id"], n.get("label", n["id"]))
        if slug in used_slugs:
            i = 2
            while f"{slug}-{i}" in used_slugs:
                i += 1
            slug = f"{slug}-{i}"
        slug_map[n["id"]] = slug
        used_slugs.add(slug)

    # Build edges (between graphify IDs, mapped through slug)
    depends_raw, unlocks_raw = build_edge_maps(links, included_ids)
    depends_on_map = {gid: [slug_map[t] for t in targets if t in slug_map]
                      for gid, targets in depends_raw.items()}
    unlocks_map = {gid: [slug_map[t] for t in targets if t in slug_map]
                   for gid, targets in unlocks_raw.items()}

    project_dir = root / "graphs" / args.project_id
    total_depends = sum(len(v) for v in depends_on_map.values())
    total_unlocks = sum(len(v) for v in unlocks_map.values())

    # Dry-run preview
    if args.dry_run:
        print(f"=== DRY RUN · project={args.project_id} filter={args.filter} ===")
        print(f"Graphify input: {len(nodes)} nodes, {len(links)} links")
        print(f"Included:       {len(included)} nodes")
        print(f"Edges kept:     depends_on={total_depends}  unlocks={total_unlocks}")
        print(f"Target dir:     {project_dir}/")
        print()
        print("Nodes:")
        for n in included:
            slug = slug_map[n["id"]]
            d = depends_on_map.get(n["id"], [])
            u = unlocks_map.get(n["id"], [])
            sf = n.get("source_file") or "(concept)"
            ft = n.get("file_type", "?")
            print(f"  [{ft:<5}] {slug}")
            print(f"          title:    {n.get('label', n['id'])}")
            print(f"          source:   {sf}")
            if d:
                print(f"          depends_on: {d}")
            if u:
                print(f"          unlocks:    {u}")
        print()
        print("To write for real, re-run without --dry-run.")
        return 0

    # Existing-dir check
    if project_dir.exists() and any(project_dir.iterdir()):
        if not args.force:
            print(f"ERROR: {project_dir} exists and is non-empty.", file=sys.stderr)
            print("       Use --force to overwrite, or pick a different --project-id.",
                  file=sys.stderr)
            return 1

    # Write
    nodes_dir = project_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    node_index = []
    for n in included:
        slug = slug_map[n["id"]]
        node_dict = make_node_dict(
            node_id=slug,
            title=n.get("label", slug),
            depends_on=depends_on_map.get(n["id"], []),
            unlocks=unlocks_map.get(n["id"], []),
        )
        (nodes_dir / f"{slug}.yaml").write_text(
            render_node_yaml(node_dict), encoding="utf-8"
        )
        node_index.append({
            "id": slug,
            "title": node_dict["title"],
            "status": "pending",
            "type": "capability",
        })

    project_yaml_text = render_project_yaml(
        project_id=args.project_id,
        project_name=args.project_name or args.project_id,
        repo=args.repo,
        node_index=node_index,
    )
    (project_dir / "project.yaml").write_text(project_yaml_text, encoding="utf-8")

    # Summary
    print(f"WROTE {project_dir.relative_to(root)}/")
    print(f"  project.yaml")
    print(f"  nodes/  ({len(node_index)} nodes)")
    print(f"    depends_on edges preserved: {total_depends}")
    print(f"    unlocks edges preserved:    {total_unlocks}")
    print()
    print("Next steps:")
    print(f"  1. Edit {project_dir.relative_to(root)}/project.yaml — fill description, vision, repo")
    print(f"  2. Walk {project_dir.relative_to(root)}/nodes/*.yaml — replace REPLACE_ME placeholders")
    print(f"     (why, acceptance, constraints are human-only fields)")
    print(f"  3. Validate: .venv/bin/python scripts/validate.py --project {args.project_id}")
    print(f"  4. Consider promoting high-degree nodes to type: milestone")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
