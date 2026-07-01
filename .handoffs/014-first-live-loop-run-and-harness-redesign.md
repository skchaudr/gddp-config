# 014 — First Live Loop Run: Shakeout, Verification Proof, and Harness Redesign

------------------------------------------------ Agent Section START

Date: 2026-06-30
Worktree: /Users/sab-mini/repos/gddp-config (graphs) + /Users/sab-mini/repos/gddp-runtime-codex (engine)
Branch: main (both)

## Empirical Reality (2-3 sentences max)

Ran the decision loop against real practice graphs for the first time; it works end-to-end (dispatch → GH issue → job guard; deterministic floor → semantic LLM → receipt). Seven bugs found and fixed purely by running it, full suite 107 passing. The verifier is sound — it correctly PASSes code and blocks only on missing execution artifacts — but the confidence *number* is miscalibrated (0.18 for a node that genuinely passes at ~0.96).

### Scope touched (one file per line, +/- for what changed)
+ gddp-runtime-codex/scripts/runtime/decision_loop/engine.py  (dispatch print fallback; pass con to dispatch; GDDP_VERIFY_MODEL override)
+ gddp-runtime-codex/scripts/runtime/decision_loop/powers/dispatch_next.py  (persist dispatched job row; con param)
+ gddp-runtime-codex/scripts/runtime/decision_loop/context_reader.py  (scope activity queries by project_id; results via join)
+ gddp-runtime-codex/scripts/runtime/decision_loop/test_decision_loop.py  (fixture + inserts carry project_id; new dispatch signature)
+ gddp-runtime-codex/scripts/runtime/verification/semantic/tools.py  (explicit input_schema for all 8 tools)
+ gddp-runtime-codex/scripts/runtime/verification/semantic/agent.py  (Anthropic tool protocol; JSON extraction; targeted extractor)
+ gddp-runtime-codex/scripts/runtime/verification/schemas.py  (coerce dict/list free-text fields to string)
+ gddp-config/graphs/gddp-runtime/nodes/semantic-submit-verdict-tool.yaml  (new)
+ gddp-config/graphs/gddp-runtime/nodes/semantic-validation-retry.yaml  (new)
+ gddp-config/graphs/gddp-runtime/nodes/verdict-confidence-split.yaml  (new)
+ gddp-config/graphs/gddp-runtime/project.yaml  (register 3 nodes, capabilities, date)

### Current Git state (2-3 sentences max)
runtime-codex: 3 commits (285739c dispatch, 89bbc69 project scoping, 60f6b40 semantic portability), clean, unpushed. config: 1 commit (7d55581 harness nodes), clean, unpushed. db/queue.db created locally (gitignored); ~/.gddp/receipts/ holds real receipts.

### Artifacts (filepath - description, 1 line max)
~/.gddp/receipts/vault-doctor/scan-vault-core.json - real receipt: all 6 criteria judged_pass via GLM, verdict needs-more-evidence (artifacts absent)
GH issue skchaudr/aa-cli#3 - live dispatch awaiting Jules
GH issue skchaudr/Automating-Selling-Random-Valuables#1 - live dispatch awaiting Jules
memory: gddp-loop-verification-run.md - run recipe (model env vars) + artifact-gate finding

### Resume point (2-3 sentences max)
Dispatch the 3 new harness nodes through the loop — first true 0→N on nodes that never existed out-of-band (dispatch → Jules → artifacts → verify → receipt). Highest-leverage node is semantic-submit-verdict-tool (kills the deepseek loop + parsing fragility). Then verdict-confidence-split to make the score trustable.

------------------------------------------------ Agent Section END

## Chronological Walkthrough (Agent — experiential log, as if you were watching)

This is what it actually felt like to run the system, intersection by intersection. Read it as a screen-recording in prose.

**0. Framing.** You said "scoreboard zero" meant one thing: we have never actually run the loop on practice graphs to shake out issues. Not "the code isn't written." So I stopped theorizing and treated the whole session as: run it, watch it break, fix what breaks, repeat.

