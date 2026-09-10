# Features

The gddp-config repo provides a set of cross-cutting capabilities built on top of its YAML schemas and Python tooling. Each capability is a workflow or export pipeline, not a runtime service. This page gives a one-paragraph overview of each and links to the dedicated feature page for details.

## Node authoring

Creating a node YAML is the most frequent human activity in the repo. Four authoring modes cover the spectrum from minimal-keystroke rapid entry to agent-assisted import. The TUI scaffold (`scripts/new_node.py`) walks every field with paginated pickers. The rapid adder (`scripts/rapid_add.py`) creates placeholder nodes in seconds. The batch filler (`scripts/batch_fill.py`) walks `REPLACE_ME` placeholders field by field. The import pipeline (`scripts/import_node.py`) validates and writes agent-produced YAML. See [Node authoring](node-authoring.md).

## Project bootstrapping

Starting a new project graph means creating a `graphs/<project-id>/` directory with a `project.yaml` and a set of starter node files. Three flows cover greenfield, outline-driven, and brownfield adoption. The unified CLI (`scripts/gddp.py project new`) dispatches to the right tool based on the `--from-outline` or `--from-graphify` flag. An empty shell mode creates a minimal project for rapid add. See [Project bootstrapping](project-bootstrapping.md).

## Obsidian export

The Obsidian export (`scripts/obsidian_export.py`) produces a one-way markdown vault from a project graph. Each node becomes a note with YAML frontmatter, wikilink dependencies, and acceptance criteria checkboxes. The export preserves user-owned frontmatter fields (`verified`, `owned`) across regeneration. The Obsidian Graph View renders the project's dependency graph visually. See [Obsidian export](obsidian-export.md).

## Shareable bundles

The bundle exporter (`scripts/export_graph_bundles.py`) collapses a project directory into a single YAML file with the project metadata and all node documents inline. This makes it easy to share or archive a whole graph without the per-node directory structure. Bundles live in `exports/shareable-graphs/` and are derived data, not used by validation. See [Shareable bundles](shareable-bundles.md).

## Related pages

- [systems/cli-tooling.md](../systems/cli-tooling.md): The gddp.py unified CLI
- [systems/schemas.md](../systems/schemas.md): The schema system
- [systems/graph-engine.md](../systems/graph-engine.md): How project graphs work
- [overview/getting-started.md](../overview/getting-started.md): Install, validate, scaffold
