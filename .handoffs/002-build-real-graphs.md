# 002 — Build the First Real Graphs

Date: 2026-06-24
Worktree: /Users/sab-mini/repos/gddp-config (main, clean, pushed)
Branch: main
Upstream: origin/main

## Empirical Reality

Two sessions built the full node + graph pipeline: unified `gddp` CLI (8 node subcommands, 2 project subcommands), schema-validated node creation via minimal-keystroke TUI (`node rapid`), agent pipeline import (`node import --stdin`), LLM drafting stub, and markdown outline bootstrapper. A third session tightened the schema contract: `node.status` is now verdict-only (pending|ready|complete|deferred), and `acceptance` uses stable keyed IDs for deterministic cross-schema joins. Validator is green: 0 errors, 1 pre-existing warning (dangling unlock). 11 nodes exist across 2 projects (vault-doctor 100%, gddp-runtime 50%). The tools are ready but zero real graphs have been created with them — everything so far was tooling and schema work.

### Scope touched

Prior sessions (all committed, pushed):
+ scripts/gddp.py (unified CLI)
+ scripts/rapid_add.py (minimal-keystroke TUI)
+ scripts/import_node.py (agent pipeline)
+ scripts/batch_fill.py (REPLACE_ME walker)
+ scripts/llm_draft.py (LLM drafting stub)
+ scripts/outline_to_nodes.py (markdown → skeleton)
+ scripts/validate.py (tightened acceptance shape checks)
+ scripts/import_node.py (acceptance shape validation)
+ schemas/v1/node.yaml (verdict-only status, keyed acceptance)
+ schemas/v1/job.yaml (node_ref + acceptance_ids vs local)
+ schemas/v1/result.yaml (acceptance_check keys by node ID)
+ schemas/v1/task_packet.yaml (acceptance labeled with node IDs)
+ graphs/*/nodes/*.yaml (all 11 nodes restructured to keyed acceptance)
+ scripts/README.md (full CLI reference)

### Current Git state

Clean working tree on main, pushed to origin. Latest commit: `b7e735f feat(node): restructure acceptance to keyed entries with stable IDs`. Validator green (0 errors). One untracked file: `session-ses_110c.md` (this session's scratch — ignore/delete).

### Artifacts

- scripts/gddp.py — unified CLI entry point, all subcommands wired
- scripts/rapid_add.py — human keystroke path: type name → Enter → number keys for deps
- scripts/import_node.py — agent pipeline: validate + write + patch, JSON stdout
- scripts/batch_fill.py — TUI walker for REPLACE_ME nodes
- scripts/llm_draft.py — deepseek/openai drafting stub (GDDP_LLM_PROVIDER, GDDP_LLM_API_KEY)
- scripts/outline_to_nodes.py — markdown outline → project skeleton
- .handoffs/000-template.md — canonical handoff template
- .handoffs/001-node-cli-next-session.md — prior session handoff (superseded by this)

### Resume point

Build real graphs. Pick one project (greenfield preferred — smallest blast radius), use `gddp project new` + `gddp node rapid` + `gddp node batch` to create a complete graph end-to-end. Then validate, then verify the graph makes structural sense (dependency edges, no cycles, acceptance criteria are specific enough to verify). Once one greenfield graph is done, do the same for a brownfield project via graphify → import pipeline. Goal: confidence that the tooling works for real work, paving the way for overnight agent runs.

------------------------------------------------ Agent Section END

## Critical Rules (carry into next session)

1. **Drift is data.** Validator marks drift; it does not authorize mass-correction. An agent that sweeps existing nodes "fixing" drift is destroying signal. Nodes get reconciled one by one by human judgment.

2. **Structural changes only.** When touching acceptance shape, preserve criterion text exactly. If a diff shows acceptance *wording* changing (not just structure), that's the alarm.

3. **node.status is verdict-only.** Values: pending | ready | complete | deferred. `running` and `failed` are job/queue_record states. If gddp-runtime code references `in_progress` or `blocked` as node statuses, that's a bug in gddp-runtime (context_reader.py:55-58 already does this).

4. **Runtime must never mutate gddp-config.** `graph_updater.py` is intentionally disabled.

5. **Schema changes require updating all mirrors.** VALID_STATUSES, VALID_TYPES, etc. live in validate.py, import_node.py, new_node.py, rapid_add.py, batch_fill.py — all must stay in sync.

## Current Schema Contract

**Node fields** (schemas/v1/node.yaml):
- `type`: capability | milestone | constraint
- `status`: pending | ready | complete | deferred (human verdict, not execution state)
- `priority`: low | medium | high | critical
- `acceptance`: list of `{id: kebab-case, criterion: string}` (semantic kebab IDs, not positional)
- `allowed_execution_modes`: jules | vertex | pi_worker | vm_worker | human
- `required_artifacts`: decision.md | result-summary.md | patch.diff | graph-update.yaml | merged_pr

**Acceptance shape** (post-Fix 2):
```yaml
acceptance:
  - id: vaultdoctor-class-exists
    criterion: VaultDoctor class exists in src/doctor.py
  - id: scan-vault-walks-directory
    criterion: scan_vault(vault_path) walks the directory tree...
```
Jobs reference by ID: `acceptance_ids: [vaultdoctor-class-exists, ...]`. Job-only criteria go in `local:`. Results key by ID: `vaultdoctor-class-exists: pass`.

## CLI Quick Reference

```bash
# Create project + rapid-add nodes (human keystroke path)
gddp project new --project-id my-app --repo org/repo
gddp node rapid --project my-app --repo org/repo
gddp node batch --project my-app            # fill why/acceptance/constraints
gddp node validate --project my-app

# Agent pipeline
echo '<yaml>' | gddp node import --stdin --project my-app
gddp node import --file draft.yaml --project my-app --dry-run

# Brownfield via graphify
gddp project new --from-graphify graphify-out/graph.json --project-id existing-app --repo org/repo

# Status
gddp node status                            # all projects, completion %
gddp node list --project vault-doctor        # per-project node list
gddp project validate                       # project.yaml integrity check
gddp node validate                          # global node validation
```

## What "done" looks like for this phase

- One complete greenfield graph (all nodes filled, 0 errors, coherent dependency edges, acceptance criteria specific enough to verify mechanically)
- One brownfield graph bootstrapped from code (graphify → import → batch fill)
- `node import` successfully used by an agent to create nodes (test the agent pipeline)
- `--llm-draft` wired to deepseek v4 pro and producing usable drafts (even if imperfect)

## Environment

```bash
cd /Users/sab-mini/repos/gddp-config
.venv/bin/python scripts/gddp.py <command>
```

LLM drafting (when ready):
```bash
export GDDP_LLM_PROVIDER=deepseek
export GDDP_LLM_API_KEY=sk-...
```

Two-repo split: gddp-config (this repo, human-owned graph truth) ↔ gddp-runtime (/Users/sab-mini/repos/gddp-runtime, execution machinery, reads but never writes gddp-config).

Known runtime issue: gddp-runtime/scripts/runtime/decision_loop/context_reader.py uses phantom status values (`in_progress`, `blocked`) that were never valid node statuses. That's a gddp-runtime bug, not a gddp-config issue.
