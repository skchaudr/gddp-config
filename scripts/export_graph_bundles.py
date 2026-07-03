#!/usr/bin/env python3
"""Export one shareable YAML bundle per project graph.

Reads graphs/<project-id>/project.yaml plus graphs/<project-id>/nodes/*.yaml and
writes a single expanded YAML file that is easier to share than a directory of
per-node files.

Output format:
  graphify-out/shareable-graphs/<project-id>.yaml

The bundle is derived data only. It is not used by validation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("This script needs `pyyaml`. Install:  pip install pyyaml")
    raise SystemExit(1)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level mapping")
    return data


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )


def find_projects(graphs_dir: Path) -> list[Path]:
    projects: list[Path] = []
    for project_dir in sorted(graphs_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name == "_template":
            continue
        if (project_dir / "project.yaml").exists():
            projects.append(project_dir)
    return projects


def ordered_node_paths(project_dir: Path, project_doc: dict) -> list[Path]:
    nodes_dir = project_dir / "nodes"
    by_stem = {path.stem: path for path in sorted(nodes_dir.glob("*.yaml"))}

    ordered: list[Path] = []
    for entry in project_doc.get("nodes", []):
        if not isinstance(entry, dict):
            continue
        node_id = entry.get("id")
        if isinstance(node_id, str) and node_id in by_stem:
            ordered.append(by_stem.pop(node_id))

    ordered.extend(by_stem.values())
    return ordered


def build_bundle(project_dir: Path) -> dict:
    project_path = project_dir / "project.yaml"
    project_doc = load_yaml(project_path)

    nodes = []
    for node_path in ordered_node_paths(project_dir, project_doc):
        nodes.append(load_yaml(node_path))

    bundle = dict(project_doc)
    bundle["schema_type"] = "project_graph_bundle"
    bundle["node_files"] = len(nodes)
    bundle["nodes"] = nodes
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=Path("graphs"),
        help="Root graphs directory (default: graphs/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("graphify-out/shareable-graphs"),
        help="Directory to write bundles to (default: graphify-out/shareable-graphs/)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Only export one project id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without creating files",
    )
    args = parser.parse_args()

    graphs_dir = args.graphs_dir
    output_dir = args.output_dir
    projects = find_projects(graphs_dir)
    if args.project:
        projects = [project_dir for project_dir in projects if project_dir.name == args.project]

    if not projects:
        print("No projects found to export.")
        return 1

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for project_dir in projects:
        bundle = build_bundle(project_dir)
        output_path = output_dir / f"{project_dir.name}.yaml"
        if args.dry_run:
            print(f"{output_path} <- {project_dir}/project.yaml + {len(bundle['nodes'])} node files")
            continue
        output_path.write_text(dump_yaml(bundle), encoding="utf-8")
        print(f"WROTE {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())