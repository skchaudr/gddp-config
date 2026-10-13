# GDAD line-pair demo

Captured 2026-10-13 after post-limit rerun. Runtime `gdad-slice` at `4f31afe` (stdin fix `b439820`, backup-dir scan). Config worktree `gdad-slice`. Substrate: `~/.local/pi-1.0.4/bin/pi` and `pi-durable-subagents`. Command env: `GDDP_CONFIG_PATH` → this worktree, `GDDP_RUNTIME_ROOT` → runtime worktree.

## Demo A (`gddp gdad run gdad-demo line-pair --decider fable`)

Opus rejected `line-pair-1` (`count=3`). Fable redispatched. `line-pair-2` wrote `one` and `two`. Opus accepted (`count=2`). Fable replied `next` with workflow null. Gate `.gddp/gates/line-pair.token` issued at 2026-10-13T18:36:00Z. After accept, `gddp gdad show` prints `pane` `none`; no `gdad-gdad-demo-line-pair` tab remained.

## Demo B (durable resume)

`line-pair-1` paused on ambiguity packet `pkt-1`. Inbox below was captured while that packet was open. Herdr tab labelled `gdad-gdad-demo-line-pair` was closed; Fable's reply was piped into `gddp gdad decide pkt-1 - --who fable` (not hand-written JSON). Same wid `01M4V9DEJTYAB0KEA0SS2M73CN` resumed; `pi-durable-subagents describe` shows workers `a` and `b` still at generation 1. Artifact mtimes before tab close:

```
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-a.txt 1791917222 1791917222
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-b.txt 1791917220 1791917220
```

Describe excerpt after Fable `resume`:

```
line-pair-1-7dea60: running — 01M4V9DEJTYAB0KEA0SS2M73CN
  a@1 scribe sealed ok (openrouter/deepseek/deepseek-v4-flash)
    | Done. I wrote exactly these two lines to `artifacts/hello-a.txt`:
    | 
    | ```
    | alpha
    | beta
    | ```
    | 
    | No other files were written.
  b@1 scribe sealed ok (openrouter/deepseek/deepseek-v4-flash)
    |  Done. Wrote hello-b.txt with exactly one line: gamma.
  gate@1 scribe running (openrouter/deepseek/deepseek-v4-flash)
    waiting: {"slot":"openrouter 1 (no limit)"}
```

