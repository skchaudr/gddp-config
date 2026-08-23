# Scout: Pi extensions + dsh plugins → daily-driver port graph

Read-only inventory 2026-08-21. No repo mutations.

## Files Retrieved

1. `~/.pi/agent/settings.json` — installed packages + extra extension path
2. `~/.pi/agent/npm/node_modules/{pi-*,@earendil-works,@llblab,@yofriadi,@juicesharp}/package.json` — npm package descriptions
3. `~/.pi/agent/extensions/*.ts` (headers) — local TypeScript extensions
4. `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/{extensions,packages,skills}.md` — packaging model
5. `~/.pi/agent/skills/*/SKILL.md` and `~/.agents/skills/` listing
6. `~/.hermes/{SOUL.md,config.yaml,plugins/,skills/,cron/}` — Hermes top-level
7. `/Users/sab-mini/repos/aa-cli/docs/verify-pathway-architecture.md` + `verify-slices/0{2-6}-*.md` + `targets.conf` — only durable `dsh` hits

---

## 1. Inventory

### A. Installed Pi packages (`settings.json` → `~/.pi/agent/npm/` or local path)

| Spec | One-liner |
|---|---|
| `npm:pi-subagents` 0.51.0 | Single-agent delegation + scripted multi-agent workflows; `contact_supervisor` bridge |
| `npm:pi-intercom` 0.10.1 | 1:1 messaging between Pi sessions (`/intercom`, Alt+M) |
| `npm:pi-web-access` 0.24.0 | Web search, fetch, GitHub clone, PDF/YouTube/local video |
| `git:github.com/skyfallsin/pi-room` | (git package; rooms/mux surface — complements herdr-room) |
| `git:github.com/skyfallsin/pi-boss` | (git package; parallel spawn — complements `pi-boss` skill) |
| `npm:pi-cyber-ui` 0.1.33 | Cyber TUI theme + HUD |
| `npm:pi-clinepass-provider` 1.2.0 | ClinePass models (GLM/Kimi/DeepSeek) via $10/mo sub |
| `npm:@llblab/pi-telegram` 0.36.5 | Telegram runtime adapter |
| `npm:@yofriadi/pi-antigravity-oauth` 0.3.0 | Antigravity OAuth provider restore |
| `~/.pi/extensions/pi-antigravity-gemini36` | Local Gemini 3.6 / Antigravity provider package |
| `npm:@juicesharp/rpiv-ask-user-question` 2.6.2 | Structured questionnaire tool (typed options) |
| `~/.pi/extensions/pi-mercury-provider` | Local Mercury provider package |

Also present in `node_modules` but **not** in `settings.json` packages (transitive or leftover):

| Package | One-liner |
|---|---|
| `pi-auto-mode` 0.1.2 | Claude-style auto mode, two-stage tool-call classifier |
| `pi-grok-cli` 0.7.0 | X Premium / SuperGrok inside Pi |
| `pi-simplify` 0.2.2 | Review recent diffs for clarity |
| `pi-studio` 0.9.33 | Two-pane browser workspace + tmux REPL |
| `pi-tool-display` 0.4.3 | Compact tool rendering (local copy also under `extensions/pi-tool-display/ARCHIVED.md`) |
| `pi-ui-minimal` 1.1.1 | Hide footer / dashed input borders |
| `@earendil-works/pi-ai` 0.74.2 | Unified LLM API (core dep, not an extension) |
| `@juicesharp/rpiv-todo` 1.19.1 | Live todo overlay (sibling of ask-user; may be dep) |
| `@juicesharp/rpiv-config` 1.20.0 | Shared config I/O for rpiv-* |
| `@nodable/entities` | XML entity parser (dep) |

Extra settings extension: `~/.config/pi-observability/vendor/extension/pi-observability.ts`.

### B. Local extensions (`~/.pi/agent/extensions/`) — the real daily-driver surface

