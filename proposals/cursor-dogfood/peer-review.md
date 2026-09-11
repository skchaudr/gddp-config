# Peer review — graph-shape decision pending

Independent reviewer run `d4e45e33-4115-4e93-8363-edbb11be421e` reviewed config `6dab125` and runtime `e4b6c8d`. Initial verdict: changes needed before Sab's graph review.

## Applied drafting corrections

1. **Bootstrap evidence:** `CURSOR-01` now verifies actual installed Cursor restart/resumption through the changed adapter in a bounded local fixture before stage-1 review. Stage 3 may repeat the observation with hooks. This removes the dependency on downstream evidence.
2. **Scope overlap:** stage 1 applies the boundary decision's workspace/session direction. Stage 2 owns hook, skill, custom-subagent and observability wiring.

## Sab's graph-shape decision

The reviewer recommends two nodes within stage 2, each with a single criterion:

- Hooks: A Cursor hook event resolves to the worker and node attempt that emitted it.
- Skill/subagent integration: Cursor loads the GDDP skill and invokes the configured custom subagent.

This would make stage 3 depend on both. The five draft files preserve their current shape while Sab considers that split; stage 6 remains open for future findings. The alternative is retaining one stage-2 capability node, with skill/subagent probes serving as supporting investigation.

## Hold

Implementation, dispatch and service changes remain held until the authored graph is approved. Follow-up peer review awaits the stage-2 shape decision.

Sab identified the concurrent edit as his work and clarified the node as execution of the already-decided repair. Its sole criterion is now: “The Cursor CLI adapter functions just like the pi_rpc adapter.” The node's purpose and worker boundary carry that settled direction; the audit/recommendation framing has been replaced.

The file retains Sab's `cursor-drift-fix` identity and `repair` type. Its older filename, dependency placement and surrounding ledger references still require the graph-authoring pass; the current validator flags the filename/ID mismatch and its supported type list. Preserve this operator direction while reconciling the graph, then repeat peer review before execution.