## gddp gdad inbox --json at the pkt-1 pause (Demo B)

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
      "wid": "01M4V9DEJTYAB0KEA0SS2M73CN",
      "qid": "ffc5adb227b2548e513965f466b21d64c9a3291b7219d45da4dac90049d46072",
      "rev": 1,
      "to": "01M4V9DEJTYAB0KEA0SS2M73CN/gate"
    },
    "open": true
  }
]
```

## gddp gdad show gdad-demo line-pair (Demo A, after gate)

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
when: 2026-10-13T18:36:00Z
run_id: line-pair-2
request_id: line-pair-2-e1a99a
wid: 01M4V8R4E7DBQ4ECH53CSQEENA

## pane
none
## journal
{"v":1,"ts":"2026-10-13T18:34:31Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/graphs/gdad-demo/gdad/line-pair/BRIEF.md"],"request_id":"line-pair-1-6feacf","wid":"01M4V8PWXT99MJ1Q0Y1BSRVMRG"}
{"v":1,"ts":"2026-10-13T18:34:52Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-1","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T18:34:52Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.md"],"note":"pkt-1 ambiguity"}
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
{"wid": "01M4V8PWXT99MJ1Q0Y1BSRVMRG", "qid": "7b6ae3f3f767a57f649b282fe955d2657da739ecf2c5534c41fb71c9b38816c9", "rev": 1, "to": "01M4V8PWXT99MJ1Q0Y1BSRVMRG/gate"}

{"v":1,"ts":"2026-10-13T18:34:56Z","type":"decision","who":"fable","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.json"],"note":"resume: resume"}
{"v":1,"ts":"2026-10-13T18:34:59Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T18:35:06Z","type":"verdict","who":"claude-opus","state":"review","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json"],"note":"reject: count=3"}
{"v":1,"ts":"2026-10-13T18:35:06Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-2.md"],"note":"pkt-2 verdict"}
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
- runs/line-pair-1/artifacts/hello-a.txt
- runs/line-pair-1/artifacts/hello-b.txt
- runs/line-pair-1/artifacts/hello.txt

## Resume
{"wid": "01M4V8PWXT99MJ1Q0Y1BSRVMRG", "qid": "", "rev": 0}

{"v":1,"ts":"2026-10-13T18:35:11Z","type":"decision","who":"fable","state":"pending","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-2.json"],"note":"redispatch: Worker A: write exactly one line, the single word one, to hello-a.txt and no other file. Worker B: write exactly one line, the single word two, to hello-b.txt and no other file. Do not write hello.txt."}
{"v":1,"ts":"2026-10-13T18:35:11Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/graphs/gdad-demo/gdad/line-pair/BRIEF.md"],"request_id":"line-pair-2-e1a99a","wid":"01M4V8R4E7DBQ4ECH53CSQEENA"}
{"v":1,"ts":"2026-10-13T18:35:36Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-2","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T18:35:36Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-3.md"],"note":"pkt-3 ambiguity"}
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
{"wid": "01M4V8R4E7DBQ4ECH53CSQEENA", "qid": "1eb366aa0bd3258537c5955e12164933a7a39ef8c8e519aff89143b704972a3e", "rev": 1, "to": "01M4V8R4E7DBQ4ECH53CSQEENA/gate"}

{"v":1,"ts":"2026-10-13T18:35:49Z","type":"decision","who":"fable","state":"running","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-3.json"],"note":"resume: resume"}
{"v":1,"ts":"2026-10-13T18:35:52Z","type":"review","who":"gdad-executor","state":"review","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello.txt"]}
{"v":1,"ts":"2026-10-13T18:35:55Z","type":"verdict","who":"claude-opus","state":"review","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/verdict.json"],"note":"accept: count=2"}
{"v":1,"ts":"2026-10-13T18:35:55Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-4.md"],"note":"pkt-4 acceptance"}
--- packet pkt-4 ---
# acceptance pkt-4
project `gdad-demo` node `line-pair` run `line-pair-2`

## Question
Opus accepted hello.txt. Close this node with next and workflow null.

## Reply
Answer with exactly one JSON object and no other text.
{"reply": "next", "packet_id": "pkt-4", "workflow": null}

## Done
- Opus accepted: count=2

## Options
- close: Close (Issue the gate and mark the node accepted)

## Evidence
count=2

## Artifacts
- runs/line-pair-2/artifacts/hello-a.txt
- runs/line-pair-2/artifacts/hello-b.txt
- runs/line-pair-2/artifacts/hello.txt

## Resume
{"wid": "01M4V8R4E7DBQ4ECH53CSQEENA", "qid": "", "rev": 0}

{"v":1,"ts":"2026-10-13T18:36:00Z","type":"decision","who":"fable","state":"accepted","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-4.json"],"note":"next: None"}
{"v":1,"ts":"2026-10-13T18:36:00Z","type":"gate","who":"gdad-executor","state":"accepted","run_id":"line-pair-2","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/.gddp/gates/line-pair.token"]}
## artifacts
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/.pi/agents/scribe.md
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-a.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-b.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/review-raw.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/verdict.json
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/prompt.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/spec.json
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/.pi/agents/scribe.md
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
  "issued_at": "2026-10-13T18:36:00+00:00",
  "node_id": "line-pair",
  "receipt_path": "/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/verdict.json",
  "verdict_receipt_sha256": "a764ed511e7a12e6af056acc8f5b22a0d9cacaf6c38f9d717d76d8dbbdd9a4e2"
}
## describe
{
  "state": "sealed",
  "wid": "01M4V8R4E7DBQ4ECH53CSQEENA",
  "request": "line-pair-2-e1a99a",
  "spec_digest": "688743e0cac752b3c7ea8f318b4aa5b209bbb3173a9cbb713a16beec600cca47",
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
      "output": " Done."
    },
    {
      "key": "b",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": "Done. Wrote the single word \"two\" to `/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-b.txt` and no other file."
    },
    {
      "key": "gate",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": " Called the ask tool with the requested question. Stopping."
    }
  ],
  "attention": [
    {
      "id": "finished:01M4V8R4E7DBQ4ECH53CSQEENA",
      "rev": 1,
      "kind": "finished",
      "text": "line-pair (01M4V8R4E7DBQ4ECH53CSQEENA) done: 3 ok\na: ok\n   Done.\nb: ok\n  Done. Wrote the single word \"two\" to `/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-2/artifacts/hello-b.txt` and no other file.\ngate: ok\n   Called the ask tool with the requested question. Stopping.\nUsage: 4.1K in / 478 out, $0.0008\nFull output: subagents status wid:01M4V8R4E7DBQ4ECH53CSQEENA"
    }
  ],
  "kind": "run"
}
```

