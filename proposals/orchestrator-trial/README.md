# Proposal ledger — heartbeat orchestrator trial

Fully-formed node YAMLs for the work remaining before an orchestrator run.
Frontier-invisible: they sit outside `graphs/`, so the heartbeat ignores them
until Sab copies the ones he wants into `graphs/gddp-runtime/nodes/` and adds
the matching summary rows to `project.yaml`.

Written 2026-09-04 by cursor-agent + claude-opus-5, following
`gddp-runtime/docs/current/heartbeat-orchestrator-plan.md`.

## Why these five

The orchestrator is a stateless allocator: woken on a pulse, handed a context
pack, decides which nodes run and whether in-flight work is healthy, then
sleeps. The wake pack already exists
(`scripts/runtime/heartbeat/orchestrator_pack.py`, commit `60d29aa`, built
outside the graph and recorded here as existing evidence rather than proposed
work). These five carry the rest.

## Shape

```
orchestrator-decision-channel ─┐
orchestrator-role-contract ────┴─→ orchestrator-wake-phase
cursor-subagent-probe          (independent)
cursor-dual-role-model         (independent)
```

Four nodes are ready on day one, which gives a first run genuine allocation to
do instead of a single node with nothing to decide.

## Executor selection

Every node declares `allowed_execution_modes: [agent]` — the neutral mode,
meaning any registered transport is acceptable. The trial picks the concrete
transport at dispatch with `GDDP_EXECUTOR_OVERRIDE=cursor_cli`, so running
cursor leaves no false claim in graph truth that cursor is this project's
habitual executor.

## Trial roles

| Role | Model |
| --- | --- |
| Orchestrator | `cursor-grok-4.6-high` |
| Executor | `composer-2.5` |

Both dispatch through `cursor_cli`, which is what makes
`cursor-dual-role-model` load-bearing for this pairing: one env var
(`GDDP_CURSOR_CLI_MODEL`) currently serves the whole process.

## Canonical notes

`gddp-runtime` already carries `README.md`, `PROJECT-BRIEF.md`, and
`docs/invariants/invariants.md`, which is everything
`semantic/context_builder.py:39-60` points an agent at. A different trial
target would need those written first.
