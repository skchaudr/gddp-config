# Code Context

## Files Retrieved
1. `graphs/daily-driver/nodes/03-dsh-harness-inventory.yaml` - node contract
2. sab-air `~/.config/deepseek-harness/packages/README.md` - package hierarchy / ctx.effect
3. sab-air `packages/core/README.md`, `agent-loop/README.md`, `tools/README.md`, `system-prompt/README.md` - spine
4. sab-air `packages/subagent/**/README.md` + `registerProvider` call sites - seams / outputSchema
5. sab-air `packages/session/session-persistence-jsonl/README.md` - JSONL memory
6. sab-air `packages/{goal,skill,workflow,compaction,preset,session-query,boot/app-boot,extensions}/README.md`
7. sab-air `~/.dsh/{settings.yaml,AGENTS.md,CONTEXT.md,patches/*,profiles/*/*,.agent-presets/gddp/*}`

## Key Code
- `dsh` → `~/.config/deepseek-harness/apps/cli/lib/bin.js` (v `0.1.0-rc.5`)
- `ctx.tools.register` / `ctx.systemPrompt.section` return fiber disposers
- `ctx.subagents.registerProvider()` — spawn/fork/acp/codex/claude-code/dsh-sdk
- Spawn/fork: `{ outputSchema: true, … }`; in-process `structured_output` tool (`subagent-in-process-driver/src/structured.ts`)
- Sessions: `~/.dsh/sessions/--<cwd>--/<id>/session.jsonl.zstd`; header has `parentSession`, `delegationDepth`
- Control tools: `list_agents` / `send_message` / `interrupt_agent`
- Live web patch inserts moshi-bridge, claude-code→:8649, `subagent_grok`→:8645, `subagent_qwen`

## Architecture
Cordis composition: profile `package.json` bundles (`dsh-base` + `dsh-web-app` or `dsh-acp-app`) then `cordis.patch.yml` then `--patch`. Host owns registries/persistence/model; presets (`gddp`) mount per-agent tools/persona. Default model `deepseek-official/deepseek-v4-flash`; extra routes grok (Hermes :8645) and qwen token-plan in `settings.yaml`.

## Start Here
`graphs/daily-driver/evidence/03-dsh-harness-inventory.md` then `~/.config/deepseek-harness/packages/README.md`.

## Supervisor coordination
None.

## Deliverable
Written: `graphs/daily-driver/evidence/03-dsh-harness-inventory.md`

### Harness map (summary)
dsh-agent-loop is the only concrete driver; plugins depend on `dsh-agent`. Tools/providers/prompt sections register as fiber-disposed effects. HMR via `watchUserPatches` + `cordis-plugin-hmr` (disabled on current web dump). `outputSchema` is an in-process scoped `structured_output` runtime. `registerProvider` is the open subagent seam. Memory is append-only JSONL.zstd with compaction, lineage/depth, list/resume/interrupt. Orchestration: goals, skills, workflows/ralph. No `agent-bus` package found.

### Plugin surface (summary)
`settings.yaml` default DeepSeek + grok/:8645 + qwen token-plan + zai + openrouter. Profiles acp (empty patch) and web (moshi, grok/qwen/claude-code tools). Patches duplicate those overlays. Preset `gddp` = orchestrator/executor GDDP persona + standard tools + continuable spawn/fork. `sessions/` zstd logs; `storages/` workspace + projcache.

### Gaps
agent-bus missing in source; HMR disabled on web dump; no live child/structured turn; session files not decompressed; ACP dump not run.