**1. First contact — the db doesn't exist.** I went to run the engine and there was no `db/queue.db`. `init_db.py` failed with "unable to open database file" — because the `db/` directory itself didn't exist. Tiny, but the very first step of standing the system up was already a gap. Created the dir, initialized. Tables appeared: events, jobs, results, decision_results, etc. First green.

**2. First loop run — escalation, not crash.** Ran against `aa-cli`. It woke, read the graph, decided to *dispatch*, and escalated cleanly: `gh_issue_create_failed: 'jules' not found`. This was the first "aha": the loop's plumbing works — wake→read→decide→act→escalate — and the failure was a real-world integration gap (the target repo had no `jules` label), not a logic error. The system failed *honestly*.

**3. Realizing dispatch ≠ verify.** I checked node statuses: all 12 aa-cli nodes `pending`. That meant the loop would only ever try to *dispatch* them (file a GH issue for Jules), never *verify* them — even though the code was already built out-of-band. Verification only fires on `complete` nodes. So "built but scoreboard 0" had a concrete mechanism: status=pending routes to dispatch, and dispatch was broken.

**4. The diagnostic that taught me the most.** I flipped one node (`common-core`) to `complete`, backed it up, and ran the loop to see the verify path. It produced a *real receipt*: deterministic probes hit the actual `lib/common.zsh`, all 5 criteria PASS with line-level evidence — yet verdict `needs-more-evidence`. Reason: three artifacts missing (`decision.md`, `result-summary.md`, `patch.diff` all `False`). That was the structural revelation of the night: **the verifier confirms the code is done, then correctly refuses to stamp it because the execution paper-trail doesn't exist.** Not a bug — the gate working as designed. I reverted the flip (it belongs in real dispatch, not artifact-limbo).

**5. Fixing dispatch, and the bug chain begins.** You said: this label thing is exactly the "little issue" to find — fix it and keep going. Created the `jules` label. Re-ran → dispatch *succeeded* and filed a real GH issue... then `main()` crashed printing the result: `DispatchResult` has no `.reason`. **Bug #1 fixed** (print fallback to issue_url). Re-ran → it dispatched *again*, issue #2, same node. **Bug #2:** dispatch never wrote a job row, so the active-job guard never fired — every tick would spam a duplicate. Fixed by persisting a `dispatched` job (had to thread the db connection into `dispatch_next.run`). Verified the fix the honest way: run 1 dispatches (#3), run 2 → `dispatch_blocked: active job already exists`. Watching that guard finally bite was satisfying.

**6. Second graph, cross-contamination.** Ran `sell-valuables` to keep shaking out. It was *blocked* — by aa-cli's job. **Bug #3:** `read_recent_activity` took a `project_id` but never used it; one project's jobs leaked into another's context. Scoped the queries. Hit a sub-bug immediately: `results` has no `project_id` column (it links via `job_id`), so I scoped it through a join. Re-ran → sell-valuables dispatched to its *own* repo. Three tests broke from the schema change; the test fixture used a simplified schema missing `project_id` — updated fixture + inserts. 20/20 green.

