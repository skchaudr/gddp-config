# Proposal: observability hub milestones for `pi-hub-projection`

**Status: proposal only.** Nothing here is in the graph. These files are frontier-invisible
and were authored by a planning agent for human review. Only the operator materializes a
node into `nodes/`. No `gddp` CLI command was run, no node status was changed, and no
existing file in any repo was modified.

Authored 2026-08-29 by `opus-5-planner`.

---

## 1. What the operator asked for, and what the evidence says

The framing was: *"convert the bad pi-obs UI into a more robust tool for tracing and
observability — agent-observability is half way there, just need the TUI/web UI."*

The survey found that the "half way there" and the "just need the UI" parts are both true,
but not in the way the framing implies. The data plane is further along than expected and
the UI is less of the remaining work than expected, because **the data plane is not
actually installed anywhere.**

### What "agent-observability" turned out to be

Not a repo and not a product. It is the `agent/observability/` data plane inside `~/.pi`,
produced by `agent/scripts/pi-observe.py` (tracked on `main`). On this host it holds:

| Source | State on 2026-08-29 |
|---|---|
| `sessions.jsonl` | 22 KB, last written 2026-07-12 |
| `subagents.jsonl` | 378 KB, last written 2026-08-20 |
| `tools.jsonl` | 1.5 MB, last written 2026-07-12 |
| `pi-instances.jsonl` | 233 KB, last written 2026-08-20 |
| `dispatches.jsonl` | 29 KB, last written 2026-08-24 |
| `artifacts.jsonl`, `hooks.jsonl` | present, 2026-07-12 |
| `pi-runtime/` | 297 entries, live as of 2026-08-29 |
| `pi-hub.db` | 7.4 MB, WAL, 13 tables, **last written 2026-08-06** |

Three candidate repos were checked and ruled out as the referent:

- `~/repos/aa-cli/hub-rs` — exists, but it is `aa-hub`, *"Rust TUI cockpit for aa-cli
  (render-only v1)"*. A different project with its own ratatui dashboard. Not the pi
  observability hub.
- `~/repos/gddp-runtime-result-surface` and `~/repos/gddp-config-result-surface` — exist,
  but they are git worktrees of `gddp-runtime` and `gddp-config` frozen at 2026-08-15.
  Result-surface checkouts, not an observability product.

A repo-wide search for the literal string `agent-observability` returns only this graph's
own node YAML and its verification receipts. The phrase is Sab's shorthand for the
`agent/observability/` plane.

### What the "bad pi-obs UI" turned out to be

Two renderers on `~/.pi` `main`, neither of which reads `pi-hub.db`:

- `harness/pi-hub-rs` — ~4,000 lines of Rust/ratatui reading the JSONL streams directly
  through `src/data/{runs,instances,subagents,tasks,fleet,machines}.rs`.
- `harness/tui/app.py` — a 19 KB Textual app driven by `PI_DISPATCH_TASKS`.

Its defects are already inventoried in `~/.pi/agent/plans/pi-hub-ui-attention-v1.yaml`, an
eight-packet non-GDDP plan: region overflow, clipping, broken borders, misleading queue
semantics, attention ordering that truncates actionable work, illegible cost/fleet
summaries, all at 80x24 and 140x32. That plan also states its own risk — the findings came
from a screenshot that may not match the current binary. That is a real defect list, not a
guess, and milestone-05 is built on it.

### The finding that reshapes everything

**All four existing nodes passed evaluation and none of their code is on `main`.**

`verification/pi-hub-projection/evaluations.yaml` records `verdict: pass` for all four
nodes, with `required_next_action: Proceed to accept_node (open evidence PR)`. But in
`~/.pi`:

```
git cat-file -e main:agent/observability/project.py   → ABSENT from main
git cat-file -e main:agent/observability/api.py       → ABSENT from main
git cat-file -e main:harness/apps/pi-hub-web          → ABSENT from main
ls ~/.pi/harness/apps                                 → No such file or directory
```

The code exists only on six unmerged `refs/heads/gddp/result-*` branches from 2026-08-06
(plus their `attempt-*` counterparts). None is an ancestor of `main`, and `main` now carries
74 commits those branches do not have.

