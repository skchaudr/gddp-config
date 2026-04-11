# Changelog

All schema and configuration changes are documented here.
Format: `## [version] - YYYY-MM-DD`

Schema tags use the format: `schema/<type>@<version>` (e.g., `schema/node@1.1`)

---

## [1.0.1] - 2026-04-07

### Changed
- `graphs/gddp-runtime/project.yaml` now describes the return path as receipt-and-review routing instead of automatic graph advancement
- `graphs/gddp-runtime/nodes/return-router.yaml` now defines the runtime boundary as: merged PRs create structured review receipts and move jobs to review; graph truth remains human-owned
- `schemas/v1/job.yaml` example wording now frames job goals as producing reviewable results rather than directly moving node truth

### Notes
- No schema shape expansion in this change
- `schemas/v1/result.yaml` already supported `status: needs_review`; that contract remains the review receipt surface

## [1.0.0] - 2026-03-12

### Added
- `schemas/v1/event.yaml` — normalized event schema v1.0
- `schemas/v1/node.yaml` — capability node schema v1.0
- `schemas/v1/job.yaml` — bounded work packet schema v1.0
- `schemas/v1/result.yaml` — executor result schema v1.0
- `schemas/v1/queue_record.yaml` — SQLite queue record schema v1.0
- `schemas/v1/artifact_verification.yaml` — artifact verification gate schema v1.0
- `schemas/v1/task_packet.yaml` — executor dispatch packet schema v1.0
- `templates/node-template.yaml` — reusable node authoring template
- `templates/job-template.yaml` — reusable job authoring template
- `graphs/_template/` — project graph folder template
- `upgrade-strategy.md` — schema versioning and rollback procedures

### Notes
- Phase 1 initial commit. Schemas promoted from Obsidian v1 design docs.
- No execution code in this commit. Schemas and structure only.
