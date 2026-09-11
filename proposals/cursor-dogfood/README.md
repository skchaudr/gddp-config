# Cursor dogfood — Sab's six-stage direction

Operator direction, 2026-09-11. Five draft nodes carry the defined work; stage 6 takes its shape from findings. These files remain outside graph discovery. Sab supplies graph placement and status; acceptance stays at human review boundaries.

## Acceptance and size

Each node has one short, binary capability or milestone criterion. Tests, traces and packet checklists supply evidence; the criterion is the acceptance question. Preserve this simplicity when refining the graph. A stage may be one task, 2–3 nodes or 4–6 nodes when the work reveals useful boundaries; Sab chooses each split and its capability-level outcomes.

## Order and execution recipes

| Stage | Draft node | Execution recipe |
| --- | --- | --- |
| 1 | `cursor-project-session-restoration` | Execute through Cursor as it works today, accepting the current extra worktrees while implementing their replacement. Use runtime packet `CURSOR-01` for workspace/resume mechanics and local checks. |
| 2 | `cursor-hooks-attribution` | Probe installed hooks, skill loading and custom-subagents. Wire events into the existing observation system with project/session/node/attempt/worker attribution. |
| 3 | `cursor-small-batch` | Run 2–3 Sab-selected nodes with hooks active. Use runtime packet `CURSOR-02` for effective startup, executable/auth/model and session/result inspection. Choose useful nodes at dispatch; the older A0/A1/B0 scenario is one available check. |
| 4 | `cursor-evaluator-reference-ack` | Inspect feedback already collected, then close any delivery/acknowledgement gap. Keep a finding's typed target reference intact through evaluator output, executor input and explicit executor acknowledgement. |
| 5 | `cursor-dogfood-audit` | Review the Cursor adapter and project executions together with hooks and agent observability. Return a cited continue-or-fix recommendation and actionable findings. |
| 6 | Open | Sab selects major fixes or other useful follow-up from actual findings. Author its nodes once its purpose is concrete. |

Stage 1 is the bootstrap exception to the earlier hook-first execution gate; stage 2 connects hooks, and stage 3 begins instrumented batch testing. Each YAML selects `cursor_cli`; verify the effective dispatch route when materializing the graph. Existing node work can supply later evidence, including an evaluator acknowledgement already demonstrated during stage 3.

Runtime recipe source: `gddp-runtime/docs/proposals/cursor-session-startup-packets.yaml`. Its detailed checks guide investigation and result collection; this ledger's short criteria define the proposed milestones. Earlier six-part outlines are historical planning context; Sab's sequence above governs this run.

## Typed references: observed starting point

The current runtime verifier/integrity tool schemas use string evidence arrays (`scripts/runtime/verification/semantic/pi_harness/gddp_verifier.ts` and `gddp_integrity.ts`). `scripts/runtime/verification/retry_budget.py` recognizes file-like references and affected-node IDs. Stage 4 must trace the real path before choosing the smallest typed-reference and acknowledgement change. A typed reference identifies a target by kind and identity, such as a repository file, graph node or canonical document; use the existing contract wherever present. Acknowledgement records that the executor received the finding; resolution and human acceptance remain separate outcomes.

## Validation and materialization

Drafts deliberately reserve `status` for Sab. Validate every other node field through the repository validator, check the five-node DAG and the single-criterion shape, and validate the materialized graph again when Sab supplies statuses. Graph indexing, service activation and node dispatch belong to the subsequent execution step.
