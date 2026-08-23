# Code Context

## Files Retrieved
1. `graphs/daily-driver/evidence/11-aa-cli-boundary.md` (full, written this run) — deliverable seam doc
2. `graphs/daily-driver/nodes/11-aa-cli-boundary.yaml` — acceptance criteria
3. `graphs/daily-driver/MAP.md` + `project.yaml` — graph scope
4. `graphs/aa-cli-tui-pass/project.yaml` + nodes 01–13 listing — TUI charted separately
5. `/Users/sab-mini/repos/aa-cli/gddp/CANONICAL.md` — aa-cli product loop
6. `/Users/sab-mini/repos/gddp-runtime/docs/proposals/LOOP.md` — GDDP loop (not `LOOP.md` at repo root)
7. `/Users/sab-mini/repos/gddp-runtime/docs/decisions/GDDP-becomes-small-and-real.md` — not `docs/GDDP-becomes-small-and-real.md`
8. `graphs/daily-driver/evidence/01-two-host-catalog.md` + `research/port-scout-report.md`
9. Live `aa-cli/targets.conf` on sab-mini and sab-air (identical MD5 `83fb17ccb5ceaba7b6082e71d7752d68`)

## Key Code
Roles: aa-cli = fire/verify TUI both hosts; Pi = coding harness sab-mini; dsh = agent harness sab-air only.

Sanctioned: `targets.conf` dispatch rows, receipts/ledger, shared `~/.agents` skills, GDDP packet/eval/human loop.

No `dsh` target row. Daily-driver has no aa-cli implementation nodes.

## Architecture
Three products stay separate. GDDP does not rebuild a TUI. aa-cli-tui-pass owns Deck/verify rooms.

## Start Here
`graphs/daily-driver/evidence/11-aa-cli-boundary.md`

## Supervisor coordination
None.

---

**Paths written:** `graphs/daily-driver/evidence/11-aa-cli-boundary.md`, this `context.md`. No commits.

**Boundary:** aa-cli stays fire/verify TUI on both hosts; Pi coding on sab-mini; dsh agent on sab-air; no verify-room/deck port.

**Sanctioned:** dispatch targets, receipts, shared skills, GDDP roles.

**Ad-hoc:** `target: dsh` without conf row; extra targets.conf copies; leftover Pi packages as fake cockpit; wrap aa into Pi/dsh.
