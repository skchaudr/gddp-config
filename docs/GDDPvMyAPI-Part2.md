
# Implementation Plan: MyAPI Part 2

Note: This is an Obsidian note in my vault, don't expect 1:1 legibility 

> [!summary] Part 2 objective
> Determine which project-knowledge sources and representations let MyAPI answer grounded questions about what happened, why it happened, and what exists now—and measure those contributions separately enough to inform Part 3.

Part 2 is a controlled experiment over real project history. Its endpoint is a reproducible, multi-source project corpus plus measured evidence about what each source contributes to retrieval quality, answer quality, grounding, provenance, and abstention.

> [!important] Experimental gate
> GDDP gates whether an experiment was executed correctly; it must not gate on whether the experimental hypothesis won.

A treatment that performs poorly can still pass when it was executed correctly and preserved valid evidence. Regressions caused by source pollution are Part 2 findings.

## Node List

1. [ ] **Define Part 2 evidence contract** — Define source classes, authority, provenance, inclusion/exclusion, supersession, and temporal semantics.
2. [ ] **Prove chat path and scoring capability** — Establish a working one-shot answer path, capture retrieval and answer evidence, probe metadata behavior, and prepare scorer mechanics.
3. [ ] **Validate the existing MyAPI anchor** — Assess `REBUILD-CONTEXT-ANCHOR.md` against the evidence contract and extend it only where Part 2 requires dated current-direction context.
4. [ ] **Inventory canonical decisions** — Preserve the byte-identical Part 1 payload while separately inventorying the semantic knowledge it represents.
5. [ ] **Inventory MyAPI handoffs** — Resolve the 29 known handoffs plus relevant VM-only, duplicate, moved, superseded, dated, and missing artifacts.
6. [ ] **Capture Git temporal/change evidence** — Reproducibly represent commits, timestamps, parents, affected files, messages, and sufficient change evidence.
7. [ ] **Inventory Graphify structural evidence** — Establish what the current graph knows and separate retrieval-friendly representation from deterministic structural lookup.
8. [ ] **Build normalized source layers** — Produce independently composable anchor, decisions, handoffs, Git, and Graphify layers with provenance intact.
9. [ ] **Validate corpus variants** — Check provenance, temporal fields, duplicates, supersession, references, attribution, deterministic rebuilds, manifests, and hashes.
10. [ ] **Freeze the Part 2 evaluation ruler** — Fix the question suite, holdout, judge, rubric, generation settings, scoring schema, wording, and absolute dates.
11. [ ] **Run the exact Part 1 continuity control** — Replay the byte-identical Part 1 payload and exact five questions, then run appropriate Part 2 questions against the untouched payload.
12. [ ] **Run the normalized-decisions treatment** — Measure the normalized canonical-decision layer under the Part 2 ruler.
13. [ ] **Run the no-decisions treatment** — Measure anchor, handoffs, Git, and Graphify without canonical decisions.
14. [ ] **Run the handoff-enriched treatment** — Measure anchor, decisions, and handoffs.
15. [ ] **Run the code-reality treatment** — Measure anchor, decisions, Git, and Graphify without handoffs.
16. [ ] **Run the full durable-knowledge treatment** — Measure anchor, decisions, handoffs, Git, and Graphify together.
17. [ ] **Analyze failures and run the CLI gap-fill treatment** — Classify failures, admit CLI-derived evidence only for genuine durable-source gaps, rerun targeted questions, and test the untouched holdout.
18. [ ] **Converge evidence and produce the Part 2 finding** — Compare source contributions, best treatments, regressions, known failure modes, and routing implications for Part 3.

## Execution Topology

The graph uses 18 nodes. Source discovery and treatment evaluation are the primary concurrency surfaces.

