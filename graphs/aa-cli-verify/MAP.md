# aa-cli-verify — wayfinding map

## Destination

Chart every open decision on aa-cli's verify pathway — the product's
load-bearing core — from a deck-dispatched packet (or an ad-hoc user-supplied
subject via generic verify) through evidence capture and verification, ending
when a task is officially marked verified/done both visually and schema-wise,
reflected in the deck and past tasks. When the way is clear, this graph
graduates into a dispatchable execution DAG.

## Notes

- Domain: aa-cli cockpit (deck → runway → verify). Subject repo: `~/repos/aa-cli`.
- Skills to consult: `/grilling` + `/domain-modeling` for human-mode nodes.
- Fact-check claims against the repo before settling them (lesson of
  2026-08-06: the checkmark convention in code differed from memory — verify
  what the code actually does).
- "Create is the inverse of verify" (Sab, 2026-08-06): a future
  `aa-cli-create` map is expected; decisions here should not pre-empt it.
- The repo-local `aa-cli/gddp/` graph (30 nodes, documented drift) is
  evidence, not truth. The gddp-config `graphs/aa-cli/` graph (12 nodes, all
  complete) is v0-era history.
- Nodes settled during charting carry their `resolution:`; the human flips
  them to `complete` in the Nodes menu
  (`cd ~/repos/gddp-config && .venv/bin/python scripts/gddp.py node browse`).
- Durability rule: commit + push gddp-config at every checkpoint. No
  `.scratch`. An unpushed resolution did not happen.

## Fog

- The create↔verify duality: how verify output should eventually feed the
  create path (future `aa-cli-create` map).
- Whether verified state feeds downstream consumers: per-target trust
  scoring, dispatch-candidate prioritization, stats.
- Needle classification for the verify / recon / audit verbs.
- Whether verifier verdicts accumulate into per-target or per-packet trust
  data.

## Out of scope

- Packet-side authoring of verify contracts — create-side; belongs to the
  future `aa-cli-create` map.
- Automated judgment replacing the human ✓✓ — no evaluator lane owns
  acceptance.
- Re-fire/amend feedback loops beyond the deck's existing machinery.
- Reconciling the repo-local `aa-cli/gddp/` 30-node graph — clean start; it
  stays as evidence.
- MyAPI — separate map, separate effort.
