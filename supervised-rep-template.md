# Supervised Rep Template

Template for the first supervised Graph-Driven Development rep on a new project graph.

Use this before treating a graph as active for real routing or execution.

## Purpose

A supervised rep is the smallest concrete walk-through that proves a graph can:

- attach an event to the correct project
- interpret the event against graph structure
- select a bounded node
- constrain executor choice
- demand real artifacts
- define what done means

This is not a philosophy exercise. It is a pressure test.

## When To Use

Run this template:

- when creating a new project graph
- when introducing a new event type
- when changing routing semantics
- when graph behavior feels plausible but unproven

## Input

Choose one plausible minimal event.

Examples:

- GitHub issue opened
- pull request opened
- webhook delivery for a supported provider
- internal retry / failure replay event

Do not choose a large or ambiguous example for the first rep.

## Output Structure

Use this exact structure.

### 1. Event

Describe the event as received.

Include:

- source
- repo
- type
- minimal payload fields that matter

### 2. Normalized Representation

Show what the runtime should reduce the event to.

Include:

- normalized event type
- project candidate
- routing-relevant fields
- missing or uncertain fields

### 3. Project / Context Attachment

Explain how the system decides this event belongs to the project graph.

If this is inferred rather than implemented, mark it.

### 4. Routing Interpretation

State which node or nodes are eligible and why.

Include:

- selected node
- rejected alternatives
- prerequisite checks

### 5. Proposed Job Packet

Describe the minimum bounded packet that would be handed to an executor.

Include:

- node ID
- executor
- task scope
- constraints
- required outputs

### 6. Executor Choice

Explain why the chosen executor is allowed.

If the graph allows multiple executors, explain the decision boundary.

### 7. Expected Return Artifacts

List the artifacts that must come back before the node can be considered complete.

Examples:

- task packet
- result summary
- verification record
- graph advancement proposal
- PR or commit linkage

### 8. Done Criteria

Define what must be true for this rep to count as complete.

Done must be evidence-backed, not executor-asserted.

### 9. Uncertainties / Doctrine Assumptions

List all places where:

- behavior is inferred
- schema is incomplete
- routing is ambiguous
- graph rules are missing

Do not hide uncertainty.

## Evaluation Questions

After the rep, answer:

1. Was project attachment deterministic?
2. Was node selection bounded and legible?
3. Was executor choice constrained?
4. Were expected artifacts concrete?
5. Was done criteria explicit?
6. Did any part of the flow rely on tribal knowledge?

If the answer to any of those is weak, the graph needs revision before activation.

## Failure Signs

The rep failed if:

- multiple nodes seem equally valid with no decision rule
- artifact expectations are implied but not stated
- executor selection depends on custom memory
- completion depends on “looks good”
- graph advancement cannot be explained concretely

## Governing Rule

Do not add more graph structure to hide a weak rep.

If the rep is weak, tighten the graph.