```text
                           01 Evidence contract
                              /          \
                             /            \
                02 Chat/scorer probe       \
                           |                \
                           |       ┌─────────┼─────────┬─────────┬─────────┐
                           |       ▼         ▼         ▼         ▼         ▼
                           |   03 Anchor  04 Decisions 05 Handoffs 06 Git  07 Graphify
                           |       └─────────┴────┬────┴─────────┴─────────┘
                           |                      ▼
                           |              08 Build source layers
                           |                      ▼
                           |              09 Validate variants
                           |                      |
                           └──────────────┬───────┘
                                          ▼
                                  10 Freeze eval ruler
                                          |
                   ┌──────────────────────┼──────────────────────┐
                   ▼                      ▼                      ▼
           11 Part 1 control       12 Decisions-only      13 No-decisions
                                          │                      │
                              ┌───────────┼───────────┐          │
                              ▼           ▼           ▼          │
                         14 Handoffs   15 Code     16 Full durable
                              └───────────┼───────────┘
                                          ▼
                                  17 Gap + CLI treatment
                                          ▼
                                  18 Convergence report
```

## Implementation Nodes

### Experiment Foundation

#### 01 — Define Part 2 evidence contract

Define project knowledge before corpus construction begins:

- source classes
- source authority
- provenance requirements
- inclusion and exclusion rules
- supersession rules
- `occurred_at` versus `recorded_at`
- treatment composition rules

The contract must be mechanically actionable by downstream nodes. It must also state the Part 2 research question: **Which sources materially improve grounded project-history answers?**

#### 02 — Prove chat path and scoring capability

Configure the isolated Khoj user so one-shot chat produces a generated answer rather than an HTTP 500. Confirm that both retrieval evidence and generated answers can be captured.

Verify whether the installed Khoj version consumes temporal and provenance fields as metadata or sees them only as document text. Record the observed behavior without redesigning the corpus around it yet.

Prepare scorer mechanics here. The final evaluation questions remain unfrozen until Node 10.

### Concurrent Source Inventory

#### 03 — Validate the existing MyAPI anchor

Treat `REBUILD-CONTEXT-ANCHOR.md` as the existing candidate authority. Do not mint a competing golden brief.

Validate whether it establishes:

- project identity and purpose
- major components
- stable terminology
- enough current orientation to interpret retrieved facts

Extend it only when Part 2 requires clearly dated current-direction information.

#### 04 — Inventory canonical decisions

Carry forward the exact [[GDDP v MyAPI Part 1 - the first slice|Part 1]] decision corpus. Inventory the semantic knowledge represented by those decision objects, including decisions, rationale, supersession, relationships, and evidence references.

Preserve the **byte-identical Part 1 payload**. A normalized Part 2 representation may be produced separately; it cannot replace the historical control.

#### 05 — Inventory MyAPI handoffs

Inventory the 29 known MyAPI handoffs and any relevant VM-only handoffs. Resolve whether each artifact is:

- Git-backed or VM-only
- duplicated or moved
- current or superseded
- dated or temporally ambiguous
- present or missing

The resulting manifest must reproduce exactly which handoffs were included. Preserve chronology and provenance rather than summarizing away the source history.

#### 06 — Capture Git temporal/change evidence

Create a reproducible representation of Git evidence relevant to project history:

- commits and timestamps
- parent relationships
- affected files
- commit messages
- sufficient diff or change information

Git supplies evidence for **what changed**. Handoffs supply evidence for **why it changed**. Graphify supplies evidence for **what structure exists now**.

Use absolute dates in evaluation questions. For example: `What changed on 2026-08-14?`

#### 07 — Inventory Graphify structural evidence

Establish precisely what the existing Graphify output knows about symbols, files, relationships, dependencies, and references.

Preserve the distinction between:

```text
retrieval-friendly Graphify representation
vs.
deterministic Graphify structural lookup
```

The retrieval experiment may use a textual representation, but the source layer must retain enough deterministic structure for native use in Part 3.

### Corpus Construction and Validation

#### 08 — Build normalized source layers

Create reproducible, independently composable layers:

```text
anchor/
decisions/
handoffs/
git/
graphify/
```

Every item must retain source identity and enough provenance to trace a retrieved statement to its origin. Independent layers keep treatment assembly cheap and observable.

#### 09 — Validate corpus variants

Validate each layer and treatment configuration for:

- provenance integrity
- temporal fields
- duplicates
- superseded material
- broken references
- source attribution
- deterministic rebuilds
- manifests and hashes

The guarantee is reproducibility: if a treatment scores differently later, its exact contents can be reconstructed.

#### 10 — Freeze the Part 2 evaluation ruler

Create and freeze a 15–25 question suite covering:

- factual decisions
- rationale
- historical change
- current implementation
- supersession
- structural relationships
- cross-source synthesis
- deliberately unanswerable questions

