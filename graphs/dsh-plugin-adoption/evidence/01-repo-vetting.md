# Research: third-party DSH plugin/repo candidates (vet)

## Summary
All ten named surfaces exist as public GitHub repos (poison-guard also on npm). None are official DeepSeek. Default install is `dsh plugin --profile <p> add github:owner/repo` (or npm/npx), which mutates a Cordis profile; risk concentrates on unpinned `main` + in-process Node plugins. **TGYD-helige/dsh-pi** is a real DSH↔Pi compatibility host (Pi loader + `ExtensionRunner` per agent), not a Pi-core fork.

## Verdict table

| Name | Verdict | Rationale | Trust |
|------|---------|-----------|--------|
| awesome-deepseek-harness | **VETTED-OK** | Curated list only; no runtime code path if you only read it. | Community catalog, 182★, created 2026-08-13, last push 2026-08-23; license GitHub `NOASSERTION`; install N/A (docs). [repo](https://github.com/Dominic789654/awesome-deepseek-harness) |
| MaimoryLab/dib | **WATCH** | DSH-in-Box packager (private Node + Go launcher → NSIS/DMG/DEB). Catalog “not checked”; pin SHA. | Community, 4★, created 2026-08-13, push 2026-08-14; MIT; `dsh plugin add github:MaimoryLab/dib`. [repo](https://github.com/MaimoryLab/dib) |
| Saktawdi/dsh-ha-orchestrator | **WATCH** | In-process Cordis plugin: model HA failover + `orchestrate` (fanout/pipeline/supervisor/map-reduce/router). | Community, 9★, created 2026-08-14, push 2026-08-18; MIT; `dsh plugin --profile web add dsh-ha-orchestrator`. [repo](https://github.com/Saktawdi/dsh-ha-orchestrator) |
| **TGYD-helige/dsh-pi** | **WATCH** | Genuine Pi compatibility host; loads **trusted unmodified Pi extensions** as Node in DSH. Young + 4★; `allowLocalPaths` is an exec boundary. | Community org, 4★, created 2026-08-13, last push 2026-08-14, updated 2026-08-22; Apache-2.0; TS; topics `dsh-plugin`, `pi-coding-agent`. Install `dsh plugin --profile demo add dsh-pi-host` + Pi pkgs; config in `cordis.patch.yml` id `dsh-pi`. [repo](https://github.com/TGYD-helige/dsh-pi) |
| Q00/ouroboros#integrations/dsh-plugin | **WATCH** | Config-only MCP mount (36 `mcp__ouroboros__*` tools). Parent is large; plugin tracks mutable `main`. | Parent 5629★, created 2026-01-14, push 2026-08-23; MIT; `dsh plugin add "github:Q00/ouroboros#main&path:integrations/dsh-plugin"`. [README](https://github.com/Q00/ouroboros/blob/main/integrations/dsh-plugin/README.md) |
| dsh-poison-guard (zoahdev) | **WATCH** | Pre-install SAST (JS-X-Ray + deobfuscation). Scanner itself is a young npm/global CLI. | Community, 1★, created 2026-08-16, push 2026-08-17; MIT; `npm i -g dsh-poison-guard`. [repo](https://github.com/zoahdev/dsh-poison-guard) |
| dsh-plugin-doctor (zoahdev) | **WATCH** | Manifest/patch/build/pack + **fresh-profile install** (can execute install). | Community, 5★, created 2026-08-15, push 2026-08-22; MIT; `npx dsh-plugin-doctor` or `dsh plugin add dsh-plugin-doctor`. [repo](https://github.com/zoahdev/dsh-plugin-doctor) |
| dsh-plugin-check (omdsh-dev) | **WATCH** | Zero-dep **read-only** local checker + `plugin_check` tool. Safer surface than doctor. | Community org, 27★, created 2026-08-08, push 2026-08-21; MIT; `dsh plugin add github:omdsh-dev/dsh-plugin-check`. [repo](https://github.com/omdsh-dev/dsh-plugin-check) |
| api-relay-audit (toby-bridges) | **WATCH** | Standalone Python relay auditor (not a DSH host plugin). `curl` raw `audit.py` install. | Community, 800★, created 2026-03-30, push 2026-08-15; AGPL-3.0; `curl …/audit.py`. [repo](https://github.com/toby-bridges/api-relay-audit) |
| DSH-Plugins-Marketplace (bradeGithub) | **REJECT** | GUI that auto-collects/installs anything tagged `dsh-plugin`; plus `install.sh` remote-exec; repo size ~376k. | Community, 137★, created 2026-08-13, push 2026-08-23; MIT; `dsh plugin install bradeGithub/DSH-Plugins-Marketplace`. [repo](https://github.com/bradeGithub/DSH-Plugins-Marketplace) |

## Ecosystem (install / supply chain)

DSH treats “everything as a plugin”: `npx @deepseek-ai/dsh plugin --profile web add <npm|github:owner/repo[#ref][&path:]>`. Activation is Cordis profile + `cordis.patch.yml`, then restart the profile. Git specs default to a **moving branch**. Cordis plugins run as **trusted Node** in the harness process (tools, LLM hooks, HA, marketplace installers). Risk concentrates on: (1) unpinned `github:…#main`, (2) marketplace/topic scrapers, (3) `curl | sh` / global npm CLIs that claim to *guard* the chain, (4) packagers that ship a private Node runtime.

## Deep-dive: TGYD-helige/dsh-pi

**What it is:** A TypeScript **compatibility host**, not a source rewriter. It uses Pi’s official loader/`ExtensionRunner`, one Pi runtime **per DSH agent**, and maps Pi tools/commands/messages/lifecycle into that agent’s Cordis context. Targets **Pi 0.80.x** and **DSH 0.1.0-rc.6** (narrow peer range). Published bundle name in docs: **`dsh-pi-host`**; Cordis row id: **`dsh-pi`**.

**Capabilities (from README):** Partial `registerTool` / `registerCommand` / send-message / exec / flags / event bus; `pi.exec` uses Pi’s process runner (cwd/env/timeout/cancel). Unsupported: shortcuts, message/entry renderers, `registerProvider` (use `@deepseek-ai/dsh-llm-pi-ai` separately), session-tree ops, compaction, system-prompt read. `allowLocalPaths` default **false**; `projectTrusted` default **false**; host does **not** auto-discover `<cwd>/.pi/extensions`. Settings via `PI_CODING_AGENT_DIR` → profile `settings.json`.

**Genuine Pi integration?** Yes, by stated design (official Pi loader, fixture tests against a sibling `pi` checkout). Owner is org **TGYD-helige** (also has a `pi` packages repo); **not** Mario/Pi-official. Related community bridges exist (`AndPuQing/dsh-pi`, `Dwsy/dsh-pi-extension-bridge`).

**Install surface:** `dsh plugin --profile demo add dsh-pi-host @amaster.ai/pi-image-gen …` then full `config` replace on the `dsh-pi` row. Pi packages are plain deps (may warn no `dsh.bundle`).

**Red flags:** 4★, ~1 day of commits after create (2026-08-13→14); community org; installing it **executes selected Pi extensions as trusted Node**; `allowLocalPaths: true` is an explicit code-exec gate. No evidence of obfuscation from README/API metadata; no full source audit in this pass.

## Findings

1. **All candidates exist** — GitHub API 200s for every named owner/repo. [GitHub API](https://api.github.com/repos/TGYD-helige/dsh-pi)
2. **dsh-pi is a host, not a thin re-export** — maps ExtensionAPI tables in README. [README](https://raw.githubusercontent.com/TGYD-helige/dsh-pi/main/README.md)
3. **Marketplace is the highest install-amplification risk** — topic scrape + shell installers. [README.en](https://github.com/bradeGithub/DSH-Plugins-Marketplace/blob/main/README.en.md)
4. **Health tools are community, overlapping** — omdsh-dev check (read-only) vs zoahdev doctor (install-verify).

## Sources
- Kept: GitHub API JSON for all 10 repos — stars, dates, license, topics
- Kept: TGYD-helige/dsh-pi README — capability matrix
- Kept: Q00/ouroboros integrations/dsh-plugin README — install spec
- Dropped: SEO clone catalogs (dshplugin.market, dsh.directory, etc.) — secondary copies

## Gaps
- No line-level source review (no clone/install per task).
- npm package provenance for `dsh-pi-host` / `dsh-poison-guard` not fetched from registry tarball.
- Did not compare TGYD-helige/dsh-pi vs AndPuQing/dsh-pi vs Dwsy/dsh-pi-extension-bridge.

## Supervisor coordination
None.
