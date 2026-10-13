# GDAD vertical slice — proposal (round 3)

The journal and status from round 2 stay the plumbing. The product is the decision packet. The main agent (Fable, or `grok claude`) sees only packets and writes only a reply.

## 1. Contract and where files live

Definition in gddp-config: `graphs/<project>/gdad/<node-id>/BRIEF.md` (`Goal`, `Scope`, `Acceptance`, `Constraints`, `Sab's words` verbatim) and `workflow.js`. Runtime state, gitignored like `jobs/*`, in gddp-runtime: `gdad/<project>/<node-id>/{status,journal.jsonl,runs/<run_id>/artifacts/,packets/}`. `gddp gdad show` prints BRIEF, status, the journal with packets and decisions inline, and artifact paths. v1 `nodes/<node-id>.yaml` stays `pending|ready|provisional|complete|deferred`. The executor never writes it. This slice creates no job.

## 2. One writer

Every change is `python3 -m gdad_run journal <project> <node> <type> [--note] [--artifact]` (`gddp-runtime/scripts/gdad_run.py`). One flock appends the line and rewrites `status` from that line (`state`, `who`, `when`, `run_id`, plus `pi_session_id` and `workflow_run_id` from the open dispatch). Callers do not pass `state`. An illegal type writes nothing.

States: `pending|running|paused|review|awaiting-decision|accepted|rejected|blocked`. Only `accepted` is terminal. `awaiting-decision` sits between running work and resolution, and is entered only by `packet`.

| type | who | resulting state |
| --- | --- | --- |
| dispatch | gdad-executor | running |
| pause | pi-workflow | paused |
| packet | pi-workflow | awaiting-decision |
| decision | fable | running on `resume`; pending plus a new `run_id` on `redispatch`; accepted on `next` when the verdict was accept |
| review | gdad-executor | review |
| verdict | claude-opus | review (the raw verdict; it does not redispatch) |
| steer | sab | unchanged |
| gate | gdad-executor | accepted |
| blocked | gdad-executor | blocked |

Round 2's automatic `rejected → redispatch` is gone. A reject stays in `awaiting-decision` until Fable's `decision`. `next` on a reject sets `rejected` and writes no gate. `dispatch` is its own line when the next run starts, including after that `redispatch`. A missing dependency gate journals `blocked`. Leaving `blocked` takes an explicit `gddp gdad run` after preflight. No automatic retry.

Line shape is unchanged (`v`, `ts`, `type`, `who`, `state`, `run_id`, `artifacts`, optional `note`). Dispatch still stores `pi_session_id` and `workflow_run_id`. `packet` and `decision` lines name the packet id in `note`.

```json
{"v":1,"ts":"2026-10-13T09:34:02Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["gdad/gdad-demo/line-pair/packets/pkt-1.md"],"note":"pkt-1 verdict"}
{"v":1,"ts":"2026-10-13T09:35:00Z","type":"decision","who":"fable","state":"pending","run_id":"line-pair-2","artifacts":["gdad/gdad-demo/line-pair/packets/pkt-1.json"],"note":"redispatch: exactly two lines"}
{"v":1,"ts":"2026-10-13T09:40:00Z","type":"gate","who":"gdad-executor","state":"accepted","run_id":"line-pair-2","artifacts":[".gddp/gates/line-pair.token"]}
```

Schemas: `schemas/gdad/node.md`, `journal.schema.json`, `reply.schema.json`.

## 3. Package, launch, pause, resume, steer

**pi-extensible-workflows@6.2.0.** `parallel()` fans out. On pi 0.87.1, `agent()` fails with `createCodemodeExtension is not a function`, so each worker is `parallel()` of `shell("pi -ne --no-session -p")` via `worker.sh`. The package still ships `subagents_steer`. `@osolmaz/pi-workflows@0.17.7` has no parallel fan-out, and its Herdr viewer needs `piw`, which is not installed. Headless `checkpoint` throws `RESUME_INCOMPATIBLE`, so the slice uses a pi TUI. bb is not the host (section 7).

`GDAD_PI_EXTENSIONS` in `gddp-config/runtime/settings.env` is the only extension-path setting. Launch is `pi -ne` plus one `-e` per path, `--session-id` chosen before start. Verified 2026-10-13: that form with `--mode rpc` accepted `get_state`. This VM's `piewf-rename-patch.mjs` renames the installed tool to `piewf_workflow`; the slice reads the name from the loaded dist and does not depend on the patch.

