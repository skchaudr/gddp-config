# GDDP config overview

gddp-config is the source-of-truth configuration repository for the Graph-Driven Agentic Development (GDDP) system. It defines YAML schemas, project graphs, authoring templates, and Python tooling that the runtime engine and executors operate against. Agents and runtime read from this repo; they do not write to it.

The core principle is: graphs define projects, agents do not. Nodes in `graphs/` define what a project is, what order it progresses, and what counts as done. The runtime maps events to nodes and dispatches bounded work, then produces review receipts. Graph truth (node status, acceptance) stays human-owned.

The companion repo `gddp-runtime` is the execution engine that reads these configs and dispatches executors (Jules, Codex, Vertex, etc.). This repo contains no runtime code, only declarative YAML configs and a small `scripts/` Python package for validation, scaffolding, and deterministic verification.

## Quick links

- [Architecture](architecture.md) - system design and data flow
- [Getting started](getting-started.md) - install, validate, scaffold
- [Glossary](glossary.md) - GDDP vocabulary
- [By the numbers](../by-the-numbers.md) - codebase statistics
- [Lore](../lore.md) - project history and timeline
- [How to contribute](../how-to-contribute/index.md) - working in this repo
- [Schemas](../systems/schemas.md) - the schema system
- [Project graphs](../projects/index.md) - the five managed projects
- [CLI tooling](../systems/cli-tooling.md) - the gddp.py unified CLI
