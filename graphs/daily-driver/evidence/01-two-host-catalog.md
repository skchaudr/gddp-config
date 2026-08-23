# Node 01 — Two-host extension/skill/harness catalog

Inventory date: 2026-08-22 (read-only).  
Hosts: **sab-mini** (this machine, Pi daily driver) · **sab-air** (`ssh sab-air`, verified live).  
No config was written on either host.

---

## Settings excerpts (drift)

### sab-mini `~/.pi/agent/settings.json`

```json
"packages": [
  "npm:pi-subagents",
  "npm:pi-intercom",
  "npm:pi-web-access",
  "git:github.com/skyfallsin/pi-room",
  "git:github.com/skyfallsin/pi-boss",
  "npm:pi-cyber-ui",
  "npm:pi-clinepass-provider",
  "npm:@llblab/pi-telegram",
  "npm:@yofriadi/pi-antigravity-oauth",
  "/Users/sab-mini/.pi/extensions/pi-antigravity-gemini36",
  "npm:@juicesharp/rpiv-ask-user-question",
  "/Users/sab-mini/.pi/extensions/pi-mercury-provider"
],
"defaultProvider": "google-antigravity",
"defaultModel": "gemini-3.6-flash",
"extensions": [
  "/Users/sab-mini/.config/pi-observability/vendor/extension/pi-observability.ts"
]
```

`theme`: `cyber-ui-dark`. `lastChangelogVersion`: `0.84.2`.

### sab-air `~/.dsh/settings.yaml` (live `cat` via ssh)

```yaml
agent-default-model:
  provider: deepseek-official
  model: deepseek-v4-flash
  reasoningEffort: high
llm-pi-ai:
  providers:
    grok:          # displayName Grok (Hermes :8645), openai-completions, grok-4.5
    qwen-token-plan-individual:  # token-plan.ap-southeast-1… qwen3.8-max / 3.7 / 3.6 + deepseek-v4-pro-0813
    zai: { apiKeyEnv: ZAI_API_KEY }
    openrouter:    # @preset/gemini-37-flash-50-off, glm52-77-off, ling3-flash
ui-theme: { preference: dark }
ui-conversation: { busyEnter: steer }
```

### sab-air Pi `~/.pi/agent/settings.json` packages (live; **divergent**)

```
npm:pi-web-access, npm:@juicesharp/rpiv-ask-user-question, npm:@juicesharp/rpiv-todo,
npm:pi-simplify, npm:pi-intercom, npm:pi-subagents@0.35.1,
{source: npm:pi-auto-mode@0.1.2, extensions: [-extensions/auto-mode.ts]},
npm:pi-studio, npm:@llblab/pi-telegram,
{source: npm:pi-ui-minimal, extensions: [-extensions/index.ts]},
npm:pi-prompt-template-model, git:github.com/22GNUs/pi-cyber-ui.git,
{source: npm:pi-grok-cli, extensions: [-src/index.ts]},
npm:pi-clinepass-provider, npm:pi-add-dir,
/Users/sab-mini/.pi/extensions/pi-provider-antigravity,
/Users/sab-mini/.pi/extensions/pi-antigravity-gemini36,
/Users/sab-mini/.pi/extensions/pi-mercury-provider
```

default: `google-antigravity` / `gemini-3.7-flash`.  
Disabled-in-packages-list extensions: `-extensions/_sentry.ts`, `-extensions/capability-cascade.ts`, `-extensions/sentry-observe.ts`.  
Explicit extra: `~/.config/pi-observability/vendor/extension/pi-observability.ts`.

**Visible drift:** sab-mini interactive set is smaller (no studio/auto-mode/grok-cli/simplify/ui-minimal/add-dir/rpiv-todo in `packages[]`); uses skyfallsin git room+boss + npm `pi-cyber-ui@0.1.33`. sab-air still enables studio, auto-mode, grok-cli, 22GNUs cyber-ui, `pi-subagents@0.35.1` vs mini `0.51.0`.

---

## A. sab-mini (Pi) — declared `packages[]`

