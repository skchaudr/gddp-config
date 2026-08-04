The documented workflow is:

```text
Wayfinder
  → map issue + decision tickets
  → resolved architectural route
  → /to-spec
  → canonical implementation spec
  → /to-tickets
  → approved implementation tickets
  → agents claim and execute the unblocked frontier
```

### 1. Wayfinder creates decision tickets

Wayfinder begins with:

1. `/grilling` + `/domain-modeling` to establish the destination.
2. A breadth-first pass to identify unresolved decisions, dependencies, and fog.
3. A GitHub `wayfinder:map` issue.
4. Child decision tickets for every question precise enough to investigate now.
5. Native GitHub dependency edges connecting those tickets.

Those tickets emerge directly from the unresolved architectural and product questions discovered during the Wayfinder conversations. Each is labeled by the appropriate resolution method:

- `wayfinder:research`
- `wayfinder:prototype`
- `wayfinder:grilling`
- `wayfinder:task`

Each session claims and resolves one decision ticket, records the answer, updates the map, and creates newly visible decision tickets until the destination is fully charted.

### 2. Existing tickets become the backlog under reconciliation

The current issues #11–29 are the starting candidate backlog. Wayfinder will compare each one against the operative architecture and classify it:

- **Keep** — its premise, scope, and acceptance criteria still fit.
- **Amend** — the work remains useful but its role, wording, dependencies, or acceptance criteria need correction.
- **Supersede** — a newly resolved decision calls for a replacement ticket.
- **Preserve as evidence** — completed tickets and their results inform the map and resulting specification.
- **Add** — Wayfinder exposes a missing decision or implementation path.

That makes the current work recoverable without treating every existing ticket as automatically correct.

### 3. `/to-spec` consolidates the resolved route

Once Wayfinder has resolved the architectural questions, `/to-spec` synthesizes:

- the operative architecture plan,
- Wayfinder’s decisions,
- relevant existing-ticket evidence,
- implementation decisions,
- testing seams,
- user stories,
- and scope boundaries.

It publishes the canonical implementation specification as a GitHub issue.

### 4. `/to-tickets` creates implementation tickets

`/to-tickets` reads that specification and the reconciled existing backlog. It then:

1. Drafts end-to-end tracer-bullet slices.
2. Defines their blocking relationships.
3. Presents the complete proposed breakdown to us.
4. Waits for our approval.
5. Keeps, amends, supersedes, or creates GitHub issues accordingly.
6. Labels executable work `ready-for-agent`.
7. Wires native GitHub dependency edges.

These are the tickets Grok/Pi workers claim and implement. Completion is recorded through checkpoint receipts and the repository’s close policy.

The repository is already configured for this workflow in [issue-tracker.md](/Users/sab-mini/.pi/docs/agents/issue-tracker.md). GitHub is the configured tracker, `ready-for-agent` is the executable state, assignment is the claim, and native dependencies define the frontier.

### Wayfinder has now started

Its first required decision is the destination. My recommended destination is:

> **Produce one authoritative, implementation-ready Pi Capability Cascade specification and a reconciled GitHub ticket graph for proving and integrating Mercury, FunctionGemma, and Needle through native Pi tooling, with every existing ticket kept, amended, superseded, or preserved as evidence.**

Is that the exact destination we should lock for the Wayfinder map?
