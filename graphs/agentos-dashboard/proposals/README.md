# Milestone restructure proposal — agentos-dashboard

**Status: PROPOSAL. Not in the graph.** Nothing in this directory is loaded by
the runtime, appears on the frontier, or changes node status. The seven YAML
files here are fully-formed node documents that only Sab can materialize into
`nodes/`. Authored 2026-08-29 by `opus-5-planner`.

Nothing under `nodes/`, `project.yaml`, `evidence/`, `research/`, or
`~/repos/agentos-dashboard` was modified.

---

## 1. What actually exists today

Grounded by inspection on 2026-08-29, not by reading the chart.

**The graph** (`graphs/agentos-dashboard/`): 12 capability nodes charted
2026-08-23 from `research/agentos-plan.md`. Arc is
`contract → schema + watcher ∥ shell + components ∥ API → live-integration →
dogfood → rollout`. Status in `project.yaml`: `scope-contract` is `complete`
(human-accepted in `9c45fc9`); the other eleven are `pending`.

**Evidence produced by the one-shot run:**

| Node | Evidence on disk | Node status |
|---|---|---|
| `scope-contract` | `evidence/01-scope-contract.md` — repo, stack, data source paths verified live | complete |
| `data-topology-schema` | `evidence/02-data-topology-schema.md`, `02-graph.schema.json`, `02-schema-validator.py`, `02-sample-graph.json` | pending |
| `frontend-shell` | app commit `413152a` in the product repo | pending |
| the other nine | none | pending |

**The product repo** (`~/repos/agentos-dashboard`, branch `main`, no remote):
two commits (`8be6a36` scaffold, `413152a` shell), eight tracked files.
`src/main.jsx` is 125 lines and `src/styles.css` is 42 lines — that is the
entire application. It contains theme tokens matching the spec, a
header/left-rail/canvas/right-rail layout, and hash-based mode switching
between two placeholder canvases. It contains no data loading, no graph
library, no watcher, no backend, no tests, and no test runner
(`package.json` scripts are `dev`, `build`, `preview` only). The right rail's
routines and "Hermes worker connected" widgets are hardcoded strings; the
left rail clock is the literal string `09:42` / `Saturday · Aug 23, 2026`.

**Evaluator verdicts: none.** `verification/`, `verification-runtime/` and
`verification-runtime-live/` contain no `agentos-dashboard` directory. The
one-shot run produced a chart, two evidence bundles, and one commit of code —
no node was ever put through the two-lane verification pass.

**Three spec-vs-reality contradictions already discovered** and recorded in
`evidence/02-data-topology-schema.md`: the vault root router is `AGENTS.md`,
not the spec's `CLAUDE.md`; the department routers `content.md`,
`business.md`, `community.md`, `apps.md` do not exist and hubs fall back to
PARA folders; vault frontmatter carries no `model` field. The charted
`radial-dag` node's `why` still names `business/content/community/product/
personal` hubs that the vault does not have.

## 2. Relationship to the existing 12 nodes

**This is a restructure proposal, not an extension.** It does not add a
parallel layer of bookkeeping on top of the existing chart; it re-cuts the same
scope along a different axis and changes the order in which reality is
contacted.

The existing 12 are cut **by layer** — shell, then orbit, then DAG, then deck,
then board, then API — with a single `live-integration` node at position 10
whose job is "swap mock data for real". That shape means nine nodes get built,
evaluated and reviewed against mocks before any of them meets the vault. The
vault has already contradicted the spec three times before a single
visualization node started. Layer-slicing puts all of that discovery after the
review budget is spent, which is the drift pattern `AGENTS.md` names.

The seven milestones are cut **by vertical slice**. Milestone 2 pulls the whole
`live-integration` intent forward to the second position: real sources →
watcher → `graph.json` → rendered in the shell, with deliberately primitive
rendering. Milestones 3–6 then build fidelity on top of data that is already
real. `live-integration` as a discrete late node disappears; its criteria are
absorbed into M2 (live data) and M5 (live runs).

### Coverage map

| Milestone | Absorbs existing nodes | New scope not in the current chart |
|---|---|---|
| M1 verifiable build baseline | — | test runner, schema contract moved into the app repo, repo remote decision |
| M2 live topology slice | `workspace-watcher`, the data half of `live-integration`, the consumption half of `data-topology-schema` | spec-vs-vault reconciliation as an explicit deliverable; read-only guarantee on all scanned sources |
| M3 artifact orbit mode | `artifact-orbit`, the search-bar wiring left unbuilt in `frontend-shell` | behavior at real vault scale, and at zero artifacts |
| M4 radial DAG mode | `radial-dag` | declaring the graph library dependency; multi-parent and cycle handling |
| M5 execution boundary | `skills-deck`, `backend-api`, the runs half of `live-integration` | executor decision gated *before* implementation; localhost binding as an explicit decision |
| M6 routines visibility | `routines-board` | removing the hardcoded routines and the unbacked "connected" indicator |
| M7 daily-driver rollout | `dogfood-dashboard`, `rollout-plan` | an adoption verdict that is allowed to be "no" |

Already covered and **not** re-litigated: `scope-contract` is accepted and the
milestones depend on it rather than redoing it. `data-topology-schema`'s
authored artifacts are real work — M1 relocates them into the app repo and M2
consumes them; nothing is rewritten. `frontend-shell`'s committed layout and
theme are reused as-is; M3, M4 and M6 fill the placeholders it left.

### Dependency edges

```text
scope-contract (accepted)
        │
        ▼
