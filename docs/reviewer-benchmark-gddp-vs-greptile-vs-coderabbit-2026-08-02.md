# Reviewer Benchmark: GDDP vs Greptile vs CodeRabbit - 2026-08-02

Status: idea capture, not a plan yet. Written the day GDDP started actually running, so the comparison is finally possible.

## The Idea

Now that GDDP runs end to end, set up Greptile and CodeRabbit on the same repos and compare all three head-to-head on a shared acceptance metric: **nodes accepted vs nodes sent back to retry** (and the tail: nodes that never converge).

The point is not "which bot writes nicer comments." It is: for a unit of work, which reviewer gets it to an accepted state, in how many passes, with how much human intervention.

## The Hard Part (write this down before building anything)

The three systems do not share a unit of work by default.

- GDDP's unit is a **node**: a graph-owned task with an acceptance contract, dispatched, verified, and either accepted or retried. Retry is a first-class, counted state.
- CodeRabbit and Greptile's unit is a **PR review**: they emit comments on a diff. There is no native "accepted / retry" verdict, and no acceptance contract to check against.

So the benchmark only means something if a common unit is defined first. Options:

1. **Node-shaped harness (preferred).** Take the same node, produce the same candidate diff, then run each reviewer over that diff. Score each reviewer's output by mapping it onto the GDDP verdict space: accept / retry-with-findings / blocker. GDDP's own verifier is one of the three contestants, not the referee.
2. **PR-shaped harness.** Wrap each GDDP node's output as a PR and let all three review it as a PR. Simpler to set up, but flattens GDDP's contract-checking advantage and probably understates it.

Either way the referee has to be something neither side owns - a human-labelled ground truth set, or at minimum a frozen labelled corpus of diffs where accept/retry is known in advance.

## Metrics Worth Collecting

- Nodes accepted first pass / total nodes.
- Retry count distribution per node (mean, p90, never-converged count).
- False accepts: reviewer said accept, ground truth says defect. This is the metric that actually matters and the one PR bots are never scored on.
- False retries: reviewer sent back clean work. Cost side of the ledger.
- Human interventions per accepted node.
- Wall-clock and cost per accepted node.

## Open Questions

- Which repos? MyAPI already has real handoffs and unclear readiness state, which makes it a decent target - but "unclear readiness" cuts both ways for ground truth.
- Corpus size needed before the numbers stop being anecdotes.
- Do Greptile/CodeRabbit get repo context parity? They index the repo; GDDP has the graph. Not the same context, and pretending it is would be dishonest either direction.
- Ground-truth labelling: who does it, and how is it kept from being GDDP-flavoured?

## Next Actions (unscheduled)

- [ ] Set up CodeRabbit on a target repo.
- [ ] Set up Greptile on the same repo.
- [ ] Define the common unit of work + verdict mapping (blocking - everything else is downstream of this).
- [ ] Pick/label a frozen diff corpus.