**7. The real prize — verification on vault-doctor.** vault-doctor had all 7 nodes already `complete`, so the loop went straight to the verify path. This is where the semantic engine got its first real workout, and it was a *staircase* of failures, each one deeper into the stack:
   - **Needed a key.** No `ANTHROPIC_API_KEY`. NoxKey's socket was down. You pointed me at keychain/env — DeepSeek + GLM Anthropic-compatible endpoints. I made the model env-overridable (`GDDP_VERIFY_MODEL`) so the runner wasn't pinned to `claude-*`, and pointed it at DeepSeek.
   - **Bug #5: tool schemas.** DeepSeek (stricter than real Anthropic) rejected `read_file`: "null is not of types boolean, object." The tools had *no* `input_schema` at all — real Anthropic tolerates it, DeepSeek doesn't. Wrote explicit schemas for all 8.
   - **Bug #6: wrong tool protocol.** Next: "unknown variant `tool`." The loop used OpenAI-style `role:"tool"` messages *and* dropped the assistant `tool_use` blocks — so tool results couldn't correlate. This path had clearly never run against a real tool call. Rewrote to Anthropic's protocol (assistant `tool_use` + a single `user`/`tool_result` turn).
   - **Now it actually talked.** Four `200 OK`s to DeepSeek, tool loop spinning, a receipt written. But: `needs-more-evidence`, 0 judgments — DeepSeek looped 16 turns and never emitted the final structured verdict (turn budget exhausted). *Model behavior*, not code.
   - **Switched to GLM.** Parse failure — but a revealing one. GLM produced *beautiful* judgments (judged_pass, 0.99, line-level evidence) wrapped in prose + a ```json fence. **Bug #7 (parser):** it expected raw JSON. I added extraction — but my first extractor grabbed the *first* `{...}`, which was a set literal `{".obsidian",".git"}` in GLM's prose. Rewrote it to target the object *enclosing* the `judgments` key. Then a schema-strictness miss: GLM returned `risks` as a dict, schema wanted a string — added a coercion validator.
   - **Full pass.** Final run: all 6 criteria `judged_pass` at 0.9–0.99 with evidence, a real receipt on disk. The entire pipeline — deterministic floor → semantic LLM tool-loop → structured verdict → receipt — working against a real repo with a real (non-Anthropic) model.

**8. The calibration gut-punch.** The verdict read confidence **0.18** despite everything passing. You (rightly) called it: that's not reflective. I traced the math. Artifacts play *zero* role in the number — they only gate the *verdict* to needs-more-evidence (matrix row 6). The 0.18 came from `min(deterministic_floor, semantic)`, where the floor was ~0.18 because the static probes were all `indeterminate` — which is the *exact reason* semantic was invoked. So the "I couldn't decide" floor overrode the phase built to decide. The weakest signal won. That's a representation bug: one scalar conflating "unsure the code works" (false) with "trail missing" (true).

**9. From bugs to design.** You reframed it: move failure *up the stack* — get to where nodes aren't fixing plumbing bugs but conceptual/logic issues, because the scaffolding is dialed in. So I turned today's three deepest findings into three gddp-runtime nodes (dogfooding the redesign through the system itself): `semantic-submit-verdict-tool` (make concluding a tool action — kills the deepseek loop + all the parsing fragility by construction), `semantic-validation-retry` (re-prompt on invalid output instead of discarding a token-spent run), `verdict-confidence-split` (separate criteria-confidence from artifact gating so a passing-but-untrailed node reads ~0.95, not 0.18). Validated (0 errors), committed.

**How I interfaced with the system, meta-note:** the rhythm was always the same — run the engine, read the *last few lines* of output, treat the escalation/exception as the next task, verify the fix against ground truth (the receipt JSON, `git diff`, the tests) not the console, commit as a checkpoint, run again. The system is legible: every failure named itself (`gh_issue_create_failed`, `context_read_failed`, `verification_needs-more-evidence`), which is *why* a cold run could shake out seven bugs in one sitting. That legibility is the system's best current asset.

**Two things I'd flag for the "future-proofing / maintainability" pass you mentioned:**
- The semantic tool-loop is hand-rolled and every failure today was in *protocol/format plumbing* (schemas, message roles, parsing). That's precisely what a typed-output substrate (pydantic-ai) removes. The three nodes steal the *patterns*; a later node could adopt the substrate.
- Test fixtures duplicate the real schema by hand (that's why they drifted when I scoped by project_id). A shared schema source between init_db and fixtures would stop that class of breakage.

## Addendum (post-session)

- ANE node was re-scoped after this session: `ane-edit-surface-eval` → `ane-verifier-read-tool-eval`. The immediately-relevant ANE surface is structural low-token *reading* for the semantic verifier (list symbols, yank one function body), not the executor edit/diff surface — which needs a local edit lane and is deferred. (commit 7b6faad)

------------------------ Do NOT edit this file past this point

## Narrative / Trajectory (SAB ONLY)

### Intent going into/at start of session

### Interpretation of how the session went

### Friction experienced or anticipated

### What's Next (Momentum or Lack Thereof)
