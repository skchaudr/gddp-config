# 03 — dsh harness inventory (sab-air, read-only)

Live host: `ssh sab-air` → `sab-air.local` (`Darwin … arm64`), `HOME=/Users/sab-mini`.
Probed: 2026-08-22. No writes to `~/.dsh` or `~/.config/deepseek-harness`.

## Live-verified probes

```
$ hostname
sab-air.local
$ command -v dsh
/Users/sab-mini/.local/bin/dsh
$ ls -la $(command -v dsh)
lrwxr-xr-x … /Users/sab-mini/.local/bin/dsh -> /Users/sab-mini/.config/deepseek-harness/apps/cli/lib/bin.js
$ dsh -V
0.1.0-rc.5
```

`dsh --help` (verbatim excerpt): boots a DeepSeek Harness profile — ordered plugin-bundle patch layers under user overrides. Flags: `--profile`, `--patch`, `--dump-config`, `--dump-default-config`. Commands: `web`, `acp`, `plugin`.

`ls ~/.config/deepseek-harness/packages` includes: `acp`, `api`, `attachment`, `boot`, `bundle`, `client`, `code-runtime`, `compaction`, `context`, `core`, `credentials`, `e2b`, `examples`, `extensions`, `feedback`, `fs`, `goal`, `guard`, `hooks`, `host`, `identity`, `interaction`, `jobs`, `llm`, `lsp`, `mcp`, `plan`, `preset`, `runtime-diagnostics`, `sandbox`, `schedule`, `sdk`, `session`, `session-query`, `settings`, `shell`, `skill`, `spill`, `storage`, `subagent`, `subprocess`, `terminal`, `test-support`, `todo`, `typert`, `util`, `web`, `workflow`, `workspace`.

`dsh --profile web --dump-config` starts with `@deepseek-ai/dsh-base` then `@deepseek-ai/dsh-web-app`. Notable: `hmr` plugin `@deepseek-ai/cordis-plugin-hmr` is present with `disabled: true` on this composed web tree.

---

## 1. Harness map (from source)

Source root: `/Users/sab-mini/.config/deepseek-harness`.

### Product spine and swappable loop

- npm scope `@deepseek-ai/dsh-*`. Cordis plugins contribute through `ctx.effect()`, `ctx.on()`, or `ctx.waterfall()`. Cited: `~/.config/deepseek-harness/packages/README.md` (opening + hierarchy table).
- `dsh-agent-loop` is swappable; UI/hook/tool plugins depend on `dsh-agent`, not the concrete driver. Cited: same README, Dependencies paragraph.
- Core group (`packages/core/README.md`): `ctx.sessions`, `ctx.systemPrompt`, `ctx.tools`, `ctx.agents`, `ctx.agentDefaultModel`, `ctx.agentLoop`. `agent` is the public contract; `agent-loop` is the default implementation.
- `packages/core/agent-loop/README.md`: only package with concrete loop logic. `ctx.agentLoop.create` / `ctx.agents.create` / `ctx.agents.resume` (resume requires `ctx.sessionPersistence`). Meta carries cwd/lineage.

### Reversible-effect registration (tools / providers / prompt sections)

Registration APIs return disposers and are fiber-scoped (HMR-safe: dispose fiber → contribution gone). Cited:

- Tools: `ctx.tools.register(definition): () => void` — “Disposed with the calling fiber.” Also `presentAs`, `restrict`, `guard`. `packages/core/tools/README.md` Public API.
- Prompt sections: `ctx.systemPrompt.section(...) : () => void`, plus `context`, `tools`, `variable` — all disposed with the calling fiber. `packages/core/system-prompt/README.md`.
- LLM providers: adapters register on `ctx.llm`. `packages/llm/README.md`.
- Subagent providers: `registerProvider(provider)` — “Registration is effect-scoped; removing it prevents new starts but does not revoke runs already returned.” Duplicate names fail loud. `packages/subagent/subagent/README.md` table.
- Package convention: “Registry contributions prove disposal through the HMR-safety test.” `packages/AGENTS.md`.

### Hot-reload

