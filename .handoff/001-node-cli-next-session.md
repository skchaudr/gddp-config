# Handoff: GDDP Node + Graph Pipeline — Next Session

## What was done (this session)

### Phase 1: Schema rationalization
- Fixed all 23 validator errors to 0 errors across both projects
- `gddp-runtime` nodes: `infrastructure` → `capability` (4 nodes), added missing fields to `decision-loop-spec.yaml`, added `unlocks` to `decision-loop-review-gate.yaml`
- `vault-doctor` nodes: `normal` → `medium` priority (2 nodes)
- Fixed YAML colon-in-list-item bug in 10 files (unquoted colons parsed as dicts by YAML)
- Updated `validate.py` to detect and warn on implicit mapping (defensive), not hard-error

### Phase 2: Unified CLI + greenfield pipeline
Built the `gddp` CLI and three pathways for node creation:

**Front A — Human keystroke path** (`node rapid`):
- Minimal typing: type node name (~10 chars) → Enter → auto-kebab → pick deps with number keys → next node
- No markdown, no YAML, no handwriting beyond the name itself
- Designed for hand/nerve preservation — single keypress interactions

**Front B — Agent pipeline** (`node import`):
- Accepts node YAML via `--file` or `--stdin` (pipeable)
- Validates against full schema (type enums, required fields, kebab-case, list types)
- Checks for duplicates (filesystem + project.yaml index)
- Writes node file + patches project.yaml
- Returns JSON findings on stdout, exit codes for programmatic use
- `--dry-run` for validation-only, `--auto-approve` for trusted pipelines

**Front C — Hybrid** (`node rapid --llm-draft`):
- Stub built in `llm_draft.py` — deepseek v4 pro via `GDDP_LLM_API_KEY` + `GDDP_LLM_PROVIDER`
- Reads project context + existing nodes → drafts `why`, `acceptance`, `constraints`
- Human reviews draft → `y` accept / `e` edit / `q` skip
- Not wired yet — function signature is clean, needs live API testing

**Outline path** (`project new --from-outline`):
- Markdown outline → skeleton YAMLs (still useful for non-TUI or agent-prepared outlines)

### Files created/modified this session

| File | Lines | Status | Purpose |
|---|---|---|---|
| `scripts/gddp.py` | 386 | NEW | Unified CLI: `node {new,rapid,batch,import,validate,list,status}`, `project {new,validate}` |
| `scripts/rapid_add.py` | 336 | NEW | Minimal-keystroke TUI rapid node adder |
| `scripts/import_node.py` | 312 | NEW | Agent-pipeline node import (validate + write + patch) |
| `scripts/llm_draft.py` | 291 | NEW | LLM drafting stub (deepseek/openai) |
| `scripts/outline_to_nodes.py` | 292 | NEW | Markdown outline → project skeleton |
| `scripts/batch_fill.py` | 320 | NEW | TUI batch fill for REPLACE_ME nodes |
| `scripts/validate.py` | 348 | MODIFIED | Fixed list_of_strings → defensive warning for implicit mapping |
| `graphs/gddp-runtime/nodes/*.yaml` | 4 files | MODIFIED | type: infrastructure → capability, quoted colons, added missing fields |
| `graphs/vault-doctor/nodes/*.yaml` | 3 files | MODIFIED | priority: normal → medium, quoted colons |

All changes committed as `d5933ac` on `main` in `gddp-config`.

---

## Current state

### What works right now

```
gddp node validate                              # 0 errors, 1 expected warning
gddp node status                                # shows all projects with completion %
gddp node list --project vault-doctor           # lists all nodes in a project
gddp project validate                           # checks project.yaml integrity
```

### What's ready to use

```bash
# Create an empty project
gddp project new --project-id my-app --repo org/repo

# Rapid-add nodes (you type names, pick deps with number keys)
gddp node rapid --project my-app --repo org/repo

# Or from a markdown outline
gddp project new --from-outline outline.md --project-id my-app --repo org/repo

# Agent pipeline: pipe a node YAML in
cat draft.yaml | gddp node import --stdin --project my-app
gddp node import --file draft.yaml --project my-app --dry-run

# Fill in REPLACE_ME fields via TUI
gddp node batch --project my-app

# Full field editor (existing tool, more keystrokes but complete control)
gddp node new
```

### Schema contract (source of truth)

