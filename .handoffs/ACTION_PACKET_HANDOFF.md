# ACTION_PACKET_HANDOFF

> Compiled: 2026-04-11  
> Purpose: Single-read context for openclaw — topology, repo reality, runtime shape, VM status.  
> Do not hand-edit runtime state sections. Update by re-running the audit.

---

## 1. System Topology

```
┌─────────────────────────────────────────────────────┐
│                  Tailscale Network                   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  ssd-big (BigPi) — CONTROL PLANE             │   │
│  │  openclaw-gateway.service :18789 (loopback)  │   │
│  │  Tailscale Serve → ssd-big.tail02ac6f.ts.net │   │
│  │  Channels: WhatsApp ✅  Telegram (unverified) │   │
│  └──────────────────────────────────────────────┘   │
│                        ▲                             │
│                        │ TLS/WSS                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  ssd-small — REMOTE NODE                     │   │
│  │  openclaw-node.service                       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘

GCP VMs (separate from Tailscale nodes above):
  first-vm             us-west2-c         16 GB
  khoj-headless-engine us-central1-a      32 GB
```

| Role | Host | Notes |
|---|---|---|
| Orchestrator / control plane | BigPi (ssd-big) | Memory, planning, dispatch, cron, intake server |
| GDDP runtime execution | first-vm | Repos cloned, heartbeat runner invocable |
| Khoj / RAG ingestion | khoj-headless-engine | Khoj healthy as of 2026-04-09 |
| Dev / UX | MacBook | Dotfiles, browser verification, one-off loops |

### SSH commands
```bash
# first-vm
gcloud compute ssh first-vm --zone=us-west2-c

# khoj-headless-engine
gcloud compute ssh --zone us-central1-a khoj-headless-engine \
  --tunnel-through-iap --project gen-lang-client-0824562549
```

### Known OpenClaw bug (non-blocking)
BigPi local CLI reports `missing scope: operator.read` on loopback.  
**Workaround:** use the UI for all BigPi operator actions. Remote node and channels are unaffected.

---

## 2. Repo Reality

### gddp-config
- **Remote:** `git@github.com:skchaudr/gddp-config.git`
- **Branch:** `feat/dag-graph-design` | Head: `d989285`
- **Role:** Human-owned source of truth for all project graphs, schemas, and templates
- **Core principle:** Graphs define projects. Agents do not. Runtime reads only — never writes.
- **Structure:** `schemas/v1/` · `graphs/` · `templates/`
- **Branch protection:** `main` is protected. All changes via PR. Human is the only merge authority.

### gddp-runtime
- **Remote:** `git@github.com:skchaudr/gddp-runtime.git`
- **Branch:** `main` | Head: `c2a10d4` (`docs: freeze receipt review workflow`)
- **Role:** Execution and orchestration layer — forward dispatch + return receipt routing
- **Phase:** Frozen at receipt routing + human review (commits `24a3bc7` + `4526dc2`)
- **Deploy surface:** Runs directly from repo checkout on BigPi and first-vm. `opclaw/` is archived — not a dependency.
- **Active service on BigPi:** `opclaw-intake.service` (Flask webhook intake, normalizes GitHub events to SQLite)

### MyAPI
- **Remote:** `git@github.com:skchaudr/MyAPI.git`
- **Branch:** `main` | Head: `a61c8b6` (`project status and next steps for front and backend`)
- **Role:** RAG pipeline for Obsidian notes + AI conversation exports → Khoj ingestion
- **Frontend:** `context-refinery/` — React/Vite scaffold (Import / Refine / Export views, Gemini summarization hook)
- **Status:** Frontend is scaffold-only, not yet wired to live processing. Canonical schema and ingestion pipeline are the next implementation target.

### opclaw
- **Status: ARCHIVED** — legacy experiment surface, superseded by gddp-config + gddp-runtime
- Do not treat as canonical for runtime behavior. `ANTIGRAVITY.md`, `global_rules/`, `global_workflows/` are archive-only.

---

## 3. GDAD Runtime Shape

### Forward path (`scripts/runtime/heartbeat/`)
| File | Responsibility |
|---|---|
| `graph_reader.py` | Reads gddp-config YAML → `ProjectGraph` / `NodeData` → `get_ready_nodes()` |
| `classifier.py` | Maps `issue.opened` events to highest-priority ready node; intent: `implement_existing_node` |
| `scope_checker.py` | Guards duplicate dispatch and unmet dependencies |
| `job_factory.py` | Builds persisted job dict and artifact directory |
| `state_recorder.py` | Inserts job and queue rows into SQLite |
| `runner.py` | Orchestrates plan → parallel dispatch → outcome recording |
| `dispatcher.py` | Routes to adapter by `job["executor"]` |

### Executor adapter (`scripts/adapters/`)
- **Active:** `jules_action_adapter.py` — creates GitHub issue for Jules
- **Stub:** `jules_cli_adapter.py` — Phase 4+, not active

### Return path (`scripts/runtime/`)
| File | Responsibility |
|---|---|
| `return_router.py` | Validates repo/job/node linkage, writes receipt, moves job → `awaiting_review` |
| `results_store.py` | Persists structured receipt into `results` table |
| `replay.py` | Replays return routing or re-dispatches a job |
| `graph_updater.py` | **Disabled stub.** Returns `{ok: False, reason: "graph_mutation_disabled_review_required"}` |

