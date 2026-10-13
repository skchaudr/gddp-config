# GDAD vertical slice — proposal (round 1)

## 1. Node contract

A GDAD node is a directory next to v1 graph truth:

`graphs/<project>/gdad/<node-id>/BRIEF.md`
`graphs/<project>/gdad/<node-id>/status`
`graphs/<project>/gdad/<node-id>/journal.jsonl`
`graphs/<project>/gdad/<node-id>/workflow.js`
`graphs/<project>/gdad/<node-id>/artifacts/`

`graphs/<project>/nodes/<node-id>.yaml` stays the v1 node. GraphReader and `gddp node validate` open that file. A directory at that path would break the graph.

**BRIEF.md** headings, in order: `Goal`, `Scope`, `Acceptance`, `Constraints`, `Sab's words`. `Sab's words` is verbatim. One `cat` shows the whole contract.

**status** is four lines, overwritten in place. The journal is the history.

```
state: running
who: gdad-executor
when: 2026-10-13T09:30:00Z
run_id: line-pair-1
```

`state` is `pending | running | paused | review | accepted | rejected | blocked`.

| from | to | who |
| --- | --- | --- |
| pending | running | gdad-executor, on dispatch |
| pending | blocked | gdad-executor, when a dependency gate is missing |
| running | paused | sab, or pi-workflow when `checkpoint` parks |
| paused | running | sab, on resume |
| running | review | gdad-executor, when `claude -p` starts |
| review | accepted | claude-opus, verdict `accept` |
| review | rejected | claude-opus, verdict `reject` |
| running, paused, review | blocked | gdad-executor, when pi will not start or BRIEF.md is missing |
| blocked | pending | sab |

`accepted` and `rejected` are terminal.

**journal.jsonl** is append-only. Every line is one JSON object: `v` (1), `ts` (ISO-8601 UTC), `type`, `who`, `state`, `run_id`, `artifacts` (array). `note` is optional. `type` is `dispatch | review | steer | pause | resume | verdict | gate`.

```json
{"v":1,"ts":"2026-10-13T09:30:00Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-1","artifacts":["graphs/gdad-demo/gdad/line-pair/BRIEF.md"]}
{"v":1,"ts":"2026-10-13T09:31:00Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-1","artifacts":["graphs/gdad-demo/gdad/line-pair/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T09:31:10Z","type":"steer","who":"sab","state":"running","run_id":"line-pair-1","artifacts":[],"note":"keep each worker to one line"}
{"v":1,"ts":"2026-10-13T09:32:00Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-1","artifacts":[],"note":"checkpoint after-workers"}
{"v":1,"ts":"2026-10-13T09:33:00Z","type":"resume","who":"sab","state":"running","run_id":"line-pair-1","artifacts":[]}
{"v":1,"ts":"2026-10-13T09:34:00Z","type":"verdict","who":"claude-opus","state":"accepted","run_id":"line-pair-1","artifacts":["graphs/gdad-demo/gdad/line-pair/artifacts/verdict.json"],"note":"accept"}
{"v":1,"ts":"2026-10-13T09:34:01Z","type":"gate","who":"gdad-executor","state":"accepted","run_id":"line-pair-1","artifacts":[".gddp/gates/line-pair.token"]}
```

Schema files to add when building: `schemas/gdad/node.md` (this contract) and `schemas/gdad/journal.schema.json`.

**v1 map.** `schemas/v1/node.yaml` status is `pending | ready | provisional | complete | deferred`. Execution state lives on the job. GDAD's seven states go in the `status` file. The executor does not write node YAML. `schemas/v1/event.yaml` is a GitHub webhook record. The journal is a new file. `schemas/v1/job.yaml` stays the heartbeat's work packet. This slice does not create a job.

**Gates.** `gddp-runtime/scripts/runtime/gate_tokens.py` `write_gate` atomically writes `.gddp/gates/<node-id>.token` with `node_id`, `issued_at`, and `verdict_receipt_sha256` of the receipt file. `read_gate` / `gate_satisfied` check it. Today `provisional_status.py` calls `write_gate` when it marks a node provisional, and `frontier.py` rewrites a missing token. `scripts/node_cli.py` calls `revoke_gate` when a human moves a node off `provisional` to anything other than `complete`. `gddp.py` does not write tokens. On GDAD `accepted`, the slice calls `write_gate(repo, node_id, verdict_path)` and leaves node YAML alone.

## 2. Workflow package

**pi-extensible-workflows@6.2.0.**

