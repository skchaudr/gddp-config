# Pi Daily Driver — graph map

Charted 2026-08-23 from grok-4.6 scout report (scout: 44c089b0). Arc: **inventory → classify → decide (dsh) → package → policy → adapters/mux/skills/boundary → dogfood**.

```text
01 inventory-extension-catalog
   ├── 02 classify-extension-tiers
   ├── 03 dsh-definition-decision (human)
   │       └── 04 package-manifest
   │             └── 05 enable-set-policy
   ├── 06 adapter-twins
   ├── 07 mux-stack
   ├── 08 skill-curation
   └── 09 aa-cli-boundary
                            └── 10 dogfood-session
```

## Node list

| # | node_id | title | status |
|---|---|---|---|
| 01 | inventory-extension-catalog | Freeze the extension/skill inventory as a checked-in catalog | planned |
| 02 | classify-extension-tiers | Tag every item: interactive / harness / provider / mux / skill / dead | planned |
| 03 | dsh-definition-decision | Human decides what dsh is (executor label vs product) | planned |
| 04 | package-manifest | One installable pi package (package.json `pi` key) | planned |
| 05 | enable-set-policy | settings.json packages[] policy diff (unapplied) | planned |
| 06 | adapter-twins | noise-trim / herdr / moshi — one behavior, Pi+Hermes adapters | planned |
| 07 | mux-stack | subagents + intercom + boss/room + herdr conflict matrix | planned |
| 08 | skill-curation | Daily-driver skill allowlist from ~/.agents/skills | planned |
| 09 | aa-cli-boundary | Written seam: aa-cli = fire/verify TUI, Pi = harness, no port | planned |
| 10 | dogfood-session | Install on sab-mini, /reload, one real session, list breaks | planned |

## Conventions

- This chart mirrors the live Pi environment (~/.pi/agent). Enable-set changes are proposed as diffs, never applied by an executor — only human accept applies them.
- Decision nodes (03, plus Telegram-boundary question) resolve during Sab's acceptance pass.
- dsh = deepseek-harness executor label per scout evidence; node 03 makes it official or drops the phrase.
- aa-cli TUI graph is charted separately at aa-cli-tui-pass — do not absorb its nodes here.
