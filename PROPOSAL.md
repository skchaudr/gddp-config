# GDAD vertical slice — proposal (round 2)

## 1. Contract and where files live

Definition stays in gddp-config, and git tracks it: `graphs/<project>/gdad/<node-id>/BRIEF.md` and `workflow.js`. BRIEF.md headings, in order: `Goal`, `Scope`, `Acceptance`, `Constraints`, `Sab's words` (verbatim).

Runtime state lives in gddp-runtime beside `jobs/`, gitignored like `jobs/*`:

`gdad/<project>/<node-id>/status`
`gdad/<project>/<node-id>/journal.jsonl`
`gdad/<project>/<node-id>/runs/<run_id>/artifacts/`

`gddp gdad show <project> <node>` prints BRIEF.md, `status`, the journal, and the current run's artifact paths in one call. `graphs/<project>/nodes/<node-id>.yaml` stays the v1 node (`pending|ready|provisional|complete|deferred`). The executor never writes it. `schemas/v1/event.yaml` stays the webhook record. This slice creates no job.

## 2. One writer

Every change goes through `python3 -m gdad_run journal <project> <node> <type> [--note] [--artifact]` (`gddp-runtime/scripts/gdad_run.py`). One flock covers the append and the status rewrite. `status` is the last journal line, rendered as four fields (`state`, `who`, `when`, `run_id`) plus `pi_session_id` and `workflow_run_id` copied from the open dispatch. Callers do not pass `state`. The helper rejects an illegal type and writes nothing.

`state`: `pending|running|paused|review|accepted|rejected|blocked`. Only `accepted` is terminal.

| type | who | resulting state |
| --- | --- | --- |
| dispatch | gdad-executor | running |
| pause | pi-workflow | paused |
| resume | sab | running |
| review | gdad-executor | review |
| steer | sab | unchanged |
| verdict | claude-opus | accepted or rejected |
| redispatch | sab or claude-opus | pending, new `run_id`, `note` holds the prior `reasons` |
| gate | gdad-executor | accepted |
| blocked | gdad-executor | blocked |

A missing dependency gate journals `blocked`. `gddp gdad run` from `blocked` journals `dispatch` only after that preflight passes.

Each line: `v` (1), `ts`, `type`, `who`, `state`, `run_id`, `artifacts`. Dispatch also stores `pi_session_id` and `workflow_run_id`. `note` is optional.

```json
{"v":1,"ts":"2026-10-13T09:30:00Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-1","pi_session_id":"01a1","workflow_run_id":"wf-1","artifacts":["graphs/gdad-demo/gdad/line-pair/BRIEF.md"]}
{"v":1,"ts":"2026-10-13T09:31:00Z","type":"steer","who":"sab","state":"running","run_id":"line-pair-1","artifacts":[],"note":"keep each worker to one line"}
{"v":1,"ts":"2026-10-13T09:32:00Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-1","artifacts":[],"note":"checkpoint after-workers"}
{"v":1,"ts":"2026-10-13T09:33:00Z","type":"resume","who":"sab","state":"running","run_id":"line-pair-1","artifacts":[]}
{"v":1,"ts":"2026-10-13T09:33:30Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-1","artifacts":["gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T09:34:00Z","type":"verdict","who":"claude-opus","state":"rejected","run_id":"line-pair-1","artifacts":["gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json"],"note":"three lines"}
{"v":1,"ts":"2026-10-13T09:35:00Z","type":"redispatch","who":"sab","state":"pending","run_id":"line-pair-2","artifacts":["gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json"],"note":"Acceptance is exactly two non-empty lines"}
{"v":1,"ts":"2026-10-13T09:40:00Z","type":"gate","who":"gdad-executor","state":"accepted","run_id":"line-pair-2","artifacts":[".gddp/gates/line-pair.token"]}
```

Schema when building: `schemas/gdad/node.md`, `schemas/gdad/journal.schema.json`.

## 3. Package, launch, pause, resume, steer

**pi-extensible-workflows@6.2.0.** `parallel()` fans out and the package ships `subagents_steer`. `@osolmaz/pi-workflows@0.17.7` has no parallel fan-out, and its Herdr viewer needs `piw`, which is not installed. `shell()` runs the reviewer. Headless `checkpoint` throws `RESUME_INCOMPATIBLE`, so the slice uses a pi TUI.

Extension paths are one setting, `GDAD_PI_EXTENSIONS` in `gddp-config/runtime/settings.env` (comma-separated). The default is the 6.2.0 `dist/src/index.js` and `dist/subagents/index.js`. Task 3 changes that value.

Launch: `pi -ne` plus one `-e` per path, `--session-id <pi_session_id>` chosen by the executor before start. Verified 2026-10-13: that `-ne -e` form with `--mode rpc` accepted `get_state`. On this VM plain `pi --mode rpc` also starts because `piewf-rename-patch.mjs` renamed the installed tool to `piewf_workflow` and the slash command to `/piewf`. The slice reads the tool name from the loaded dist and does not depend on the patch. Stock source still registers `workflow` in both packages.