- Boot glue: `watchUserPatches(ctx, options)` registers the named patch file with Cordis HMR; add/change/removal recomposes the full patch list. Every profile boot keeps `cordis.patch.yml` live. Failed parse keeps last good tree; broadcasts `hmr/config-update-failed`. `packages/boot/app-boot/README.md`.
- Live web compose: `dsh --profile web --dump-config` shows `id: hmr` / `@deepseek-ai/cordis-plugin-hmr` with `disabled: true` (so source HMR plugin exists; this profile currently has it disabled).
- Extensions family (`packages/extensions/README.md`): model-facing live plugin inspect/mount/unmount (`tool-cordis`).

### Structured-output scoped runtime (`outputSchema`)

- Capability flag on providers: spawn/fork advertise `{ outputSchema: true, depthLimit: true, toolFilter: true, persona: true }`. `packages/subagent/subagent-spawn-in-process/README.md`, `subagent-fork-in-process/README.md`.
- Out-of-process providers (ACP, dsh-sdk) advertise `outputSchema: false`; service rejects requests that require them. `subagent-acp/README.md`, `subagent-dsh-sdk/README.md`.
- In-process driver: scoped `structured_output` tool + turn-concluding instruction. Canonical ack `{ recorded: true }`. Implementation: `packages/subagent/subagent-in-process-driver/src/structured.ts` (`STRUCTURED_OUTPUT_TOOL = 'structured_output'`). Docs: `subagent-in-process-driver/README.md` lines ~41–74.
- Descriptor omits `outputSchema` (activation result contract, not durable child identity). `packages/subagent/subagent/README.md`.

### `ctx.subagents.registerProvider()` seam

Call sites (live source):

- `packages/subagent/subagent-spawn-in-process/src/index.ts:63`
- `packages/subagent/subagent-fork-in-process/src/index.ts:93`
- `packages/subagent/subagent-acp/src/index.ts:188`
- `packages/subagent/subagent-codex/src/index.ts:100`
- `packages/subagent/subagent-claude-code/src/index.ts:111`
- `packages/subagent/subagent-dsh-sdk/src/index.ts:137`

Family table: `packages/subagent/README.md` (`ctx.subagents` + spawn/fork/acp/codex/claude-code/dsh-sdk + model tools).

### Memory model

- In-memory session is an append-only event log. Durable JSONL backend: one logical JSONL per session, default file `session.jsonl.zstd`. `packages/session/session-persistence-jsonl/README.md`.
- Header: `{ type: 'session', version, id, cwd?, createdAt, parentSession?, seedLength?, origin?, delegationDepth, agentPreset? }`. `delegationDepth` required; `0` for top-level. `parentSession` + depth = lineage.
- Layout on sab-air: `~/.dsh/sessions/--<normalized-cwd>--/<id>/session.jsonl.zstd` (observed).
- Compaction: `ctx.compaction` + `compaction-basic` + tool-result pruner + `/compact`. `packages/compaction/README.md`. Descriptor events retained across compaction (`subagent/README.md`).
- Continuable children: `backgroundMode: continuable` on spawn/fork tools; descriptor records provider/model/persona/toolFilter for cold resume. `subagent/README.md`.
- List / resume / interrupt:
  - Resume: `ctx.agents.resume({ resumeSessionId, … })` (`agent-loop/README.md`).
  - List/interrupt/send: `list_agents`, `interrupt_agent`, `send_message` (`packages/subagent/tool-subagent-control/README.md`). Interrupt stops current turn (`keepInbox`); lineage-checked.
- Session-query family: authorized reads, lineage/relationships, FTS. `packages/session-query/README.md`.

### Orchestration layers

| Layer | ctx / tools | Source |
|---|---|---|
| Goals | `ctx.goals`, `tool-goal`, `/goal` | `packages/goal/README.md` |
| Skills | `ctx.skills`, `skill-filesystem`, `tool-skill` | `packages/skill/README.md` |
| Workflows | `ctx.workflowEngine`, `tool-workflow`, `tool-ralph` | `packages/workflow/README.md` |
| Jobs | `tool-jobs` | `packages/jobs` (group in packages/README.md) |
| Presets | `ctx.agentPresets` | `packages/preset/README.md` |

**Agent-bus:** no package, file, or README named `agent-bus` / `agentBus` under `~/.config/deepseek-harness` (search returned only unrelated node_modules). `~/.dsh/CONTEXT.md` lists “agent-bus” as an orchestration layer; that claim is **not** sourced in the checkout. Closest live surfaces: `ctx.subagents` control tools + `ctx.workflowEngine`.

---

## 2. Plugin surface (`~/.dsh`)

Root listing (live `ls -la ~/.dsh`):

