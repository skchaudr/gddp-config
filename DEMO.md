# GDAD line-pair demo

Captured 2026-10-13. Substrate: `~/.local/pi-1.0.4/bin/pi` 1.0.4 and `pi-durable-subagents` 1.0.39. `~/.local/bin/pi` is still 0.87.1. `graphs/gdad-demo/nodes/line-pair.yaml` status is still `pending`. After accept, `gddp gdad show` prints `pane` `none`, and no `gdad-line-pair` tab is left.

## Durable resume

`line-pair-1` paused on ambiguity packet `pkt-1`. The inbox below was saved while that packet was open. Herdr tab `wN:t2A` pane `wN:p3D` was closed; `herdr pane get` returned `pane_not_found`. `gddp gdad decide pkt-1` journaled `resume` and opened one new tab, `wN:t2B`, on the same pi session `f87ddf46-7260-4d4a-80b7-1478d8c13df2`. `describe` of wid `01M4TTRVR0KVBX53EZ3QF16NHY`: calls `a`, `b`, and `gate` sealed at gen 1. `hello-a.txt` mtime_ns `1791901869534653336` and `hello-b.txt` mtime_ns `1791901872386648090` are the writes from before the pane was closed.

## Reject, redispatch, accept

Opus rejected `line-pair-1` (`count=3`). Fable redispatched. `line-pair-2` wrote `one` and `two`. Opus accepted (`count=2`). Fable replied `next` with workflow null. Gate `.gddp/gates/line-pair.token` was issued at 2026-10-13T14:37:51Z. While that continuation ran, the live `gdad-line-pair` tab count stayed at most 1. The first answer to `pkt-3` collided with an older global request id and was not applied; `pkt-4` answered the same question.

## gddp gdad inbox --json at the pkt-1 pause

```json
[
  {
    "packet_id": "pkt-1",
    "project": "gdad-demo",
    "node": "line-pair",
    "run_id": "line-pair-1",
    "kind": "ambiguity",
    "done": [
      "Workers are waiting on a question"
    ],
    "question": "Workers finished. Resume to review?",
    "options": [
      {
        "id": "resume",
        "label": "Resume",
        "consequence": "Answer the subagent and continue"
      }
    ],
    "evidence": "Workers finished. Resume to review?",
    "artifacts": [],
    "resume_handle": {
      "wid": "01M4TTRVR0KVBX53EZ3QF16NHY",
      "qid": "08c6ce4067d4e2526e438550d4e5682e5da87e02b9b1e64c8d7a1d2c94087eab",
      "rev": 1,
      "to": "01M4TTRVR0KVBX53EZ3QF16NHY/gate"
    },
    "open": true
  }
]
```

## gddp gdad show gdad-demo line-pair

