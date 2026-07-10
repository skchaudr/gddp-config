# Project bootstrapping

Creating a new project graph means producing a `graphs/<project-id>/` directory with a `project.yaml` and a set of starter node YAML files. The repo provides three bootstrapping flows, all dispatched through the unified CLI (`scripts/gddp.py project new`). The flows cover greenfield (empty shell), outline-driven (markdown checklist), and brownfield adoption (graphify AST output).

## Empty shell creation

The simplest flow. Invoke `gddp project new --project-id <id> --repo <org/repo>` with no source flag. The CLI calls `rapid_add.ensure_project_shell()`, which creates `graphs/<project-id>/project.yaml` with a full project skeleton: `schema_version`, `schema_type`, `project_id`, `project_name`, `description` (as `REPLACE_ME`), `repo`, a `blueprint` block with `REPLACE_ME` placeholders, `graph_version`, `created_at`, `last_updated`, `nodes_dir`, an empty `nodes` list, and an `execution_policy` block with sensible defaults (`default_executor: jules`, `max_concurrent_jobs: 1`, `require_human_review_before_overnight: true`, `artifact_gate_enforced: true`).

No node files are created. The printed next step is `gddp node rapid --project <id> --repo <org/repo>` to start adding nodes one at a time.

## Outline to nodes (`scripts/outline_to_nodes.py`)

For greenfield projects where you already have a mental model of the node breakdown. You write a markdown outline with checkbox items and dependency arrows, and the tool produces a full project skeleton with node YAMLs.

Invoke with `gddp project new --from-outline outline.md --project-id <id> --repo <org/repo>`. The parser reads the outline, creates one node YAML per checklist item, resolves dependency edges, and writes `project.yaml` plus `nodes/*.yaml`. The `--dry-run` flag previews the plan without writing. The `--force` flag overwrites an existing non-empty project directory.

### Outline format

The outline is a markdown file with checkboxes and dependency arrows:

```markdown
# my-app

## Phase 1: Foundation

- [ ] scan-vault-core
- [ ] find-duplicates -> scan-vault-core
- [ ] find-stale-todos -> scan-vault-core
- [ ] check-performance -> scan-vault-core

## Phase 2: Surface

- [ ] performance-dashboard -> check-performance
- [ ] triage-cli-core -> find-duplicates, find-stale-todos, check-performance

- [x] already-done-node
```

Parsing rules:
- `- [ ] node-name` creates a pending node. The title is derived from the kebab-case id (e.g., `scan-vault-core` becomes "Scan Vault Core").
- `- [x] node-name` creates a complete node.
- `-> dep1, dep2` after the node name declares `depends_on` (comma-separated, kebab-case).
- `## heading` sections are purely organizational and do not produce nodes.
- `# heading` sets the project name (optional, falls back to `--project-id`).
- `- node-name` without a checkbox also works and is treated as pending.
- Indentation is ignored. Lines not starting with `-` are ignored.
- Non-kebab-case ids and duplicate ids produce a warning on stderr and are skipped.

All nodes are created with `REPLACE_ME` placeholders for `why`, `acceptance_criteria`, and `constraints`. The printed next steps are `gddp node batch --project <id>` then `gddp node validate --project <id>` then `gddp project validate --project <id>`.

## Graphify to nodes (`scripts/graphify_to_nodes.py`)

For brownfield adoption: bootstrapping a GDDP project graph from an existing codebase. The tool takes a `graphify-out/graph.json` file (produced by the graphify AST extractor) and emits a starter project skeleton. Graphify extracts a graph skeleton from source code, but cannot infer execution semantics. This tool does the mechanical translation. The human does the meaning.

Invoke with `gddp project new --from-graphify graph.json --project-id <id> --repo <org/repo>`. The tool reads the graphify JSON, filters nodes by the selected mode, slugifies graphify ids to kebab-case node ids, lifts `depends_on` and `unlocks` edges (only edges where both endpoints are included), and writes `project.yaml` plus `nodes/*.yaml`.

### Filter modes

| Mode | What it includes |
|---|---|
| `smart` (default) | One node per source file (collapsed) plus concept nodes. Drops rationale and intra-file symbols. |
| `files` | One node per source file. No concept nodes. |
| `documents` | Only graphify nodes with `file_type=document`. |
| `all` | Every graphify node. Will be noisy. |

The `--max-nodes` flag caps the output count. The `--dry-run` flag previews. The `--force` flag overwrites. All nodes are created with `REPLACE_ME` placeholders for the human-only fields. The `project.yaml` description is flagged as "bootstrapped from graphify; needs human framing."

Edge relations recognized: `depends_on` and `unlocks`. All other graphify relations (`calls`, `references`, `contains`, `method`, `rationale_for`, `describes`, `defines`, `conceptually_related_to`) are dropped as too granular or too inferential for a project node graph.

## The project template

`graphs/_template/project.yaml` is the canonical blank project. It documents every field with inline comments. Key fields:

- `project_id`, `project_name`, `description`, `repo`: identity and provenance.
- `blueprint`: `vision` (one sentence), `architecture_notes` (key constraints), `major_capabilities` (list).
- `graph_version`, `created_at`, `last_updated`: versioning metadata.
- `nodes_dir`: relative path to node files (always `nodes/`).
- `nodes`: index list with `id`, `title`, `status`, `type` per entry. The system reads the `nodes/` directory directly; this index is for human navigation.
- `execution_policy`: `default_executor`, `max_concurrent_jobs`, `require_human_review_before_overnight`, `artifact_gate_enforced`.

The template header notes: "The graph is the source of truth. Agents never modify this file." Copy this folder to `graphs/<project-id>/` for manual project creation.

## Key source files

| File | Role |
|---|---|
| `scripts/gddp.py` | Unified CLI dispatching `project new` to the right sub-tool |
| `scripts/outline_to_nodes.py` | Markdown outline parser and skeleton generator |
| `scripts/graphify_to_nodes.py` | graphify JSON to project skeleton with filter modes |
| `scripts/rapid_add.py` | `ensure_project_shell()` for empty shell creation |
| `graphs/_template/project.yaml` | Canonical blank project template |

## Related pages

- [Node authoring](node-authoring.md): Filling in node fields after bootstrap
- [systems/cli-tooling.md](../systems/cli-tooling.md): The gddp.py unified CLI
- [systems/graph-engine.md](../systems/graph-engine.md): How project graphs work
- [projects/index.md](../projects/index.md): The five managed project graphs
