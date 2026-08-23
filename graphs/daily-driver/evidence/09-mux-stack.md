# Node 09 — mux-stack (sab-mini): compose without double-binding

Inventory date: 2026-08-22 (read-only). Host: **sab-mini**.  
Sources: live `~/.pi/agent/settings.json`, wrapper `~/.pi/agent/bin/pi`, command/tool registrations in npm + git packages + local extensions.  
No settings, packages, or extension files were changed.

Stack in scope: **pi-subagents** + **pi-intercom** + **pi-boss / pi-room** (skyfallsin git) + **herdr mux** (herdr-boss / herdr-room / herdr/mux.ts / herdr-agent-state) + **moshi-hooks**.

---

## 1. Conflict matrix

Legend: **DOUBLE-BOUND** = same slash-command name or same `registerTool` name registered by two live mux surfaces.  
Slash collisions among this stack: **0**. Tool-name collisions: **3**.

### Surfaces and bindings

| Surface | Live path | Slash / shortcut | Tools / other | Collides with |
|---------|-----------|------------------|---------------|---------------|
| pi-subagents 0.51.0 | `~/.pi/agent/npm/node_modules/pi-subagents` (`src/slash/slash-commands.ts`, `src/extension/index.ts`) | `/subagents`, **`/run`**, `/subagent-cost`, `/subagents-doctor`, `/subagents-guide`, `/subagents-refine`, `/subagents-fleet`, `/subagents-detach`, `/subagents-stop`, `/subagents-models`, `/subagents-profiles`, `/subagents-load-profile`, `/subagents-refresh-provider-models`, `/subagents-generate-profiles`, `/subagents-check-profile` | tool **`subagent`**; herdr status bridge emits `herdr:busy` / `herdr:blocked` | purpose overlap with `spawn` (not same name) |
| pi-intercom 0.10.1 | `~/.pi/agent/npm/node_modules/pi-intercom/index.ts` L2433–2446 | **`/intercom`**, `/intercom-id`, shortcut **`alt+m`** | overlay + broker; no tools | none in this stack |
| pi-room (skyfallsin git 1.0.0) | `~/.pi/agent/git/github.com/skyfallsin/pi-room/extensions/room.ts` | none | tools **`peek`**, **`steer`** (tmux) | **DOUBLE-BOUND** vs herdr-room |
| pi-boss (skyfallsin git 1.0.0) | `~/.pi/agent/git/github.com/skyfallsin/pi-boss/extensions/boss.ts` | none | tool **`spawn`** (tmux panes) | **DOUBLE-BOUND** vs herdr-boss |
| herdr mux helper | `~/.pi/agent/extensions/herdr/mux.ts` | none (library, not an extension entry) | `herdrExec` / `herdrJson` / `HERDR_PANE_ID` | n/a |
| herdr-room | `~/.pi/agent/extensions/herdr-room/index.ts` | none | tools **`peek`**, **`steer`** (Herdr panes) | **DOUBLE-BOUND** vs pi-room |
| herdr-boss | `~/.pi/agent/extensions/herdr-boss/index.ts` | none | tool **`spawn`** (Herdr panes + dispatch jsonl) | **DOUBLE-BOUND** vs pi-boss |
| herdr-agent-state | `~/.pi/agent/extensions/herdr-agent-state.ts` | none | socket status to Herdr (`herdr:pi`); no tools | event-bus overlap with subagents herdr bridge + moshi |
| moshi-hooks | `~/.pi/agent/extensions/moshi-hooks.ts` | none | lifecycle hooks → `/opt/homebrew/bin/moshi-hook pi-hook` | none (hooks only) |
| workmux-status (adjacent mux) | `~/.pi/agent/extensions/workmux-status.ts` | none | `workmux set-window-status` on agent events | status-channel overlap with herdr-agent-state |

### DOUBLE-BOUND rows ( Sab accept — not silently changed )

| ID | Binding | A | B | Severity |
|----|---------|---|---|----------|
| C1 | tool `spawn` | skyfallsin **pi-boss** | **herdr-boss** | **high** — last `registerTool` wins; tmux vs Herdr backends diverge |
| C2 | tool `peek` | skyfallsin **pi-room** | **herdr-room** | **high** |
| C3 | tool `steer` | skyfallsin **pi-room** | **herdr-room** | **high** |

No slash command is registered twice inside this mux set. **`/run`** is generic but unique here (pi-subagents only). **`alt+m`** is unique (pi-intercom only).

### Soft / purpose overlaps (not same binding)