`workflow.js` journals `pause`, writes the ambiguity packet, then `checkpoint({name:"after-workers"})`. A live `resume` reply is `herdr agent prompt <pane>` calling dist tool `workflow_respond` with `{runId, name:"after-workers", approved:true}`. Dist `workflow_resume` is only for `budget_exhausted`. A live mid-run park uses trajectory actions `pause` and `resume` the same way. `steer` journals, then `herdr agent prompt` calls `subagents_steer` with `{id, message}`. A dead pane relaunches `pi --session-id` for that `listRunIds(cwd, sessionId)` run and then `workflow_respond`. Finished `parallel` calls stay done.

## 4. Reviewer and gate

`schemas/gdad/review-prompt.md` plus BRIEF Acceptance and the artifact listing go to `claude -p --model opus --output-format json`. Verified 2026-10-13: exit 0, `type=result`, `is_error=false`, model `claude-opus-5-5`. The reviewer writes `verdict.json` (`verdict`, non-empty `reasons`) and prints that object. The wrapper accepts only exit 0, a parseable envelope, and a file that matches. Otherwise it journals `blocked` and saves the raw stdout. That path never accepts and never writes a gate.

`verdict.json` is packet `evidence`. It does not move the node to `accepted` and it does not redispatch. The gate is `gate_tokens.write_gate(repo, node_id, verdict.json)`, so `verdict_receipt_sha256` is that file, and it is written only after a `next` reply, or a `resume` past the final acceptance checkpoint, and only when the verdict was accept. `provisional_status.py` and `frontier.py` also call `write_gate`, on provisional promotion. This slice does not enter that loop. `node_cli.py` still revokes a gate when a human leaves `provisional` for anything other than `complete`.

## 5. Commands, Herdr, files

Sab's command is `gddp gdad run <project> <node>`: dispatch, unfocused pane, follow the journal. `watch` only tails. Also `pause`, `steer`, `show`, `inbox [--json]`, and `decide` (section 7). The pane is `herdr tab create --cwd <runtime node dir> --label gdad-<node> --no-focus`, then `herdr pane run`. No focus command.

**gddp-config:** `schemas/gdad/{node.md,journal.schema.json,reply.schema.json,review-prompt.md}`, `runtime/settings.env`, `graphs/gdad-demo/project.yaml`, `graphs/gdad-demo/nodes/line-pair.yaml` (`status: pending`), `graphs/gdad-demo/gdad/line-pair/{BRIEF.md,workflow.js}`, `scripts/cli_gdad.py`, `scripts/gddp.py` (`gdad` in `_CLI_COMMANDS` only), `scripts/timeline.py` (reads the runtime journal).

**gddp-runtime:** `scripts/gdad_run.py`, `.gitignore` line `gdad/*`.

**Unchanged:** `runner.py`, `reconciler.py`, `pi_rpc_adapter.py`, `provisional_status.py`, `frontier.py`, `gate_tokens.py`, `node_cli.py`, jobs / evaluations / receipt / watch.

**In the way:** `pi_rpc_adapter.py` spawns `pi --mode rpc` under settings discovery. `runner.py`, `reconciler.py`, and `provisional_status.py` write node YAML to `provisional` and issue the gate before a decider's `next`.

## 6. Demo

`gddp gdad run gdad-demo line-pair` proves one pause, packet, decision, resume cycle. Fable sees only the rendered packet and its reply is piped to `gddp gdad decide`.

1. Workers write three lines. Opus rejects.
2. A `verdict` packet is written. Fable replies `redispatch` with changes. Workers write two lines. Opus accepts.
3. An `acceptance` packet is written. Fable replies `next` with `workflow: null`. The gate is issued.
4. Separately, `after-workers` is an `ambiguity` packet. Kill the pane. `gddp gdad decide` with `resume` relaunches that pi session. The finished workers are not rerun.

`gddp gdad show gdad-demo line-pair` prints the journal with those packets and decisions inline.

## 7. Decision packet

**Packet.** On each durable pause (verdict, ambiguity checkpoint, acceptance) the workflow writes one `gdad/<project>/<node>/packets/<packet_id>.json` and a rendered `<packet_id>.md`, and journals `packet`. Fields: `packet_id`, `project`, `node`, `run_id`; `kind` of `verdict|ambiguity|acceptance`; `done` (at most 5 bullets); `question` (one sentence); `options` as `[{id, label, consequence}]`; `evidence` (verdict reasons, or the checkpoint prompt); `artifacts` (paths only); `resume_handle` `{pi_session_id, workflow_run_id, checkpoint}`; optional `expires`. The `.md` is capped at about 2 KB.

