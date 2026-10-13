# GDAD node contract

Definition lives in gddp-config at `graphs/<project>/gdad/<node-id>/`.

`BRIEF.md` headings, in order: Goal, Scope, Acceptance, Constraints, Sab's words.
`Sab's words` is verbatim.

Runtime state lives in gddp-runtime, gitignored, at `gdad/<project>/<node-id>/`:

- `status` — projection of the last `journal.jsonl` line
- `journal.jsonl` — append-only, one JSON object per line
- `runs/<run_id>/artifacts/` — worker output
- `packets/<packet_id>.json` and `<packet_id>.md` — the decision packet

`status` fields: `state`, `who`, `when`, `run_id`, `request_id`, `wid`.

States: `pending`, `running`, `paused`, `review`, `awaiting-decision`, `accepted`, `rejected`, `blocked`.
Only `accepted` is terminal. `awaiting-decision` is entered by a `packet` line.

Journal types: `dispatch`, `pause`, `resume`, `packet`, `decision`, `review`, `verdict`, `steer`, `gate`, `blocked`.

v1 `graphs/<project>/nodes/<node-id>.yaml` stays graph truth. The executor does not write it.
