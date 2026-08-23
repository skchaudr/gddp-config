# AA CLI — TUI Design Pass (graph map)

Charted 2026-08-23 from grok-4.6 scout report (scout: e3de9ed7). Arc: **inventory → design pass ∥ backend wiring → integration → operator walkthrough → graph-walk verification**.

```text
01 tui-inventory-and-keymap-audit
   ├── 02 tui-visual-system ─┬─ 03 tui-deck-runway-pass
   │                         ├─ 04 tui-create-linear-room ── 09 backend-create-verb-edges
   │                         └─ 05 tui-verify-rooms-polish
   ├── 06 tui-picker-grammar
   ├── 07 backend-deck-actions
   ├── 08 backend-packet-schema-align
   └── 10 backend-registry-dispatch
                            └── 11 frontend-integration
                                       └── 12 operator-walkthrough
                                                  └── 13 graph-walk-verification
```

## Node list

| # | node_id | title | status |
|---|---|---|---|
| 01 | tui-inventory-and-keymap-audit | Walk every surface vs tui-design; binding map | planned |
| 02 | tui-visual-system | Shared density, glyphs, truncation, empty states | planned |
| 03 | tui-deck-runway-pass | Deck + runway spatial memory pass | planned |
| 04 | tui-create-linear-room | One linear create room | planned |
| 05 | tui-verify-rooms-polish | Evidence/Agent/Contract rooms to tui-design | planned |
| 06 | tui-picker-grammar | Nucleo default; fzf only on ';' | planned |
| 07 | backend-deck-actions | f/v/o/Enter → bin/aa with receipts | planned |
| 08 | backend-packet-schema-align | Dual-write packet schema reconciled | planned |
| 09 | backend-create-verb-edges | Enter-as-call, sticky pathway, blank respond fixed | planned |
| 10 | backend-registry-dispatch | Executors via targets.conf only | planned |
| 11 | frontend-integration | Hub calls only documented aa subcommands | planned |
| 12 | operator-walkthrough | Replace stale AA_TEST_WALKTHROUGH.md | planned |
| 13 | graph-walk-verification | Run whole graph; one receipt per node | planned |

## Conventions

- Project-local graph lives in aa-cli (mirror of this dir); this gddp-config copy is the dispatch/aggregator chart. Do NOT touch stale aa-cli/gddp/ pilot statuses.
- Executors: pi subagents (tui-design agent is in-repo at `hub-rs/.agents/skills/tui-design`). Only human ✓✓ releases.
- dsh is the deepseek-harness agent loop on sab-air (not an aa-cli surface) — the two-host daily-driver port is charted separately at daily-driver.
- All nodes start `planned`; charting acceptance (Sab) promotes them to the frontier.