**Replies.** Only three, validated by `schemas/gdad/reply.schema.json`. `gddp gdad decide <packet_id> <reply.json|->` journals `decision` and performs it. `gddp gdad inbox [--json]` lists open packets. The main agent reads only inbox and the packet.

- `{"reply":"resume","packet_id":"...","option_id":"..."}` or the same with `"decision":"<text>"` instead of `option_id`: `workflow_respond` on the resume handle, and the workflow continues.
- `{"reply":"redispatch","packet_id","changes":"<text>"}`: new `run_id`. `changes` are what the next workers read. A later `dispatch` line starts that run.
- `{"reply":"next","packet_id","workflow":"<project>/<node>"|null}`: close this node. If the verdict was accept, journal `gate` and set `accepted`. `workflow` names what runs next, or `null`.

**Roles.** Opus produces `verdict.json`, which is packet evidence. Fable decides. Verified 2026-10-13 on this VM: `claude -p --model claude-fable-5-1 --output-format json` returned `type=result`, `is_error=false`, model `claude-fable-5-1`, result `{"ok":true}`. The demo gives Fable only `packet.md` and pipes that reply JSON into `decide`.

**Host.** bb's CLI has `thread` and no `workflow` command. A thread can park on an interaction (`bb thread interactions answer|respond` takes a structured value) and `bb thread stop` keeps history for a later turn. State is the bb server at `BB_SERVER_URL` (`http://127.0.0.1:38886`); `~/.bb/` here is only `pi-bridge-sessions/`, not a run journal. That park is a conversation turn. It does not replay a script so finished `parallel` calls stay done. pi-extensible-workflows `checkpoint` plus `workflow_respond`, keyed by `listRunIds(cwd, sessionId)`, does. Keep pi. Do not host the slice on both.

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

## Review 2 (Opus steward): BUILD

Round 2 closes all eight Review 1 points. I checked `pi --session-id <id>` (it creates the session if missing) and it exists, so the dead-pane resume path is real. Build the slice as proposed, with these notes:

- **Order.** Start with `gdad_run.py journal` and its unit tests: legal and illegal transitions, flock, status derived from the last line, and redispatch giving a new `run_id`. Then `cli_gdad.py`, then `workflow.js`, then the reviewer step. Commit and push after each piece.
- **Demo flow.** `dispatch` should follow a `redispatch` as its own journal line when the next run starts. A `blocked` node needs an explicit `gddp gdad run` to leave `blocked`; no automatic retry.
- **Don't fake the demo.** If a pi tool name (`workflow_respond`, the trajectory `pause`/`resume` actions, `subagents_steer`) turns out different from your reading of the dist, use the real one and correct the proposal. Never fake a journal line to make the demo pass.
- **Done, both repos.** Run the full demo on this VM:
  - reject → redispatch → accept, with the gate issued;
  - pause at `after-workers`, kill the pane, `gddp gdad resume`, and the workers are not rerun.
  
  Then save `gddp gdad show gdad-demo line-pair` output as `DEMO.md` in the gddp-config worktree, commit with the cursor-agent trailer, push both branches, and STOP. I review the code and merge.

## Review 3 (Opus steward, 2026-10-13 09:41Z): NORTH STAR. Hold the build; add the decision packet first

The brief gained a North star section from Sab. Read it in full: ~/.dsh/briefs/task-1-gdad.md, "North star". Sab: "workflows pause it from working or running and returning to it the exact work it needs to make decisions on and re-dispatching OR choosing which workflows to run next". This changes the center of the contract. The journal and status stay as designed in round 2, but they become plumbing. The product is the **decision packet**, and the main agent (Fable in Claude Code, or `grok claude`) sees nothing except packets.

Add section 7 (decision packet), adjust sections 2, 4 and 6 to fit, stay within 2.5 pages, commit, push, and STOP for a quick Review 4. Then build.

