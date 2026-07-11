# Configuration

`gddp-config` is a declarative configuration repo. Configuration happens at three levels: schemas define the shapes, `project.yaml` configures each project, and individual node YAML files configure each capability.

## How schemas define config shapes

Schemas live in `schemas/v1/` and define the canonical shape of every document in GDDP. Each schema file is a YAML document with inline comments that serve as the canonical documentation. The schemas are not parsed by a library at runtime. Instead, the validator (`scripts/validate.py`) mirrors the schema constants inline as Python constants.

Every schema uses a shared envelope pattern:

```yaml
schema_version: "1.0"
schema_type: node
```

The `schema_version` is a string (quoted to avoid float parsing) in `major.minor` format. The `schema_type` identifies the document type (`node`, `event`, `job`, `result`, `queue_record`, `artifact_verification`, `task_packet`, `shape_profile`, `project_graph`).

Schema versioning follows a defined bump policy:

| Change type | Version bump |
|---|---|
| Add optional field | minor |
| Add new enum value | minor |
| Rename a field | major |
| Remove a field | major |
| Change field semantics | major |
| Change required vs optional | major |

See `.handoffs/upgrade-strategy.md` for the full versioning and rollback procedure.

## How project.yaml configures each project

Each project lives in `graphs/<project-id>/` and contains a `project.yaml` file. The template is at `graphs/_template/project.yaml`. A project.yaml has three main sections:

### Blueprint

Defines the project vision, architecture notes, and major capabilities. This is the human-authored project definition.

```yaml
blueprint:
  vision: "one sentence: what this project is"
  architecture_notes: "key constraints that shape the whole project"
  major_capabilities:
    - capability-one
    - capability-two
```

### Execution policy

Controls how the runtime dispatches work for this project:

```yaml
execution_policy:
  default_executor: jules
  max_concurrent_jobs: 1
  require_human_review_before_overnight: true
  artifact_gate_enforced: true
```

### Node index

Lists all nodes with their id, title, status, and type. This is for human navigation. The system reads the `nodes/` directory directly for validation.

```yaml
nodes:
  - id: auth-boundary
    title: Establish authenticated request boundary
    status: pending
    type: capability
```

The `project validate` subcommand checks that the node index matches the files in `nodes/` (no missing or orphan YAMLs).

## How node YAML files configure individual capabilities

Each node is a single YAML file at `graphs/<project-id>/nodes/<node-id>.yaml`. The template is at `templates/node-template.yaml`. A node defines:

- **Identity**: `node_id` (kebab-case, matches filename), `title`, `type` (`capability`, `milestone`, `constraint`)
- **Purpose**: `why` (one sentence explaining why this capability must exist)
- **Dependencies**: `depends_on` (nodes that must be complete first), `unlocks` (nodes this one enables)
- **Acceptance**: `acceptance_criteria` (list of `{id, criterion}` entries, each verifiable)
- **Constraints**: `constraints` (hard limits the executor must respect)
- **Execution**: `allowed_execution_modes` (which executors can run this), `required_artifacts` (what must exist before advancement)
- **Status**: `status` (`pending`, `ready`, `complete`, `deferred`), `priority` (`low`, `medium`, `high`, `critical`)

Node status is human-owned. The runtime produces verdicts and receipts, but only a human can change node status to `complete`.

## Configuration files and their purposes

| File | Location | Purpose |
|---|---|---|
| Node schema | `schemas/v1/node.yaml` | Canonical shape for node documents |
| Event schema | `schemas/v1/event.yaml` | Shape for normalized events |
| Job schema | `schemas/v1/job.yaml` | Shape for bounded work units |
| Result schema | `schemas/v1/result.yaml` | Shape for executor return values |
| Queue record schema | `schemas/v1/queue_record.yaml` | Shape for job lifecycle tracking |
| Artifact verification schema | `schemas/v1/artifact_verification.yaml` | Shape for artifact gate records |
| Task packet schema | `schemas/v1/task_packet.yaml` | Shape for executor payloads |
| Shape profile schema | `schemas/v1/shape_profile.yaml` | Optional structural context for projects |
| Project template | `graphs/_template/project.yaml` | Starting point for new project graphs |
| Node template | `templates/node-template.yaml` | Starting point for new node files |
| Job template | `templates/job-template.yaml` | Shape for manual dry-run jobs |
| Draft node prompt | `templates/draft-node-prompt.md` | Saved prompt for LLM-drafting node fields |

## Related pages

- [Data models](data-models.md): how the 8 schemas relate to each other
- [Dependencies](dependencies.md): external dependencies
- [Primitives](../primitives/index.md): foundational domain objects in detail
- [Schemas](../systems/schemas.md): the schema system
- [Patterns and conventions](../how-to-contribute/patterns-and-conventions.md): YAML and graph authoring conventions
