# Project Graph Quality

Minimum quality contract for a GDD project graph.

This document defines what a project graph must contain before it should be treated as a real routing surface for OpenClaw or any executor.

## Purpose

A project graph exists to answer, concretely:

1. What project does this event belong to?
2. Which node or nodes are eligible?
3. Which executor is allowed?
4. What artifact must come back?
5. What counts as done?
6. What graph state changes next?

If a graph cannot answer those questions without human improvisation, it is not ready.

## Minimum Required Structure

Each project graph must have:

- a `project.yaml`
- a `nodes/` directory
- stable `project_id`
- stable `node_id` values

## `project.yaml` Contract

`project.yaml` must define:

- project identity
- repo identity
- project scope and intent
- graph-level done semantics
- default executor policy
- graph entrypoints
- advancement / completion expectations

At minimum, a graph should make clear:

- what kinds of events belong here
- what kinds of work this graph governs
- what must be true before graph state advances

## Node Contract

Each node must define:

- `node_id`
- purpose
- triggering inputs or conditions
- prerequisites / dependencies
- allowed executors
- required artifacts
- verification expectations
- done criteria
- failure / retry posture

Nodes should be authored as bounded units of work or bounded units of doctrine, not broad aspirations.

## A Good Node

A good node is:

- bounded
- legible
- evidence-bearing
- reviewable
- advanceable without hidden tribal knowledge

A good node lets an operator or orchestrator determine:

- why the node exists
- when it is eligible
- what it can dispatch
- what output must return
- how completion is judged

## Artifact Contract

Every executable node must imply or explicitly define an artifact contract.

Minimum artifact surface:

- job packet / task packet
- result payload
- verification record
- advancement signal
- human review requirement, if any

Artifacts are evidence-bearing objects. Chatty output is not enough.

## Minimum Routing Contract

For a graph to be routing-ready, a single event should allow the system to derive:

1. normalized event
2. project attachment
3. target node or candidate nodes
4. executor choice
5. expected return artifacts
6. completion decision
7. next graph state

If any of those are undefined, the graph is still design-stage.

## Anti-Patterns

Common graph failures:

- nodes that are really vague goals
- nodes with no artifact contract
- nodes with no done criteria
- nodes that mix doctrine, implementation, and review in one blob
- graphs where project attachment is ambiguous
- graphs that require operator memory to route basic work
- executor choice implied only by custom or historical knowledge

## Recommended Shape For A New Graph

Start small.

A new project graph should usually begin with 3-7 core nodes:

- at least one entry / intake node
- at least one execution node
- at least one verification or review node

Do not expand the graph until the first supervised rep has been walked through end to end.

## Graph Readiness Litmus Test

Before treating a graph as active, test it with one plausible event and verify that a human can derive:

- event normalization
- project attachment
- selected node
- executor
- required artifacts
- done criteria
- advancement outcome

If that supervised rep wobbles, the graph needs refinement before automation.

## Governing Principle

Graphs define projects. Executors do not.

OpenClaw, Jules, Codex, or any other executor may operate against a graph, but they do not define project truth. The human-authored graph remains the authority on routing boundaries, artifacts, and completion.
