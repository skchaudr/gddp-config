# gddp-config

Source of truth for the Graph-Driven Agentic Development (GDAD) system.

This repo defines the schemas, graphs, and templates that the Agentic Graph Engine (AGE)
and OpenClaw orchestrator operate against. Agents read from this repo. They do not write to it.

---

## What This Repo Is

| Directory | Purpose |
|---|---|
| `schemas/v1/` | Canonical YAML schemas for all system objects |
| `graphs/` | Project graphs — one folder per project |
| `templates/` | Node and job authoring templates |
| `scripts/` | Validation and utility scripts (future) |
| `rules/` | OpenClaw rule configs (future) |
| `workflows/` | OpenClaw workflow configs (future) |

---

## Core Principle

> Graphs define projects. Agents do not.

Nodes in `graphs/` define what the project is, what order it progresses,
and what counts as done. OpenClaw maps events to nodes and dispatches
bounded work. It does not invent direction.

---

## Schema Index

| Schema | File | Version |
|---|---|---|
| Event | `schemas/v1/event.yaml` | 1.0 |
| Node | `schemas/v1/node.yaml` | 1.0 |
| Job | `schemas/v1/job.yaml` | 1.0 |
| Result | `schemas/v1/result.yaml` | 1.0 |
| Queue Record | `schemas/v1/queue_record.yaml` | 1.0 |
| Artifact Verification | `schemas/v1/artifact_verification.yaml` | 1.0 |
| Task Packet | `schemas/v1/task_packet.yaml` | 1.0 |

---

## Creating a New Project

```bash
cp -r graphs/_template graphs/<project-id>
# edit graphs/<project-id>/project.yaml
# add node files to graphs/<project-id>/nodes/
```

Before authoring or onboarding a new graph, use:

- [Project Graph Quality](project-graph-quality.md)
- [Repo Onboarding Checklist](repo-onboarding-checklist.md)
- [Supervised Rep Template](supervised-rep-template.md)

---

## Branch Protection

`main` is protected. No agent can push to `main`.
All changes go through a PR. The human is the only merge authority.
See `upgrade-strategy.md` for the full rationale.

---

## Related

- Obsidian vault: `01 Projects/GDDP/GDD-Control-Center/` — design docs and v1 schema references
- `openclaw-ops` repo — OpenClaw agent behavior config (separate from this repo)
