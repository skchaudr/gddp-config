# Node 02 — Tier classification

Tiers: `interactive-core` | `harness-only` | `provider` | `mux` | `skill-only` | `dead/archived`.  
Source: `graphs/daily-driver/evidence/01-two-host-catalog.md`. Classification only.

---

## sab-mini

### interactive-core
M-P01 pi-subagents, M-P02 pi-intercom, M-P06 pi-cyber-ui, M-P11 rpiv-ask-user-question  
M-E01 _arg-complete, M-E03/04 advisor-mode*, M-E05 agent-guardrails, M-E06 answer-noise-trim, M-E07 atuin, M-E09 browse, M-E13 daily-memory, M-E16 filter-output, M-E17 git-context, M-E18 handoff-compaction, M-E21 hashline-edit, M-E26 identity-anchor, M-E27 language-guard, M-E29 mutation-confirm, M-E32 paste-markers, M-E33 pi-instance-registry, M-E35 recoverability-gate, M-E34 recoverability-coverage, M-E38 session-recap, M-E39 session-tagger, M-E40 stop-and-checkpoint, M-E42 task-packet  
M-S09 loop-breaker, M-S10 node-packet-ledger, M-S11 pi-boss

### harness-only
M-E08 audit-log, M-E10 capability-cascade, M-E11 cost-tracker, M-E12 cwd-guard, M-E14 eval-report-linter, M-E15 eval-run-invalidator, M-E19 harness-context, M-E20 harness-state, M-E45 pi-observability  
M-E36 sentry-observe (gated; still harness-shaped)

### provider
M-P03 pi-web-access, M-P07 pi-clinepass-provider, M-P09 antigravity-oauth, M-P10 gemini36 local, M-P12 mercury local

### mux
M-P04 pi-room, M-P05 pi-boss (git), M-P08 pi-telegram  
M-E22 herdr-agent-state, M-E23 herdr/mux, M-E24 herdr-boss, M-E25 herdr-room, M-E28 moshi-hooks, M-E43 workmux-status  
M-H01–H05 all Hermes plugins (mux/bridge to Hermes/Herdr)

### skill-only
M-S01–S08 (agent-bus, bailian*, droid*, factory*)  
M-A01–M-A55 entire `~/.agents/skills` tree

### dead/archived
M-E02 `_sentry.ts.disabled`, M-E37 `sentry-observe.ts.disabled`, M-E44 `pi-tool-display/` (ARCHIVED.md 2026-06-29)

### leftover npm (not declared — do not count as live installs; tagged for cleanup later)
pi-auto-mode, pi-studio, pi-grok-cli → **unresolved**  
pi-simplify, pi-ui-minimal, @juicesharp/rpiv-todo → **dead/archived** (not in packages[], no settings hook)  
@sentry/node → harness-only transitive  
pi-tool-display npm copy → dead/archived

---

## sab-air

### interactive-core
A-D01 settings.yaml, A-D02 AGENTS.md, A-D03 CONTEXT.md, A-D06 profile web, A-D07 profile acp, A-D12 gddp preset  
A-H01 apps/cli, A-H02 apps/web, A-H07 bundle, A-H12 core, A-H22 host, A-H24 interaction, A-H35 session, A-H37 settings, A-H44 terminal, A-H51 workspace  
Air Pi packages: pi-web-access, rpiv-ask-user-question, rpiv-todo, pi-simplify, pi-intercom, pi-subagents@0.35.1, pi-ui-minimal, pi-prompt-template-model, 22GNUs pi-cyber-ui, pi-add-dir

### harness-only
A-D13 sessions, A-D14–15 storages  
A-H09 code-runtime, A-H10 compaction, A-H11 context, A-H20 guard, A-H21 hooks, A-H25 jobs, A-H31 runtime-diagnostics, A-H32 sandbox, A-H33 schedule, A-H40 spill, A-H43 subprocess, A-H45 test-support, A-H54 landlock-run, A-H56 scripts, A-H57 repo patches, A-H52–53 python sdk*

### provider
A-H26 llm, A-H13 credentials, A-H28 mcp  
Air Pi: pi-clinepass-provider, pi-provider-antigravity, pi-antigravity-gemini36, pi-mercury-provider  
settings.yaml grok/qwen/zai/openrouter blocks

### mux
A-H03 acp, A-H42 subagent, A-H49 web package, A-D08 profile node_modules  
Air Hermes: herdr-agent-state, moshi-hooks  
Air Pi: @llblab/pi-telegram