## gddp gdad show gdad-demo line-pair (Demo B, after Fable resume)

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
state: running
who: fable
when: 2026-10-13T18:47:34Z
run_id: line-pair-1
request_id: line-pair-1-7dea60
wid: 01M4V9DEJTYAB0KEA0SS2M73CN

## pane
wP:p2
## journal
{"v":1,"ts":"2026-10-13T18:46:50Z","type":"dispatch","who":"gdad-executor","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-config/.worktrees/gdad-slice/graphs/gdad-demo/gdad/line-pair/BRIEF.md"],"request_id":"line-pair-1-7dea60","wid":"01M4V9DEJTYAB0KEA0SS2M73CN"}
{"v":1,"ts":"2026-10-13T18:47:15Z","type":"pause","who":"pi-workflow","state":"paused","run_id":"line-pair-1","artifacts":[],"note":"subagent question"}
{"v":1,"ts":"2026-10-13T18:47:15Z","type":"packet","who":"pi-workflow","state":"awaiting-decision","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.md"],"note":"pkt-1 ambiguity"}
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
{"wid": "01M4V9DEJTYAB0KEA0SS2M73CN", "qid": "ffc5adb227b2548e513965f466b21d64c9a3291b7219d45da4dac90049d46072", "rev": 1, "to": "01M4V9DEJTYAB0KEA0SS2M73CN/gate"}

{"v":1,"ts":"2026-10-13T18:47:34Z","type":"decision","who":"fable","state":"running","run_id":"line-pair-1","artifacts":["/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/packets/pkt-1.json"],"note":"resume: resume"}
## artifacts
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/.pi/agents/scribe.md
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-a.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/artifacts/hello-b.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/prompt.txt
/home/sab-mini/gddp-runtime/.worktrees/gdad-slice/gdad/gdad-demo/line-pair/runs/line-pair-1/spec.json
## gate
(no gate)
## describe
{
  "state": "running",
  "wid": "01M4V9DEJTYAB0KEA0SS2M73CN",
  "request": "line-pair-1-7dea60",
  "spec_digest": "f3dd472d06f240e0cb52d48326674c1a8c0cddfdd0a2bf9303f598436640f17c",
  "status": "running",
  "calls": [
    {
      "key": "a",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": "Done. I wrote exactly these two lines to `artifacts/hello-a.txt`:\n\n```\nalpha\nbeta\n```\n\nNo other files were written."
    },
    {
      "key": "b",
      "gen": 1,
      "phase": "sealed",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "status": "ok",
      "ok": true,
      "output": " Done. Wrote hello-b.txt with exactly one line: gamma."
    },
    {
      "key": "gate",
      "gen": 1,
      "phase": "running",
      "agent": "scribe",
      "model": "openrouter/deepseek/deepseek-v4-flash",
      "waiting": {
        "slot": "openrouter 1 (no limit)"
      }
    }
  ],
  "kind": "run"
}
```