`parallel(name, { a: () => agent(...), b: () => agent(...) })` in `src/execution.ts` fans out and waits. The same package ships `subagents_run / inspect / steer / stop / retry`. `@osolmaz/pi-workflows@0.17.7` exports `agent`, `shell`, `checkpoint`, and `compute`. Its engine has no parallel fan-out.

Pause is `checkpoint({ name, prompt })`, journaled. Host action `pause` calls `lifecycle.pause()`. Resume replays by structural path plus occurrence, so finished `parallel` and `agent` calls stay done. osolmaz `/workflow pause` into `~/.pi/agent/workflows/state.sqlite` is a clean park, and it also has `shell()`. Its Herdr plugin (`plugins/herdr/viewer.mjs`) starts `piw`. `piw` is not on this VM. extensible `src/herdr.ts` `openHerdrPane` uses the `herdr` CLI, which is installed.

`shell(command)` is the review step: `claude -p --model opus` reads BRIEF.md plus `artifacts/`, prints `{"verdict":"accept"|"reject","reasons":[...]}` to stdout, and the script returns that JSON. Headless checkpoints throw `RESUME_INCOMPATIBLE`, so the slice runs a pi TUI in the Herdr pane.

**Launch until Task 3.** Both packages register a tool named `workflow` (`src/host.ts`, `@osolmaz/pi-workflows/src/extension/index.ts`). Settings load both. The slice runs:

`pi -ne -e ~/.pi/agent/npm/node_modules/pi-extensible-workflows/dist/src/index.js -e ~/.pi/agent/npm/node_modules/pi-extensible-workflows/dist/subagents/index.js`

Verified 2026-10-13: that command with `--offline --no-session --mode rpc` accepted `{"type":"get_state"}` and returned a session id. On this VM, plain `pi --mode rpc` also starts, because `~/.pi/agent/bin/piewf-rename-patch.mjs` has rewritten the installed dist tool to `piewf_workflow` and the slash command to `/piewf`. The slice does not depend on that patch. The launch prompt calls the tool name actually registered in the loaded dist.

## 3. Executor path

`gddp gdad watch gdad-demo line-pair` reads BRIEF.md, sets `status` to `running`, appends `dispatch`, and splits a Herdr pane running the pi command above with an initial message: call the workflow tool, `scriptPath` = `workflow.js`, `name` = `line-pair`, `foreground` = true.

`workflow.js`: `parallel("workers", …)` writes `artifacts/hello.txt` (one line per worker); `checkpoint({ name: "after-workers" })` parks (status `paused`, journal `pause`); resume appends `resume` and continues; `shell` runs `claude -p --model opus`; the wrapper sets `review` then `accepted` or `rejected`, appends `review` and `verdict`. On accept it writes `artifacts/verdict.json` and calls `write_gate` with that path, then appends `gate`. Steer appends a `steer` line Sab typed into the watch command; the wrapper forwards it with `subagents_steer` while workers run.

## 4. Observability

The Herdr pane is the pi TUI, so the workflow widget is live. `gddp timeline` reads git, `node_status_history`, `queue.db`, attempt `events.jsonl`, and receipts. `gddp watch` reads attempt `events.jsonl` (`session_started`, `tool_started`, …). This run has a GDAD journal, so those commands stay as they are. `gddp gdad watch <project> <node>` follows `journal.jsonl`. `timeline.py` gains one reader so `gddp timeline gdad-demo --node line-pair` prints the same lines.

## 5. Files

**gddp-config:** `schemas/gdad/node.md`, `schemas/gdad/journal.schema.json`, `graphs/gdad-demo/project.yaml`, `graphs/gdad-demo/nodes/line-pair.yaml` (v1, `status: pending`), `graphs/gdad-demo/gdad/line-pair/{BRIEF.md,workflow.js}`, `scripts/cli_gdad.py`, `scripts/gddp.py` (`gdad` in `_CLI_COMMANDS` and argparse only), `scripts/timeline.py` (journal reader).

**gddp-runtime:** `scripts/runtime/gdad_run.py` (pane, status, journal, `write_gate`).

**Unchanged:** `runner.py`, `reconciler.py`, `pi_rpc_adapter.py`, `provisional_status.py`, `frontier.py`, `gate_tokens.py`, `node_cli.py`, and `gddp` jobs / evaluations / receipt / watch.

**In the way:** `pi_rpc_adapter.py` spawns `pi --mode rpc` under settings discovery, with a built-in `subagent` preamble. That is the wrong transport for this slice. `runner.py`, `reconciler.py`, and `provisional_status.py` write node YAML to `provisional` and issue the gate on an evaluator pass, before accept. This slice does not enter that loop.