Freeze the following with the suite:

- judge model
- judge prompt and rubric
- relevant generation settings
- scoring schema
- query wording
- absolute dates
- untouched holdout subset

Score at least four dimensions independently:

```text
retrieval quality
answer quality
grounding / provenance
abstention behavior
```

### Controlled Treatments

#### 11 — Exact Part 1 continuity control

Use the **byte-identical Part 1 decision payload** and replay the **exact five Part 1 questions**. Preserve comparable outputs. Then run technically appropriate Part 2 questions against the same untouched payload.

This control answers: **Did behavior change before the corpus changed?**

#### 12–16 — Part 2 treatment matrix

Run Nodes 12–16 concurrently with the same questions, scorer, answer path, and environment.

| Node | Treatment | Sources included | Primary contribution under test |
|---|---|---|---|
| 12 | Normalized decisions | Anchor + decisions | High-signal canonical decisions under the new ruler |
| 13 | No decisions | Anchor + handoffs + Git + Graphify | Unique value contributed by canonical decisions |
| 14 | Handoff-enriched | Anchor + decisions + handoffs | Rationale, chronology, progression, and why questions |
| 15 | Code reality | Anchor + decisions + Git + Graphify | Current structure, temporal change, and relationships |
| 16 | Full durable knowledge | Anchor + decisions + handoffs + Git + Graphify | Combined durable-source performance and source pollution |

Acceptance criteria concern experimental integrity, reproducibility, and preserved evidence. Treatment quality is a measured result.

### Gap Treatment and Convergence

#### 17 — Analyze durable-source failures and run CLI gap-fill treatment

Classify each durable-treatment failure:

```text
knowledge exists but retrieval missed it
knowledge was retrieved but synthesis failed
knowledge genuinely does not exist in durable sources
```

Only the third category earns CLI-session investigation.

Search session history for the missing facts, extract them into provenance-preserving artifacts, and add them as a distinct `cli-derived` treatment layer. Rerun the targeted questions, then run the untouched holdout subset. This tests whether CLI-derived knowledge generalizes beyond the questions that caused its inclusion.

#### 18 — Converge evidence and produce the Part 2 finding

Compare all treatments and produce the evidence required by Part 3. The final artifact must map each question class to:

```text
question class
├── decisions contribution
├── handoffs contribution
├── Git contribution
├── Graphify contribution
├── CLI contribution
├── best observed treatment
├── known failure mode
└── measured vs inferred
```

It must answer:

- Which knowledge belongs in MyAPI's durable corpus?
- Which questions are best served by which source?
- Where does semantic retrieval fail despite the knowledge being present?
- Where is deterministic or structural lookup indicated?
- What knowledge exists only in session history?
- What should Part 3 route rather than indiscriminately send through RAG?

## Completion Criteria

Part 2 is complete when the run has produced and preserved:

- a mechanically actionable evidence contract
- independently composable source layers
- manifests and hashes sufficient to reconstruct every treatment
- a working, evidence-capturing answer path
- a frozen evaluation suite with an untouched holdout
- the exact [[GDDP v MyAPI Part 1 - the first slice|Part 1]] continuity control
- treatment results across retrieval, answer quality, grounding/provenance, and abstention
- classified durable-source failures and a separately measured CLI-derived treatment
- a convergence report distinguishing measured results from analyst inference
- preserved regressions and source-pollution findings

The intended outcome is:

> **MyAPI has a reproducible, multi-source project corpus and measured evidence showing what each source contributes to grounded answers.**

## Part 3 Boundary

The three-part progression is:

```text
PART 1
Can the whole path execute?
decision → corpus → Khoj → query
                 ✓

PART 2
What actually produces good grounded answers?
source A ─┐
source B ─┼→ controlled treatments → evidence
source C ─┘

PART 3
Given a question, how should MyAPI answer it?
              question
                 ↓
             classifier/
              router
          ↙      ↓       ↘
       RAG    Graphify   temporal/
                         canonical
```

> [!stop] Stop boundary
> Stop Part 2 before intelligent routing. Part 2 delivers a real corpus, a real benchmark, provenance, treatment results, known failure classes, and evidence-backed CLI gap coverage. Part 3 builds routing intelligence on that evidence.