7a. **Packet.** On every durable pause (review verdict, ambiguity checkpoint, acceptance), the workflow writes exactly one packet: `gdad/<project>/<node>/packets/<packet_id>.json` plus a rendered `<packet_id>.md`, and journals `packet`. Fields:
- `packet_id`, `project`, `node`, `run_id`;
- `kind`: `verdict | ambiguity | acceptance`;
- `done`: at most 5 bullets of what happened;
- `question`: one sentence;
- `options`: `[{id, label, consequence}]`;
- `evidence`: the reviewer's verdict.json reasons, or the checkpoint prompt;
- `artifacts`: paths only;
- `resume_handle`: `{pi_session_id, workflow_run_id, checkpoint}`;
- `expires`: optional.

Cap the rendered `.md` at about 2 KB. That cap is the "least amount of work" contract. Add a state between running and resolution, `awaiting-decision`, entered when a packet is written.

7b. **The three replies, and only these:**
- `{"reply":"resume","packet_id","option_id"|"decision":"<text>"}`: answer the checkpoint, and the workflow continues;
- `{"reply":"redispatch","packet_id","changes":"<text>"}`: new `run_id`, with `changes` fed to the workers (this replaces round 2's reject → redispatch, which is now the decider's call, not automatic);
- `{"reply":"next","packet_id","workflow":"<project>/<node>"|null}`: close this node (accept if the verdict was accept) and name what runs next.

Command: `gddp gdad decide <packet_id> <reply.json|->`. It validates against `schemas/gdad/reply.schema.json`, journals `decision` with the reply, and performs it: resume via `workflow_respond`, redispatch, or gate+next. `gddp gdad inbox [--json]` lists open packets. The main agent reads only `inbox` and the packet, and writes only `decide`.

7c. **Roles.** The Opus reviewer (`claude -p --model opus`) still produces `verdict.json`, which becomes packet `evidence`. The decider is a separate role, Fable. In the demo the stand-in is `claude -p --model claude-fable-5-1 --output-format json` (verify it runs headless on this VM). It gets only the rendered packet.md and must answer with one reply JSON, which the demo pipes into `gddp gdad decide`. Gates are issued only after a `next` (or a `resume` past the final acceptance checkpoint) on an accept verdict.

7d. **Host evaluation.** Sab allows bb (`bb-cli`, on PATH as `bb`) threads/workflows as the host *if* they already give durable pause/resume. Spend at most 15 minutes: `bb --help`, `bb workflow`/`thread` subcommands, and where state lives. Write one paragraph: does bb give a durable park plus a structured resume value that's better than pi-extensible-workflows' `checkpoint` + `workflow_respond`? Keep pi unless bb is clearly better; never use both.

7e. **Demo (replaces section 6's sequence).** Your one command `gddp gdad run gdad-demo line-pair` must prove one full pause → packet → decision → resume cycle with Fable deciding:
1. Workers write three lines, and the reviewer rejects.
2. A `verdict` packet is written; Fable replies `redispatch` with changes; the workers write two lines; the reviewer accepts.
3. An `acceptance` packet is written; Fable replies `next` with `null`; the gate is issued.
4. Separately, show the durable resume: the `after-workers` checkpoint is an `ambiguity` packet; kill the pane; `gddp gdad decide` with `resume` relaunches on the pi session; the workers are not rerun.

`gddp gdad show` prints the journal with the packets and decisions inline.

## Review 4 (Opus steward): BUILD

Section 7 is right. The packet fields, the three replies, `inbox`/`decide`, Fable as the separate decider, and the bb evaluation (a park on a conversation turn is not a replaying journal, so pi stays) all match the North star. Build now, in the Review 2 order. Two additions:

- **`--decider`.** `gddp gdad run <project> <node> --decider fable|none` (default `none`). With `fable`, the executor pipes each new `packet.md` into `claude -p --model claude-fable-5-1 --output-format json` with a fixed prompt file (`schemas/gdad/decider-prompt.md`: "answer with exactly one reply JSON from the schema") and passes the result to `decide`. A reply that's invalid against the schema leaves the packet open and journals a `blocked` note; it is never auto-resolved. With `none`, packets wait in `inbox` for Sab or Claude Code. The demo uses `--decider fable`, and Sab's one command is `gddp gdad run gdad-demo line-pair --decider fable`.
- **Real tool names.** Same rule as before: use the real names (`workflow_respond` etc.), never fake a journal line, and correct the proposal if the dist differs.

Done: both demos run on this VM, `DEMO.md` holds the `gddp gdad show` output plus `gddp gdad inbox` at one pause, both branches are pushed, then STOP for code review.