## 6. Demo

Node `line-pair` in project `gdad-demo`. Goal: two workers, two lines in `artifacts/hello.txt`. Acceptance: the file exists and has exactly two non-empty lines. Constraints: no other files, no graph YAML edits. `Sab's words` is that goal sentence.

Sab runs:

```
gddp gdad watch gdad-demo line-pair
```

## Review 1 (Opus steward, 2026-10-13): REVISE, then build after round 2 if these are closed

This is solid on the good choices: gate reuse through `gate_tokens.write_gate` with the verdict receipt, keeping v1 node YAML untouched, an honest "in the way" list, and pi-extensible-workflows for `parallel` plus checkpoint-replay. Keep all of those. Close the gaps below in the proposal (keep it to 2 pages), then stop again.

1. **One writer for status and journal.** `workflow.js` runs inside pi (JS), while the executor is `gdad_run.py` (Python) in another process. As written, nobody owns the `pause` line when `checkpoint` parks inside pi. Specify one helper, for example `python3 -m gdad_run journal <node> <type> [--note] [--artifact]`, that appends the journal line and rewrites `status` atomically in the same call (flock). Every writer uses it: the executor, `workflow.js` via `shell(...)` before and after `checkpoint`, the reviewer step, and Sab's commands. Derive `status` from the last journal line so the two can never disagree.
2. **Rejected is not terminal. Review-and-redispatch is the point of GDAD** (Sab: "review or evaluation pipeline"; the steward "re-dispatches grok to dial in its proposal"). Add `rejected -> pending` (who: sab or reviewer) with a `redispatch` journal type that carries the review findings, and a new `run_id`. The next dispatch must feed the previous verdict's `reasons` into the workers' prompt. Only `accepted` is terminal.
3. **Split dispatch from watch.** `watch` must be read-only, safe to run any number of times, and re-attachable. Add `gddp gdad run <project> <node>`, which dispatches, opens the herdr pane and then follows the journal (this is the one command Sab runs), plus `gddp gdad watch` (tail only), `gddp gdad pause`, `gddp gdad resume`, `gddp gdad steer "<text>"` and `gddp gdad show` (cat BRIEF + status + journal). Say concretely how pause, resume and steer reach the running pi: for example `herdr agent prompt <pane>` to call the workflow tool's pause/resume host action, or `subagents_steer`. Name the exact tool and action names from the 6.2.0 dist.
4. **Durable resume across a dead pane.** Runs are keyed to the pi session (`session-lease.js`, `listRunIds(cwd, sessionId)`), so resuming needs the same pi session. Record `pi_session_id` and the workflow `runId` in the journal `dispatch` line. `gddp gdad resume` must work after the pane or pi process is gone, by relaunching pi on that session and resuming the run by id. Show that in the demo: pause, kill the pane, resume, and the finished `parallel` workers are not rerun.
5. **Reviewer contract.** `claude -p --model opus --output-format json` with a fixed prompt file (`schemas/gdad/review-prompt.md`) that gets BRIEF.md (especially Acceptance) plus an artifact listing. Parse strictly. Unparseable output or a non-zero exit means `blocked` with the raw output saved as an artifact, never `accepted`. The reviewer writes `artifacts/verdict.json` itself, including `reasons`. The gate is issued only from that file's sha.
6. **Where state lives.** The definition (`BRIEF.md`, `workflow.js`) belongs in gddp-config. Runtime state (`status`, `journal.jsonl`, `artifacts/`, per-run dirs) should live in gddp-runtime, next to `jobs/`, so running nodes don't churn the config repo's git. Either do that, or justify keeping it in config with a stated git policy. `gddp gdad show` must still print everything in one call.
7. **Demo acceptance must be mechanical, so the reviewer can actually reject.** Keep `line-pair`, but in round 2 also say how you'll exercise one reject → redispatch → accept (for example, round 1 workers are told to write three lines). That proves the GDAD loop, not just the happy path.
8. **Smaller points.**
   - Verify `claude -p --model opus` runs non-interactively on this VM (auth) and say so.
   - Say what happens to `herdr` pane focus: open the pane in a new tab, never steal Sab's focused pane.
   - Pin the extension paths via one config value instead of hard-coding them, because Task 3 will change the conflict fix.

Round 2: update the proposal, keep the review sections in place, commit with the cursor-agent trailer, push, and stop.