| Artifact | Purpose (from files) |
|---|---|
| `settings.yaml` | User settings. `agent-default-model`: `deepseek-official` / `deepseek-v4-flash` / `reasoningEffort: high`. `llm-pi-ai.providers`: **grok** (`http://127.0.0.1:8645/v1`, model `grok-4.5`, `DSH_GROK_API_KEY`); **qwen-token-plan-individual** (Aliyun token-plan, `thinkingFormat: qwen`, models incl. `qwen3.8-max`); **zai**; **openrouter** presets. UI: dark theme, `busyEnter: steer`. |
| `.credentials.yaml` | Keys present (names only): `DSH_GROK_API_KEY`, `QWEN_TOKEN_PLAN_API_KEY`, `ZAI_API_KEY`, `OPENROUTER_API_KEY`. Not opened for values. |
| `AGENTS.md` | Operating rules for the agent; points at `CONTEXT.md`. |
| `CONTEXT.md` | Capability-framing doctrine + unverified-until-now harness claims (this inventory is the source check). |
| `.anonymous-user-id` | Identity cookie (not read). |
| `profiles/acp/` | ACP stdio profile. `package.json` bundles `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-acp-app`. `cordis.yml` is `[]`; `cordis.patch.yml` is `[]`. |
| `profiles/web/` | Web GUI profile. Bundles `dsh-base` + `dsh-web-app`. Extra dep: linked `dsh-subagent-claude-code`. `cordis.patch.yml` inserts moshi-bridge, keybindings, claude-code subagent via Hermes `:8649`, native `subagent_grok` (spawn → grok/:8645), native `subagent_qwen` (spawn → qwen-token-plan). Also `moshi-bridge.mjs`, `keybindings.mjs`. |
| `profiles/node_modules/` | Shared profile installs. |
| `patches/claude-code-grok.yml` | Opt-in overlay: Claude Code child → Hermes `:8649` + `toolName: subagent_claude_code`. |
| `patches/subagent-grok.yml` | Opt-in native Grok spawn (`subagent_grok`, maxDepth 3). |
| `patches/subagent-qwen.yml` | Opt-in native Qwen spawn (`subagent_qwen`, `qwen3.8-max`). |
| `.agent-presets/gddp/` | User preset. `preset.yml`: name `gddp`, “GDDP graph-loop agent — orchestrator and node-executor roles…”. `agent.cordis.yml`: persona (ORCHESTRATOR vs EXECUTOR doctrine), bash/fs/jobs/skills/goals/plan/compaction, continuable spawn+fork, workflow+ralph, ask-user, todo, web. Codex/claude-code tool rows present but `disabled: true`. Host keeps registries/sandbox/persistence/model route. |
| `sessions/` | Per-cwd session stores; transcripts are `session.jsonl.zstd`. Workspaces include home, `.config`, deepseek-harness, zed, `.dsh`, `.t3`, litellm-gateway, aa-cli, gddp-runtime. |
| `storages/` | `workspace.json`, `session_projcache.json` (non-session storage hub; `packages/storage`). |

### gddp preset (what it does)

Mounts a standing agent-plane composition: GDDP persona (orchestrator dispatches node contracts; executor fulfills one node; no live steering; graph truth human-owned). Enables standard coding tools plus goal/skill/job/plan/compaction and **continuable** in-process subagents + workflow/ralph. Does not own host registries. Product subagents (codex, claude-code) are in the file but disabled.

---

## 3. Capability gaps (not verified)

- No `agent-bus` package or docs in the source tree.
- HMR **plugin is composed but disabled** on the live web dump; `watchUserPatches` is documented; we did not mutate `cordis.patch.yml` to watch a live reload.
- Did not decompress a `session.jsonl.zstd` to print a header (read-only; would be observational only — skipped to avoid implying session content review).
- Did not run a live child / structured_output turn (would be a write/runtime experiment).
- Did not dump ACP compose tree (`dsh --profile acp --dump-config`).
- `.anonymous-user-id` and credential **values** unread.

---

## Files another agent should open first

1. `~/.config/deepseek-harness/packages/README.md` — group map.
2. `~/.dsh/settings.yaml` + `~/.dsh/profiles/web/cordis.patch.yml` — live model routes and inserted tools.
3. `~/.dsh/.agent-presets/gddp/agent.cordis.yml` — intended GDDP composition.
