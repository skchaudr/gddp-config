# Code Context

## Files Retrieved
1. `graphs/daily-driver/nodes/01-inventory-extension-catalog.yaml` — node 01 criteria
2. `graphs/daily-driver/nodes/02-classify-extension-tiers.yaml` — node 02 tiers
3. `~/.pi/agent/settings.json` (sab-mini packages[])
4. `~/.pi/agent/npm/package.json` — leftover deps
5. Live `ssh sab-air`: `~/.dsh/settings.yaml`, patches, profiles, `~/.config/deepseek-harness`, air `settings.json` packages
6. Written: `graphs/daily-driver/evidence/01-two-host-catalog.md`, `02-tier-classification.md`

## Key Code
- Mini packages[]: 12 declared (subagents 0.51, intercom, web-access, skyfallsin room+boss, cyber-ui 0.1.33, clinepass, telegram, antigravity-oauth, local gemini36+mercury, rpiv-ask).
- Air packages[]: 18 entries including studio, auto-mode, grok-cli, simplify, ui-minimal, add-dir, rpiv-todo, 22GNUs cyber-ui, subagents **0.35.1**.
- Air dsh default: deepseek-official / deepseek-v4-flash; llm-pi-ai grok :8645, qwen token-plan, zai, openrouter.

## Architecture
Two-host daily driver: sab-mini = Pi interactive; sab-air = dsh (`~/.dsh` + `~/.config/deepseek-harness` 0.1.0-rc.5) plus a fuller/older Pi enable-set. Shared local providers (gemini36, mercury) and mux hooks (herdr, moshi). Leftovers on mini disk are not in packages[].

## Start Here
`graphs/daily-driver/evidence/01-two-host-catalog.md` then `02-tier-classification.md`.

## Supervisor coordination
None required.

## Report
- Paths: `graphs/daily-driver/evidence/01-two-host-catalog.md`, `02-tier-classification.md`
- Catalog rows: sab-mini **136**; sab-air **92** (dsh 15 + source 59 + pi packages 18)
- Tiers (approx resolved): mini ic31 / ho10 / prov5 / mux14 / skill63 / dead6; air ic22 / ho18 / prov8 / mux6 / skill5 / dead3
- Unresolved: pi-auto-mode, pi-studio, pi-grok-cli leftovers; needle-*; dsh three patches not proven in profile; air minus-prefix extensions; air pi-claude-style-tools
- Read-only both hosts; no commits