| # | Item | Path | Purpose |
|---|------|------|---------|
| M-P01 | npm:pi-subagents 0.51.0 | `~/.pi/agent/npm/node_modules/pi-subagents` | Single-agent delegation + scripted multi-agent workflows |
| M-P02 | npm:pi-intercom 0.10.1 | `~/.pi/agent/npm/node_modules/pi-intercom` | Supervisor/subagent intercom channel |
| M-P03 | npm:pi-web-access 0.24.0 | `~/.pi/agent/npm/node_modules/pi-web-access` | Web search, URL fetch, GH clone, PDF, YouTube |
| M-P04 | git:skyfallsin/pi-room 1.0.0 | `~/.pi/agent/git/github.com/skyfallsin/pi-room` | Multi-agent awareness via tmux peers |
| M-P05 | git:skyfallsin/pi-boss 1.0.0 | `~/.pi/agent/git/github.com/skyfallsin/pi-boss` | Spawn/manage sub-agents in visible tmux panes |
| M-P06 | npm:pi-cyber-ui 0.1.33 | `~/.pi/agent/npm/node_modules/pi-cyber-ui` | Cyber theme + compact TUI chrome |
| M-P07 | npm:pi-clinepass-provider 1.2.0 | `~/.pi/agent/npm/node_modules/pi-clinepass-provider` | ClinePass models (GLM/Kimi/DS/…) |
| M-P08 | npm:@llblab/pi-telegram 0.36.5 | `~/.pi/agent/npm/node_modules/@llblab/pi-telegram` | Telegram runtime adapter |
| M-P09 | npm:@yofriadi/pi-antigravity-oauth 0.3.0 | `~/.pi/agent/npm/node_modules/@yofriadi/pi-antigravity-oauth` | Antigravity OAuth restore |
| M-P10 | local pi-antigravity-gemini36 1.0.0 | `~/.pi/extensions/pi-antigravity-gemini36` | Adds Gemini 3.6/3.7 Flash to antigravity |
| M-P11 | npm:@juicesharp/rpiv-ask-user-question 2.6.2 | `~/.pi/agent/npm/node_modules/@juicesharp/rpiv-ask-user-question` | Structured questionnaire tool |
| M-P12 | local pi-mercury-provider 1.0.0 | `~/.pi/extensions/pi-mercury-provider` | Inception Mercury 2 provider + keychain |

### Possibly-transitive / leftover (in `npm/package.json` or `node_modules`, **not** in `packages[]`)

Do **not** treat as current installs.

| Item | Version on disk | Path | Note |
|------|-----------------|------|------|
| pi-auto-mode | 0.1.2 | `~/.pi/agent/npm/node_modules/pi-auto-mode` | leftover Claude-style auto mode |
| pi-studio | 0.9.33 | `~/.pi/agent/npm/node_modules/pi-studio` | leftover two-pane browser workspace |
| pi-grok-cli | 0.7.0 | `~/.pi/agent/npm/node_modules/pi-grok-cli` | leftover X/SuperGrok subscription provider |
| pi-simplify | 0.2.2 | `~/.pi/agent/npm/node_modules/pi-simplify` | leftover clarity review ext |
| pi-ui-minimal | 1.1.1 | `~/.pi/agent/npm/node_modules/pi-ui-minimal` | leftover minimal UI |
| pi-tool-display | 0.4.3 | `~/.pi/agent/npm/node_modules/pi-tool-display` | archived 2026-06-29 (`extensions/pi-tool-display/ARCHIVED.md`) |
| @juicesharp/rpiv-todo | 1.19.1 | `~/.pi/agent/npm/node_modules/@juicesharp/rpiv-todo` | in package.json deps, not packages[] |
| @sentry/node | 10.56.0 | `~/.pi/agent/npm/node_modules/@sentry/node` | likely sentry-observe dep |

Hundreds of other `node_modules` names (`@aws-sdk`, `zod`, `openai`, …) are ordinary transitives of the above.

---