### skill-only
A-H39 skill  
Air Pi skills: find-skills, show-me, pi-subagent-invoke, plus shared bailian/loop-breaker copies

### dead/archived
A-H58 website (docs, not runtime daily driver)  
A-H15 examples, A-H55 vendor (supporting, not operator-facing)

---

## Cross-host (same name on both)

| Item | Both? | Same install? |
|------|-------|----------------|
| pi-subagents | yes | **divergent** mini 0.51.0 vs air 0.35.1 |
| pi-intercom | yes | same 0.10.1 |
| pi-web-access | yes | same 0.24.0 |
| pi-cyber-ui | yes | **divergent** npm 0.1.33 (mini) vs `git:22GNUs/pi-cyber-ui` (air) |
| pi-clinepass-provider | yes | both 1.2.0 (air npm lock) |
| @llblab/pi-telegram | yes | mini 0.36.5 vs air ^0.36.0 |
| pi-antigravity-gemini36 | yes | both `~/.pi/extensions/…` local 1.0.0 |
| pi-mercury-provider | yes | both local 1.0.0 |
| rpiv-ask-user-question | yes | both ^2.6.2 |
| herdr-agent-state + moshi-hooks | yes | present both Pi + Hermes |
| agent-bus / bailian / loop-breaker skills | yes | shared-family copies |
| pi-room / pi-boss git | **mini only** | air has no skyfallsin git pkgs in packages[] |
| pi-studio / pi-auto-mode / pi-grok-cli | **air declared**; mini leftover disk only | air studio 0.9.44 vs mini leftover 0.9.33; grok-cli air 0.8.1 vs mini leftover 0.7.0 |
| pi-provider-antigravity | **air only** | — |
| ~/.dsh + deepseek-harness | **air only** | — |

---

## Unresolved (evidence, not guesses)

1. **pi-auto-mode (mini)** — `npm/package.json` + `node_modules/pi-auto-mode@0.1.2`; **not** in mini `packages[]`. Air **declares** `npm:pi-auto-mode@0.1.2` with `extensions: [-extensions/auto-mode.ts]` (disabled-looking minus prefix — same syntax air uses for sentry). Whether minus means disabled is schema-ambiguous.
2. **pi-studio** — mini leftover 0.9.33 not in packages[]; air **declares** `npm:pi-studio` 0.9.44. Daily-driver intent on mini unclear.
3. **pi-grok-cli leftovers** — mini 0.7.0 on disk only; air declared 0.8.1. Mini also has `archive/grok-delegate-2026-07-17` and `grok-delegate` agent override **disabled** in settings.
4. **dsh patches not proven in active profile** — `~/.dsh/patches/{subagent-grok,claude-code-grok,subagent-qwen}.yml` exist; comments say `dsh --profile web --patch …`. Profile `cordis.patch.yml` files were not shown to include them. Cannot claim active or dead without a live `dsh` process/args dump.
5. **Air `extensions: [-extensions/_sentry.ts, …]`** — minus-prefix looks like disable; `_sentry.ts` still on disk (not `.disabled` like mini).
6. **needle-active / needle-shadow** — live files; catalog-admitted vs shadow — could be harness-only or experimental core. Left **unresolved**.
7. **@viniraioli/pi-claude-style-tools** on air npm deps, not in packages[].

---

## Tier counts (resolved rows only; unresolved excluded)

| Tier | sab-mini | sab-air |
|------|----------|---------|
| interactive-core | 31 | 22 |
| harness-only | 10 | 18 |
| provider | 5 | 8 |
| mux | 14 | 6 |
| skill-only | 63 | 5 (+ shared skills exist on air, not fully counted) |
| dead/archived | 6 | 3 |
| unresolved | 5 (auto-mode, studio, grok-cli, needles×2) | 4 (3 patches + minus-prefix + claude-style-tools) |

Mini catalog tagged ≈ 31+10+5+14+63+6 = **129** + 5 unresolved leftovers/needles.  
Air dsh+source+declared-pi tagged ≈ 22+18+8+6+5+3 = **62** + unresolved patches (source modules not all individually re-listed in counts if folded into buckets above).

---

## Method

- Live `ssh sab-air` + local reads 2026-08-22.  
- No installs/uninstalls/config writes.  
- Ambiguous → unresolved, not guessed into interactive-core.
