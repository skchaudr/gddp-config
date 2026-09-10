# Task packet

A task packet is the exact payload constructed before dispatching to an executor. It is archived in the job's artifacts folder regardless of outcome. Whether the executor succeeds, fails, or errors, the task packet is preserved for audit and replay.

Source: `schemas/v1/task_packet.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `task_packet_id` | string | Unique identifier for the task packet |
| `job_id` | string | ID of the job this packet was built from |
| `executor` | enum | `jules`, `codex`, `vertex`, `vm_worker` |
| `title` | string | Title of the task |
| `prompt` | string | Multi-section prompt, see below |
| `repo_source` | string | Source path for the repository |
| `starting_branch` | string | Branch to start work from |

## Prompt structure

The `prompt` field is a multi-line string with fixed sections. Each section serves a specific purpose in communicating the task to the executor.

| Section | Description |
|---|---|
| Goal | What the executor should produce |
| Why | Rationale for the task |
| Constraints | Rules that scope the work |
| Acceptance Criteria | Criteria from the target [node](node.md), with IDs and descriptions |
| Relevant Paths | File paths in the repo relevant to the task |
| Related Context | PR numbers, node references, and other context |
| Output Requirements | What the executor must return |

The Acceptance Criteria section pulls directly from the [node](node.md) definition, carrying both the criterion ID and the human-readable criterion text. This ensures the executor works against the same acceptance bar that the [verification harness](../systems/verification-harness.md) will check.

## Executor enum

| Value | Description |
|---|---|
| `jules` | Jules executor |
| `codex` | Codex executor |
| `vertex` | Vertex-based executor |
| `vm_worker` | VM-based worker |

Note: the task packet executor enum includes `codex`, which does not appear in the [job](job.md) executor enum. This reflects that the task packet is the dispatch layer, where codex may be used as a dispatch target even if the job schema uses a different executor classification.

## Archival

The task packet is archived in the job's `artifacts_dir` regardless of outcome. This means:

- If the executor succeeds, the packet is stored alongside the [result](result.md) and patch.
- If the executor fails or errors, the packet is still stored for debugging and replay.
- If the job is retried, each attempt gets its own task packet if the packet content changes.

Archival supports audit trails, replay for debugging, and evidence for the human review process. The task packet is the definitive record of what was asked of the executor.

## Related pages

- [Primitives index](index.md)
- [Job](job.md)
- [Node](node.md)
- [Result](result.md)
- [Artifact verification](artifact-verification.md)
