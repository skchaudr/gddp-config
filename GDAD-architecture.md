# GDAD 5-LAYER ARCHITECTURE & OPENCLAW ROLE
Context: This system uses a 5-layer architecture. Do not attempt to collapse these layers into a single AI agent. OpenClaw is the execution engine, NOT the source of truth.

## THE 5 LAYERS
1. Source-of-Truth Layer (The Graph): YAML files defining nodes, dependencies, evidence expectations, and boundaries.
2. Runtime Translation Layer (`gddp-runtime`): Converts graph reality into a JSON payload for the agent (active state, context, schemas).
3. Enforcement Layer: Python scripts and gates validating context, evidence, and state transitions.
4. Execution Layer (OpenClaw): The Gateway handling sessions, routing, and bounded execution of a specific task.
5. Reflection Layer (Health): SQLite logs and cron jobs calculating integrity and task drift.

## OPENCLAW'S CURRENT PHASE: "PHASE 0"
OpenClaw is currently an obedient, bounded executor. It is NOT an autonomous project manager.
* **Can Think:** Reads the `gddp-config` graph, SQLite logs, and PR diffs.
* **Can Propose:** Drafts next-step issues, summarizes failures, drafts PR reviews.
* **Can Execute (Strictly Gated):** OpenClaw CANNOT merge PRs or rewrite the graph directly. It proposes actions to the `gddp-runtime`, which executes them only if Evidence Requirements are met.
