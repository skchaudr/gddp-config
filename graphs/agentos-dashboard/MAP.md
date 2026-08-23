# AgentOS Dashboard — graph map

Charted 2026-08-23 from Sab's plan (research/agentos-plan.md, sourced from
sab-air vault). Arc: **contract → schema+watcher ∥ shell+components ∥ API →
live integration → dogfood → rollout**.

```text
01 scope-contract
   ├── 02 data-topology-schema ── 03 workspace-watcher
   └── 04 frontend-shell ─┬─ 05 artifact-orbit ┐
                          ├─ 06 radial-dag     ├─ 10 live-integration
                          ├─ 07 skills-deck ─┬─┘      │
                          └─ 08 routines-board┘       │
                           07/08 ── 09 backend-api ───┘
                                                      ▼
                                            11 dogfood-dashboard
                                                      ▼
                                            12 rollout-plan
```

## Node list

| # | node_id | title | status |
|---|---|---|---|
| 01 | scope-contract | Freeze plan scope, data sources, repo, build posture | planned |
| 02 | data-topology-schema | ARMS DAG schema: root/hubs/leaves, frontmatter contract, graph.json | planned |
| 03 | workspace-watcher | Daemon parses router md + frontmatter → graph.json | planned |
| 04 | frontend-shell | React+Vite+Tailwind shell, theme, layout, routing | planned |
| 05 | artifact-orbit | Mode A: orbit ring, search/highlight, HUD card | planned |
| 06 | radial-dag | Mode B: concentric DAG, 4 layouts, physics sliders | planned |
| 07 | skills-deck | Floating launchpad: skill pads, model + effort selectors | planned |
| 08 | routines-board | Firing board: next/queued/fired, local vs cloud, sync | planned |
| 09 | backend-api | /api/skills/run + SSE/WebSocket live logs | planned |
| 10 | live-integration | Swap mock data for real graph.json + real runs | planned |
| 11 | dogfood-dashboard | Run against Sab's real environment; polish pass | planned |
| 12 | rollout-plan | Step-by-step debugging + iteration rollout doc | planned |

## Conventions

- Plan is inspiration ("expect the rest to be learned while building") —
  each node is one bounded deliverable with evidence; learning happens inside
  nodes, not in the chart.
- Data sources (vaults, artifact dirs, routines) are settled in node 01 by
  Sab/human, not assumed by executors.
- Executors: pi subagents. Only human acceptance releases nodes.
- Theme and interaction details pinned in the plan (research/agentos-plan.md).
