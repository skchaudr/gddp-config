# Primitives

GDDP is built on 8 foundational schema types defined in `schemas/v1/`. These schemas are the domain objects that the pipeline reads, writes, and routes. Every schema file uses a shared envelope of `schema_version` and `schema_type`, followed by an example instance with inline documentation comments.

Graph truth is human-owned. The schemas separate what the human authors (nodes, shape profiles) from what the runtime produces (events, jobs, results, queue records, artifact verifications, task packets). This separation is the core design principle: graphs define projects, agents do not.

## Schema summary

| Schema | File | Version | Description |
|---|---|---|---|
| Node | `schemas/v1/node.yaml` | 1.0 | A capability, milestone, or constraint in a project graph |
| Event | `schemas/v1/event.yaml` | 1.0 | Something happened, normalized from raw webhooks before routing |
| Job | `schemas/v1/job.yaml` | 1.0 | Bounded work to perform, derived from one or more events |
| Result | `schemas/v1/result.yaml` | 1.0 | The shared return contract every executor produces |
| Queue record | `schemas/v1/queue_record.yaml` | 1.0 | SQLite lifecycle tracking for a job, with leasing |
| Artifact verification | `schemas/v1/artifact_verification.yaml` | 1.0 | Hard gate record, one per artifact per job |
| Task packet | `schemas/v1/task_packet.yaml` | 1.0 | The exact payload constructed before executor dispatch |
| Shape profile | `schemas/v1/shape_profile.yaml` | 1.0 | Optional structural context for semantic verification |

## Pages

- [Node](node.md)
- [Event](event.md)
- [Job](job.md)
- [Result](result.md)
- [Queue record](queue-record.md)
- [Artifact verification](artifact-verification.md)
- [Task packet](task-packet.md)
- [Shape profile](shape-profile.md)

## Related pages

- [The schema system overview](../systems/schemas.md)
- [System architecture with data flow diagrams](../overview/architecture.md)
- [GDDP vocabulary](../overview/glossary.md)