**Operator / session UX**
- `advisor-mode.ts` + `advisor-mode-core.ts` — on-demand read-only advisor (fast model + oracle subagent)
- `browse.ts` — `/browse` read-only transcript overlay
- `session-recap.ts` — idle/resume/compaction LLM recap
- `stop-and-checkpoint.ts` — `/hold`, `/looping`, `/scp`
- `task-packet.ts` — NTP / packet state + slash complete
- `workmux-status.ts` — tmux window status via workmux
- `atuin.ts` — log bash tool cmds to Atuin as author `pi`
- `daily-memory.ts` — ensure `memory/YYYY-MM-DD.md` exists
- `git-context.ts` — inject branch/status/last 3 commits
- `identity-anchor.ts` — re-inject Pi identity each turn
- `handoff-compaction.ts` — archive + structured handoff on compact
- `pi-instance-registry.ts` — idle/running/ended records under observability

**Guards / policy**
- `agent-guardrails.ts` — cheap behavioural nudges
- `answer-noise-trim.ts` — strip unsolicited “not” framing
- `language-guard.ts` — banned-term sanitizer
- `mutation-confirm.ts` — `/mut` confirm before bash/write/edit
- `cwd-guard.ts` — keep tools inside `$GUARD_ROOT` (harness)
- `recoverability-gate.ts` + `recoverability-coverage.ts` — trash backup before deletes
- `filter-output.ts` — redact secrets from tool results
- `hashline-edit.ts` — line-hashed safe edits
- `paste-markers.ts` — `>>>`/`<<<` operator vs paste regions

**Harness / eval (silent without `ARTIFACT_DIR`)**
- `audit-log.ts`, `cost-tracker.ts`, `harness-context.ts`, `harness-state.ts`, `eval-report-linter.ts`, `eval-run-invalidator.ts`, `session-tagger.ts`, `sentry-observe.ts`

**Capability / Needle**
- `capability-cascade.ts` — observe-only tool admission scaffold
- `needle-active.ts` / `needle-shadow.ts` — Needle routing (active vs shadow)

**Mux / rooms (herdr)**
- `herdr/mux.ts`, `herdr-boss/index.ts`, `herdr-room/index.ts`, `herdr-agent-state.ts` — herdr-managed; overwrite on reinstall
- `subagent/config.json` — pi-subagents local config
- `moshi-hooks.ts` — generated moshi-hook integration

**Helpers / disabled**
- `_arg-complete.ts` — slash-arg complete helper
- `_sentry.ts.disabled`, `sentry-observe.ts.disabled`

### C. Pi skills (`~/.pi/agent/skills/`)

- `agent-bus` — SQLite/FastAPI STATE/ASK/ACK between agents (`sab-mini:8765`)
- `droid-heartbeat` — Factory/Droid heartbeat + drift labels
- `factory-droid-observation-context` — recall for `droid exec` / factory observe
- `loop-breaker` — abort + trim on `/looping`
- `node-packet-ledger` — compile plans into Pi Node Task Packets
- `pi-boss` — parallel subagent/spawn orchestration
- `bailian-*` — Aliyun Bailian CLI family (also in `~/.agents/skills`)

### D. Shared skills (`~/.agents/skills/`) — families

| Family | Members | Role |
|---|---|---|
| Bailian | `bailian-cli`, `docs-llm-wiki`, `finetune`, `gen`, `managed-agent`, `model-recommend`, `protocol`, `train-deploy` | Aliyun DashScope/`bl` |
| GDDP / graph | `gddp-node`, `gddp-wayfinder`, `wayfinder`, `graphify`, `graphify-query` | Graph navigation + node work |
| Memory / session | `daily-memory-intake`, `write-to-daily-memory`, `read-memory-space`, `session-align`, `handoff`, `claude-handoff` | Continuity |
| Grill / spec | `grill-me`, `grill-with-docs`, `grilling`, `batch-grill-me`, `to-spec`, `to-tickets`, `to-questionnaire` | Intent lock |
| Code craft | `code-review`, `codebase-design`, `improve-codebase-architecture`, `domain-modeling`, `tdd`, `implement`, `prototype`, `diagnosing-bugs`, `resolving-merge-conflicts` | Engineering loop |
| Teaching / Matt | `ask-matt`, `setup-matt-pocock-skills`, `setup-ts-deep-modules`, `teach`, `scaffold-exercises` | Pedagogy |
| Writing | `writing-beats`, `writing-fragments`, `writing-great-skills`, `writing-shape`, `edit-article` | Prose |
| Meta | `agent-bus`, `loop-me`, `triage`, `research`, `wizard`, `html-report`, `obsidian-vault`, `mp_skills`, `setup-pre-commit`, `migrate-to-shoehorn` | Misc |

