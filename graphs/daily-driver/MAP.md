# Daily Driver — graph map

Re-charted 2026-08-23 after direct recon of sab-air: dsh is a real agent harness there
(~/.dsh config home + ~/.config/deepseek-harness source). Arc: **two-host inventory →
classify → dsh inventory → split decision (human) → package both sides → policies →
twins/mux/skills/boundary → two-host dogfood**.

```text
01 inventory-extension-catalog ─┬─ 02 classify-extension-tiers ── 05 package-manifest (pi)
                                └─ 03 dsh-harness-inventory ─── 04 split-decision (human)
                                      └─ 04 ─┬─ 05 (scoped)
                                             ├─ 07 dsh-daily-driver-config
                                             └─ 08 adapter-twins
01 ─┬─ 09 mux-stack
    ├─ 10 skill-curation
    └─ 11 aa-cli-boundary
05 ── 06 enable-set-policy (pi)
06,07,08,09,10,11 ── 12 dogfood-session (two-host)
```

## Node list

| # | node_id | title | host | status |
|---|---|---|---|---|
| 01 | inventory-extension-catalog | Two-host extension/skill/harness catalog | both | planned |
| 02 | classify-extension-tiers | Tag every item: interactive/harness/provider/mux/skill/dead | both | planned |
| 03 | dsh-harness-inventory | What dsh is on sab-air: seams, plugin surface, config | sab-air | planned |
| 04 | split-architecture-decision | Human: confirm split, what runs where, named seams | both | planned |
| 05 | package-manifest | One installable Pi daily-driver package | sab-mini | planned |
| 06 | enable-set-policy | Pi settings.json packages[] policy diff (unapplied) | sab-mini | planned |
| 07 | dsh-daily-driver-config | Curated .dsh profiles/patches/presets diff (unapplied) | sab-air | planned |
| 08 | adapter-twins | Capabilities shared across Pi / dsh / Hermes | both | planned |
| 09 | mux-stack | Pi coordination stack conflict matrix + load order | sab-mini | planned |
| 10 | skill-curation | Daily-driver skill allowlist | both | planned |
| 11 | aa-cli-boundary | aa-cli stays fire/verify TUI on both hosts; no port | both | planned |
| 12 | dogfood-session | Apply both sides, one real session per host, list breaks | both | planned |

## Conventions

- This chart mirrors two live hosts (sab-mini Pi + sab-air dsh). All config
  changes are proposed diffs — only human acceptance applies them.
- Decision node 04 resolves during Sab's acceptance pass. dsh is REAL
  (harness on sab-air) — node 03 inventories it; node 04 formalizes the split.
- aa-cli TUI graph is charted separately (aa-cli-tui-pass) — no aa-cli
  implementation nodes here.
- Scout reports preserved under research/.