## B. sab-mini local extensions (`~/.pi/agent/extensions`)

| # | File | Purpose |
|---|------|---------|
| M-E01 | `_arg-complete.ts` | Slash-command argument autocomplete |
| M-E02 | `_sentry.ts.disabled` | Disabled Sentry hook |
| M-E03 | `advisor-mode-core.ts` | Policy helpers for advisor-mode |
| M-E04 | `advisor-mode.ts` | On-demand read-only advisor check-ins |
| M-E05 | `agent-guardrails.ts` | Short lifecycle behavioural nudges |
| M-E06 | `answer-noise-trim.ts` | Strip unsolicited negative framing |
| M-E07 | `atuin.ts` | Log pi bash into Atuin as author `pi` |
| M-E08 | `audit-log.ts` | `tool-trace.jsonl` for harness runs |
| M-E09 | `browse.ts` | Read-only session transcript overlay |
| M-E10 | `capability-cascade.ts` | Observe-only capability registry scaffold |
| M-E11 | `cost-tracker.ts` | Per-turn cost jsonl for harness |
| M-E12 | `cwd-guard.ts` | Confine tools to `$GUARD_ROOT` |
| M-E13 | `daily-memory.ts` | Wire daily memory before interactive start |
| M-E14 | `eval-report-linter.ts` | Lint eval reports |
| M-E15 | `eval-run-invalidator.ts` | Fail eval on infra/runtime errors |
| M-E16 | `filter-output.ts` | Redact secrets from tool results |
| M-E17 | `git-context.ts` | Inject branch/status/last commits |
| M-E18 | `handoff-compaction.ts` | Archive + structured handoff on compact |
| M-E19 | `harness-context.ts` | Reinforce harness scope/stop each turn |
| M-E20 | `harness-state.ts` | Inject mut/cwd/steer state each turn |
| M-E21 | `hashline-edit.ts` | Anchor-hashed file edits |
| M-E22 | `herdr-agent-state.ts` | Herdr pane lifecycle (managed by herdr) |
| M-E23 | `herdr/mux.ts` | Herdr mux helper |
| M-E24 | `herdr-boss/index.ts` | Herdr boss integration |
| M-E25 | `herdr-room/index.ts` | Herdr room integration |
| M-E26 | `identity-anchor.ts` | Re-anchor Pi identity every turn |
| M-E27 | `language-guard.ts` | Banned-term nudge + sanitize |
| M-E28 | `moshi-hooks.ts` | Moshi lifecycle / terminal approval (generated) |
| M-E29 | `mutation-confirm.ts` | Optional `/mut` confirm before writes |
| M-E30 | `needle-active.ts` | Active Needle read/grep slice |
| M-E31 | `needle-shadow.ts` | Passive Needle shadow routing |
| M-E32 | `paste-markers.ts` | Operator/context paste-marker parser |
| M-E33 | `pi-instance-registry.ts` | Instance UUID/registry |
| M-E34 | `recoverability-coverage.ts` | Which tools are recoverable |
| M-E35 | `recoverability-gate.ts` | Archive deletes to `~/.pi/trash/` |
| M-E36 | `sentry-observe.ts` | Optional Sentry spans (`SENTRY_DSN`) |
| M-E37 | `sentry-observe.ts.disabled` | Disabled twin |
| M-E38 | `session-recap.ts` | Idle/resume LLM recap |
| M-E39 | `session-tagger.ts` | Session id on outbound provider calls |
| M-E40 | `stop-and-checkpoint.ts` | `/hold` interrupt + checkpoint |
| M-E41 | `subagent/config.json` | Subagent ext config dir |
| M-E42 | `task-packet.ts` | Task-packet / NTP filesystem tools |
| M-E43 | `workmux-status.ts` | Report status to workmux tmux |
| M-E44 | `pi-tool-display/` | Archived compact tool renderer |
| M-E45 | settings `extensions[]` | `~/.config/pi-observability/vendor/extension/pi-observability.ts` — vendor observability |

---

## C. sab-mini Pi skills (`~/.pi/agent/skills/*`)

