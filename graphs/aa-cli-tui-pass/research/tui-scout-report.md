# Scout: aa-cli TUI/graph graph (read-only)

## Files Retrieved

1. `/Users/sab-mini/repos/aa-cli/AGENTS.md` (1–97+) — product intent, picker-first TUI, packet fields
2. `/Users/sab-mini/repos/aa-cli/gddp/project.yaml` (full) — pilot graph statuses
3. `/Users/sab-mini/repos/aa-cli/gddp/CANONICAL.md` (1–80) — two-path cockpit, node rule
4. `/Users/sab-mini/repos/aa-cli/bin/aa` (1–80, 103–189) — CLI surface
5. `/Users/sab-mini/repos/aa-cli/hub-rs/Cargo.toml` — ratatui 0.30 + crossterm + nucleo-picker
6. `/Users/sab-mini/repos/aa-cli/hub-rs/src/keymap.rs` (1–80) — deck/verify keys
7. `/Users/sab-mini/repos/aa-cli/hub-rs/.agents/skills/tui-design/SKILL.md` (1–60) — in-repo TUI design skill
8. `/Users/sab-mini/repos/aa-cli/docs/verify-slices/README.md` + `02-verify-schema-and-verdict.md` + `docs/verify-pathway-architecture.md` — dsh + verify landed
9. `/Users/sab-mini/repos/aa-cli/7.29.26-aa-cli-plan.md` — last foundational pass (create verb-first)
10. `/Users/sab-mini/repos/aa-cli/DISPATCH-CANDIDATES.md`, `AA_TEST_WALKTHROUGH.md` — deck cards; walkthrough is stale zsh-root-menu
11. `/Users/sab-mini/repos/aa-cli/peek.out` — sample GDDP receipt text dump
12. `/Users/sab-mini/.pi/agent/skills/pi-boss/SKILL.md` — parallel orchestration, not TUI design
13. `/Users/sab-mini/.pi/agent/npm/node_modules/pi-subagents/skills/pi-subagents/SKILL.md` — parent-only subagent router
14. `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/tui.md` — Pi extension TUI components (TypeScript `@earendil-works/pi-tui`), not aa-hub
15. `/Users/sab-mini/repos/aa-cli/docs/fzf-face.md` — fzf as escape hatch
16. `/Users/sab-mini/repos/aa-cli/gddp/nodes/deck-action-wiring.yaml` — typical node shape

---

## aa-cli state snapshot

**What exists**

- **Intent:** human dispatch/review cockpit (not autonomous loop). Paths: Deck = session home; Create = Tab lane; converge on packet → fire → result → verify. Pickers first (nucleo in-hub; shell fzf suspend-and-return).
- **Frontend:** `hub-rs/` Rust binary `aa-hub` — **ratatui + crossterm + nucleo-picker**. UI modules: `dashboard`, `runway`, `create_prepare`, `verify`, `recon`, `root`, `pick`, `submenu`. Shared keymap in `hub-rs/src/keymap.rs`.
- **Backend:** `bin/aa` (zsh) + `lib/*.zsh` — fire, ledger, reconcile, deck, verbs, validate, vault, inventory, jules, pi.
- **CLI commands today:** bare `aa` → zsh `aa_root_menu`; `gen`, `refine`, `fire PACKET`; `deck` (`--list|--output|--peek|--fzf|--sync|import-pi` or interactive); `ledger`; `reconcile`; `vault sync`; `inventory`; `jules {status|pull|diff|apply|open|fire}`; `pi`; verbs `audit|recon|brief|explain|study`; `verify`; `archive`; `agent-shot`; `generate-path`; `generate-import`.
- **State:** packets under `AA_DATA_HOME`, runs/ledger under `AA_STATE_HOME`. `targets.conf` registry. Schema `schema/packet.schema.json`.
- **Pilot GDDP (`gddp/`):** last_updated 2026-07-17. Complete: graph ownership, two-path shell, deck-home, dispatch-lifecycle, common-core, target-registry, ledger, dispatch-router, sync-backgrounding, reconciliation, cockpit-state-machine. In progress: deck-runway, deck-baseline-ui, deck-action-wiring, deck-verification-review, create-baseline-flow, create-recon-tools, create-task-authoring. Ready: openclaw-cross-machine. Planned: keymap, create-linear-surface, packet-schema-align, fzf-nav, polish, depends_on, runnable-now filter, create-fzf, prompt-skill-reuse, create-converge-fire-or-deck, target-dispatch-via-registry.
- **Verify slices (docs/verify-slices, recut 2026-08-20):** 01–07 **landed** (rooms, schema/verdict, accept/archive, evidence picker, review log, agent room, gddp receipts). One grammar: Evidence / Agent / Contract; only human ✓✓ releases.
- **Create verb-first (7.29.26 plan):** P0–P3 shipped on `feat/create-verb-first` (pathway door, `aa <verb>` call, respond). P4 verb-filtered templates / P5 respond-on-verify not done. Known Enter/sticky-pathway bugs.
- **Deck cards:** `DISPATCH-CANDIDATES.md` is Jules work for *other* repos; not the TUI graph.
- **Walkthrough:** `AA_TEST_WALKTHROUGH.md` still describes old numeric Root lobby (`0 generate / 1 deck`) — **stale vs hub-deck-home**.