`gddp-config/schemas/v1/node.yaml` defines the canonical schema. Valid values:
- `type`: `capability` | `milestone` | `constraint`
- `status`: `pending` | `ready` | `running` | `complete` | `failed` | `deferred`
- `priority`: `low` | `medium` | `high` | `critical`
- `allowed_execution_modes`: `jules` | `vertex` | `pi_worker` | `vm_worker` | `human`

**Schema changes require updating `validate.py`, `import_node.py`, `new_node.py`, `rapid_add.py`, and `batch_fill.py` constants.**

### YAML gotcha

Unquoted colons in list items parse as YAML dicts: `- "text: more"` is safe, `- text: more` becomes `{"text": "more"}`. The validator warns on this. Always quote list items containing colons.

---

## Next phase: Start creating nodes and graphs

### Goal
Put the tools to work. Create actual project graphs — start with small/known projects, build up to complex multi-graph projects.

### Priority order

1. **Greenfield project from scratch** — use `gddp node rapid` to create a project you know well. The goal is to test the full flow end-to-end: create project → rapid-add nodes → batch-fill semantics → validate → verify the graph is coherent. Pick a project small enough to complete in one session (5-10 nodes).

2. **Brownfield project adoption** — use graphify to extract a skeleton from an existing codebase, then rapid-add/batch-fill the semantics. This tests the `graphify_to_nodes.py` → `batch_fill.py` pipeline.

3. **Multi-graph project** — a non-trivial project that needs 2+ graphs (e.g., a build/CI graph + a feature graph, or an infrastructure graph + a capability graph). Test that multiple `gddp-config/graphs/<project>/` directories coexist and the validator handles them independently.

4. **LLM drafting integration** — wire `--llm-draft` to actually call deepseek v4 pro. Test that drafts are reasonable, review flow works, and the human is genuinely present in the process (not just rubber-stamping). Requires `GDDP_LLM_API_KEY` env var.

5. **Agent bulk creation** — test the `node import --stdin` pipeline with an actual agent (Claude, Codex, Jules). The agent should be able to create 5-10 nodes by producing YAML and piping it through the validator. This is the "two-front" approach: human does structure (rapid), agent does volume (import).

### Success criteria
- One complete greenfield graph (all nodes filled, 0 errors, coherent dependency edges)
- One brownfield graph bootstrapped from code
- `node import` successfully used by an agent to create nodes
- `--llm-draft` producing usable drafts (even if imperfect)

### Design decisions made this session (do not undo without asking)

1. **Schema is the contract.** Nodes that violate it are wrong, fix the nodes not the schema. No rubber-stamping.
2. **`infrastructure` type was never in the schema.** The 4 gddp-runtime nodes using it were reclassified to `capability`. If a new type is needed, it goes through `schemas/v1/node.yaml` first.
3. **Validator is defensive on YAML gotchas** (implicit mappings) but still warns — the YAML files should be fixed.
4. **Agent import requires validation.** No backdoor to skip schema checks. `--auto-approve` skips review, not validation.
5. **LLM drafting is advisory.** The human always reviews. The draft function returns suggestions; nothing writes without human approval.

### Environment

```bash
cd /Users/sab-mini/repos/gddp-config
.venv/bin/python scripts/gddp.py <command>
```

LLM drafting env vars (when ready):
```bash
export GDDP_LLM_PROVIDER=deepseek    # deepseek | openai | anthropic | ollama
export GDDP_LLM_API_KEY=sk-...
export GDDP_LLM_MODEL=deepseek-chat  # optional, has sensible defaults
```

### Gotchas

- `gddp-config` is the source of truth. `gddp-runtime` only reads it.
- Runtime must not mutate `gddp-config` automatically.
- `graph_updater.py` in gddp-runtime is intentionally disabled.
- The `validate.py` schema constants are mirrored inline — if `schemas/v1/node.yaml` changes, update all scripts.
- `project.yaml` format differs between vault-doctor (full blueprint) and gddp-runtime (minimal). `project new` creates the full format.
- Paths on this machine: `gddp-config` at `/Users/sab-mini/repos/gddp-config`, `gddp-runtime` at `/Users/sab-mini/repos/gddp-runtime`.
- Python 3.14 is installed — regex character class ranges (`\w-`) must use escaped dashes (`[\w\-]` or `[a-zA-Z0-9_-]`).
