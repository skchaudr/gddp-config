# 065 — GDDP hub evaluations Phase 3 (find the hub, demote argparse fat)

------------------------------------------------ Agent Section START

Date: 2026-09-15
Worktree: /workspace
Branch: cursor/gddp-hub-evaluations-0e79

## Empirical Reality (2-3 sentences max, anything more must be critically justifiable)

Phase 3 code + tests complete. Hub `e` opens graph-scoped receipt picker with “evaluate a node…” → eval hub; More `e` removed (timeline `t` kept). Argparse/help trimmed: no `node new|rapid|batch|import`, `project new`, or `obsidian`; `static_overview` is graph/runtime/eval oriented. `./bin/gddp --help` works. pytest 224/231 pass; 7 env-gap failures unchanged (no gddp-runtime checkout).

### Scope touched (One file per line, +/- for only what was changed)

~ scripts/gddp.py — hub `e`, interactive_graph_evaluations, remove More `e` + interactive_evaluate, static_overview trim, _CLI_COMMANDS drop obsidian
~ scripts/cli_parser.py — remove authoring/obsidian argparse subcommands
~ scripts/test_gddp.py — hub letter `e` test, rewrite evaluate→hub test, CLI command set update

### Constrained areas touched (none / list + justification)

none — inherited verification dirty files untouched

### Current Git state (2-3 sentences max, anything more must be critically justifiable)

Branch `cursor/gddp-hub-evaluations-0e79` off `38f8014`. Changes staged/committed; draft PR pending. Vision + adversarial gates not run this session.

### Artifacts (Filepath - Description, 1 line max per artifact)

scripts/gddp.py — hub e wiring + overview trim
scripts/cli_parser.py — argparse fat removed

### Vision checklist (coordinator — live TUI on box desktop)

- [ ] **Hub e** — graph hub `e` → receipts for this graph + “evaluate a node…” → eval hub
- [ ] **More** — no duplicate `e`; `t` timeline still present
- [ ] **Help/overview** — `gddp --help` graph/runtime/eval; static overview hides verify/project/obsidian authoring

### Adversarial review

| Finding | Disposition |
| --- | --- |
| Muscle memory: `gddp node rapid` dropped from unified CLI help | **NOTE** — use `scripts/rapid_add.py` directly; documented in PR |
| `interactive_evaluations()` now only reachable via dead TUI path | **WAIVE** — shell `gddp evaluations` + hub `e` cover operator paths |
| Env-only pytest failures (7/231) | **WAIVE** — pre-existing; no gddp-runtime sibling checkout |

### Resume point (2-3 sentences max, anything more must be critically justifiable)

Code + tests done. Run vision checklist on box desktop; fill adversarial if findings. Draft PR open; do not merge.

------------------------------------------------ Agent Section END
