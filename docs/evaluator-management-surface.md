# Evaluator Management Surface — Design & Implementation Plan

**Status:** DRAFT — for review, nothing committed
**Branch:** `feat/gddp-eval-menu` (gddp-config) — no main merge until approved
**Author:** Pi + deepseek-v4-flash

---

## 1. Problem

`gddp` is the interactive entrance for everything. The *executor* side has a
dispatch surface; the *evaluator* side does not. Today an operator can view an
existing verdict (node menu `e` / `m → t`), run the judge from the shell
(`gddp verify node --project X --node Y --live --base <sha>`), or — on this
branch — run it live via `gddp eval <node>`. But there is no surface that
answers the three questions an operator actually asks:

1. **How is the evaluator configured right now?**
2. **What is it being told?** (what instructions/context go to the model)
3. **What have its runs actually looked like?** (what, when, with what result)

The existing first pass on this branch (`b0411bc`, `29a1669`) added a
*trigger* (run the judge, print a compact verdict) but not a *surface*
(config / instructions / runs).

## 2. The middle bound

The scope sits deliberately between two extremes:

- **Past:** just exposing/editing the `--model` flag.
- **Short of:** dumping the adapter source or the whole `cli.py`.

It is a **transparency + control layer**: read-only insight over how the
evaluator is configured and what it receives, plus per-run knobs — rendered
interactively, not as source or env dumps.

## 3. Key finding: the data already exists

The receipt already persists everything needed for the "instructions" lens.
No new evaluation machinery is required.

`LaneCoverage` (per run, per lane) already stores:

- `rating` — none/low/medium/high
- `offered` — count of canonical paths offered
- `content_accessed` / `not_observed` — counts
- `accessed_paths` / `not_observed_paths` — **the actual file lists**

And the receipt's `canonical_context` field holds the offered pointers
(README, PROJECT-BRIEF, foundational node, neighbor YAMLs, with
`UNAVAILABLE:` markers).

So the evaluator already records, per run: "offered these canonical files,
the criteria lane read these, the integrity lane read those." The current
surface renders only `rating` — a single word — and throws the file lists
away. **The instructions lens is un-collapsing data already in the receipt,
not building new instrumentation.**

## 4. Design — one surface, three lenses

Collapse the current redundancy (`evaluate` / `verify now` / `gddp eval` are
one code path, three names) into a single **`gddp eval`** entry. Front-page
`e` and node-menu `v` both land on it. Three lenses inside:

### 4.1 Config — "how it's configured"

Resolved, human-readable view of the *effective* evaluator settings:
model preset, thinking level, integrity on/off, timeouts, key source,
default lanes, base-pinning. Reads the same `runtime/settings.env` the config
menu already edits — this lens *shows* it coherently instead of raw env.

### 4.2 Instructions — "what it receives"

Two parts, both already computed per run:

1. **Prompt context** — node contract (why / acceptance criteria /
   constraints), project vision + blueprint, and the deterministic evidence
   handed to the model (probe results, files-touched, mismatches).
2. **Canonical offered-vs-read** — from `canonical_context` +
   `LaneCoverage.accessed_paths / not_observed_paths`:

   > Offered: README.md · PROJECT-BRIEF.md · neighbor:node-04
   > Read (criteria): README ✓ · PROJECT-BRIEF ✓ · node-04 ✗
   > Read (integrity): — (none)

   This is what `context_coverage` was already measuring, shown as files
   instead of a percentage.

### 4.3 Runs — "what/when its runs are like"

Receipt history per node: verdict, confidence, wall time, tool calls, model
used, commit evaluated, lanes run. Drill-in to one run's full breakdown
(deterministic probes, semantic reasoning, integrity, coverage). Model-aware
— extend what `gddp evaluations` does today, but per-node and interactive.

## 5. Run knobs (control, connected to the insight)

`gddp eval <node>` gains per-run overrides, each **recorded into the receipt**
so runs are comparable:

- `--model <preset|id>` — named presets (`cheap` / `expensive`) or raw id
- `--thinking <level>`
- `--integrity on|off`
- `--lanes live|deterministic`
- `--base <sha>` — pin the exact subject (already exists)

Receipts must also record the **model id** used (currently not surfaced in
the receipt summary), so the Runs lens can show "same node, cheap vs
expensive" side by side.

## 6. Non-goals

- No daemon, no queue, no new storage engine. Receipts already land in
  `verification/<project>/<node>/`.
- Evaluator remains **evidence-only** — it never mutates graph/node status;
  only the human accepts a node.
- No executor-side changes this pass (executor dispatch/config is the sibling
  surface, same treatment, after this).
- No changes to gddp-runtime/`main`; the worktree/old architecture untouched.

## 7. Implementation plan

**Increment A — one entry + run knobs + model-in-receipt**
- Collapse `interactive_evaluate` / `_node_review_menu` `v` / `cmd_eval` to a
  single `_run_live_eval` + one command surface.
- Add `--model/--thinking/--integrity/--lanes` to `cmd_eval`; pass through to
  `cli.py` semantic args.
- Persist model id + knobs into the receipt summary (`verification/cli.py`
  receipt write path) so Runs can read them.

**Increment B — the three lenses**
- `eval config` — render resolved settings (read `settings.env` + env).
- `eval instructions <node>` — render prompt context + canonical
  offered-vs-read from an existing receipt (or assembled pre-run).
- `eval runs <node>` + `eval show <run>` — read the receipt dir, per-node,
  model-aware, with drill-in.

**Increment C — preset config**
- Extend the config surface with named model presets (one token maps to a
  model id), default lanes/integrity, timeout, key source — same
  `runtime/settings.env`, menu and shell stay in sync.

Tests: extend `test_gddp.py` (fake-getch harness for menu wiring; mock
subprocess for command construction); pty smoke driver (from
`/tmp/gddp_tui_smoke.py`, move into repo) for the interactive lenses.

## 8. Open questions for Sab

1. Confirm the three lenses are the right shape, or is "instructions" the
   star and config/runs secondary?
2. Model presets: what are the actual `cheap` / `expensive` ids you'd want
   bound? (e.g. deepseek-v4-flash vs a frontier model)
3. Should `eval instructions` show the assembled prompt *before* a run (live
   assembly) or *after* (from the receipt)? Both, or one?
4. Where should this doc live — `gddp-config/docs/` is fine?
