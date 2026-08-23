# 02 — ARMS DAG data topology schema

Charted 2026-08-23. Deliverable of node `data-topology-schema` (agentos-dashboard).
Schema + sample + validator only. Watcher implementation is node 03.

## Node types

| Type | Role | Typical source |
|---|---|---|
| `root` | Vault / workspace router | `/Users/sab-mini/Obsidian/SSD/AGENTS.md` (live vault has no `CLAUDE.md`; AGENTS.md is the operator root) |
| `hub` | Domain / PARA folder router | `00 Inbox`, `01 Projects`, `02 Areas`, `_dispatch`, `_tasks` |
| `skill` | Headless-run SOP | `~/.pi/agent/skills/*/SKILL.md`, `~/.agents/skills` |
| `artifact` | Generated or durable work product | vault notes / html / pdf / logs (node 05 refines dirs) |
| `routine` | Declared schedule | `~/.hermes/cron/jobs.json` |
| `app` | Connector / CLI / MCP leaf | e.g. pi-dispatch queue in `_dispatch/tasks.md` |

Plan named department routers (`content.md`, `business.md`, `community.md`, `apps.md`). Those files are **not** present in SSD. Hubs map to PARA folders until Sab authors department routers.

## Required frontmatter fields (graph contract)

Watcher (node 03) **normalizes** vault YAML into this object on every node. Vault V4 notes do not already carry all of these keys.

| Field | Type | Notes from live vault |
|---|---|---|
| `title` | string | Present on inspected notes (`title:`). |
| `tags` | string[] | Often `[]` or `[rebuild]`. |
| `type` | enum above | Vault uses PARA types (`resource`, `utility`, `event`) or empty `type:`. Graph `type` is ARMS, not vault PARA type. Store vault PARA type in extra key `vault_type` if needed later. |
| `dates` | `{created, modified}` | Vault uses `created` / `modified` as strings (`2026/05/24, 00:05:30` or `2025-12-23 04:14:26`). Null allowed when absent. |
| `model` | string \| null | Not present on inspected vault notes. Required on graph nodes; default `null`. |
| `path` | string | Absolute filesystem path of the source file/dir. |

## Edge semantics

| `kind` | Meaning |
|---|---|
| `parent_child` | Structural containment: root → hub, hub → hub. |
| `router_leaf` | Router declares / owns a leaf: hub/root → skill \| artifact \| routine \| app. |

Rules: both endpoints exist; no self-loops; graph is a DAG (no cycles). Multiple parents allowed (DAG, not tree).

## graph.json JSON Schema

Canonical file: `graphs/agentos-dashboard/evidence/02-graph.schema.json`.

Top-level:

```json
{
  "schema_version": "1.0",
  "generated_at": "<iso or opaque string>",
  "vault_root": "/Users/sab-mini/Obsidian/SSD",
  "nodes": [{ "id", "type", "label", "frontmatter" }],
  "edges": [{ "from", "to", "kind" }]
}
```

`frontmatter.type` must equal `node.type`.

## Sample provenance (files inspected 2026-08-23)

| Path | What was read |
|---|---|
| `/Users/sab-mini/Obsidian/SSD/AGENTS.md` | V4 FM: title AGENTS, created/modified, empty type/area |
| `/Users/sab-mini/Obsidian/SSD/01 Projects/AGENTS.md` | hub router FM |
| `/Users/sab-mini/Obsidian/SSD/01 Projects/Rebuilds/Rebuilds Anchor Note.md` | `type: utility`, `tags: [rebuild]` |
| `/Users/sab-mini/Obsidian/SSD/01 Projects/Pi observability hub MVP ready for Pi delegation and parallel work.md` | `type: resource` |
| `/Users/sab-mini/Obsidian/SSD/_dispatch/tasks.md` | `status`, `task: true` |
| `/Users/sab-mini/Obsidian/SSD/_tasks/2026-W03 Project Anchor.md` | `type: event` |
| `/Users/sab-mini/.pi/agent/skills/loop-breaker/SKILL.md` | skill name/description YAML |
| `/Users/sab-mini/.hermes/cron/` | `jobs.json`, ticker files present |

Sample graph: `02-sample-graph.json` (representative, not a full vault walk).

## Validator

```
python3 graphs/agentos-dashboard/evidence/02-schema-validator.py \
  graphs/agentos-dashboard/evidence/02-sample-graph.json
```

Checks required FM fields, node types, edge kinds, id uniqueness, DAG acyclicity.