Worse: **`~/.pi/.gitignore` line 81 ignores `agent/observability/` wholesale.** The
projector and API were force-added into a runtime-state directory. The node-01 evaluator
even noted *"the gitignore/force-add story in the report checks out"* — it verified the
workaround rather than flagging the shape. Code is living inside an ignored directory,
which means ordinary staging will never pick it up again.

`pi-hub.db` exists in the worktree because the executor ran the projector on the host on
2026-08-06 and the database is gitignored runtime state. The database is the residue of a
past agent run, not evidence of an installed tool.

All four nodes remain `status: provisional` in `project.yaml`. That is correct — the
evaluator passed them, the human never accepted them. Per
`docs/decisions/Tests-can-fail-nodes-can-pass.md`, a pass verdict is evidence, not graph
truth. The graph is behaving exactly as designed; the work simply stopped at the gate.

### gddp-runtime surfaces to consume, not rebuild

| Surface | What it already provides |
|---|---|
| `scripts/adapters/executor_events.py` | Canonical `ExecutorEvent` v1: seven types, envelope `(v, ts, executor, session_id, turn_id, seq, type, raw_type)`, `TurnUsage` with token/cost fields and `scope` of `message` or `turn`, plus `read_events()` and `turn_usage()`. Executor-neutral by construction. |
| `scripts/runtime/local_attempt.py` | `AttemptPaths` owns the per-attempt spool layout: `command.json`, `packet.json`, `events.jsonl`, `raw.jsonl`, `exit.json`, `result.json`, `pid`, `supervisor.pid`, `worktree_path`, `session_file`, `prompt_cache_report.json`, `context_coverage.json`. 121 attempt dirs currently under `jobs/local-subprocess-spool/`. |
| `node_status_history/<project>/<node>.jsonl` | Per-node status transition log across seven projects. |
| `scripts/jobs_status.py` | The only sanctioned runtime job read/write route (`list`, `show`, `results`, `set`, `adopt`, `retry`). |
| `db/queue.db` | Jobs, results, decision_results, events. |
| `verification/<project>/<node>/<job>-attempt<N>.json` + `evaluations.yaml` | Verdict receipts, already ingested by node-04. |

`scripts/intake_server.py` was checked and is **not** an observability API. It is a
255-line Flask app with exactly two routes — `POST /webhook` for GitHub payloads and
`GET /health` — writing the `events` table in `db/queue.db`. It is frozen infrastructure
per `AGENTS.md`. No milestone here touches it.

One correction to the task brief: `AGENTS.md` directs readers to start at `LOOP.md`, but
`~/repos/gddp-runtime/LOOP.md` does not exist. The frozen-infrastructure list and the
watch/steer surface described there could not be read. The milestones treat
`deploy/mini-heartbeat/` and `scripts/intake_server.py` as frozen based on `AGENTS.md`
directly.

**The gap between "half way there" and "robust tracing" is precisely this:** the canonical
`ExecutorEvent` spool — the one surface that records per-phase status, tools, and cost, and
the only one that is already executor-neutral — is projected by nothing. Node-04 ingested
*verdicts*; nobody ingested the *work that produced them*. That is milestone-02, and it is
the highest-value new capability in this proposal.

---

## 2. Relationship to the existing four nodes

**This proposal extends `pi-hub-projection`. It does not supersede or parallel it.**

- Nothing in the existing four nodes is wrong. The projector, the loopback cursor API, the
  receipts ingester, and the visualizer fork are the right components, and the evaluator
  verified each against its own criteria.
- They are simply **not landed**, and their destination path is gitignored. Milestone-01
  exists solely to fix that, and it must come first — every later milestone builds on
  components that currently have no installed existence.
- Milestone-04 resolves a contradiction the existing graph text created. `node-02`'s `why`
  says surfaces read *"through one API, not raw SQLite"*; `node-03`'s `why` explicitly
  permits reading `pi-hub.db` directly. The executor took the permission, and the node-03
  verdict recorded the consequence as a medium-severity graph observation: the browser
  surface bypasses the proven redaction layer. The evaluator was explicit that this is *"a
  graph-design tension created by the graph text itself; the executor followed its assigned
  node."* Resolving it belongs in the graph.
- Milestone-05 is the only milestone touching a component the existing nodes never went
  near. `harness/pi-hub-rs` is on `main` and no result branch modifies it.