### E. Hermes (`~/.hermes/`) — what it is

Hermes Agent (Nous Research): standalone agent with `config.yaml` (default grok-4.5 / xai-oauth + clinepass), `skills/` (large hub + profiles), `cron/`, `kanban/`, `hooks/`, `agent-hooks/`, `platforms/`, `sessions/`, `memories/`.  
**Plugins** live in `~/.hermes/plugins/` as Python packages + `plugin.yaml`:

- `answer_noise_trim`, `herdr-agent-state`, `moshi-hooks`, `one_screen_output_guard` — **same concerns as Pi extensions**, already dual-homed
- `hermes-achievements` — scan state only

Not a Pi package host. Overlap is policy/hooks (noise trim, herdr, moshi), not the extension API.

---

## 2. What is “dsh”?

**No binary, no repo, no plugin format found.** `command -v dsh` empty; no alias; no `*dsh*` tree under repos/hermes/homebrew.

Only durable hits:

1. **Author identity** — `aa-cli/docs/verify-pathway-architecture.md` line 4: `Author: dsh architecture pass 1 of 3 (deepseek-harness)`.
2. **aa-cli packet `target:`** on verify slices 02–06 (`target: dsh`). `targets.conf` has grok/pi/codex/claude/hermes/jules/droid/… — **no `dsh` row**. Slice 01/07 use `target: —`.

Interpretation: **dsh = DeepSeek Harness**, a named *dispatch/authoring persona* used when writing aa-cli verify design, **not** a plugin SDK. “dsh plugins” is undocumented/planned (or a speech mix-up with Hermes plugins / Pi packages / aa-cli targets).

aa-cli itself (`/Users/sab-mini/repos/aa-cli`) is the TUI daily loop (create/verify rooms, deck, fire via `targets.conf`). That is the closest “daily driver” product next to Pi.

---

## 3. Port seams

### Pi plugin shape (real, documented)

- **Extension** = TS module `export default function (pi: ExtensionAPI)` — events, `registerTool`, `registerCommand`, `ctx.ui`, session entries. Auto-load `~/.pi/agent/extensions/` or `.pi/extensions/`; `/reload`.
- **Package** = npm/git/path bundle (`pi` key or conventional dirs) of extensions + skills + themes + prompts. `pi install` → `settings.json`.
- **Skill** = Agent Skills `SKILL.md` (prompt+scripts), loaded on demand from `~/.pi/agent/skills` + `~/.agents/skills`.

### dsh plugin shape

**None.** If Sab meant Hermes: `plugin.yaml` + Python package. If he meant aa-cli: zsh `lib/*.zsh` + Rust `hub-rs` + `targets.conf` rows, not plugins.

### What unifies cleanly

1. **Policy twins already dual-homed**: answer-noise-trim, herdr-agent-state, moshi-hooks — one behavior, Pi TS + Hermes Python. Daily-driver package should treat these as *one capability, two adapters*.
2. **Session coordination**: pi-subagents + pi-intercom + pi-boss/pi-room + herdr mux — already the “rooms” stack; package + document enable-set.
3. **Skills are already shared** via `~/.agents/skills` (Pi + others). Port = curate a daily-driver skill set, not rewrite.
4. **Providers** (clinepass, antigravity, mercury, grok-cli) are independent packages — keep as optional installs, not core.

### What does not unify

- **aa-cli TUI / verify rooms** vs **Pi TUI extensions** — different runtimes (Rust+zsh vs Pi ExtensionAPI). Do not wrap aa-cli as a Pi extension.
- **Hermes plugin.yaml** ≠ **Pi ExtensionAPI**. Dual adapters, not one plugin file.
- **Harness-only extensions** (`ARTIFACT_DIR`, cwd-guard, eval-*) stay out of interactive daily-driver package.
- **dsh target** cannot be ported until it exists in `targets.conf` or a repo.