| ID | Overlap | Notes |
|----|---------|-------|
| S1 | `subagent` tool + `/run` vs `spawn` | In-process pi-subagents vs visible pane spawn. Different names; operators can still fire both. |
| S2 | herdr status | pi-subagents `herdr-status.ts` + `herdr-agent-state.ts` + moshi-hooks all talk to pane/lifecycle. Complementary if Herdr is the mux; noisy if workmux also enabled. |
| S3 | profile wrapper vs `packages[]` | `~/.pi/agent/bin/pi` **lite** uses `--no-extensions` then re-adds user `extensions/*` + leftovers + **pi-subagents only** — **omits** pi-intercom, pi-boss, pi-room. **full** adds intercom + telegram, still not git boss/room. |

---

## 2. Load order

### Declared `packages[]` (settings.json, current)

1. `npm:pi-subagents`  
2. `npm:pi-intercom`  
3. `npm:pi-web-access`  
4. `git:github.com/skyfallsin/pi-room`  
5. `git:github.com/skyfallsin/pi-boss`  
6. …providers / UI / telegram / mercury  

If the **real** Pi binary honors `packages[]` (no `--no-extensions`), git **room then boss** load after subagents+intercom. Local `~/.pi/agent/extensions/**` still load via default discovery **in addition**, so herdr-boss/room register the **same** tool names again.

### Wrapper `~/.pi/agent/bin/pi` (this machine’s `pi` on PATH)

`add_user_extensions`: all `extensions/*.ts` (alpha) then each `extensions/*/index.ts` (dir alpha).

Relevant mux order on **lite** (`pi` default profile):

1. `herdr-agent-state.ts`  
2. `moshi-hooks.ts`  
3. `workmux-status.ts`  
4. `herdr-boss/index.ts`  *(before room — alpha)*  
5. `herdr-room/index.ts`  
6. then hardcoded leftovers (`pi-web-access`, rpiv-*, **pi-simplify**, **pi-auto-mode**, 22GNUs cyber-ui, grok-cli, …)  
7. `pi-subagents/index.ts`  

**Not** on lite: pi-intercom, skyfallsin pi-boss/pi-room.

**full**: user extensions + same leftovers + **pi-intercom** + pi-subagents + telegram.

`herdr/mux.ts` is imported by herdr-boss/room; it is not itself registered.

### Recommended enable/load order (for Sab accept)

Intended mux for sab-mini daily driver is **Herdr**, not raw tmux skyfallsin packages (herdr-boss comments: “visible Herdr panes”; catalog node 02 puts both in `mux`).

1. **Keep** `herdr/mux.ts` as library only.  
2. **Enable herdr-room before herdr-boss** (rename/prefix if load order must be explicit; today alpha loads boss first — runtime-safe because room is only needed when peek/steer run).  
3. **Enable moshi-hooks** after pane identity (`herdr-agent-state`) so SessionStart sees `HERDR_PANE_ID`.  
4. **Enable pi-intercom** on any interactive profile that should use `/intercom` + Alt+M (today **missing on lite**).  
5. **Enable pi-subagents last** among coordinators so `/run` + `subagent` see intercom + herdr status.  
6. **Do not enable skyfallsin pi-room + pi-boss in the same process as herdr-room + herdr-boss.**

---

## 3. Recommendations (Sab accept — not applied)

| Rec | Action | Why |
|-----|--------|-----|
| R1 | **Remove** `git:github.com/skyfallsin/pi-room` and `git:github.com/skyfallsin/pi-boss` from `packages[]` **or** disable `herdr-boss` + `herdr-room`. Pick one mux backend. | Resolves C1–C3. Herdr-shaped daily driver → drop git pkgs. |
| R2 | If keeping Herdr: leave tools named `spawn`/`peek`/`steer` on herdr-* only. | Matches skill `pi-boss` docs + existing herdr-boss API. |
| R3 | Add **pi-intercom** to the lite wrapper allowlist (or stop using `--no-extensions` for interactive). | Alt+M / `/intercom` otherwise absent on default `pi`. |
| R4 | Keep pi-subagents `subagent` + `/run` as **in-process** delegation; use `spawn` only for visible panes. Document in AGENTS/skill so agents do not double-dispatch. | Soft overlap S1. |
| R5 | Wrapper `common_extensions` still force-loads leftover simplify/auto-mode/grok-cli/22GNUs cyber-ui — out of mux node but pollutes the same process. Clean in a later node. | Unexpected extra surfaces. |
| R6 | Prefer one status sink: herdr-agent-state **or** workmux-status in interactive Herdr panes. | Avoid dual window-status writers. |

---

## Verify notes

- `pi.registerCommand` / `registerTool` / `registerShortcut` read live on disk 2026-08-22.  
- settings `packages[]` matches catalog node 01.  
- Conflict count **hard = 3** (spawn, peek, steer). Slash double-binds in this stack = **0**.  
- Top 3: C1 spawn, C2 peek, C3 steer → R1.

## Residual

- Last-writer-wins behavior of `registerTool` not traced in `@mariozechner/pi-coding-agent` source on this host (package not in npm tree).  
- Whether this interactive session used wrapper lite vs real binary + `packages[]` is process-dependent; both paths documented.
