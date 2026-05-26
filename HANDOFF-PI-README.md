# Handoff for Pi README Agent

This is the `gddp-config` repo entrypoint for the Pi agent. The matching runtime-side handoff lives at `../gddp-runtime/HANDOFF-PI-README.md`; this file repeats the essentials so a cold agent can start from either repo root.

## Project identity

GDDP is a system for turning software projects into explicit maps of work, then using agents to move through those maps without losing human control. Underneath that plain-language idea is a graph-driven agentic development control plane: `gddp-config` defines project truth as schemas, graphs, nodes, constraints, and acceptance criteria; `gddp-runtime` reads that truth, dispatches bounded work, records jobs/results/receipts in SQLite, and stops at human review instead of silently rewriting the graph.

## Repo topology

- `gddp-runtime`: primary repo for the portfolio README. It contains the runtime/orchestration layer, Big Pi deploy scripts, heartbeat loop, executor adapters, webhook intake, result/receipt handling, tests, and operational docs.
- `gddp-config`: technical source-of-truth repo. It contains schemas, templates, and project graphs. Agents read it; they should not rewrite it.

Recommended README placement:

- Draft the primary portfolio `README.md` in `gddp-runtime`.
- Keep this repo's `README.md` as a smaller technical contract for schemas, graphs, and templates.
- Cross-reference this repo from the runtime README instead of trying to merge both repos into one README.

## Current state (post-hygiene)

### gddp-config

Current branch name: `feat/openclaw-nodes`. The active graph objects now use decision-loop naming; the branch name is historical.

Top-level structure:

- `README.md`: source-of-truth contract for schemas, graphs, and templates.
- `schemas/v1/`: canonical YAML schemas for events, jobs, nodes, results, queue records, artifact verification, and task packets.
- `templates/`: reusable node and job templates.
- `graphs/`: project graphs for `_template`, `vault-doctor`, and `gddp-runtime`.
- `upgrade-strategy.md`: schema versioning, rollback, executor adapter, and credential isolation policy.
- `_archive/april-update.txt`: historical transcript material; not operational documentation.
- `rules/`, `scripts/`, `workflows/`: future/empty local dirs, not tracked source yet.

What works:

- All YAML graph/schema/template files parse locally: `parsed 24 yaml files`.
- `graphs/vault-doctor` is complete with 7/7 nodes complete.
- `graphs/gddp-runtime/project.yaml` currently maps:
  - `return-router`: complete
  - `decision-loop-spec`: complete
  - `decision-loop-runtime`: pending
  - `decision-loop-review-gate`: pending
- Node files under `graphs/gddp-runtime/nodes/` hold the real acceptance criteria, constraints, allowed execution modes, and required artifacts.

### gddp-runtime

Current branch: `main`, clean and pushed to `origin/main`.

What works:

- Runtime tests pass locally: `python3 -m pytest -q` -> `40 passed`.
- `scripts/init_db.py` initializes the SQLite schema.
- `scripts/intake_server.py` handles GitHub webhook intake and optional `GITHUB_WEBHOOK_SECRET` signature validation.
- `scripts/runtime/heartbeat/runner.py` is the canonical graph-driven heartbeat entrypoint.
- `scripts/runtime/heartbeat/graph_reader.py` reads this repo via `--config-path`, `GDDP_CONFIG_PATH`, or sibling repo fallback.
- `scripts/adapters/jules_action_adapter.py` dispatches Jules work through GitHub issues and requires `GITHUB_TOKEN` or `GH_TOKEN`.
- `scripts/runtime/return_router.py` converts merged-PR return events into review receipts.
- `deploy/BIGPI_RUNBOOK.md` is the operational runbook for the live Big Pi control plane.

What is intentionally incomplete or frozen:

- Runtime must not mutate `gddp-config` automatically.
- Merged PRs create structured receipts and move work to review-needed states; human review decides whether graph truth changes.
- `scripts/runtime/graph_updater.py` remains only as a disabled compatibility stub.
- No auto-review, richer graph state machine, or automatic return-path completion in the frozen phase.
- Decision-loop review/accept powers are draft/future, not the current stable contract.

## Portfolio framing (Pi agent voice — quote verbatim)

"This is a portfolio README for a project built solo by a recent CS graduate who entered the field later in life and is working at the technical frontier. Audience is mixed: senior engineers should see technical depth and honest tradeoffs; recruiters should see scope and seriousness; people without context should understand what was built and why it's interesting. Confident and accurate — not boastful, not self-deprecating."

## Pi agent deliverables

- Draft `README.md` in `gddp-runtime`, with appropriate cross-references to `gddp-config`.
- Produce a separate polish punchlist covering hardening opportunities across both repos.
- Do not push to GitHub. Drafts only.

## Gotchas

Paths:

- Runtime repo on this machine: `/Users/saboor/repos/gddp-runtime`
- Config repo on this machine: `/Users/saboor/repos/gddp-config`
- Big Pi source runtime checkout: `~/repos/gddp-runtime`
- Big Pi source config checkout: `~/repos/gddp-config`
- Big Pi deployed execution surface: `~/opclaw/scripts`
- Big Pi live runtime state: `~/opclaw/db`, `~/opclaw/events`, `~/opclaw/jobs`

Environment variables:

- `GDDP_CONFIG_PATH`: path to this repo for graph reads.
- `GDDP_RUNTIME_ROOT`: runtime state root. Legacy `OPCLAW_ROOT` may still be accepted by older scripts as a compatibility fallback.
- `GITHUB_TOKEN` or `GH_TOKEN`: required for Jules GitHub issue dispatch.
- `GITHUB_WEBHOOK_SECRET`: optional webhook signature validation secret for runtime webhook intake.

Files/dirs to skip:

- Do not use `_archive/april-update.txt` as live docs.
- Do not treat `.claude/`, `.aider*`, `.DS_Store`, `.pytest_cache/`, or `__pycache__/` as source material.
- Do not draft the portfolio README in `gddp-config` unless Saboor explicitly redirects you.
- Do not mutate graph truth from runtime. The current contract is receipt creation plus human review.
- Do not assume `rules/`, `scripts/`, or `workflows/` are implemented because the README mentions them as future surfaces.