| # | Skill | Path | Purpose |
|---|-------|------|---------|
| M-S01 | agent-bus | `…/skills/agent-bus` | SQLite/FastAPI STATE/ASK/ACK bus |
| M-S02 | bailian-cli | `…/skills/bailian-cli` | Aliyun Bailian `bl` CLI hub |
| M-S03 | bailian-finetune | `…/skills/bailian-finetune` | Bailian fine-tune entry |
| M-S04 | bailian-gen | `…/skills/bailian-gen` | Bailian image/video/audio gen |
| M-S05 | bailian-managed-agent | `…/skills/bailian-managed-agent` | Bailian hosted agents.yaml |
| M-S06 | bailian-protocol | `…/skills/bailian-protocol` | Shared `bl` consent/auth protocol |
| M-S07 | droid-heartbeat | `…/skills/droid-heartbeat` | Factory/Droid heartbeat + drift |
| M-S08 | factory-droid-observation-context | `…/skills/factory-droid-observation-context` | Droid/factory observation recall |
| M-S09 | loop-breaker | `…/skills/loop-breaker` | `/looping` abort + trim |
| M-S10 | node-packet-ledger | `…/skills/node-packet-ledger` | Compile NTPs from plans |
| M-S11 | pi-boss | `…/skills/pi-boss` | Boss-mode parallel spawn docs |

---

## D. sab-mini shared skill families (`~/.agents/skills/*`)

Top-level families only (mp_skills nests extra copies).

| # | Family | Path | Purpose |
|---|--------|------|---------|
| M-A01 | agent-bus | `~/.agents/skills/agent-bus` | Cross-agent bus (shared copy) |
| M-A02 | ask-matt | `~/.agents/skills/ask-matt` | Router over Matt Pocock skills |
| M-A03–A10 | bailian-* | `~/.agents/skills/bailian-{cli,docs-llm-wiki,finetune,gen,managed-agent,model-recommend,protocol,train-deploy}` | Bailian CLI / wiki / train-deploy family |
| M-A11 | batch-grill-me | `…/batch-grill-me` | Parallel frontier interview |
| M-A12 | claude-handoff | `…/claude-handoff` | Hand off to background agent |
| M-A13 | code-review | `…/code-review` | Two-axis review since a baseline |
| M-A14 | codebase-design | `…/codebase-design` | Deep-module design vocab |
| M-A15 | daily-memory-intake | `…/daily-memory-intake` | Drain Obsidian daily_memory |
| M-A16 | diagnosing-bugs | `…/diagnosing-bugs` | Instrument-first diagnosis loop |
| M-A17 | domain-modeling | `…/domain-modeling` | Domain language / model |
| M-A18 | edit-article | `…/edit-article` | Article rewrite |
| M-A19 | gddp-node | `…/gddp-node` | Author/amend GDDP node YAML |
| M-A20 | gddp-wayfinder | `…/gddp-wayfinder` | Huge work → GDDP graph |
| M-A21 | graphify | `…/graphify` | Build/update Graphify KG |
| M-A22 | graphify-query | `…/graphify-query` | Read-only Graphify query |
| M-A23 | grill-me | `…/grill-me` | Relentless plan interview |
| M-A24 | grill-with-docs | `…/grill-with-docs` | Grill + ADRs |
| M-A25 | grilling | `…/grilling` | Generic grill |
| M-A26 | handoff | `…/handoff` | Compact to handoff doc |
| M-A27 | html-report | `…/html-report` | HTML report format |
| M-A28 | implement | `…/implement` | Implement from spec/tickets |
| M-A29 | improve-codebase-architecture | `…/improve-codebase-architecture` | Deepening scan + grill |
| M-A30 | loop-me | `…/loop-me` | Grill specs for workflows |
| M-A31 | migrate-to-shoehorn | `…/migrate-to-shoehorn` | `as` → shoehorn |
| M-A32 | mp_skills | `…/mp_skills` | Upstream Matt Pocock skill tree (incl. deprecated/) |
| M-A33 | obsidian-vault | `…/obsidian-vault` | Vault notes/wikilinks |
| M-A34 | prototype | `…/prototype` | Throwaway prototype |
| M-A35 | read-memory-space | `…/read-memory-space` | Read durable Obsidian canon |
| M-A36 | research | `…/research` | High-trust research notes |
| M-A37 | resolving-merge-conflicts | `…/resolving-merge-conflicts` | Merge/rebase conflict help |
| M-A38 | scaffold-exercises | `…/scaffold-exercises` | Exercise dir scaffolding |
| M-A39 | session-align | `…/session-align` | Hermes Telegram vs TUI align |
| M-A40 | setup-matt-pocock-skills | `…/setup-matt-pocock-skills` | Wire issue tracker for skills |
| M-A41 | setup-pre-commit | `…/setup-pre-commit` | Husky + lint-staged |
| M-A42 | setup-ts-deep-modules | `…/setup-ts-deep-modules` | dependency-cruiser deep modules |
| M-A43 | tdd | `…/tdd` | Test-first loop |
| M-A44 | teach | `…/teach` | Teach a concept in-workspace |
| M-A45 | to-questionnaire | `…/to-questionnaire` | Decision → questionnaire |
| M-A46 | to-spec | `…/to-spec` | Conversation → spec |
| M-A47 | to-tickets | `…/to-tickets` | Plan → tracer tickets |
| M-A48 | triage | `…/triage` | Issue/PR triage SM |
| M-A49 | wayfinder | `…/wayfinder` | Huge work map (non-GDDP) |
| M-A50 | wizard | `…/wizard` | Interactive bash wizard |
| M-A51 | write-to-daily-memory | `…/write-to-daily-memory` | Drop note into daily_memory |
| M-A52 | writing-beats | `…/writing-beats` | Assemble writing beats |
| M-A53 | writing-fragments | `…/writing-fragments` | Mine fragments |
| M-A54 | writing-great-skills | `…/writing-great-skills` | Skill-writing reference |
| M-A55 | writing-shape | `…/writing-shape` | Shape article |

