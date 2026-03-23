# GDAD Graph Rules

Standing rules that apply to every project graph, every node, every executor.
These are not suggestions. They are the contract OpenClaw enforces.

---

## Rule 1: Smallest Verifiable Artifact

Every node must produce the **smallest artifact that proves the claim and can be
checked by a script without human interpretation.**

| Claim type | Artifact form |
|------------|---------------|
| An enumeration exists | YAML/JSON with count check |
| A data model exists | Schema file with syntax check |
| A process ran | Manifest/report JSON with key + threshold check |
| A decision was made | Markdown with required section existence check only |

Never ask for prose when a count will do.
Never ask for a count when a schema check will do.
The artifact must be the minimum that makes the pass/fail signal unambiguous.

---

## Rule 2: Every Executable Node Declares Both a Success Artifact and a Failure Artifact

Success proofs alone are not enough for wake-state decisions.

When a node fails, stalls, or produces partial output, OpenClaw still needs a
machine-readable receipt that distinguishes:

- `retryable` — Jules can be dispatched again without human input
- `partial` — some work was done, retry with correction prompt
- `escalate` — human must intervene before work can continue

**Every executable node must declare:**

```yaml
success_artifact:
  file: <filename>
  verification: <rule>

failure_artifact:
  file: failure_report.json
  fields_required: [error_type, reason, partial_artifacts]
  error_type_enum: [retryable, partial, escalate]
```

**failure_report.json minimum shape:**
```json
{
  "error_type": "retryable | partial | escalate",
  "reason": "specific human-readable explanation",
  "partial_artifacts": ["list of files produced before failure, if any"],
  "failed_at": "ISO8601 timestamp"
}
```

OpenClaw reads `error_type` at wake-up and maps it directly to an action:
- `retryable` → retry
- `partial` → retry with correction context
- `escalate` → escalate to human

Without this, the agent cannot distinguish a timeout from a design flaw.

---

## Rule 3: Signal IDs Must Be Cross-Referenced

Any node that references a `signal_id`, `indicator_id`, `source_id`, or similar
foreign key from another node's artifact must validate that the reference exists.

No orphan references. If the taxonomy changes, downstream nodes must be updated.

---

## Rule 4: No Ambiguous Pass Conditions

Every acceptance criterion must be checkable with a script.
The following are not valid acceptance criteria:

- "Jules implements the feature correctly"
- "The output looks reasonable"
- "Tests pass" (without specifying which tests and what threshold)

Valid forms:
- "File X exists and parses as valid YAML"
- "JSON field Y contains >= N items"
- "Script Z exits with code 0"
- "File X contains sections A, B, C (existence check, not content check)"

---

## Rule 5: DAG Entry Points Are Explicit

Every project graph must have at least one node with `depends_on: []`.
If all nodes have dependencies, the graph has a cycle or was designed incorrectly.

Prefer multiple entry points where work is genuinely independent.
Do not add artificial dependencies to enforce sequencing that the work doesn't require.

---

## Applies To

All graphs under `graphs/` in this repository.
All nodes authored for any project.
All executors (Jules, future executors).
