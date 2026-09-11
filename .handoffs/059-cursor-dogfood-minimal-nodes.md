# 059 — Cursor dogfood node drafts

------------------------------------------------ Agent Section START

Date: 2026-09-11
Worktree: /home/sab-mini/gddp-config
Branch: main

## Empirical Reality (2-3 sentences max, anything more must be critically justifiable)

Sab selected six stages with minimal capability-level acceptance. Five node drafts each contain one criterion; stage 6 remains open for actual findings, and graph placement/status remain human-owned.

### Scope touched (One file per line, +/- for only what was changed)

+ proposals/cursor-dogfood/README.md
+ proposals/cursor-dogfood/cursor-project-session-restoration.yaml
+ proposals/cursor-dogfood/cursor-hooks-attribution.yaml
+ proposals/cursor-dogfood/cursor-small-batch.yaml
+ proposals/cursor-dogfood/cursor-evaluator-reference-ack.yaml
+ proposals/cursor-dogfood/cursor-dogfood-audit.yaml
+ .handoffs/059-cursor-dogfood-minimal-nodes.md

### Constrained areas touched (none / list + justification)

Proposal ledger only; graphs, project policies, jobs and services retain their previous state.

### Current Git state (2-3 sentences max, anything more must be critically justifiable)

Started clean and synchronized on main. This commit contains the draft ledger and handoff; runtime's companion documentation records the same bootstrap exception and simplified acceptance.

### Artifacts (Filepath - Description, 1 line max per artifact)

- proposals/cursor-dogfood/ — five drafts pass both schema validators with only the deliberately reserved status field; single-criterion shape and DAG verified.
- scripts/validate.py --quiet — global validation returned errors=0 warnings=14; gddp-runtime graph returned errors=0 warnings=1.
- ByteRover query — configured /Users script path unavailable on this Linux host; repository source and operator direction used directly.

### Resume point (2-3 sentences max, anything more must be critically justifiable)

Present the five simple criteria for Sab's graph placement and status selection. Stage 1 uses existing Cursor execution with temporary per-attempt worktrees, stage 2 wires hooks, stage 3 runs 2–3 selected nodes, stage 4 closes typed-reference acknowledgement, and stage 5 audits; Sab selects any stage-6 work or useful splits.

------------------------------------------------ Agent Section END
