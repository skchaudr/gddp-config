# 01 — Scope Contract (draft for Sab's acceptance)

Charted 2026-08-23. Deliverable of node `scope-contract` (agentos-dashboard).
DRAFT — acceptance completes this node; adjust any line and re-accept.

## Repo (settled by Sab)

- **Location:** `/Users/sab-mini/repos/agentos-dashboard` (new standalone repo, scaffolded `8be6a36`).
- Standalone web application per the plan: app + watcher + API together. Remote: none yet (push target settled in rollout-plan unless Sab says otherwise).

## Stack (per plan, confirmed)

- **Frontend:** React + Vite + Tailwind CSS + Canvas/D3 (or force-graph lib), theme `#0c0d10` with accents `#ff6b35` / `#f59e0b` / `#38bdf8`.
- **Backend:** Node or Python watcher daemon → `graph.json`; `/api/skills/run`; SSE or WebSocket log piping.
- Executor for headless runs: settled in node 09 (candidate: `claude -p` per plan, or pi/dsh per node-01 scope — Sab confirms).

## Data sources (proposed — confirm or edit)

| Source | Path (verified live 2026-08-23) | Feeds |
|---|---|---|
| Vault root (second-brain) | `/Users/sab-mini/Obsidian/SSD` (synced sab-mini ↔ sab-air; `_dispatch`, `_tasks`, `00 Inbox`, `01 Projects`, `02 Areas` present on both) | radial DAG hubs/leaves; root router note discovered in node 02/06 (not assumed) |
| Artifacts | SSD-wide scan for generated outputs (`.html`, `.excalidraw`, `.pdf`, `.md` logs, code) — v1 scope; exact dirs refined in node 05 | artifact orbit |
| Routines | `~/.hermes/cron/` (sab-mini) + any dsh routines (sab-air, per daily-driver graph node 03) | routines board |
| Skills | Pi skills (`~/.agents/skills`, `~/.pi/agent/skills`) — headless-run candidates settled in node 07/09 | skills deck |
| Apps/connectors | MCP servers + aa-cli targets (metadata leaf type only) | DAG leaves |

## Build posture

- **Mock-first where the plan is thin** (physics sliders, HUD actions, worker distinction): components render from mock graph.json until node 10 swaps live data.
- **Evidence-gated where the plan is concrete** (theme, layouts, endpoints, frontmatter contract).
- "Expect the rest to be learned while building" lives inside nodes — the chart stays bounded deliverables.

## Out of scope (fence)

- Remove Ball = UI-metadata removal only; never deletes files.
- No scheduling engine — routines board renders declared routines only.
- No auth/multi-user (personal dashboard).
