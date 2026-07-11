# Shareable bundles

The shareable graph bundle exporter (`scripts/export_graph_bundles.py`) collapses a project directory into a single YAML file with the project metadata and all node documents inline. This makes it easy to share or archive a whole graph without the per-node directory structure.

## What a bundle is

A bundle is a single YAML file that contains everything needed to understand a project graph in one document. The exporter reads `graphs/<project-id>/project.yaml` and every `graphs/<project-id>/nodes/*.yaml` file, then writes one combined file to `exports/shareable-graphs/<project-id>.yaml`.

The bundle structure:
- All fields from the project `project.yaml` (schema_version, project_id, project_name, description, repo, blueprint, graph_version, created_at, last_updated, nodes_dir, execution_policy).
- `schema_type` is set to `project_graph_bundle` to distinguish the bundle from a plain project graph.
- `node_files` is added as an integer count of inline nodes.
- The `nodes` key is replaced with a list of full node documents (the complete content of each `nodes/*.yaml` file), ordered to match the project index and falling back to filesystem order for any nodes not in the index.

For example, `exports/shareable-graphs/sell-valuables.yaml` contains the project metadata for the sell-valuables pipeline followed by every node document inline, from `intake-folder-convention` through the final capability nodes.

## Why bundles are useful

The canonical project graph is a directory of per-node YAML files. This is good for editing, validation, and version control diffs. It is less convenient when you want to share a whole graph with someone who does not have the repo cloned, archive a snapshot, or feed the full graph to a tool that expects a single document.

The bundle solves this by putting everything in one file. You can attach it to a message, store it as an artifact, or parse it with a single YAML load call. The bundle is derived data only. It is not used by validation. Regenerating bundles does not affect the source graphs.

## The --output-dir flag

The exporter writes to `exports/shareable-graphs/` by default. The `--output-dir` flag redirects the output to any directory:

```bash
.venv/bin/python scripts/export_graph_bundles.py --output-dir /tmp/my-bundles
```

Other flags:

| Flag | Effect |
|---|---|
| `--graphs-dir <path>` | Override the source graphs directory. Default is `graphs/`. |
| `--output-dir <path>` | Override the output directory. Default is `exports/shareable-graphs/`. |
| `--project <id>` | Export only one project. Default is all projects. |
| `--dry-run` | Print what would be written without creating files. |

When no `--project` is specified, the exporter walks every directory under `graphs/` that has a `project.yaml` (skipping `_template`) and writes one bundle per project.

## Usage

```bash
# Export all projects to the default location
.venv/bin/python scripts/export_graph_bundles.py

# Export one project
.venv/bin/python scripts/export_graph_bundles.py --project aa-cli

# Preview without writing
.venv/bin/python scripts/export_graph_bundles.py --dry-run

# Write to a custom directory
.venv/bin/python scripts/export_graph_bundles.py --output-dir /tmp/bundles
```

The repo currently ships five pre-built bundles in `exports/shareable-graphs/`: `aa-cli.yaml`, `album-production.yaml`, `gddp-runtime.yaml`, `sell-valuables.yaml`, and `vault-doctor.yaml`.

## Key source files

| File | Role |
|---|---|
| `scripts/export_graph_bundles.py` | Bundle exporter: reads project.yaml + nodes/*.yaml, writes single YAML |
| `exports/shareable-graphs/<project>.yaml` | Pre-built bundle outputs (one per managed project) |

## Related pages

- [Obsidian export](obsidian-export.md): Another export format, markdown notes instead of a single YAML
- [systems/cli-tooling.md](../systems/cli-tooling.md): The gddp.py unified CLI
- [systems/graph-engine.md](../systems/graph-engine.md): How project graphs work
- [projects/index.md](../projects/index.md): The five managed project graphs