```
# gdad-demo/line-pair
## BRIEF
# line-pair

## Goal

Two workers write hello.txt. Acceptance is exactly two non-empty lines.

## Scope

Only hello-a.txt, hello-b.txt, hello.txt, and workers.done under this run's artifacts directory. The workflow concatenates the two worker files into hello.txt.

## Acceptance

hello.txt exists and has exactly two non-empty lines.

## Constraints

No other files. No graph YAML edits.

## Sab's words

Workers write three lines on the first run so the reviewer rejects, then two lines after a redispatch so the reviewer accepts.

## status
state: accepted
who: gdad-executor
when: 2026-10-13T14:37:51Z
run_id: line-pair-2
request_id: line-pair-2-717660
wid: 01M4TTW6C6BBFXNGWSVPVDHDXW

## pane
none
## journal
{"v":1,"ts":"2026-10-13T14:30:55Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/graphs/gdad-demo/gdad/line-pair/BRIEF.md"],"request_id":"line-pair-1-307391","wid":"01M4TTRVR0KVBX53EZ3QF16NHY"}
{"v":1,"ts":"2026-10-13T14:31:25Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-1","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T14:31:25Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.md"],"note":"pkt-1 ambiguity"}
--- packet pkt-1 ---
# ambiguity pkt-1
project `gdad-demo` node `line-pair` run `line-pair-1`

## Question
Workers finished. Resume to review?

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "resume", "packet_id": "pkt-1", "option_id": "resume"}

## Done
- Workers are waiting on a question

## Options
- resume: Resume (Answer the subagent and continue)

## Evidence
Workers finished. Resume to review?

## Artifacts

## Resume
{"wid": "01M4TTRVR0KVBX53EZ3QF16NHY", "qid": "08c6ce4067d4e2526e438550d4e5682e5da87e02b9b1e64c8d7a1d2c94087eab", "rev": 1, "to": "01M4TTRVR0KVBX53EZ3QF16NHY/gate"}

{"v":1,"ts":"2026-10-13T14:32:08Z","type":"decision","who":"sab","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.json"],"note":"resume: resume"}
{"v":1,"ts":"2026-10-13T14:32:28Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T14:32:35Z","type":"verdict","who":"claude-opus","state":"review","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json"],"note":"reject: count=3"}
{"v":1,"ts":"2026-10-13T14:32:35Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-2.md"],"note":"pkt-2 verdict"}
--- packet pkt-2 ---
# verdict pkt-2
project `gdad-demo` node `line-pair` run `line-pair-1`

## Question
hello.txt failed acceptance (count=3). Redispatch so the workers write exactly two lines.

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "redispatch", "packet_id": "pkt-2", "changes": "Worker A: write exactly one line, the single word one, to hello-a.txt and no other file. Worker B: write exactly one line, the single word two, to hello-b.txt and no other file. Do not write hello.txt."}

## Done
- Opus rejected: count=3

## Options
- redispatch: Redispatch (New run writes exactly two lines)

## Evidence
count=3

## Artifacts
- runs/line-pair-1/artifacts/.pi/agents/scribe.md
- runs/line-pair-1/artifacts/hello-a.txt
- runs/line-pair-1/artifacts/hello-b.txt
- runs/line-pair-1/artifacts/hello.txt

## Resume
{"wid": "01M4TTRVR0KVBX53EZ3QF16NHY", "qid": "", "rev": 0}

{"v":1,"ts":"2026-10-13T14:32:43Z","type":"decision","who":"fable","state":"pending","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-2.json"],"note":"redispatch: Worker A: write exactly one line, the single word one, to hello-a.txt and no other file. Worker B: write exactly one line, the single word two, to hello-b.txt and no other file. Do not write hello.txt."}
{"v":1,"ts":"2026-10-13T14:32:44Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/graphs/gdad-demo/gdad/line-pair/BRIEF.md"],"request_id":"line-pair-2-717660","wid":"01M4TTW6C6BBFXNGWSVPVDHDXW"}
{"v":1,"ts":"2026-10-13T14:33:19Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-2","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T14:33:19Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-3.md"],"note":"pkt-3 ambiguity"}
--- packet pkt-3 ---
# ambiguity pkt-3
project `gdad-demo` node `line-pair` run `line-pair-2`

## Question
Workers finished. Resume to review?

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "resume", "packet_id": "pkt-3", "option_id": "resume"}

## Done
- Workers are waiting on a question

## Options
- resume: Resume (Answer the subagent and continue)

## Evidence
Workers finished. Resume to review?

## Artifacts

## Resume
{"wid": "01M4TTW6C6BBFXNGWSVPVDHDXW", "qid": "aeb5d5982e4ab79acc6450a30198a5e227e1b05ab9d15356a080790f7e4b36ee", "rev": 1, "to": "01M4TTW6C6BBFXNGWSVPVDHDXW/gate"}

{"v":1,"ts":"2026-10-13T14:33:25Z","type":"decision","who":"fable","state":"running","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-3.json"],"note":"resume: resume"}
{"v":1,"ts":"2026-10-13T14:37:18Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-2","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T14:37:18Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-4.md"],"note":"pkt-4 ambiguity"}
--- packet pkt-4 ---
# ambiguity pkt-4
project `gdad-demo` node `line-pair` run `line-pair-2`

## Question
Workers finished. Resume to review?

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "resume", "packet_id": "pkt-4", "option_id": "resume"}

## Done
- Workers are waiting on a question

## Options
- resume: Resume (Answer the subagent and continue)

## Evidence
Workers finished. Resume to review?

## Artifacts

## Resume
{"wid": "01M4TTW6C6BBFXNGWSVPVDHDXW", "qid": "aeb5d5982e4ab79acc6450a30198a5e227e1b05ab9d15356a080790f7e4b36ee", "rev": 1, "to": "01M4TTW6C6BBFXNGWSVPVDHDXW/gate"}

{"v":1,"ts":"2026-10-13T14:37:23Z","type":"decision","who":"fable","state":"running","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-4.json"],"note":"resume: resume"}
{"v":1,"ts":"2026-10-13T14:37:38Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T14:37:44Z","type":"verdict","who":"claude-opus","state":"review","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/verdict.json"],"note":"accept: count=2"}
{"v":1,"ts":"2026-10-13T14:37:44Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-5.md"],"note":"pkt-5 acceptance"}
--- packet pkt-5 ---
# acceptance pkt-5
project `gdad-demo` node `line-pair` run `line-pair-2`

## Question
Opus accepted hello.txt. Close this node with next and workflow null.

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "next", "packet_id": "pkt-5", "workflow": null}

## Done
- Opus accepted: count=2

## Options
- close: Close (Issue the gate and mark the node accepted)

## Evidence
count=2

## Artifacts
- runs/line-pair-2/artifacts/.pi/agents/scribe.md
- runs/line-pair-2/artifacts/hello-a.txt
- runs/line-pair-2/artifacts/hello-b.txt
- runs/line-pair-2/artifacts/hello.txt

## Resume
{"wid": "01M4TTW6C6BBFXNGWSVPVDHDXW", "qid": "", "rev": 0}

{"v":1,"ts":"2026-10-13T14:37:51Z","type":"decision","who":"fable","state":"accepted","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-5.json"],"note":"next: None"}
{"v":1,"ts":"2026-10-13T14:37:51Z","type":"gate","who":"gdad-executor","state":"accepted","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/.gddp/gates/line-pair.token"]}
## artifacts
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/.pi/agents/scribe.md
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-a.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-b.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/review-raw.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/prompt.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/spec.json
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/.pi/agents/scribe.md
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-a.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-b.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/review-raw.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/verdict.json
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/prompt.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/spec.json
hello.txt line-pair-1: 3 non-empty lines
hello.txt line-pair-2: 2 non-empty lines
## gate
{
  "issued_at": "2026-10-13T14:37:51+00:00",
  "node_id": "line-pair",
  "receipt_path": "/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/verdict.json",
  "verdict_receipt_sha256": "c6ba5ec22e775ddd6429b4497e35af54bc5d474f5053d7d42d168a7673cf9f90"
}
## describe
{
  "state": "sealed",
  "wid": "01M4TTW6C6BBFXNGWSVPVDHDXW",
  "request": "line-pair-2-717660",
  "spec_digest": "67024a5d86ee37e8a6a779777a1f1ebf76015ba98cf176ead98371936fd74d27",
  "status": "done",
  "calls": [
    {
      "key": "a",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": " Done. Wrote exactly one line containing the single word \"one\" to `/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-a.txt` and no other file."
    },
    {
      "key": "b",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": "Done. Wrote exactly one line (\"two\") to hello-b.txt in the artifacts directory."
    },
    {
      "key": "gate",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": " I called the ask tool with exactly that question, as instructed, and have stopped.\n\nNo additional processes were running on my end — the only action taken was the `ask` call, which was shut down along with the session while awaiting the answer. There's nothing to resume or verify beyond that. Let me know if you'd like me to take any next step."
    }
  ],
  "attention": [
    {
      "id": "finished:01M4TTW6C6BBFXNGWSVPVDHDXW",
      "rev": 1,
      "kind": "finished",
      "text": "line-pair (01M4TTW6C6BBFXNGWSVPVDHDXW) done: 3 ok\na: ok\n   Done. Wrote exactly one line containing the single word \"one\" to `/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-a.txt` and no other file.\nb: ok\n  Done. Wrote exactly one line (\"two\") to hello-b.txt in the artifacts directory.\ngate: ok\n   I called the ask tool with exactly that question, as instructed, and have stopped.\n\nNo additional processes were running on my end — the only action taken was the `ask` call, which was shut down along with the session while awaiting the answer. There's nothing to resume or verify beyond that. Let me know if you'd like me to take any next step.\nUsage: 4.1K in / 712 out, $0.0011\nFull output: subagents status wid:01M4TTW6C6BBFXNGWSVPVDHDXW"
    }
  ],
  "kind": "run"
}
```
