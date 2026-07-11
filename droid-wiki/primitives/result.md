# Result

A result is the shared return contract every executor produces. Downstream stages do not care which executor produced the result. This uniformity lets the pipeline treat Jules, Vertex, VM workers, and human results identically.

Source: `schemas/v1/result.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `result_id` | string | Unique identifier for the result |
| `job_id` | string | ID of the job this result belongs to |
| `executor` | enum | Which executor produced this result |
| `received_at` | timestamp | When the result was received |
| `execution_duration_seconds` | int | How long execution took |
| `outcome` | enum | `success`, `failure`, `partial`, `error` |
| `status` | enum | `completed`, `failed`, `needs_review` |
| `changed_files` | list[string] | Files modified by the executor |
| `patch_path` | string | Path to the patch diff |
| `summary_path` | string | Path to the result summary |
| `logs_path` | string | Path to execution logs |
| `acceptance_check` | object | Per-criterion verdicts, see below |
| `risks` | list[string] | Risks identified during execution |
| `followup_candidates` | list[string] | Node IDs suggested for followup |
| `github_action` | object | GitHub action to take, see below |

## Outcome enum

| Value | Description |
|---|---|
| `success` | The executor completed the work successfully |
| `failure` | The executor could not complete the work |
| `partial` | Some criteria passed but not all |
| `error` | An error occurred during execution |

## Status enum

| Value | Description |
|---|---|
| `completed` | The result is final and accepted |
| `failed` | The result indicates failure |
| `needs_review` | The result requires human or validator review before advancing |

## Acceptance check

The `acceptance_check` object maps each acceptance criterion ID to a per-criterion verdict. The keys correspond to the `acceptance_ids` referenced in the [job](job.md) and defined on the [node](node.md).

| Verdict | Description |
|---|---|
| `pass` | The criterion was satisfied |
| `fail` | The criterion was not satisfied |
| `untested` | The criterion was not evaluated |

This per-criterion structure allows partial results to be tracked precisely. A result with one `untested` criterion can still advance once that criterion is verified, rather than requiring a full re-run.

## Risks

The `risks` list captures risks the executor identified during work. These are informational and feed into the review process. Risks do not block node advancement on their own, but they inform the human review decision.

## Followup candidates

The `followup_candidates` list suggests [node](node.md) IDs that may be appropriate next steps based on the result. These are suggestions, not graph truth. The human decides whether to act on them.

## GitHub action

The `github_action` object specifies what GitHub action, if any, should be taken in response to this result.

| Field | Type | Description |
|---|---|---|
| `type` | enum | `comment_only`, `pr_update`, `open_pr`, `close_issue`, `comment_or_pr_update`, `none` |
| `target_pr` | int or null | PR to act on |
| `target_issue` | int or null | Issue to act on |

## Related pages

- [Primitives index](index.md)
- [Job](job.md)
- [Node](node.md)
- [Artifact verification](artifact-verification.md)
- [The verification harness](../systems/verification-harness.md)
