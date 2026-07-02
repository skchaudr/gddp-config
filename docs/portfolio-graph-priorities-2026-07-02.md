# Portfolio Graph Priorities - 2026-07-02

Purpose: keep the graph work aligned with the portfolio story while Sab handles
visualization separately. This file names graph/data priorities a future
visualization can consume, but does not define UI structure.

## Priority Order

1. Harden the GDDP verifier receipt contract.
   - First node: `graphs/gddp-runtime/nodes/verification-receipt-contract.yaml`
   - Why first: every portfolio claim about human-owned graph truth depends on
     receipts that separate code judgment from artifact completeness and graph
     advancement.

2. Execute the semantic harness hardening lane.
   - First implementation node: `semantic-submit-verdict-tool`
   - Then: `semantic-validation-retry`
   - Then: `verdict-confidence-split`, after the receipt contract exists
   - Optional spike: `ane-verifier-read-tool-eval` only if verifier reads stay
     token-heavy after the terminal verdict and retry fixes.

3. Use one non-GDDP graph to prove the receipt is reusable.
   - First candidate: MyAPI readiness inventory.
   - Graph shape: read-only verification graph, not an implementation graph.
   - First node candidate: `myapi-readiness-inventory`
   - Done signal: a receipt classifies migration docs, handoffs, live repo
     state, and unknowns as ready, blocked, or needs-review without mutating the
     MyAPI repo or any GDDP graph state.

## Why MyAPI First

MyAPI is the best first non-GDDP/client candidate because the runway already
identifies it as a real read-only target with handoffs, migration docs, and
unclear readiness state. It exercises the verifier's core promise without
adding executor risk: inspect existing evidence, produce a trustworthy receipt,
and leave the human with an explicit accept/retry/block/defer decision.

## Explicit Non-Goals

- Do not build graph visualization UI in this repo.
- Do not add visualization-specific layout, coordinates, colors, or rendering
  metadata to node YAML.
- Do not create a MyAPI graph until the verifier receipt contract is stable
  enough to reuse.