**UI/UX gaps (documented or obvious)**

- Shared primary keymap (`cockpit-keymap`) still **planned**; fzf must stay on `;` not `f`.
- Deck readability, runway, polish, runnable-now filter, depends_on — graph says in_progress/planned.
- Create still multi-surface vs planned **one linear room** (command/insert, f/s on-surface).
- Prompt picker lost on create (`p` rebound to Pathway); empty follow-up re-fires; Enter-as-call while verb pathway set.
- Dual packet field models (AGENTS vs hub-authored) — `packet-schema-align` planned.
- `AA_TEST_WALKTHROUGH` / Root lobby docs drift.

**Backend wiring missing / incomplete for frontend**

- `deck-action-wiring` still in_progress: f/o/Enter/v must hit `bin/aa` and return receipts/toasts.
- `target-dispatch-via-registry` planned (all executors registry-driven).
- Verify already has `aa verify`, `aa archive`, `aa agent-shot`; create needs reliable `aa <verb>` + last-run capture (P2/P3 exist; edges remain).
- Peek plumbing exists (`aa deck --peek`) — `peek.out` is a **sample receipt dump** (gddp `needs-more-evidence` fixture text), not a live TUI snapshot.
- Dual-write packet schema (validated vs verified/verdict) — slices landed; graph node `packet-schema-align` not marked complete.

---

## TUI design skill inventory

| Asset | Path | Applies how |
|---|---|---|
| **tui-design skill (in aa-cli)** | `hub-rs/.agents/skills/tui-design/SKILL.md` + `references/` | **Primary.** Framework-agnostic process: layout paradigm, interaction, visual system, anti-patterns. Ratatui-relevant. User/agent named in brief exists here as repo skill. |
| **Pi tui.md / keybindings.md** | `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/tui.md` (+ keybindings.md) | Pi **extension** TUI (`@earendil-works/pi-tui` TS Component interface). Pattern reference only; **do not** port aa-hub onto it. |
| **pi-boss** | `~/.pi/agent/skills/pi-boss/SKILL.md` | Orchestration (subagent/spawn). Not TUI design. |
| **pi-subagents** | npm skill | Parent orchestrator only. |
| **Framework in product** | `hub-rs/Cargo.toml` | **ratatui 0.30 + crossterm 0.29 + nucleo-picker**. No ink/textual/bubbletea. |
| **Design docs already in repo** | `docs/verify-pathway-architecture.md`, `hub-rs/fable-claude-aa-cli-tui-rooms-design.md`, `docs/fzf-face.md`, `docs/specs/2026-06-14-cockpit-ideas.md` | Rooms grammar, fzf hatch, salvaged cockpit ideas |

**Walkthrough graph arc:** run tui-design against **every operator surface** (Deck, runway, Create, Verify rooms, pickers, keymap), then close backend gaps, then integrate, then operator walkthrough.

---

## dsh meaning + location (boundary)

**dsh = Deepseek harness / Deepseek Pro (author/executor), not “dashboard shell”.**

