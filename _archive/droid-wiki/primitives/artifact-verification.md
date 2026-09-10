# Artifact verification

An artifact verification is a hard gate record. One record is created per artifact, per [job](job.md). All `required_artifacts` listed on a [node](node.md) must verify before the node advances. No verification means no node advancement.

Source: `schemas/v1/artifact_verification.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `verification_id` | string | Unique identifier for the verification record |
| `job_id` | string | ID of the job whose artifact is being verified |
| `node_id` | string | ID of the node requiring this artifact |
| `artifact_type` | string | File type from the node's `required_artifacts` |
| `validation_method` | enum | `file_exists`, `content_check`, `github_api_check`, `human_audit` |
| `verified` | bool | Whether the artifact passed verification |
| `verified_at` | timestamp | When verification occurred |
| `verified_by` | enum | `runtime_validator`, `human`, `codex_reviewer` |
| `notes` | string | Notes about the verification result |

## Validation methods

| Method | Description |
|---|---|
| `file_exists` | Checks that the artifact file exists in the job folder |
| `content_check` | Checks that the file is non-empty and structurally valid |
| `github_api_check` | Queries GitHub API to confirm PR merged, issue closed, etc. |
| `human_audit` | Pauses for human review, waits for manual sign-off |

## Verified by options

| Value | Description |
|---|---|
| `runtime_validator` | Automated runtime validator |
| `human` | Human reviewer |
| `codex_reviewer` | Codex-based reviewer |

## Default method mapping

The schema defines default validation methods based on artifact type:

| Artifact type | Default method |
|---|---|
| Most artifacts | `file_exists` + `content_check` |
| `merged_pr` | `github_api_check` |
| First overnight | `human_audit` |

## The hard gate

Artifact verification is a hard gate, not a soft check. The rule is simple: every artifact in a node's `required_artifacts` list must have a verification record with `verified: true` before the node can advance to `complete` status.

This means:

- A [result](result.md) with `outcome: success` does not advance a node on its own. The result is necessary but not sufficient.
- The [verification harness](../systems/verification-harness.md) runs after the result is produced and checks each required artifact.
- If any artifact fails verification, the node stays in its current status and the job may be retried or sent for review.
- Only when all artifacts pass does the node become eligible for human review and advancement.

This design prevents the runtime from self-certifying completion. The graph truth advancement decision remains human-owned, and the verification gate provides deterministic evidence for that decision.

## Related pages

- [Primitives index](index.md)
- [Node](node.md)
- [Job](job.md)
- [Result](result.md)
- [The verification harness](../systems/verification-harness.md)
