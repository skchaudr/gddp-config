# Obsidian export

The Obsidian export (`scripts/obsidian_export.py`) produces a one-way markdown vault from a project graph. It converts each node YAML into an Obsidian note with structured frontmatter, wikilink dependencies, and acceptance criteria checkboxes. The YAML in gddp-config stays source of truth. The export is a derived view for navigation and visual graph exploration.

## What it exports

The tool exports one graph per run. Invoke with `gddp obsidian export --project <id>`. It reads `graphs/<project>/project.yaml` and every `graphs/<project>/nodes/*.yaml` file, then writes markdown notes to a destination vault folder.

For each node, the generated note contains:
- **YAML frontmatter** with `node_id`, `project`, `title`, `type`, `status`, `priority`, `repo`, `tags` (`gdd/auto-generated`, `gdd/graph/<project>`), `source_yaml` path, and `generated_at` timestamp.
- **A banner** warning that the note is auto-generated and that only `verified` and `owned` frontmatter fields should be edited.
- **A level-1 heading** with the node title.
- **The `why` field** as body text.
- **Dependencies section** with `[[wikilink]]` references to each `depends_on` node.
- **Unlocks section** with `[[wikilink]]` references to each `unlocks` node.
- **Acceptance criteria section** with unchecked markdown checkboxes (`- [ ]`) keyed by criterion id.
- **Constraints section** with bullet points.
- **Evidence section** linking back to the source YAML path, the repo, and the verification receipt (`verification/<project>/<node>/result.json`) if it exists.
- **Execution section** listing allowed execution modes and required artifacts.

The tool writes a `_project.md` index note with frontmatter, the project description, and a wikilink list of all nodes. It also drops a `.obsidian/graph.json` into the vault folder with color groups for each status (complete, ready, pending, deferred) so the Obsidian Graph View renders the dependency graph with status-based coloring.

Notes that no longer correspond to a node YAML are deleted during export, keeping the vault in sync with the graph.

## Frontmatter preservation

The export is regenerative. Re-running it overwrites every generated note. Two frontmatter fields are user-owned and preserved across regeneration: `verified` and `owned`. Before overwriting a note, the tool reads the existing note's frontmatter, extracts those two keys if present, and merges them into the new note's frontmatter. This means a human can mark a node as `verified: true` or assign `owned: <person>` in Obsidian without losing that annotation on the next export.

All other frontmatter fields are regenerated from the YAML source every run.

## The Graph View use case

The primary motivation for the export is Obsidian's Graph View. Each note's `[[wikilink]]` dependencies create edges in the graph. Opening the vault folder (e.g., `~/Obsidian/gdd-aa-cli`) as an Obsidian vault shows only that project's dependency graph, isolated from other projects. The injected `graph.json` applies color groups so complete nodes appear green, ready nodes appear teal, pending nodes appear orange, and deferred nodes appear grey.

This gives a visual, navigable view of project status that complements the `gddp node status` text summary.

## Flags

| Flag | Effect |
|---|---|
| `--project <id>` | Required. Which graph to export. |
| `--vault <path>` | Override the destination folder. Default is `~/Obsidian/gdd-<project>/`. |
| `--dry-run` | Print the paths that would be written without creating or deleting any files. |
| `--root <path>` | Override the gddp-config root. Defaults to the repo root. |

## Usage

```bash
# Export one project to the default vault location
.venv/bin/python scripts/gddp.py obsidian export --project aa-cli

# Export to a custom vault folder
.venv/bin/python scripts/gddp.py obsidian export --project aa-cli --vault /path/to/vault

# Preview without writing
.venv/bin/python scripts/gddp.py obsidian export --project aa-cli --dry-run
```

The default vault location is `~/Obsidian/gdd-<project>/`. One graph per run. To export multiple projects, invoke the command once per project.

## Key source files

| File | Role |
|---|---|
| `scripts/obsidian_export.py` | Vault exporter: YAML to markdown notes with frontmatter and wikilinks |
| `scripts/gddp.py` | Unified CLI dispatching the `obsidian export` subcommand |
| `scripts/README.md` | Documents the obsidian subcommand and flags |

## Related pages

- [Shareable bundles](shareable-bundles.md): Another export format, single YAML instead of markdown notes
- [systems/cli-tooling.md](../systems/cli-tooling.md): The gddp.py unified CLI
- [systems/graph-engine.md](../systems/graph-engine.md): How project graphs work
- [overview/getting-started.md](../overview/getting-started.md): Install and setup