`workflow.js` calls the journal helper via `shell` before and after `checkpoint({name:"after-workers"})`. While the process is alive, `gddp gdad resume` runs `herdr agent prompt <pane>` telling pi to call dist tool `workflow_respond` with `{runId, name:"after-workers", approved:true}`. Dist tool `workflow_resume` is only for `budget_exhausted`; this slice does not use it for pause. A live mid-run park uses trajectory action `pause` (`lifecycle.pause()`) and action `resume` (`lifecycle.resume()` when state is `paused`), reached the same way: `herdr agent prompt`. `gddp gdad steer "<text>"` journals `steer`, then `herdr agent prompt` to call `subagents_steer` with `{id, message}`.

If the pane is dead, `gddp gdad resume` reads `pi_session_id` and `workflow_run_id` from the journal, opens a new unfocused tab, and relaunches `pi --session-id <pi_session_id>` with the same cwd. Runs for that pair are `listRunIds(cwd, sessionId)` in the dist. The new prompt cold-resumes that `workflow_run_id` and, if the checkpoint is still pending, calls `workflow_respond`. Finished `parallel` calls stay done.

## 4. Reviewer and gate

Prompt file: `schemas/gdad/review-prompt.md`. It includes BRIEF.md, with Acceptance called out, plus the artifact listing. The step is `claude -p --model opus --output-format json`. Verified 2026-10-13 on this VM: exit 0, envelope `type=result`, `is_error=false`, model `claude-opus-5-5`. The prompt tells the reviewer to write `runs/<run_id>/artifacts/verdict.json` (`verdict`: `accept|reject`, `reasons`: non-empty string array) and to print that same object. The wrapper accepts only when the process exits 0, the envelope parses, and the file matches the object. Anything else journals `blocked` and saves the raw stdout as an artifact. `accepted` is never that path.

On `accept`, `gate` calls `gate_tokens.write_gate(repo, node_id, verdict.json)`. The token's `verdict_receipt_sha256` is that file. `provisional_status.py` and `frontier.py` call `write_gate` when they mark a node provisional; this slice does not enter that loop. `node_cli.py` still `revoke_gate`s when a human leaves `provisional` for anything other than `complete`.

On `reject`, the next `gddp gdad run` journals `redispatch` with a new `run_id` and puts `reasons` into `runs/<new>/prompt.txt`. `workflow.js` feeds that file to both `agent()` calls.

## 5. Commands, Herdr, files

Sab's command is `gddp gdad run <project> <node>`. It dispatches, opens the pane, then follows the journal. `gddp gdad watch` only tails the journal: read-only, repeatable, re-attachable. Also `pause`, `resume`, `steer "<text>"`, and `show`.

The pane is `herdr tab create --cwd <runtime node dir> --label gdad-<node> --no-focus`, then `herdr pane run` of pi in that tab's root pane. No `herdr tab focus`, `herdr pane focus`, or `herdr agent focus`.

**gddp-config:** `schemas/gdad/node.md`, `journal.schema.json`, `review-prompt.md`, `runtime/settings.env` (`GDAD_PI_EXTENSIONS`), `graphs/gdad-demo/project.yaml`, `graphs/gdad-demo/nodes/line-pair.yaml` (`status: pending`), `graphs/gdad-demo/gdad/line-pair/{BRIEF.md,workflow.js}`, `scripts/cli_gdad.py`, `scripts/gddp.py` (`gdad` in `_CLI_COMMANDS` only), `scripts/timeline.py` (reads the runtime journal).

**gddp-runtime:** `scripts/gdad_run.py`, `.gitignore` line `gdad/*`.

**Unchanged:** `runner.py`, `reconciler.py`, `pi_rpc_adapter.py`, `provisional_status.py`, `frontier.py`, `gate_tokens.py`, `node_cli.py`, jobs / evaluations / receipt / watch.

**In the way:** `pi_rpc_adapter.py` spawns `pi --mode rpc` under settings discovery. `runner.py`, `reconciler.py`, and `provisional_status.py` write node YAML to `provisional` and issue the gate before accept.

## 6. Demo

Node `line-pair`, project `gdad-demo`. Acceptance: `hello.txt` has exactly two non-empty lines. Constraints: no other files, no graph YAML edits. First `prompt.txt` tells the workers to write three lines, so the reviewer rejects. `gddp gdad run` again redispatches with those `reasons`, the workers write two lines, the reviewer accepts, and the gate is issued.

Demo of durable resume: `run` until `pause` at `after-workers`, kill the pane, `gddp gdad resume gdad-demo line-pair`. The journal shows `pause` then `resume`, and the finished `parallel` workers do not run again.

```
gddp gdad run gdad-demo line-pair
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
