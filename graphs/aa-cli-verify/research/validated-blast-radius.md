# Research: validated → verified migration blast radius

Node: `validated-blast-radius` ("What is the blast radius of the
validated-to-verified state-model migration?")
Date: 2026-08-06 · Agent-mode research against `~/repos/aa-cli` (read-only)

**The decided model** (see node `verify-state-model`): white ✓ machine-returned
("something returned, task is over") · green ✓ agent-good
(`verified: completion`) · red ✓ agent-disagrees with a stated, viewable reason
· ✓✓ human-accepts-only (`verified: review`). `verified: completion|review`
replaces `validated: bool` on the JSON packet; machine-run verify commands
become evidence, never state. Whether agent-disagree is a third `verified`
value plus a reason field, or separate, is for the `verifier-agent-contract`
node to decide — this report flags the touchpoints either way.

## Summary table

| File | Sites |
|---|---|
| `lib/validate.zsh` | 4 |
| `lib/ledger.zsh` | 8 |
| `lib/deck.zsh` | 6 |
| `lib/reconcile.zsh` | 2 |
| `lib/generate.zsh` | 1 |
| `schema/packet.schema.json` | 1 |
| `hub-rs/src/models.rs` | 14 |
| `hub-rs/src/data/packets.rs` | 5 |
| `hub-rs/src/app.rs` | 5 |
| `hub-rs/src/keymap.rs` | 3 |
| `hub-rs/src/ui/dashboard.rs` | 2 |
| `hub-rs/src/main.rs` | 5 |
| `hub-rs/tests/render.rs` | 10 |
| `tests/acceptance.zsh` | 18 |
| **Code + tests total** | **~86** |
| Docs / repo-local gddp / handoffs | ~38 (listed at end) |

## Per-file detail — code & tests

### `lib/validate.zsh` — the verify flow

| Line | Site | Change under new model |
|---|---|---|
| 68 | `jq '.validated = true' "$packet"` — write on verify-command pass | Write `"verified": "completion"` (agent-good). Field name AND value shape change |
| 69-71 | Comment: validated=true upgrades glyph ✓→✓✓ via aa_deck_glyph | Rewrite: verify commands are evidence; they set green ✓ (completion), never ✓✓ |
| 73 | `aa_ledger_update_state "$id" done -` | Keep `done` as ledger state (ledger unaffected), or revisit with the ledger-state question |
| 74 | `print "✓ validated $id"` | Message → `verified $id` |

### `lib/ledger.zsh` — glyph and state derivation

| Line | Site | Change |
|---|---|---|
| 69 | Comment documenting `validated ✓✓` | Update to new glyph language |
| 80 | `aa_state_glyph` branch: `validated) ✓✓ bold green` | New mapping: absent→white ✓, `completion`→green ✓, disagree→red ✓, `review`→✓✓ |
| 89-96 | `aa_deck_glyph()` reads `.validated // false`; done+validated→✓✓ | Read `.verified // ""`; branch on the value |
| 99 | `aa_state_glyph done` fallback | Maps to white ✓ (machine-returned) |
| 155, 160 | `aa_ledger_print()` done-state glyph derivation | Transitively affected |
| 174 | Comment: terminal = done+validated or validated | Update terminal definition |
| 177-186 | `aa_dep_is_terminal()` reads `.validated` for done packets | Read `.verified`; terminal when `review` (human-accepted) — decide whether `completion` counts as terminal for deps |

### `lib/deck.zsh` — deck rendering, sync, interactivity

| Line | Site | Change |
|---|---|---|
| 123 | `validated:false` default in `aa_deck_sync_card()` | Omit the field or default `"verified": ""` |
| 485 | Deck legend: `✓ done  ✓✓ validated` | New legend: white ✓ returned, green ✓ agent-good, red ✓ agent-disagrees, ✓✓ accepted |
| 556-615 | `aa_deck_unvalidated_siblings()` — pre-fire warning reading `.validated` across workdir packets | Read `.verified`; new skip condition (non-empty / `review`); rename likely |
| 567 | batch jq reading `.validated // false` | `.verified // ""` |
| 571-574 | skip-if-validated loop | New condition |
| 614-615 | unvalidated-siblings warning text | Update language |

### `lib/reconcile.zsh`

| Line | Site | Change |
|---|---|---|
| 14 | Comment listing states | Update |
| 127 | `to_be_verified\|done\|validated\|error)` terminal pass-through | Revisit terminal set if `verified` becomes a ledger state (current decision: it stays a packet field, ledger keeps `done`) |

### `lib/generate.zsh`

| Line | Site | Change |
|---|---|---|
| 59 | `validated:false` in packet creation jq | Omit or `"verified": ""` |

### `schema/packet.schema.json`

| Line | Site | Change |
|---|---|---|
| 14 | `(($packet \| has("validated") \| not) or ($packet.validated \| type == "boolean"))` | Dual-accept during migration, then: optional `verified` string enum `completion\|review` (plus disagree shape per `verifier-agent-contract`) |

### `hub-rs/src/models.rs` — DisplayState

| Line | Site | Change |
|---|---|---|
| 24 | `pub validated: bool` on Packet | `pub verified: String` (or enum); type change cascades ~20 Rust call sites |
| 25, 59, 103 | Comments + `word()` for Validated | Update |
| 93-100 | `glyph()`: Done→✓, Validated→✓✓ | Four-mark mapping (white ✓ / green ✓ / red ✓ / ✓✓); likely new DisplayState variant for agent-disagree |
| 113 | `is_terminal()`: Done \| Validated | Revisit per terminal definition |
| 119-122 | `DisplayState::resolve(state, validated: bool, ts)`; `done if validated => Validated` | Signature takes the new field; branch on its value |
| 197-219 | Unit tests pinning resolve() behavior | Rewrite |

### `hub-rs/src/data/packets.rs`

| Line | Site | Change |
|---|---|---|
| 28 | `validated: false` default for draft packets | New field default |
| 75 | `validated: bool` in RawPacket deserialization | Type change |
| 90 | RawPacket→Packet mapping | Map new field |
| 120, 182 | Tests | Update |

### `hub-rs/src/app.rs`

| Line | Site | Change |
|---|---|---|
| 899 | `"validated": false` in `finalize_packet()` | New field |
| 935 | `DisplayState::resolve(state, packet.validated, ts)` | Pass new field |
| 1561 | test `dummy_packet()` | Update |

### `hub-rs/src/main.rs` — Accept key (the human flip)

| Line | Site | Change |
|---|---|---|
| 468-469 | Comments | Update |
| 476 | `val["validated"] = Bool(true)` — manual accept writes packet | Write `"verified": "review"` — the human-only ✓✓ mark |
| 477, 483 | sets packet state `done` + ledger `done` | Keep (ledger model unchanged) |

### `hub-rs/src/keymap.rs`

| Line | Site | Change |
|---|---|---|
| 67 | `a` → `SubmenuAction::Accept` on Verify map | Structure unchanged; action semantics change |
| 88 | Footer labels | Unchanged |
| 135, 242 | Tests | Update fixture field |

### `hub-rs/src/ui/dashboard.rs`

| Line | Site | Change |
|---|---|---|
| 81 | Comment: green for done/validated | New color rules |
| 279 | Detail preview renders `validated {bool}` | Render `verified` with label |

### `hub-rs/tests/render.rs` — 10 sites

Lines 38, 50, 69, 78, 115-127, 299, 335, 346, 355, 709: synthetic packet
fixtures (`validated: false`), the `synthetic_packet(..., validated: bool)`
helper, "Hidden validated packet" filter tests, and a
`DisplayState::resolve(state, p.validated, ts)` call. Update en masse when the
Rust type change lands.

### `tests/acceptance.zsh` — 18 sites

Lines 676-773 (val-pass/val-fail/val-none packets, `jq -e '.validated == …'`
assertions, unvalidated-siblings warning expectations), 854-866 (dep-base
terminal/unblocked assertions). Lines 399 and 837 use the word "validated"
unrelatedly — no change. Update fixtures and assertions with the dual-read
step.

## Docs / repo-local gddp / handoffs (~38 sites, no code)

- `docs/aa-cli-v2-implementation-plan.md` (9) — primary spec; defines validated + glyph table. Rewrite with the new model.
- `docs/Finalizing-architecture.md` (5) — `fire → audit/verify → validated` flow. Rewrite.
- `docs/CONFUSIONS.md` (1) — field list. Update.
- `hub-rs/docs/plan-simplify-deck-runway-verify.md` (2). Update.
- Repo-local `gddp/` graph: `nodes/cockpit-state-machine.yaml` (4), `deck-runnable-now-filter.yaml` (2), `deck-dependency-model.yaml` (2), `deck-verification-review.yaml` (1), `reconciliation.yaml` (1), `project.yaml` (1) — all reference validated/done semantics. NOTE: this graph is drifted evidence, not truth (see MAP.md); amend only if the repo-local graph is revived.
- `gddp/receipts/2026-07-05-aa-cli-node-status.md`, `.handoffs/001-hub-rs-cockpit-state.md` — historical; leave.

## Migration considerations

**Rename-vs-coexistence: coexistence wins.** A hard rename strands every
packet on disk carrying `validated` (glyphs regress, old verified work looks
unverified). Instead: dual-read (new field first, fall back to `validated`),
write-only-new, one-time migration command, then harden.

**Ledger rows are unaffected** — the ledger stores the `done` state, not the
flag. Only the packet field and glyph derivation change.

Suggested slicing for the future execution graph:

| Step | Scope | Content |
|---|---|---|
| 1 | `schema/packet.schema.json` | Dual-accept `validated: bool` and `verified` (new shape) |
| 2 | Rust atomic commit | `Packet.validated: bool` → `verified` type change across models/packets/app/main/keymap/dashboard + render tests (~35 sites, one commit) |
| 3 | zsh dual-read | ledger.zsh glyph/terminal reads, deck.zsh sibling filter, generate/deck defaults read new field with fallback |
| 4 | New-write paths | validate.zsh writes `verified: completion` on pass; Accept key writes `verified: "review"`; stop writing `validated` |
| 5 | Glyph + legend | four-mark glyph set in ledger.zsh + models.rs, deck legend, dashboard colors |
| 6 | Migration command + harden | one-pass idempotent rewrite of on-disk packets (`validated:true` → `verified:"completion"`, drop old key); then schema removes `validated`, fallbacks deleted, docs updated |

Riskiest sites: the Rust type change (step 2, ~20 cascading call sites) and
the `aa_deck_glyph` / `aa_dep_is_terminal` derivation reads (step 3) — they
decide what every list view shows and when dependents unblock.
