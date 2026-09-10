# Event

An event is "something happened." GitHub webhook payloads are normalized into this format before any routing. Raw webhooks never directly trigger execution.

The event schema is the entry point for external signals into the GDDP pipeline. It captures what occurred, who triggered it, and where it points. Classification and routing sections are filled in by downstream stages, starting in a `pending` state until the pipeline processes them.

Source: `schemas/v1/event.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Unique identifier for the event |
| `received_at` | timestamp | When the event was received |
| `source` | enum | `github`, `transcript`, or `manual` |
| `event_type` | enum | Controlled value, see below |
| `action` | string | Specific action within the event type |
| `actor` | string | Who or what triggered the event |
| `branch` | string | Branch associated with the event |
| `base_branch` | string | Target branch |
| `pr_number` | int or null | PR number if applicable |
| `issue_number` | int or null | Issue number if applicable |
| `commit_sha` | string | Commit hash if applicable |
| `url` | string | Canonical URL for the event source |
| `project_id` | string | Project this event maps to |
| `project_node_candidates` | list[string] | Nodes this event might relate to |
| `scope_status` | enum | `pending`, `in_scope`, `out_of_scope` |
| `priority` | enum | `pending`, `low`, `medium`, `high`, `critical` |
| `risk_level` | enum | `pending`, `low`, `medium`, `high` |
| `raw_payload_path` | string | Path to the original raw payload |
| `normalized_payload_path` | string | Path to the normalized YAML payload |
| `classification` | object | Classification section, see below |
| `routing` | object | Routing section, see below |
| `status` | string | Event processing status |

## Source types

| Value | Description |
|---|---|
| `github` | GitHub webhook or API event |
| `transcript` | Captured transcript from a session |
| `manual` | Manually triggered by a human |

## Controlled event_type values

| Value | Description |
|---|---|
| `issue.opened` | A new issue was opened |
| `issue.commented` | An issue received a comment |
| `pull_request.opened` | A pull request was opened |
| `pull_request.updated` | A pull request was updated |
| `pull_request.review_commented` | A review comment was added to a PR |
| `push.branch_updated` | A branch was updated by a push |
| `workflow.failed` | A CI workflow run failed |
| `workflow.succeeded` | A CI workflow run succeeded |
| `manual.triggered` | A manual trigger was invoked |
| `transcript.captured` | A transcript was captured |
| `transcript.reviewed` | A transcript was reviewed |
| `transcript.dismissed` | A transcript was dismissed |

## Classification section

The `classification` object holds the output of the classifier stage. All fields start as `pending` and are filled in as the pipeline processes the event.

| Field | Type | Description |
|---|---|---|
| `category` | enum | Category of the event, starts `pending` |
| `intent` | enum | Detected intent, starts `pending` |
| `requires_code_execution` | enum | Whether code execution is needed, starts `pending` |
| `requires_reasoning` | enum | Whether reasoning is needed, starts `pending` |
| `requires_human_review` | enum | Whether human review is needed, starts `pending` |

## Routing section

The `routing` object records where the event was sent.

| Field | Type | Description |
|---|---|---|
| `selected_executor` | enum | `pending`, `jules`, `vertex`, `pi_worker`, `vm_worker`, `human` |
| `selected_queue` | string | Queue the event was routed to |

## Pending states

Three fields use a `pending` initial value to indicate the pipeline has not yet classified them:

- `scope_status`: `pending` | `in_scope` | `out_of_scope`
- `priority`: `pending` | `low` | `medium` | `high` | `critical`
- `risk_level`: `pending` | `low` | `medium` | `high`

## Webhook normalization

Raw webhooks are normalized into this format before routing. The raw payload is preserved at `raw_payload_path`, and the normalized version is written to `normalized_payload_path`. This normalization step ensures that all downstream stages work against a consistent structure regardless of the original source format. One event can create zero, one, or multiple [jobs](job.md).

## Related pages

- [Primitives index](index.md)
- [Job](job.md)
- [Queue record](queue-record.md)
- [System architecture with data flow diagrams](../overview/architecture.md)
