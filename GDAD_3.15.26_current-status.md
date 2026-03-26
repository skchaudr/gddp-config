# CURRENT ENVIRONMENT & OPENCLAW V1 IMPLEMENTATION
Context: The target environment is a Raspberry Pi ("Big Pi") running systemd services and Tailscale. The forward/return webhook loops are operational. We are now building the OpenClaw V1 integration.

## DEPLOYED REPOSITORIES
1. `gddp-config`: Holds the project graphs (YAML) and SQLite DB.
2. `gddp-runtime`: Holds the webhook receiver, heartbeat loop, and return router.
3. `vault-doctor`: The current target project repo.

## OPENCLAW V1 CONTRACT
We are building the smallest real OpenClaw boundary. It is an event-driven function invoked by the webhook router.
* **Triggers:** issue opened/closed, PR opened/closed, cron heartbeat.
* **Inputs (Payload):** Trigger event, graph state, recent SQLite rows, optional PR metadata.
* **Allowed Outputs (Strict Schema):** `dispatch_next`, `recommend_accept`, `recommend_changes`, `mark_blocked`, `escalate`.
* **Forbidden Actions:** No direct merging, no direct graph mutation, no writing code.

## IMMEDIATE TASK DIRECTIVE
Do not over-engineer. Write the following 4 implementation components inside `gddp-runtime/src/openclaw/`:
1. `openclaw-v1-contract.md`: The rulebook.
2. `payload_builder.py`: Compiles the state, logs, and event into one JSON object.
3. `schema.py`: Pydantic models enforcing the 5 Allowed Outputs.
4. `wake.py`: The function that receives the payload, calls the model, and returns the structured decision.