**No existing node needs amendment for these milestones to be coherent.** The four nodes
stay as authored, at `provisional`, awaiting the operator's accept-or-revise decision. If
the operator instead decides some component should be dropped rather than landed,
milestone-01's per-component recommendation criterion is where that decision gets its
evidence.

---

## 3. Milestones and dependency edges

```
milestone-01-land-projection-plane   (critical)   depends_on: []
        │
        └──► milestone-02-executor-event-projection   (high)
                    │
                    ├──► milestone-03-one-attempt-trace-view    (high)
                    ├──► milestone-04-redaction-boundary        (high)
                    └──► milestone-06-single-refresh-entrypoint (medium)

milestone-05-tui-defect-retirement   (medium)     depends_on: []   [parallel]
```

| Milestone | Intent |
|---|---|
| `milestone-01-land-projection-plane` | Get the four evaluator-passed components onto one reviewable integration branch, off the gitignored path, with per-component land/drop recommendations for the operator. |
| `milestone-02-executor-event-projection` | Project the canonical `ExecutorEvent` spool into the hub database so an attempt's turns, tools, and cost become queryable — the actual missing half of tracing. |
| `milestone-03-one-attempt-trace-view` | Render one attempt id as a phase list with status, cost, log paths, and pass/fail receipt path, on an existing surface, and stop there. |
| `milestone-04-redaction-boundary` | Put every hub reader behind one redaction boundary, closing the hole the node-03 verdict flagged before event `text` and `command` fields make it live. |
| `milestone-05-tui-defect-retirement` | Repair the inventoried `pi-hub-rs` rendering defects at 80x24 and 140x32 so the answer to a bad TUI is a fixed TUI, not a third renderer. |
| `milestone-06-single-refresh-entrypoint` | Make refresh one restartable command with per-source failure isolation, so the hub stops going stale — without installing a scheduler. |

`milestone-03` and `milestone-04` are unordered relative to each other on purpose. Rather
than serialize them, milestone-03 carries a constraint: until milestone-04 lands, the trace
view must not render secret-bearing fields (`assistant_message.text`,
`tool_started.command`, packet prompt content) — it renders a placeholder and the file path
instead. That keeps both runnable concurrently within the graph's `max_concurrent_jobs: 2`
without opening the leak milestone-04 exists to close.

### Deliberately not proposed

