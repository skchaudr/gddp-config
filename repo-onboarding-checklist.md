# Repo Onboarding Checklist

Checklist for bringing a new repository into GDD with its own project graph.

## Goal

Create a minimal, routing-ready project graph for a repo without overbuilding it.

## 1. Establish Project Identity

- choose a stable `project_id`
- confirm the canonical repository name
- define the graph scope in one sentence
- define what kinds of events should attach to this project

## 2. Create The Graph Skeleton

- copy `graphs/_template` to `graphs/<project-id>`
- create or update `graphs/<project-id>/project.yaml`
- create `graphs/<project-id>/nodes/`

## 3. Author Only Core Nodes

Start with 3-7 nodes.

Include:

- one entry / intake node
- one execution node
- one verification or review node

Do not model every future capability up front.

## 4. Define Node Contracts

For each node, confirm:

- clear purpose
- clear prerequisites
- allowed executors
- required artifacts
- verification expectations
- done criteria

If any node cannot answer those questions, do not treat it as active.

## 5. Define Artifact Expectations

Confirm what durable outputs must exist for work on this repo.

Typical minimums:

- task packet
- result summary
- verification record
- advancement decision

## 6. Define Routing Expectations

For the first supported event types, confirm:

- how events are normalized
- how `project_id` is attached
- which node(s) are eligible
- what executor is permitted
- what counts as completion

## 7. Run One Supervised Rep

Use one plausible minimal event.

Walk it through:

1. event
2. normalized representation
3. project attachment
4. routing interpretation
5. proposed job packet
6. executor choice
7. expected return artifacts
8. done criteria
9. uncertainties

Do not expand the graph until this rep is coherent.

## 8. Record Known Gaps

After the supervised rep, capture:

- ambiguous routing logic
- missing node contracts
- missing artifact schemas
- unclear review gates
- undefined advancement behavior

Mark these as explicit graph gaps, not operator memory.

## 9. Activate Conservatively

Before calling a project graph active, verify:

- project attachment is deterministic enough for the supported event set
- at least one execution path is bounded and reviewable
- artifact expectations are concrete
- completion semantics are explicit

If those are not true, keep the graph in supervised mode.

## 10. Operator Rules

- do not let agents invent doctrine for a new graph
- do not treat chat output as an artifact
- do not add nodes faster than they can be tested
- prefer one tight graph that routes correctly over a large graph that only sounds smart

## Exit Criteria

A repo is onboarded when:

- it has its own project graph
- the graph passes one supervised rep
- routing boundaries are understandable
- artifacts and done criteria are explicit
- the human accepts the graph as authoritative enough for bounded execution