Cleanest unification seam: **one `pi` package** (`daily-driver` or similar) that *selects and documents* the interactive extension+skill set, plus a thin **capability catalog** mapping Hermes/aa-cli twins. Graph nodes = inventory → classify (interactive vs harness vs provider vs mux) → package manifest → adapter twins → enable/disable policy → dogfood.

---

## 4. Proposed GDDP nodes (~10)

Each = one bounded deliverable + evidence.

1. **`dd-inventory`** — Freeze this inventory as a checked-in catalog (package / local ext / skill / hermes plugin / aa-cli target). Evidence: markdown table + `settings.json` excerpt.
2. **`dd-classify`** — Tag each item: interactive-core | harness-only | provider | mux | skill-only | dead/archived. Evidence: tagged catalog; `pi-tool-display` ARCHIVED resolved.
3. **`dd-dsh-decision`** — Human: define dsh (deepseek-harness target vs speech error). Evidence: one decision note; either add `targets.conf` row or drop “dsh plugins” from graph.
4. **`dd-package-manifest`** — `package.json` `pi` key listing core interactive extensions+skills to install via `pi install`. Evidence: installable path package; `pi list` shows it.
5. **`dd-enable-set`** — settings policy: which current `packages[]` stay, which leftovers uninstall, harness ext stay local-only. Evidence: proposed `settings.json` diff (not applied until accept).
6. **`dd-adapter-twins`** — Spec for noise-trim / herdr / moshi: shared behavior, Pi+Hermes adapters, no third runtime. Evidence: one-page contract + file map.
7. **`dd-mux-stack`** — Document/compose subagents + intercom + boss/room + herdr without double-binding slash commands. Evidence: conflict matrix + recommended load order.
8. **`dd-skill-curation`** — Daily-driver skill allowlist from `~/.agents/skills` (gddp/memory/grill/code vs bailian/teaching). Evidence: allowlist file.
9. **`dd-aa-cli-boundary`** — Written seam: aa-cli remains fire/verify TUI; Pi remains coding harness; no verify-room port. Evidence: decision doc citing `LOOP.md` / `GDDP-becomes-small-and-real.md`.
10. **`dd-dogfood`** — Install package on sab-mini, `/reload`, one real session; list broken commands. Evidence: session recap + `pi list`.

Optional 11–12: **`dd-provider-optional`** (clinepass/antigravity/mercury as extras); **`dd-retire-leftovers`** (uninstall unused npm leftovers).

---

## 5. Open questions

1. Confirm **dsh** = deepseek-harness author/target only, not a plugin product.
2. Is the daily driver **a Pi package**, **aa-cli**, or a **meta-layer** over both? (Scout seam assumes Pi package + explicit aa-cli boundary.)
3. Should Hermes stay a first-class twin or become a consumer of Pi-only policy?
4. Keep Telegram (`@llblab/pi-telegram`) in daily-driver or optional? (USER.md Telegram boundary.)
5. `pi-studio` / `pi-grok-cli` / `pi-auto-mode` installed on disk but not in `packages[]` — intentional leftovers?

## Architecture (short)

Pi discovers **packages** (npm/git/path) and **loose TS extensions**. Skills overlay from `~/.agents`. Hermes has a separate Python plugin dir with overlapping *behaviors*. aa-cli is the operator TUI with named **targets**, one of which was labeled `dsh` in design packets only. Daily-driver port = curate/package the Pi interactive set + name the Hermes/aa-cli boundaries — not merge three plugin APIs.

## Start here

`/Users/sab-mini/.pi/agent/settings.json` (`packages` + `extensions`) then `~/.pi/agent/extensions/` — that pair is the live daily-driver, not `node_modules` alone.

## Residual risks

- Inventory of leftover npm pkgs may include transitive deps, not Sab installs.
- git packages `pi-room`/`pi-boss` not opened beyond settings spec.
- dsh remains unverified product-wise until Sab decides.
