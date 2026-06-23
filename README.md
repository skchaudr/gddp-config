# gddp-config

Source of truth for the Graph-Driven Agentic Development (GDDP) system.

This repo defines the schemas, graphs, and templates that the runtime and
executors operate against. Agents and runtime read from this repo. They do not
write to it.

---

## What This Repo Is

| Directory | Purpose |
|---|---|
| `schemas/v1/` | Canonical YAML schemas for all system objects |
| `graphs/` | Project graphs — one folder per project |
| `templates/` | Node and job authoring templates |
| `scripts/` | `validate.py` (strict schema validator) · `new_node.py` (TUI scaffold) · `terminal.py` (shared input helper) — see `scripts/README.md` |
| `rules/` | Decision-loop rule configs (future) |
| `workflows/` | Decision-loop workflow configs (future) |

---

## Core Principle

> Graphs define projects. Agents do not.

Nodes in `graphs/` define what the project is, what order it progresses,
and what counts as done. Runtime maps events to nodes and dispatches bounded
work. It does not invent direction, and it does not mutate graph truth on the
return path.

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

## Node Tooling

Two scripts under `scripts/` replace hand-typing node YAML. Both standalone,
stdlib + `rich` + `pyyaml`. See `scripts/README.md` for install + flags.

**Validate** — strict global schema check, catches drift before commit:

```bash
.venv/bin/python scripts/validate.py                 # human report
.venv/bin/python scripts/validate.py --json          # machine-readable
.venv/bin/python scripts/validate.py --project vault-doctor
```

**Scaffold a new node** — keyboard-driven TUI, writes the YAML file and
patches the project's `project.yaml` index (with `.bak` backup):

```bash
.venv/bin/python scripts/new_node.py
```

Keymap: number keys pick, `←`/`→` paginate, `m` manual, `s` skip, `q` quit,
`Enter` = default. Review screen before write. Post-write: runs `validate.py`
loudly but exits non-zero only if the new node or the `project.yaml` patch is
the cause — pre-existing repo drift surfaces visibly but doesn't block.

For the prose-heavy fields (`why`, `acceptance`, `constraints`), see
`templates/draft-node-prompt.md` — a saved prompt for drafting those fields
with an LLM in the established voice.

---

## Branch Protection

`main` is protected. No agent can push to `main`.
All changes go through a PR. The human is the only merge authority.
See `upgrade-strategy.md` for the full rationale.

---

## Current Graph State

| Project | Status |
|---|---|
| `vault-doctor` | 7/7 nodes complete |
| `gddp-runtime` | 1/1 nodes complete (`return-router`); OpenClaw expansion pending on `feat/openclaw-nodes` |

See `graphs/<project-id>/project.yaml` for the canonical per-project status.

---

## Related

- Obsidian vault: `01 Projects/GDDP/GDD-Control-Center/` — design docs and v1 schema references
- `gddp-runtime` repo — execution/orchestration layer (separate from this repo)
