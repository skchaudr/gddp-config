# 064 — GDDP CLI modules Phase 2 (split gddp.py, same UX)

------------------------------------------------ Agent Section START

Date: 2026-09-15
Worktree: /workspace
Branch: cursor/gddp-cli-modules-9ba7

## Empirical Reality (2-3 sentences max, anything more must be critically justifiable)

Phase 2 complete: seven modules + `gddp_proxy.py`; `gddp.py` entry + TUI + re-exports (4815 lines, down from 7567). Circular-import fix verified via `./bin/gddp --help`. Coordinator vision PASS on picker/hub/nodes/more (quit clean). pytest 198/204 on test_gddp+dispatch; env-gap failures unchanged.

### Scope touched (One file per line, +/- for only what was changed)

+ scripts/graph_io.py — project list, YAML load, three repo-resolve predicates preserved
+ scripts/cli_dispatch.py — build_dispatch_plan … cmd_dispatch
+ scripts/cli_watch.py — attempt discovery, watch/runs/steer
+ scripts/cli_eval.py — knobs, _run_live_eval, cmd_eval*, cmd_verify_node live path
+ scripts/cli_heartbeat.py — launchd/systemd heartbeat TUI
+ scripts/cli_status.py — show_status, validate, interactive status/validate
+ scripts/cli_parser.py — argparse body (parse_cli_argv)
+ scripts/gddp_proxy.py — lazy console proxy for patched gddp.console in tests
+ scripts/gddp.py — thin main, imports, full TUI retained, re-exports for test_gddp patches
~ docs/gddp-cli-reduction.plan.md — unchanged (reference only)

### Constrained areas touched (none / list + justification)

none — inherited verification dirty files untouched; no hub letter `e`; no Phase 1 behavior renegotiation

### Current Git state (2-3 sentences max, anything more must be critically justifiable)

Branch `cursor/gddp-cli-modules-9ba7`; draft PR #17 open. Vision + adversarial gates passed; human merge remaining.

### Artifacts (Filepath - Description, 1 line max per artifact)

scripts/gddp.py — 7567→4815 lines; main + TUI + re-exports

### Vision checklist (coordinator — live TUI on box desktop)

- [x] **Picker** — graph picker Esc→plane, refresh, fzf unchanged
- [x] **Hub** — graph hub n/d/w/m keys, truth block, no shell-only footers
- [x] **Nodes** — paged list columns, running marker, review menu e/v/x/u/m
- [x] **More** — jobs, frontier, status, validate, timeline pager from hub more

Quit clean on all paths.

### Adversarial review

| Finding | Disposition |
| --- | --- |
| Circular import: cli_* top-level `import gddp` while gddp loading | **FIX** — removed top-level imports; lazy inside functions; `./bin/gddp --help` works |
| `gddp.py` ~4815 lines vs plan 2800–3200 | **WAIVE** — TUI intentionally remains in gddp.py per §7 |
| Env-only pytest failures (no runtime/repo/cbreak) | **WAIVE** — pre-existing on monolithic main |
| Risk of reintroducing top-level `import gddp` in cli_* | **WAIVE** — documented; lazy-import pattern is the contract |

### Resume point (2-3 sentences max, anything more must be critically justifiable)

Phase 2 code + tests + vision + adversarial complete. Human merge of PR #17 remaining. Do not start Phase 3 unless tasked.

------------------------------------------------ Agent Section END
