#!/usr/bin/env python3
"""enrich_graph.py — post-process graphify output to embed GDDP node metadata.

Takes a graphify-out/graph.json and adds status/priority/type/why/etc. to each
node that corresponds to one of our node YAML files. Writes the enriched graph
to graphify-out/graph-enriched.json (doesn't clobber graphify's output).

Why: graphify extracts the graph skeleton from existing code, but drops the
per-node semantics. This puts the semantics back so visualizers (like the
Lovable inspect-graph app) can color/filter/annotate by status, priority,
type, etc. The detail panel also benefits immediately — clicking a node will
show its `why`, acceptance count, and execution metadata.

Field naming (top-level on each node dict):
  status, priority            — direct from YAML, viz can color by these
  node_type                   — our type (capability/milestone/constraint);
                                named to avoid collision with graphify's
                                existing `file_type` field
  gddp_node_id                — our kebab-case ID
  why                         — short description for detail panels
  depends_on_count, unlocks_count,
  acceptance_count, constraints_count,
  required_artifacts_count    — numeric fields useful for sizing/coloring

For project.yaml-representing nodes, also adds:
  project_id, description, repo, node_count

Self-contained — no imports from other scripts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Install: pip install pyyaml")
    sys.exit(1)


# Direct field copies (yaml_key -> graphify_field_name).
# Renames avoid collisions with graphify's native fields.
NODE_ENRICH_FIELDS = {
    "status": "status",
    "priority": "priority",
    "type": "node_type",         # graphify already uses `file_type`
    "node_id": "gddp_node_id",   # our kebab ID
    "why": "why",
}

# List fields become counts (useful for sizing/coloring in viz).
NODE_COUNT_FIELDS = {
    "depends_on": "depends_on_count",
    "unlocks": "unlocks_count",
    "acceptance": "acceptance_count",
    "constraints": "constraints_count",
    "required_artifacts": "required_artifacts_count",
}

# Fields we lift from project.yaml onto project-graph nodes.
PROJECT_ENRICH_FIELDS = {
    "project_id": "project_id",
    "description": "description",
    "repo": "repo",
}


def is_node_yaml(source_file: str | None) -> bool:
    if not source_file:
        return False
    return "/nodes/" in source_file and source_file.endswith(".yaml")


def is_project_yaml(source_file: str | None) -> bool:
    if not source_file:
        return False
    # Accept both "graphs/..." and "/graphs/..." (relative vs absolute paths)
    return source_file.endswith("project.yaml") and "graphs/" in source_file


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def enrich_node(graphify_node: dict, root: Path) -> dict:
    """Return a new node dict with GDDP metadata merged in (does not mutate input)."""
    sf = graphify_node.get("source_file")
    enriched = dict(graphify_node)

    if is_node_yaml(sf):
        yaml_path = root / sf
        if yaml_path.exists():
            doc = load_yaml(yaml_path)
            for yaml_key, field_name in NODE_ENRICH_FIELDS.items():
                if yaml_key in doc:
                    enriched[field_name] = doc[yaml_key]
            for yaml_key, field_name in NODE_COUNT_FIELDS.items():
                val = doc.get(yaml_key)
                if isinstance(val, list):
                    enriched[field_name] = len(val)
            # Allowed execution modes as a list (useful for filtering)
            modes = doc.get("allowed_execution_modes")
            if isinstance(modes, list):
                enriched["execution_modes"] = modes
            # Required artifacts as a list (detail panel)
            artifacts = doc.get("required_artifacts")
            if isinstance(artifacts, list):
                enriched["required_artifacts"] = artifacts

    elif is_project_yaml(sf):
        yaml_path = root / sf
        if yaml_path.exists():
            doc = load_yaml(yaml_path)
            for yaml_key, field_name in PROJECT_ENRICH_FIELDS.items():
                if yaml_key in doc:
                    enriched[field_name] = doc[yaml_key]
            nodes = doc.get("nodes")
            if isinstance(nodes, list):
                enriched["node_count"] = len(nodes)

    return enriched


def enrich_graph(graph: dict, root: Path) -> dict:
    """Return a new graph dict with all nodes enriched. Does not mutate input."""
    new_graph = dict(graph)
    new_graph["nodes"] = [enrich_node(n, root) for n in graph.get("nodes", [])]
    # Mark the graph so consumers can detect enrichment
    metadata = new_graph.setdefault("graph", {})
    if isinstance(metadata, dict):
        metadata["gddp_enriched"] = True
    return new_graph


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path,
                        default=Path("graphify-out/graph.json"),
                        help="Input graphify graph.json (default: graphify-out/graph.json)")
    parser.add_argument("--output", type=Path,
                        default=Path("graphify-out/graph-enriched.json"),
                        help="Output path (default: graphify-out/graph-enriched.json)")
    parser.add_argument("--root", type=Path, default=None,
                        help="gddp-config root (default: parent of scripts/)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output file")
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent

    if not args.input.exists():
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        return 1
    if args.output.exists() and not args.force:
        print(f"ERROR: {args.output} exists. Use --force to overwrite.",
              file=sys.stderr)
        return 1

    try:
        graph = json.loads(args.input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {args.input}: {e}", file=sys.stderr)
        return 1

    enriched = enrich_graph(graph, root)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(enriched, indent=2, default=str),
        encoding="utf-8",
    )

    # Stats
    node_yaml_count = sum(1 for n in enriched["nodes"]
                          if is_node_yaml(n.get("source_file")))
    project_yaml_count = sum(1 for n in enriched["nodes"]
                             if is_project_yaml(n.get("source_file")))

    print(f"WROTE {args.output}")
    print(f"  Total nodes:        {len(enriched['nodes'])}")
    print(f"  Node YAMLs enriched:  {node_yaml_count}  "
          f"(status/priority/node_type/why/counts)")
    print(f"  Project YAMLs enriched: {project_yaml_count}  "
          f"(project_id/description/repo/node_count)")
    print()
    print(f"Load {args.output.name} in your viz tool to see the extra fields.")
    print(f"To refresh after graphify update: re-run this script with --force.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
