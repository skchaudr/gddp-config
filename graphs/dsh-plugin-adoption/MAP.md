# dsh Plugin Adoption — graph map

Charted 2026-08-23 from Sab's plugin list. Arc: **vet → protocol → isolate → install+smoke → dsh-pi → human rollout → runbook**.

```text
01 repo-vetting ── 02 threat-model-protocol ── 03 isolated-test-profile
                                                     │
                                      ┌──────────────┴──────────────┐
                                      ▼                             ▼
                              04 install-and-smoke          05 dsh-pi-bridge
                                      └──────────────┬──────────────┘
                                                     ▼
                                             06 rollout-decision (human)
                                                     │
                                             07 adoption-runbook
```

## Node list

| # | node_id | title | status |
|---|---|---|---|
| 01 | repo-vetting | Vet all 8 candidate repos from source/web | planned |
| 02 | threat-model-protocol | Supply-chain threat model + safe-install protocol | planned |
| 03 | isolated-test-profile | Empty macOS user profile on sab-air (no creds, disposable) | planned |
| 04 | install-and-smoke | Preflight-scan install + smoke-test each vetted plugin | planned |
| 05 | dsh-pi-bridge | Deep-dive dsh-pi: vet, implement, test in isolation | planned |
| 06 | rollout-decision | Human: per-plugin promote-to-real / keep-isolated / reject | planned |
| 07 | adoption-runbook | Safe future plugin adoption runbook | planned |

## Conventions

- NOTHING from this graph touches the live ~/.dsh on sab-air until node 06 (human decision). Isolated profile only.
- Executors: grok-4.6 / GLM 5.2 route; GLM-77%-off reviewer. Human acceptance only.
- dsh-pi findings feed back to daily-driver node 04 (split decision).
- Vetting evidence comes from researcher run 09f4bea7.
