# 064 — GDDP CLI modules Phase 2 (split gddp.py, same UX)

------------------------------------------------ Agent Section START

Date: 2026-09-15
Worktree: /workspace
Branch: cursor/gddp-cli-modules-9ba7

## Empirical Reality (2-3 sentences max, anything more must be critically justifiable)

Phase 2 mechanical split landed: seven new modules under `scripts/` plus `gddp_proxy.py` for test-patch routing. `gddp.py` is entry + TUI + re-exports (4815 lines, down from 7567). pytest 224/231 pass; 7 failures match pre-split environment gaps (no sibling repo checkout, no gddp-runtime on PATH).

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

Branch `cursor/gddp-cli-modules-9ba7`; draft PR pending. Commits pushed; working tree clean after handoff.

### Artifacts (Filepath - Description, 1 line max per artifact)

scripts/gddp.py — 7567→4815 lines; main + TUI + re-exports

### Vision checklist (coordinator — live TUI on box desktop)

- [ ] **Picker** — graph picker Esc→plane, refresh, fzf unchanged
- [ ] **Hub** — graph hub n/d/w/m keys, truth block, no shell-only footers
- [ ] **Nodes** — paged list columns, running marker, review menu e/v/x/u/m
- [ ] **More** — jobs, frontier, status, validate, timeline pager from hub more

### Adversarial review (coordinator stub)

| Area | Question |
| --- | --- |
| Re-export surface | Any test patch target missing from gddp.py re-exports? |
| Circular imports | cli_* → gddp lazy imports safe at scale? |
| Line budget | gddp.py 4815 > plan 2800–3200 — acceptable given TUI retained? |

### Resume point (2-3 sentences max, anything more must be critically justifiable)

Code + tests done for Phase 2 split. Coordinator: live TUI vision (checklist above) + adversarial pass. Optional follow-up: shrink gddp.py further via gddp_tui.py (Phase 2 optional in plan).

------------------------------------------------ Agent Section END