---

## E. sab-mini Hermes plugins (`~/.hermes/plugins/`)

| # | Plugin | Path | Purpose |
|---|--------|------|---------|
| M-H01 | answer_noise_trim | `~/.hermes/plugins/answer_noise_trim` | Port of Pi answer-noise-trim |
| M-H02 | herdr-agent-state | `~/.hermes/plugins/herdr-agent-state` | Report Hermes lifecycle to Herdr |
| M-H03 | hermes-achievements | `~/.hermes/plugins/hermes-achievements` | Achievement scan state (no plugin.yaml) |
| M-H04 | moshi-hooks | `~/.hermes/plugins/moshi-hooks` | Moshi lifecycle / terminal approval |
| M-H05 | one_screen_output_guard | `~/.hermes/plugins/one_screen_output_guard` | One-screen response budget |

---

## F. sab-air dsh (`~/.dsh`) — live ssh

| # | Item | Path | Purpose |
|---|------|------|---------|
| A-D01 | settings.yaml | `~/.dsh/settings.yaml` | Default model + llm-pi-ai providers + UI |
| A-D02 | AGENTS.md | `~/.dsh/AGENTS.md` | dsh operating rules |
| A-D03 | CONTEXT.md | `~/.dsh/CONTEXT.md` | Capability framing / harness-shapeability |
| A-D04 | .credentials.yaml | `~/.dsh/.credentials.yaml` | Secrets (not opened) |
| A-D05 | .anonymous-user-id | `~/.dsh/.anonymous-user-id` | Anonymous id |
| A-D06 | profile web | `~/.dsh/profiles/web` | Web app profile (`dsh-web-app` + claude-code subagent link) |
| A-D07 | profile acp | `~/.dsh/profiles/acp` | ACP app profile (`dsh-acp-app`) |
| A-D08 | profiles/node_modules | `~/.dsh/profiles/node_modules` | Profile-resolved deps (transitive) |
| A-D09 | patch subagent-grok.yml | `~/.dsh/patches/subagent-grok.yml` | Opt-in spawn Grok via :8645 |
| A-D10 | patch claude-code-grok.yml | `~/.dsh/patches/claude-code-grok.yml` | Opt-in Claude Code → Hermes Grok :8649 |
| A-D11 | patch subagent-qwen.yml | `~/.dsh/patches/subagent-qwen.yml` | Opt-in Qwen token-plan spawn |
| A-D12 | preset gddp | `~/.dsh/.agent-presets/gddp` | GDDP orchestrator/executor preset |
| A-D13 | sessions/ (9) | `~/.dsh/sessions/*` | Per-cwd session dirs (home, .config, dsh, zed, t3, litellm, aa-cli, gddp-runtime, deepseek-harness) |
| A-D14 | storages/workspace.json | `~/.dsh/storages/workspace.json` | Workspace storage |
| A-D15 | storages/session_projcache.json | `~/.dsh/storages/session_projcache.json` | Session project cache |

