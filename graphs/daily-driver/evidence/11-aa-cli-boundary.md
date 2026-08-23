# Node 11 — aa-cli / Pi / dsh written seam

Date: 2026-08-23. Hosts checked live: **sab-mini** (`hostname`) and **sab-air** (`ssh sab-air`, `aa` at `/usr/bin/aa` on both).  
No aa-cli, Pi, or dsh config was changed. No commits.

Cited doctrine (paths as they exist on disk; node yaml listed a shorter `docs/` path that is not present):

- `/Users/sab-mini/repos/aa-cli/gddp/CANONICAL.md`
- `/Users/sab-mini/repos/gddp-runtime/docs/proposals/LOOP.md`
- `/Users/sab-mini/repos/gddp-runtime/docs/decisions/GDDP-becomes-small-and-real.md`

Inventory context: `graphs/daily-driver/evidence/01-two-host-catalog.md`.  
TUI implementation graph: `graphs/aa-cli-tui-pass/`.

---

## 1. Seam (roles stay split)

| Surface | Role | Where |
|---------|------|--------|
| **aa-cli** | Fire / verify TUI (Deck, Create, verify rooms, `targets.conf` dispatch) | Both hosts. `/usr/bin/aa` on sab-mini and sab-air. Repo: `/Users/sab-mini/repos/aa-cli`. |
| **Pi** | Interactive coding harness (extensions, skills, daily-driver package) | Daily driver on **sab-mini**. Pi also exists on sab-air (divergent `packages[]` — catalog node 01); that copy is not the daily-driver coding seat. |
| **dsh** | Agent harness (`~/.dsh` + `~/.config/deepseek-harness`) | **sab-air** only. sab-mini has no `~/.dsh`. |

**Boundary statement:** aa-cli remains the operator cockpit for packet → fire → result → evidence → human decision. Pi remains the coding harness on sab-mini. dsh remains the agent harness on sab-air. **No verify-room, Deck, runway, or create-lane implementation is ported into Pi extensions, dsh effects, or this graph.**

Doctrine this restates:

- **CANONICAL.md** — aa-cli product is Path 0 Create + Path 1 Deck; they converge at the same dispatch/verification loop; verify settle lives in `deck-verification-review`; no extra menu without a node *inside aa-cli*.
- **LOOP.md** — GDDP loop is packet / dispatch / return / evaluate / human. Files are truth. Human acceptance is graph truth. That loop is *around* work, not a second TUI.
- **GDDP-becomes-small-and-real.md** — “GDDP is not the executor. GDDP is not the agent harness.” It is intent-preservation and graph integrity. “You do not need to invent a new TUI.” “GDDP doesn’t rebuild the loop.” Dispatch already uses named targets (`targets.conf`). Wrapping aa-cli into Pi or dsh would rebuild a TUI the doctrine already refuses.

aa-cli TUI work (Deck, runway, verify rooms, keymap) stays in **aa-cli-tui-pass**, not daily-driver.

---

## 2. Interface — sanctioned cross-points only

These are the only named seams between aa-cli, Pi, and dsh. Everything else is out of scope or listed for removal.

### Sanctioned

1. **Dispatch targets** — `aa-cli/targets.conf` rows. Live files on both hosts are **byte-identical** (`MD5 83fb17ccb5ceaba7b6082e71d7752d68`, 59 lines). Primaries: `grok`, `pi` (`__pi_async`), `codex`, `claude`, `hermes`, `openclaw`, `antigravity`, `jules` (+ lanes), `open-interpreter`, `gemini`, `droid`, `human`, `dry`. Aliases `grk` / `pir` / `cdx` are fire/ledger only. **There is no `dsh` row.** dsh is not an aa fire target; it is a sab-air harness. Pi is a *target* of aa, not a host for Deck.

2. **Receipts / ledger / result files** — packet fire produces run dirs, ledger, and (for GDDP) executor receipts + evaluator verdicts. GDDP consumes files; it does not own Deck or verify rooms. LOOP.md: files are truth; sqlite is an index.

3. **Shared skills** — `~/.agents` skill overlay (node 10). Curate allowlists; do not reimplement verify rooms as skills.

4. **Named GDDP roles** — config graph + runtime dispatch + independent evaluator + human `gddp` review. Executors may be Pi, dsh, Claude, Jules, etc. None of those executors absorb aa-cli chrome.

### Ad-hoc / remove or do not grow

| Item | Severity | Why |
|------|----------|-----|
| aa-cli verify-slice packets with `target: dsh` and **no** `targets.conf` row | medium | `research/port-scout-report.md`; design-persona leak. Do not add a fake `dsh` target to paper over it unless Sab authors that row. |
| Duplicate `targets.conf` trees (`Pi-Coding-Agent/harness/`, `~/.pi/harness/`, worktrees, iCloud preservation copies) | low | Only `/Users/sab-mini/repos/aa-cli/targets.conf` is the live cockpit on both hosts. |
| Treating leftover npm (`pi-studio`, `pi-auto-mode`, …) as a second cockpit | medium | Catalog 01 leftovers; not aa-cli, must not become Deck. |
| Wrapping aa-cli (Rust+zsh `hub-rs`) as a Pi extension or dsh effect | blocker if attempted | Explicit over-reach in node 11 `why`. |
| Porting verify rooms / Deck into daily-driver nodes | blocker if attempted | Charted in `graphs/aa-cli-tui-pass/` (nodes 01–13 include `05-tui-verify-rooms-polish`, `03-tui-deck-runway-pass`). |
| Using `dsh` as an aa-cli plugin SDK | medium | Scout: dsh = DeepSeek Harness on sab-air, not plugins. |

---

## 3. Graph scope

`graphs/daily-driver/` nodes 01–12:

| node | aa-cli implementation? |
|------|------------------------|
| 01–10, 12 | No. Inventory, classify, dsh inventory, split, package, policy, twins, mux, skills, dogfood. |
| 11 aa-cli-boundary | Written seam only. |

`MAP.md` already: “aa-cli TUI graph is charted separately (aa-cli-tui-pass) — no aa-cli implementation nodes here.”  
`project.yaml` architecture_notes: same.

`graphs/aa-cli-tui-pass/` is the TUI pass (Deck, runway, create, verify rooms, backend wiring, walkthrough). That graph’s `project.yaml` points daily-driver the other way: dsh is an executor label there, not a product surface.

---

## Live checks

- sab-mini: `command -v aa` → `/usr/bin/aa`; `targets.conf` MD5 `83fb17ccb5ceaba7b6082e71d7752d68`; no `~/.dsh`.
- sab-air: `aa` → `/usr/bin/aa`; same `targets.conf` path and MD5; `~/.dsh` present; `~/.pi` present.
- Cited LOOP / small-and-real files exist under `docs/proposals/` and `docs/decisions/` (not the shorter paths in the node yaml).