M1 verifiable-build-baseline
        │
        ▼
M2 live-topology-slice
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
M3 artifact-orbit  M4 radial-dag  M5 execution   M6 routines
        └──────────────┴──────────────┴──────────────┘
                              ▼
                  M7 daily-driver-rollout
```

M3, M4, M5 and M6 are independent after M2 and are dispatchable concurrently.

### Two ways to materialize this, if Sab wants it at all

**(A) Replace.** The eleven pending capability nodes are superseded by the
seven milestones; `scope-contract` stays as the accepted root. The YAMLs here
are written for this option — their `depends_on` and `unlocks` reference
milestone ids and `scope-contract`, and they form a valid DAG on their own.
Cost: the already-authored `data-topology-schema` and `frontend-shell` node
documents are retired even though their evidence is kept and reused.

**(B) Overlay.** Keep the 12 and add the milestones as review checkpoints. This
requires editing every `depends_on` in these files to point at capability node
ids, and it leaves two competing decompositions of the same scope in one graph.
I do not recommend it — the value of this proposal is the resequencing, and an
overlay keeps the old sequence.

Either way, materialization is all-or-nothing per option: importing a subset
would leave dangling `depends_on` references.

## 3. Viability assessment

**Is this shaped right for graph-driven execution?** After the two changes
above — a verification substrate and data-first resequencing — mostly yes.
Each milestone is a human-reviewable unit of intent that produces something
Sab can look at and judge, and each has criteria an evaluator can attack with
cited evidence. Before those changes, no. A chart whose criteria say "component
+ tests" against a repo with no test runner cannot be verified by the
deterministic lane at all, and the semantic lane would be grading prose.

**What blocks it right now:**

1. **No test runner in the product repo.** Nine charted nodes require tests.
   Nothing can run them. This is M1 and it blocks everything.
2. **The executor decision is unmade and human-owned.** `scope-contract` left
   `claude -p` vs pi vs dsh open. M5 cannot start until Sab decides, and M5 is
   where the dashboard gains the ability to spawn processes. Treat that
   decision as a gate, not a detail.
3. **The contract lives in the wrong repo.** The JSON Schema and validator that
   define `graph.json` sit in `evidence/`. The app cannot import them, so the
   frontend and the watcher would each drift their own private idea of the
   shape.
4. **No remote on the product repo.** Two commits exist on one machine. Any
   multi-host or delegated execution is currently impossible, and the work is
   one disk failure from gone.
5. **The graph text has already drifted from discovered reality.** `radial-dag`
   describes hubs that node 02 proved absent. Nothing in the chart owns
   reconciling that; M2 makes it an acceptance criterion, but the amendment to
   the node text itself is Sab's act, not an executor's.

**What is missing from both the old chart and this one:** nobody owns
performance at real vault scale (the sample graph has 10 nodes; SSD has
thousands of files), nobody owns which machine runs the dashboard when sab-mini
and sab-air both have the vault, and nobody owns what happens to the watcher
process when the machine sleeps. M3 and M7 touch the edges of these; none is a
first-class node in either decomposition. If Sab wants them owned, they are
three more nodes, not criteria bolted onto these.

**The honest caution:** this is a personal dashboard derived from a YouTube
demo, and the demo's fidelity to a real vault is already 0-for-3 on the
structural claims that were checkable. The value is unproven and the graph
costs seven human review cycles. The main thing the milestone shape buys is a
cheap kill point: after M2, roughly one node of work, Sab can look at his own
topology rendered plainly and decide whether the remaining five milestones are
worth it. The layer-sliced chart offers no such point before node 10.

**Verdict in three sentences.** The concept is viable for graph-driven
execution, but the existing chart is not executable as written because it has
no verification substrate and defers all contact with reality to its tenth
node. Restructuring into seven milestones fixes the sequencing and makes the
executor decision an explicit gate rather than a deferred detail. Whether the
dashboard is worth building at all is a question only Sab can answer, and the
proposal is deliberately shaped so that answer can be reached after M2 instead
of after M7.

## 4. Files in this proposal

- `m1-verifiable-build-baseline.yaml`
- `m2-live-topology-slice.yaml`
- `m3-artifact-orbit-mode.yaml`
- `m4-radial-dag-mode.yaml`
- `m5-execution-boundary.yaml`
- `m6-routines-visibility.yaml`
- `m7-daily-driver-rollout.yaml`

All seven use `type: milestone` (valid per `schemas/v1/node.yaml`) and
`status: pending`, the initial value the node template assigns. Node ids are
prefixed `m<n>-` so they cannot collide with the existing 12 under either
materialization option.