Patches are **opt-in CLI `--patch`**; `cordis.yml` says apply bundles then `cordis.patch.yml` then `--patch`. Grep of profile `cordis.patch.yml` did not show these three filenames inlined (usage comments only). **Active-use unresolved** (see node 02).

---

## G. sab-air `~/.config/deepseek-harness` top-level (live)

Root: `@deepseek-ai/dsh-root` **0.1.0-rc.5**.

| # | Module | Path | Purpose (from name + tree) |
|---|--------|------|----------------------------|
| A-H01 | apps/cli | `…/apps/cli` | CLI app |
| A-H02 | apps/web | `…/apps/web` | Web app |
| A-H03 | packages/acp | `…/packages/acp` | Agent Client Protocol |
| A-H04 | packages/api | `…/packages/api` | HTTP/API surface |
| A-H05 | packages/attachment | `…/packages/attachment` | Attachments |
| A-H06 | packages/boot | `…/packages/boot` | Boot/startup |
| A-H07 | packages/bundle | `…/packages/bundle` | Bundle composition |
| A-H08 | packages/client | `…/packages/client` | Client SDK |
| A-H09 | packages/code-runtime | `…/packages/code-runtime` | Code execution runtime |
| A-H10 | packages/compaction | `…/packages/compaction` | Context compaction |
| A-H11 | packages/context | `…/packages/context` | Context assembly |
| A-H12 | packages/core | `…/packages/core` | Core types/runtime |
| A-H13 | packages/credentials | `…/packages/credentials` | Creds |
| A-H14 | packages/e2b | `…/packages/e2b` | E2B sandbox |
| A-H15 | packages/examples | `…/packages/examples` | Examples |
| A-H16 | packages/extensions | `…/packages/extensions` | Extension loader |
| A-H17 | packages/feedback | `…/packages/feedback` | Feedback |
| A-H18 | packages/fs | `…/packages/fs` | Filesystem tools |
| A-H19 | packages/goal | `…/packages/goal` | Goals |
| A-H20 | packages/guard | `…/packages/guard` | Guards |
| A-H21 | packages/hooks | `…/packages/hooks` | Hooks |
| A-H22 | packages/host | `…/packages/host` | Host process |
| A-H23 | packages/identity | `…/packages/identity` | Identity |
| A-H24 | packages/interaction | `…/packages/interaction` | Interaction loop |
| A-H25 | packages/jobs | `…/packages/jobs` | Jobs |
| A-H26 | packages/llm | `…/packages/llm` | LLM providers |
| A-H27 | packages/lsp | `…/packages/lsp` | LSP |
| A-H28 | packages/mcp | `…/packages/mcp` | MCP |
| A-H29 | packages/plan | `…/packages/plan` | Planning |
| A-H30 | packages/preset | `…/packages/preset` | Presets |
| A-H31 | packages/runtime-diagnostics | `…/packages/runtime-diagnostics` | Diagnostics |
| A-H32 | packages/sandbox | `…/packages/sandbox` | Sandbox |
| A-H33 | packages/schedule | `…/packages/schedule` | Scheduling |
| A-H34 | packages/sdk | `…/packages/sdk` | SDK |
| A-H35 | packages/session | `…/packages/session` | Sessions |
| A-H36 | packages/session-query | `…/packages/session-query` | Session query |
| A-H37 | packages/settings | `…/packages/settings` | Settings schema/load |
| A-H38 | packages/shell | `…/packages/shell` | Shell tool |
| A-H39 | packages/skill | `…/packages/skill` | Skills |
| A-H40 | packages/spill | `…/packages/spill` | Spill/overflow |
| A-H41 | packages/storage | `…/packages/storage` | Storage |
| A-H42 | packages/subagent | `…/packages/subagent` | Subagents (incl. claude-code linked by web profile) |
| A-H43 | packages/subprocess | `…/packages/subprocess` | Subprocess |
| A-H44 | packages/terminal | `…/packages/terminal` | Terminal UI |
| A-H45 | packages/test-support | `…/packages/test-support` | Tests |
| A-H46 | packages/todo | `…/packages/todo` | Todos |
| A-H47 | packages/typert | `…/packages/typert` | Typing helper |
| A-H48 | packages/util | `…/packages/util` | Utils |
| A-H49 | packages/web | `…/packages/web` | Web package |
| A-H50 | packages/workflow | `…/packages/workflow` | Workflows |
| A-H51 | packages/workspace | `…/packages/workspace` | Workspace |
| A-H52 | python/sdk | `…/python/sdk` | Python SDK |
| A-H53 | python/sdk-runtime | `…/python/sdk-runtime` | Python runtime |
| A-H54 | native/landlock-run | `…/native/landlock-run` | Landlock helper |
| A-H55 | vendor/* | `…/vendor` | Vendored cordis/cosmokit/hmr/loader/… |
| A-H56 | scripts/ | `…/scripts` | Repo scripts |
| A-H57 | patches/ | `…/patches` | Upstream source patches (repo, not ~/.dsh/patches) |
| A-H58 | website/ | `…/website` | Docs site |
| A-H59 | node_modules/ | `…/node_modules` | Source install deps (transitive) |

---

## H. sab-air Pi install (exists)

`~/.pi/agent` present (52 entries). Live packages listed in settings excerpt. Extra local ext: `~/.pi/extensions/pi-provider-antigravity` (not on mini).  
Air Hermes plugins: `herdr-agent-state`, `moshi-hooks` only.  
Air Pi skills extras vs mini: `find-skills`, `pi-subagent-invoke`, `show-me` (plus shared bailian/loop-breaker/etc.).

### sab-air leftover vs its own packages[]

Air `packages[]` **includes** auto-mode, studio, grok-cli, simplify, ui-minimal, add-dir, rpiv-todo.  
`npm/package.json` also has `@viniraioli/pi-claude-style-tools`, `pi-tool-display`, `@yofriadi/pi-antigravity-oauth` — last two / first one may be unused-in-packages (oauth is **not** in air packages[]). Flag as possibly leftover, not new installs.

---

## Row counts

| Host / bucket | Rows |
|---------------|------|
| sab-mini declared packages | 12 |
| sab-mini leftover npm first-party | 8 |
| sab-mini local extensions (files/dirs + obs) | 45 |
| sab-mini pi skills | 11 |
| sab-mini shared skill families | 55 (A01–A55; A03–A10 = 8 bailian) |
| sab-mini hermes plugins | 5 |
| **sab-mini catalog total** | **136** |
| sab-air ~/.dsh items | 15 |
| sab-air dsh-source modules | 59 |
| sab-air Pi noted (settings packages unique) | 18 declared package entries |
| **sab-air catalog total (dsh+source+pi-packages)** | **15+59+18 = 92** (Pi skills/ext on air not fully row-expanded; see 02 for Pi-air overlap) |

Verification: all sab-air paths from `ssh sab-air` 2026-08-22; not assumed from mini.
