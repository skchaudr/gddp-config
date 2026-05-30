# AGENTS.md — gddp-config

Configuration repo for the GDDP pipeline. Contains YAML schemas, rules,
templates, workflows, and graphs. No runtime code — purely declarative.
Companion repo: `gddp-runtime` (the execution engine).

## Operator relay

This task may have a live operator on the other end of an HTTPS relay
(see https://github.com/skchaudr/jules-relay).

Env vars (set per-session):
- `RELAY_URL` — base URL of the relay
- `RELAY_TOKEN` — bearer token

On session start, open an SSE subscription:

```bash
curl -N "$RELAY_URL/events" -H "Authorization: Bearer $RELAY_TOKEN" &
```

Behavior rules:
- Post STATE at task start and task finish only. No checkpoints.
- If a message arrives with `from=m1` and `kind=ASK`, **pause the specific
  gated decision it refers to** until an `ACK` arrives from `m1`, or until
  the relay becomes unreachable. Continue everything else.
- If the relay is unreachable (connection refused, 5xx, timeout): proceed
  per the original task brief, EXCEPT for actions explicitly marked
  "operator-gated" in the task.
- NEVER place secrets, credentials, private URLs, tokens, SSH details, or
  sensitive repo contents in relay messages. Coordination text only.

### Message envelope

`POST $RELAY_URL/msg` with `Authorization: Bearer $RELAY_TOKEN`:

```json
{ "from": "jules", "kind": "STATE" | "ASK" | "ACK", "text": "..." }
```

`text` must be ≤ 4096 chars, non-empty.

## Environment

| Var | Purpose | Set by |
|---|---|---|
| `RELAY_URL` | Relay endpoint | Jules session env |
| `RELAY_TOKEN` | Relay auth | Jules session env |

## Project snapshot

- **Language:** YAML / Markdown only — no code to build or test
- **Install:** none
- **Validate schemas:** `python3 -c "import yaml; yaml.safe_load(open('rules/*.yml'))"` (manual)
- **Key dirs:** `rules/`, `schemas/`, `templates/`, `workflows/`, `graphs/`
