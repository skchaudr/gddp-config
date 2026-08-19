# MyAPI Part 2 — node authorship under a strict orchestrator (WORKING DRAFT v0)

Status: draft for Sab + ChatGPT to dial in. Verified against live state 2026-08-19.

## Verified snapshot

Graph `graphs/myapi-part2/` (18 nodes), as of 2026-08-19:

| Nodes | Graph status | Last eval verdict |
|---|---|---|
| 01 evidence-contract, 01b contract-review | provisional | pass |
| 04 inventory-decisions | provisional | pass |
| 02 chat-path-scorer, 03 validate-anchor, 06 git-evidence, 07 graphify-evidence | ready | **fail** |
| 05 inventory-handoffs | ready | needs-human-review (checker timed out 1200s) |
| 08–18 | pending | never dispatched |

Runtime facts on record (handoff 098): 22 orchestrator spawns, 12 SIGTERMed
pre-agent_end; reconciler resurrection bug fixed (`dc136dd`); retry budget is
0/3 spent on the current awaiting_review jobs.

**Control baseline (Part 1 node 11, now local):** Khoj runs on the mini
(`localhost:42110`, homebrew py3.12, local postgres), chat path wired via
OpenRouter `google/gemini-2.5-flash`. Raw capture: MyAPI
`codex/myapi-decision-plan@4267673` `04-evaluation/results/raw-api-responses.json`.
Signal: q1/q2 correct + cited; q3 hedged-abstain (no supersession fact in set);
q4 traced D18↔D17 companion; q5 clean abstain. This is the ruler's anchor
point for node-11-part1-control.

## Executor landscape (post-Codex)

- **Orchestrator** (gddp-runtime `33a2a19`): read-only Pi, observe→dispatch→
  monitor→report, boundary steering only, no steer channel, report-don't-cancel.
- **Executor**: pi_rpc process gets "You are the EXECUTOR" preamble; one git
  worktree per session, not per attempt (handoff 101).
- **Available models**: gemini-3.1-pro, gemini-3.6-flash (abundant),
  deepseek-v4-pro, deepseek-v4-flash (abundant), grok-4.6, glm-5.2 (some),
  qwen (some). Codex lane out.

## Authorship principles (proposed)

The orchestrator cannot rescue a bad node mid-flight. Everything the
attempt needs must live in the node YAML at dispatch time:

1. **Decomposition hint, not decomposition.** Node carries a suggested
   worker split + model assignments (cheap fanout = gemini-3.6-flash /
   deepseek-v4-flash; reasoning = deepseek-v4-pro / gemini-3.1-pro; workers
   = grok-4.6). Executor may deviate but must record why.
2. **Evidence paths are acceptance criteria.** Every criterion names the exact
   file it is satisfied by (`part2/probe/scorer-mechanics.md` style). Evaluator
   checks file existence + content contract, not vibes. Node-05's checker
   timeout says: also cap the evidence surface the checker must read.
3. **Failure-input field.** Nodes that retry carry the prior attempt's
   evaluator fix-list as structured dispatch context — this is the only legal
   steering channel now (boundary steering).
4. **One measurable output per node.** If a node can pass without producing a
   diff/artifact another node consumes, it is a disguised meeting.
5. **Infra vs hypothesis failure separation.** Node defines which acceptance
   failures are infra-class (retry automatic) vs evidence-class (needs fix-list).

## Per-node disposition (open questions for Sab + ChatGPT)

| Node | Question |
|---|---|
| 02 | Chat path now works locally — does the node shrink to scorer-mechanics only? |
| 03 | What exactly did validate-anchor fail on? (pull receipt before re-spec) |
| 05 | Checker timed out — evidence surface too big, or checker prompt too slow? |
| 06/07 | Both evidence-layer nodes failed twice; are they over-scoped for one attempt? |
| all | Do 02–07 merge into fewer nodes now that worktree is per-session (setup cost dropped)? |