Each of these was considered and rejected against the note's Explicit Non-goals (*no full
multi-model swim-lane product, no custom DSL or new agent framework, no third-party factory
install*) and its Pi finish move (*"observability before multi-model roster"*, *"not a full
IndyDevDan clone"*):

- A graph-frontier or node-status dashboard over `node_status_history/`. Real surface, but
  it is graph-state visualization, not tracing, and it competes with `gddp` itself.
- Live event streaming or tailing. The spool is append-only on local disk; polling the
  projection is sufficient and `tail -F raw.jsonl` already exists.
- Cost aggregation, model comparison, or roster views. Explicitly the non-goal.
- Multi-host or fleet views. `pi-hub-rs` already has a bounded-SSH fleet pane; extending it
  is a different project.
- Any scheduler, launchd job, or heartbeat wiring. Frozen infrastructure; milestone-06
  stops at the manual entrypoint on purpose.

---

## 4. Viability assessment

**Shaped right for graph-driven execution: mostly yes, with one structural caveat.**

What works. Each milestone has acceptance criteria an evaluator can adjudicate from a
checkout plus a host run, following the pattern the existing four nodes proved: a
deterministic self-check reproducible in the checkout, plus host-local evidence captured in
a report. The node-01 verdict identified this precisely — live evidence against gitignored
runtime state *"can only be re-verified on the host"*, so *"downstream nodes and the
harness should lean on deterministic self-checks."* Every milestone here carries at least
one criterion satisfiable from a fixture rather than from host state alone. Scope
boundaries are enforceable by path constraints, matching the pattern the four nodes already
executed cleanly (node-03's 52-file diff stayed entirely inside its allowed trees).

**Caveat one: milestone-01 is not really executor work.** Its true deliverable is an
operator decision — merge, revise, or drop four components. An executor can prepare the
integration branch, prove the components run, and write the recommendation, but it cannot
land them; `AGENTS.md` reserves merges to `main` for the human, and the graph doctrine
reserves acceptance for the human too. It is authored as a milestone that produces decision
material rather than a merge, with `allowed_execution_modes: [droid, human]` so the
operator can take it directly. If the operator would rather just do the merge by hand, this
node should be dropped from the graph rather than dispatched — that is a legitimate review
outcome and probably the faster one.

**Caveat two: moving code off the gitignored path is a real change, not bookkeeping.**
Milestone-01 asks for `project.py` and `api.py` to leave `agent/observability/` for a
tracked path — `agent/scripts/` already holds `pi-observe.py` and is tracked, so it is the
natural home. That changes import paths and every documented invocation in the node-01
through node-04 reports. The alternative — keep force-adding code into an ignored directory
— is the shape that produced the current situation. Worth flagging to the operator as the
one place this proposal argues with how the existing work was built.

**Caveat three: the operator has not chosen between TUI and web.** The framing says
"TUI/web UI" and both surfaces exist: the landed-but-unmerged `pi-hub-web` browser fork and
the on-`main` `pi-hub-rs` TUI. This proposal deliberately keeps both alive —
milestone-03 makes the surface choice a recorded decision inside the node, and milestone-05
repairs the TUI regardless. That is honest but it is also two surfaces to maintain. If the
operator wants one, either milestone-03 should be pinned to a named surface or
milestone-05 should be dropped before materialization. This is the single most useful thing
for the operator to settle at review time.

### What blocks this today

1. **Unlanded work is the whole blocker.** Six milestones deep, five of them depend on code
   that has no installed existence. Nothing here can start before milestone-01 or the
   operator's manual equivalent.
2. **`allowed_repos` is narrower than the work.** `project.yaml` declares
   `allowed_repos: [/Users/sab-mini/.pi]`, but milestone-02 and milestone-06 must *read*
   `~/repos/gddp-runtime/jobs/local-subprocess-spool/` and
   `~/repos/gddp-config/verification/`. Node-04 already established the precedent —
   read cross-repo in place, write only inside `~/.pi` — and the evaluator accepted it. The
   milestones follow that precedent explicitly, but the operator may want `project.yaml` to
   say so out loud. **That would be an amendment to `project.yaml`, which this proposal
   does not make.**
3. **Cross-repo vocabulary coupling has no established pattern.** `executor_events.py`
   lives in `gddp-runtime`; the projector lives in `~/.pi`. Importing across repos is
   fragile, copying diverges silently. Milestone-02 requires a drift check as an acceptance
   criterion rather than picking for the operator, but this is a genuine open design
   question and the criterion may prove harder to satisfy than it reads.
4. **`pi-hub.db` is nine weeks stale.** Whatever the operator saw as the "bad UI" may have
   been rendering stale data rather than rendering badly. Milestone-05's first criterion —
   reproduce against the *current* binary before fixing — is the guard, but the operator
   should know that some of the perceived badness may be milestone-06's problem, not
   milestone-05's.

### What is missing

- **No test for whether the operator will use it.** Every milestone verifies that a surface
  renders correct data; none verifies that anyone reaches for it during a real run. That is
  not a fixable criterion, it is a review question.
- **Attribution between pi sessions and GDDP attempts is unproven.** Milestone-03 assumes
  an attempt id can be joined to a node verdict through `gate_results`, and node-04's
  verdict says those rows carry `project_id`, `node_id`, `verdict`, and `receipt_path`.
  Whether the *executor* `session_id` in the event spool joins cleanly to those rows was
  not verified during this survey. If it does not, milestone-03's
  `verdict-and-receipt-path` criterion will fail and a join node is needed between
  milestone-02 and milestone-03. **This is the most likely place the proposed shape breaks,
  and it should be checked before dispatching milestone-03.**
- **The upstream reference tree is gone.** `~/repos/_reference/sssf` (pinned
  `de313748`) does not exist on this host; the node-03 verdict already noted this. If any
  milestone needed to re-derive from upstream it could not. None of these six do, which is
  deliberate.

### Verdict

The shape is right and the sequencing is honest, but the first milestone is a landing
problem rather than a capability problem, and that is the real state of this project: four
passed nodes, zero installed components, one nine-week-stale database. The highest-value
new work is milestone-02, because the canonical `ExecutorEvent` spool is the tracing
substrate the operator's framing assumes already feeds the hub and nothing currently reads
it. Before dispatching anything, the operator should settle two questions: whether to land
milestone-01 by hand instead of through the graph, and whether the session-to-verdict join
milestone-03 depends on actually exists.