### Upstream / legacy
- `intake_server.py` — Flask webhook intake on BigPi; upstream of dispatch, not a dispatcher
- `heartbeat.py` — legacy hardcoded heartbeat, retained only
- `dry_run.py` — demo path modeling receipt-to-review

### Canonical heartbeat invocation
```bash
cd ~/work/repos/gddp-runtime/scripts
python3 -m runtime.heartbeat.runner \
  --project <project-id> \
  --repo <owner/repo> \
  --config-path ~/work/repos/gddp-config
```

### Phase freeze invariants — must not be reintroduced
- No automatic node advancement from executor output or merged PR
- No auto-review, no smart return routing, no richer graph states
- No path from receipt back to gddp-config mutation
- Executor success ≠ node completion
- Documented: `README.md:97` and `deploy/BIGPI_RUNBOOK.md:88`

---

## 4. Project Graph Status

### gddp-runtime project
```
return-router → complete
```
One node. Fully resolved. Next node TBD.

### vault-doctor project
```
7/7 nodes → complete
```
First real GDAD project. Fully resolved.

### How to check ready nodes
```bash
python3 - <<'PY'
from pathlib import Path
import yaml
project = Path.home() / "work/repos/gddp-config/graphs/<project-id>/project.yaml"
data = yaml.safe_load(project.read_text())
print([n["id"] for n in data.get("nodes", []) if n.get("status") == "ready"])
PY
```

---

## 5. VM State

### first-vm (16 GB) — GDDP runtime host
| | |
|---|---|
| OS | Debian 12, kernel 6.1.0-44-cloud-amd64 |
| RAM | 15 GB total / 13 GB available |
| Disk | 9.7 GB root / 4.7 GB free |
| Python | 3.11.2 |
| Node | v24.14.0 |
| Docker | 29.3.0 |
| Tailscale | running |
| Key pip packages | fastapi, pyyaml, requests |
| Repos | `gddp-config`, `gddp-runtime`, `MyAPI`, others — at `/home/saboor/work/repos/` |
| GDDP deploy | No intake service needed (BigPi owns that). Heartbeat runner invocable directly from repo. |

### khoj-headless-engine (32 GB) — Khoj / RAG host
| | |
|---|---|
| OS | Ubuntu 22.04 |
| Khoj service | `khoj.service` — `active (running)` as of 2026-04-09 |
| Venv | `/home/sbkchaudry_gmail_com/khoj-engine/venv` |
| Health endpoint | `http://localhost:42110/api/health` → `200 OK` |
| PostgreSQL | localhost:5432, DB=`khoj`, user=`khoj` |
| Status | Healthy. Prior failure (missing migration table) was fixed by force-reinstalling `khoj==1.42.10`. |

---

## 6. Workstream Status

### Workstream A — Repo reality
| Repo | Status |
|---|---|
| gddp-config | Fully documented. Phase-frozen. Human-owned truth. |
| gddp-runtime | Fully documented. Phase-frozen at receipt + human review. |
| MyAPI | Documented in `project-docs/`. Context Refinery scaffold present. Ingestion pipeline TBD. |
| opclaw | Archived. Do not treat as canonical. |

### Workstream B — VM bootstrap
| VM | Status |
|---|---|
| first-vm | Ready. Repos cloned, runtime deps present, heartbeat invocable. |
| khoj-headless-engine | Ready. Khoj service healthy, health endpoint 200. |

### Workstream C — Next actions

| Priority | Action | Machine | Repo | Dependency | Success condition |
|---|---|---|---|---|---|
| 1 | Define canonical document schema | khoj-headless-engine or Mac | MyAPI | None | `CanonicalDocument` type + validation layer committed |
| 2 | Implement ingestion pipeline (source adapters: Obsidian, ChatGPT, Claude) | khoj-headless-engine | MyAPI | Schema spec done | First real document normalized and exported |
| 3 | Determine next GDDP graph node | BigPi | gddp-config | return-router complete | New node added to project graph with status `ready` |
| 4 | First real heartbeat dispatch | first-vm | gddp-runtime | Ready node exists | Job created, Jules issue opened, receipt written to SQLite |
| 5 | Wire context-refinery UI to live pipeline | khoj-headless-engine | MyAPI | Pipeline working | ImportView → real ingest, ExportView → real Khoj-ready output |

### What openclaw should not assume
- context-refinery is scaffold only — no live ingestion yet
- BigPi CLI loopback bug is unresolved — use UI for operator actions
- No tmux sessions confirmed running on BigPi
- Verify `systemctl status khoj` before acting on Khoj VM state — last confirmed 2026-04-09

---

## 7. Key Identifiers

| Item | Value |
|---|---|
| GCP project | `gen-lang-client-0824562549` |
| GCP region (first-vm) | `us-west2-c` |
| GCP region (khoj) | `us-central1-a` |
| Tailscale hostname | `ssd-big.tail02ac6f.ts.net` |
| ssd-small device ID | `0b43c62a448bded3dff2c64d9fc643e87763ac65089a5454fbdc15b0f57c71eb` |
| Gateway token location | `ssd-big:~/.openclaw/openclaw.json` → `gateway.token` |
| GitHub org | `skchaudr` |
| gddp-config remote | `git@github.com:skchaudr/gddp-config.git` |
| gddp-runtime remote | `git@github.com:skchaudr/gddp-runtime.git` |
| MyAPI remote | `git@github.com:skchaudr/MyAPI.git` |
