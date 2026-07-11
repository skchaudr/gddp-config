# Queue record

A queue record is a minimal record stored in SQLite for [job](job.md) lifecycle tracking. Leasing prevents two workers from picking up the same job.

The queue record is the runtime tracking layer. It does not duplicate job content. It holds only the state, timing, and lease information needed to manage the job through its lifecycle. See [system architecture](../overview/architecture.md) for how queue records fit into the data flow.

Source: `schemas/v1/queue_record.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `queue_item_id` | string | Unique identifier for the queue record |
| `job_id` | string | ID of the job being tracked |
| `queue` | enum | Current queue state, see below |
| `available_at` | timestamp | When the job became available in this state |
| `lease_owner` | string or null | Worker ID that holds the lease, or null |
| `lease_expires_at` | timestamp or null | When the lease expires, or null |
| `retry_count` | int | Number of retries attempted |
| `last_error` | string or null | Last error message if any |

## Queue state values

| Value | Description |
|---|---|
| `intake` | Webhook received, not yet normalized or classified |
| `classified` | Intent known, graph or scope checks may still be pending |
| `blocked` | Job exists but a dependency node is not yet unlocked |
| `ready` | Can be handed to an executor now |
| `running` | Executor has accepted the job |
| `awaiting_result` | Task launched, polling or waiting for callback |
| `awaiting_review` | Result produced but needs human or validator check |
| `complete` | Result accepted and graph updated |
| `failed` | Execution failed after max retries |
| `deferred` | Intentionally postponed |
| `cancelled` | Superseded or manually killed |

## Leasing mechanism

The `lease_owner` and `lease_expires_at` fields implement a leasing system that prevents two workers from picking up the same job simultaneously.

- When a worker picks up a job, it sets `lease_owner` to its worker ID and `lease_expires_at` to a future timestamp.
- While the lease is held, no other worker can claim the job.
- If the worker crashes or stalls, the lease expires and the job becomes available again.
- When the worker finishes or releases the job, `lease_owner` and `lease_expires_at` are reset to null.

This is a cooperative locking mechanism. It does not guarantee exactly-once execution, but it prevents the common case of duplicate work under normal operation.

## Relationship to job status

The queue record tracks where the job sits in the pipeline. The [job](job.md) schema tracks the job's own `status`, `attempt`, and `max_attempts`. These two layers are complementary: the queue record answers "where is this job in the pipeline," while the job answers "what is the work and how many times have we tried."

## Related pages

- [Primitives index](index.md)
- [Job](job.md)
- [Event](event.md)
- [Result](result.md)
- [System architecture with data flow diagrams](../overview/architecture.md)
