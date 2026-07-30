# Plugins

The gddp-config repo ships agent skills and harness integrations as installable plugins rather than runtime services. Plugins extend authoring and analysis workflows (for example `/understand` knowledge graphs, onboarding guides, and domain flow graphs) without changing graph truth in `graphs/` or the validation contracts in `schemas/v1/`.

## What lives in a plugin

A typical plugin bundles skill definitions (`SKILL.md`), Node helper scripts for scanning and batching, and optional agent definitions used by the harness. Skills read project files and write artifacts under `.ua/` (or legacy `.understand-anything/`). They do not mutate node YAML unless a separate authoring tool is invoked.

## Relationship to gddp-config

Graph and schema content in this repo remains human-owned. Plugins help humans and agents *understand* and *navigate* the repo; they are not part of the GDDP runtime pipeline (events, jobs, results). Configuration for plugins usually lives in the user harness install path, not in `graphs/<project>/`.

## Installed skills in this workspace

The `.pi/skills/` directory lists symlinked understand-* skills (understand, understand-chat, understand-dashboard, understand-diff, understand-domain, understand-explain, understand-figma, understand-knowledge, understand-onboard). These mirror the Understand-Anything plugin capabilities used during development.

## When to use plugins vs repo scripts

| Need | Use |
|---|---|
| Validate or scaffold node YAML | `scripts/gddp.py`, `scripts/validate.py` |
| Export Obsidian vault or shareable bundles | `scripts/obsidian_export.py`, `scripts/export_graph_bundles.py` |
| Build or refresh a codebase knowledge graph | Understand plugin (`/understand`) |
| Author graph nodes interactively | Node authoring scripts (see [Node authoring](node-authoring.md)) |

## Related pages

- [Features index](index.md)
- [systems/cli-tooling.md](../systems/cli-tooling.md)
- [how-to-contribute/tooling.md](../how-to-contribute/tooling.md)