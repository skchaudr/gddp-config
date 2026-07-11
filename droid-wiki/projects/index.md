# Projects

GDDP manages real software projects through project graphs. A project graph is a human-owned blueprint that defines what a project is, what it needs to do, and the dependency order in which the work should proceed. Each project graph lives in `graphs/<project-id>/` and contains a `project.yaml` (the blueprint, node index, and execution policy) plus a `nodes/` directory of per-node YAML files. Nodes carry acceptance criteria, constraints, and a status field that represents graph truth, not execution state. Agents execute against the graph but never mutate it. The core principle is: graphs define projects, agents do not.

The graph engine system underpins how project graphs work. See [systems/graph-engine.md](../systems/graph-engine.md) for the mechanics of `project.yaml`, node dependencies, and status semantics. The schema system defines the shape every graph document must follow. See [systems/schemas.md](../systems/schemas.md).

## How to create a project graph

Creating a new project graph means adding a directory under `graphs/` with a `project.yaml` and starter node files. Three flows cover greenfield, outline-driven, and brownfield adoption. The unified CLI (`scripts/gddp.py project new`) dispatches to the right tool based on the `--from-outline` or `--from-graphify` flag. See [features/project-bootstrapping.md](../features/project-bootstrapping.md) for the full creation walkthrough.

## Project graph summary

| Project | Repo | Nodes | Status | Description |
|---------|------|-------|--------|-------------|
| [AA CLI](aa-cli.md) | `skchaudr/aa-cli` | 12 | 12/12 complete | Zsh task compiler and dispatcher that turns prompts into validated packets, routes them to executor targets, and tracks runs in a TSV ledger |
| [Vault Doctor](vault-doctor.md) | `skchaudr/vault-doctor` | 7 | 7/7 complete | Python CLI tool that scans, triages, and prescribes fixes for Obsidian vaults |
| [GDDP Runtime Engine](gddp-runtime.md) | `skchaudr/gddp-runtime` | 13 | 5 complete, 3 ready, 5 pending | The GDDP control plane that dispatches executors and turns their outputs into reviewable receipts while keeping graph truth human-owned |
| [Sell Valuables Pipeline](sell-valuables.md) | `skchaudr/Automating-Selling-Random-Valuables` | 10 | 0/10 complete (all pending) | iMessage intake folders to listing markdown to Facebook Marketplace posting hooks |
| [Album Production](album-production.md) | `sab-mini/album-production` | 10 | 0/10 complete (all pending) | End-to-end pipeline from songwriting through mastering, artwork, marketing, distribution, and release |

Two projects (AA CLI and Vault Doctor) are fully complete. The GDDP Runtime Engine, the control plane that runs all other graphs, is the most complex project with mixed node statuses. Sell Valuables and Album Production are both fully pending, representing planned work that has not started execution.

## Status semantics

Each node in a project graph carries a human-owned status field. The values and their meanings:

- **pending**: The node has not been started. Dependencies may or may not be satisfied.
- **ready**: Dependencies are satisfied and the node is queued for execution.
- **complete**: The node's acceptance criteria have been met and a human has confirmed the work.
- **deferred**: The node is intentionally set aside.

Only a human moves a node to `complete`. Agents execute work and produce evidence, but graph truth stays human-owned. See [overview/glossary.md](../overview/glossary.md) for the full GDDP vocabulary.

## Execution policy

Every `project.yaml` includes an `execution_policy` block that governs how agents work on the project. Common fields across all five projects:

- `default_executor`: The executor agents use by default (all five projects use `jules`)
- `max_concurrent_jobs`: How many jobs can run at once (all five set this to `1`)
- `require_human_review_before_overnight`: Whether a human must approve before overnight runs (varies by project)
- `artifact_gate_enforced`: Whether nodes must produce required artifacts before advancing (all five enforce this)

## Related pages

- [systems/graph-engine.md](../systems/graph-engine.md): How project graphs work
- [systems/schemas.md](../systems/schemas.md): The schema system
- [features/project-bootstrapping.md](../features/project-bootstrapping.md): Project creation flows
- [overview/glossary.md](../overview/glossary.md): GDDP vocabulary
