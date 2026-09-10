# Job

A job is "here is the bounded work to perform." One [event](event.md) can create zero, one, or multiple jobs. A job binds an event to a specific [node](node.md) and an executor, carrying the context and constraints needed to produce a reviewable result.

Source: `schemas/v1/job.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `job_id` | string | Unique identifier for the job |
| `created_at` | timestamp | When the job was created |
| `event_id` | string | ID of the event that produced this job |
| `project_id` | string | Project this job belongs to |
| `repo` | string | Repository identifier |
| `node_id` | string | Node this job targets |
| `job_type` | enum | `implementation`, `review`, `reasoning`, `context_update` |
| `executor` | enum | `jules`, `vertex`, `pi_worker`, `vm_worker`, `human` |
| `queue` | string | Current queue state |
| `title` | string | Human-readable job title |
| `goal` | string | What the job aims to produce |
| `why` | string | Rationale for the job |
| `source_context` | object | Repository and branch context, see below |
| `constraints` | list[string] | Rules that scope the work |
| `acceptance_criteria` | object | References to node criteria plus local criteria, see below |
| `dependencies` | list[string] | Node dependencies, prefixed `node:` |
| `priority` | enum | `low`, `medium`, `high`, `critical` |
| `risk_level` | enum | `low`, `medium`, `high` |
| `estimated_effort` | enum | Effort estimate |
| `status` | enum | Current job status |
| `attempt` | int | Current attempt number, starts at 0 |
| `max_attempts` | int | Maximum attempts before failure |
| `artifacts_dir` | string | Directory for job artifacts |
| `result_summary_path` | string or null | Path to result summary once produced |

## Job type enum

| Value | Description |
|---|---|
| `implementation` | Produce code changes for a node |
| `review` | Review existing work or a PR |
| `reasoning` | Perform reasoning or analysis without code changes |
| `context_update` | Update project context or documentation |

## Executor enum

| Value | Description |
|---|---|
| `jules` | Jules executor |
| `vertex` | Vertex-based executor |
| `pi_worker` | Pi worker |
| `vm_worker` | VM-based worker |
| `human` | Human executor |

## Source context structure

The `source_context` object carries the repository and branch context the executor needs.

| Field | Type | Description |
|---|---|---|
| `repo_source` | string | Source path for the repository |
| `starting_branch` | string | Branch to start work from |
| `target_branch` | string | Branch to target for merge |
| `relevant_paths` | list[string] | Paths in the repo relevant to this job |
| `related_pr` | int or null | Related PR number |
| `related_issue` | int or null | Related issue number |

## Acceptance criteria structure

The `acceptance_criteria` object on a job references [node](node.md) criteria by ID and can add local criteria specific to this job.

| Field | Type | Description |
|---|---|---|
| `node_ref` | string | The node ID whose criteria are referenced |
| `acceptance_ids` | list[string] | IDs from the node's `acceptance_criteria` list |
| `local` | list[string] | Job-specific criteria not on the node |

This design means the job inherits the node's acceptance criteria as the primary success measure, while allowing job-specific checks (such as "PR summary explains implementation choice") to be added without modifying graph truth.

## Dependencies, status, and retry

Dependencies use a `node:` prefix to reference [node](node.md) IDs. A job blocked on a dependency node that is not yet complete will sit in the `blocked` queue state (see [queue record](queue-record.md)).

The `status`, `attempt`, and `max_attempts` fields track execution lifecycle. `attempt` starts at 0 and increments on each retry. If `attempt` reaches `max_attempts` without success, the job fails. The [result](result.md) schema captures the outcome of each attempt.

## Related pages

- [Primitives index](index.md)
- [Node](node.md)
- [Event](event.md)
- [Result](result.md)
- [Queue record](queue-record.md)
- [Task packet](task-packet.md)
