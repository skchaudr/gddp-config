# Node

A node is a capability, milestone, or bounded project state in a project graph. Nodes are authored by the human. The runtime decision loop reads them and writes receipts. Human review decides whether graph truth changes.

Nodes are the primary unit of project definition. They declare what must be true, why it matters, what depends on what, and what evidence is required before the node can advance. See [how project graphs work](../systems/graph-engine.md) for the broader graph structure.

Source: `schemas/v1/node.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `node_id` | string | Unique identifier for the node |
| `title` | string | Human-readable title |
| `type` | enum | One of `capability`, `milestone`, `constraint` |
| `why` | string | Rationale for why this node exists |
| `depends_on` | list[string] | Node IDs that must be complete before this node can be ready |
| `acceptance_criteria` | list[object] | Keyed criteria the evaluator judges, each with `id` and `criterion` |
| `constraints` | list[string] | Rules that scope the work |
| `allowed_execution_modes` | list[enum] | Executors permitted to work on this node |
| `required_artifacts` | list[string] | Artifacts that must exist and verify before advancement |
| `status` | enum | Human-owned graph truth status |
| `priority` | enum | `low`, `medium`, `high`, `critical` |
| `unlocks` | list[string] | Node IDs that become available once this node is complete |

## Type enum

| Value | Description |
|---|---|
| `capability` | A system behavior that must exist |
| `milestone` | A checkpoint that groups capabilities |
| `constraint` | A rule that scopes other nodes, not directly executable |

## Status enum

Node status is a human-owned decision on graph truth, not execution state. The word "verdict" is reserved for evaluator output.

| Value | Description |
|---|---|
| `pending` | Exists but prerequisites not yet met |
| `ready` | All dependencies complete, can be issued |
| `complete` | Human reviewed and accepted, graph truth advanced |
| `deferred` | Intentionally postponed |

Execution states such as `running` or `failed` live on the [job](job.md) and [queue record](queue-record.md), not on the node. This separation keeps the graph stable while execution state churns.

## Priority enum

| Value | Description |
|---|---|
| `low` | Low priority |
| `medium` | Medium priority |
| `high` | High priority |
| `critical` | Critical priority |

## Execution mode enum

| Value | Description |
|---|---|
| `jules` | Jules executor |
| `vm_worker` | VM-based worker |
| `human` | Human executor |

## Acceptance criteria structure

Each entry in `acceptance_criteria` is a keyed object with two fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable identifier referenced by jobs, results, and artifact verifications |
| `criterion` | string | Human-readable statement of what must be true |

The `id` is the linkage point. Jobs reference these IDs via `acceptance_criteria.acceptance_ids`, and results report per-criterion verdicts in `acceptance_check` keyed by the same IDs. Acceptance itself is the human act that advances graph truth. The evaluator only issues verdicts against this list.

## Required artifacts and verification

Every artifact listed in `required_artifacts` must pass [artifact verification](artifact-verification.md) before the node can advance. No verification means no node advancement. This is a hard gate enforced by the [verification harness](../systems/verification-harness.md).

## Related pages

- [Primitives index](index.md)
- [How project graphs work](../systems/graph-engine.md)
- [The verification harness](../systems/verification-harness.md)
- [Job](job.md)
- [Artifact verification](artifact-verification.md)