- `docs/verify-pathway-architecture.md` line 4: **Author: dsh architecture pass 1 of 3 (deepseek-harness)**.
- Verify slice YAML `target: dsh` on slices 02–06 = dispatch target for that design/impl pass.
- **Separate graph** (Pi extensions + dsh plugins as daily driver) must not absorb aa-cli TUI nodes. dsh is an **executor label** in this repo, not a product surface to port.

---

## Proposed node list (8–14) — TUI/UX → backend → integrate → walkthrough

Keep **separate** from existing `gddp/` pilot (do not silently rewrite old node statuses). New graph IDs:

1. **tui-inventory-and-keymap-audit** — Walk all screens vs tui-design skill; produce binding map (Deck/Create/Verify/pickers) vs `keymap.rs` + AGENTS defaults. Evidence: inventory md + conflict list.
2. **tui-visual-system** — Shared density, glyphs (white/green/red ✓, ✓✓), truncation, empty states. Evidence: before/after render tests in `hub-rs/tests`.
3. **tui-deck-runway-pass** — Top list + bottom runway spatial memory; fire keeps TUI. Evidence: `ui/dashboard.rs` + `ui/runway.rs` render tests.
4. **tui-create-linear-room** — One create room; pathway door already P1; finish linear chrome (P4 templates optional). Evidence: create_prepare + keys.
5. **tui-verify-rooms-polish** — Evidence/Agent/Contract already landed; apply tui-design (focus, picker-not-keybar). Evidence: `ui/verify.rs` + slice docs.
6. **tui-picker-grammar** — Nucleo default; fzf only `;` suspend. Evidence: `picker.rs` + `docs/fzf-face.md` alignment.
7. **backend-deck-actions** — Close `deck-action-wiring`: f/v/o/Enter/a → `bin/aa` receipts. Evidence: exec/fire tests + toast contract.
8. **backend-packet-schema-align** — Dual-write AGENTS fields / verified+verdict; ledger never released except human review. Evidence: schema + `lib/validate.zsh` + generate.
9. **backend-create-verb-edges** — Fix Enter-as-call, sticky pathway, blank respond (7.29 issues 1–4). Evidence: cargo tests + cited main.rs/app.rs.
10. **backend-registry-dispatch** — Remaining executors via `targets.conf` only. Evidence: `lib/fire.zsh` + targets tests.
11. **frontend-integration** — Hub calls only documented `aa` subcommands; no parallel fire path. Evidence: `exec.rs`/`fire.rs` command table.
12. **operator-walkthrough** — Replace stale `AA_TEST_WALKTHROUGH.md` with Deck-home + create + fire + verify ✓✓ script. Evidence: walkthrough + recorded peek/receipt.
13. **graph-walk-verification** — Run entire new graph as operator session; one receipt per node. Evidence: `gddp/executor-receipts/` style files (proposal-only status).

Optional 14: **deck-runnable-now-and-deps** — filter + `depends_on` (only if walkthrough proves clutter).

---

## Architecture (pieces)

```
operator → aa-hub (ratatui) → exec.rs shells out → bin/aa → lib/*.zsh
                ↑                      ↓
         nucleo pickers          ledger.tsv, run dirs, packets JSON
         keymap.rs               targets.conf
```

Verify rooms invert Create rooms; human Accept writes `verified: review` + archive. GDDP graph is project-local; executors write receipts, humans change node yaml.

---

## Start Here

Open `hub-rs/.agents/skills/tui-design/SKILL.md` then `hub-rs/src/keymap.rs` and `gddp/CANONICAL.md`. Those three define design process, live keys, and existing graph debt.

---

## Open questions / not found

- No `tui-design` under `~/.pi/agent` (only in `aa-cli/hub-rs/.agents/skills/`). Confirm whether parent's “user agent in subagent list” is this skill or a separate Pi agent file.
- `gddp/project.yaml` vs verify-slices: graph timestamps (2026-07-17) lag landed 2026-08 verify work — statuses are **stale**.
- Branch/HEAD of aa-cli at scout time not recorded as git status (read-only; did not treat as gddp-runtime worktree).
- Pi `docs/keybindings.md` not fully read (tui.md is extension-component docs).
- `peek.out` origin commit / generator script not traced beyond content.

---

## Supervisor coordination

None required (no product ambiguity blocking scout deliverable).
