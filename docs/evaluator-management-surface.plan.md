# Evaluator Management Surface — Function-level plan

**Status:** PLAN — not implemented, not committed
**Spec:** `docs/evaluator-management-surface.md` (`89a163f`)
**Branch:** `feat/gddp-eval-menu` (gddp-config only)
**Author:** planner pass (verified against live code 2026-08-18)

This plan is gddp-config-only. It does not edit gddp-runtime/`main`.
Every field name below was checked against
`gddp-runtime/scripts/runtime/verification/schemas.py`,
`cli.py`, `receipt_sink.py`, and a live receipt
(`verification/myapi-part1/node-05-validate-decision-set/job_20260814T214732845a5af48c5dcf-attempt0.json`).

---

## 0. What is already true

| Surface | File:fn | What it does today |
|---|---|---|
| Shell trigger | `scripts/gddp.py:cmd_eval` / `_run_live_eval` | Fuzzy-resolves node, shells `verification/cli.py` live+pi+integrity, prints compact verdict |
| Front-page `e` | `interactive_evaluate` | Pick graph → node → `_run_live_eval` → pause. Fire-and-forget. |
| Node-menu `v` | `_node_review_menu` | Same fire-and-forget `_run_live_eval` |
| Node-menu `e` | `_node_review_menu` | **Different thing**: current-job evidence view (`node_cli.cmd_show view="evaluation"`). Keep it. |
| Front-page `c` | `interactive_config` | Writes `runtime/settings.env` via `SETTINGS_FIELDS` |
| Receipt list | `scripts/evaluations.py` + `cmd_evaluations` + `interactive_evaluations` | Newest-first rows: when, verdict, wall, lane chips, project/node. **No model. No coverage files.** |
| Settings load | `_load_runtime_settings` | `setdefault` from `runtime/settings.env` at `main()` |

`_run_live_eval` is already the single runner. The gap is the *surface*
(config / instructions / runs) and per-run knobs, not another executor.

---

## 1. Model-in-receipt boundary (spec Increment A vs runtime/main)

**Finding: the model id is not in the receipt and cannot be derived.**

Checked:

- `VerdictReceipt` (`schemas.py:177-214`) has no `model`, `provider`,
  `thinking`, or `semantic_args` field. Provenance fields are
  `evaluated_commit_sha`, `expected_base_commit_sha`, `job_id`,
  `canonical_context`, `context_coverage`, `evaluation_timing`.
- `cli.py:main` writes the full `VerdictReceipt` via `write_receipt`, then
  prints a stdout summary (`receipt_path`, `verdict`, `criteria_confidence`,
  `completeness_status`, `required_next_action`, SHAs). No model.
- `PiHarnessRunner(model=args.semantic_pi_model, thinking=...)` is
  constructed in `cli.py:321-336` and **discarded after the run**.
- Live receipt top-keys include `canonical_context` and `context_coverage`
  but **`has model? False`**. `semantic.budget_trace` is `{tool_calls: [...]}`
  only — no provider/model/thinking.

So spec Increment A's "persist model id into the receipt summary
(`verification/cli.py` receipt write path)" **requires a gddp-runtime
schema + cli.py change**. That is off-limits this pass.

**Recommendation (operator decision, do not silently take):**

1. **This branch (A1, gddp-config-only):** `_run_live_eval` writes a sidecar
   next to the receipt:
   `verification/<project>/<node>/<job_id>-attempt<N>.knobs.json`
   ```json
   {
     "model": "deepseek-v4-flash",
     "preset": "cheap",
     "thinking": "medium",
     "integrity": "on",
     "lanes": "live",
     "base": "<sha>",
     "semantic_args": "...",
     "job_id": "manual-...",
     "written_at": "<iso>"
   }
   ```
   Runs/show merge sidecar + receipt. Historical receipts without a sidecar
   display model as `-`. No gddp-runtime edit.

2. **Later, separate gddp-runtime branch (A2, operator-gated):** add
   `semantic_provider`, `semantic_pi_model`, `semantic_thinking`,
   `integrity_mode` to `VerdictReceipt` and have `cli.py` stamp them.
   Then retire the sidecar. Do not start A2 without an explicit go.

Do **not** encode knobs in `job_id`. Do **not** invent a model by grepping
`budget_trace`.

---

## 2. Data-source map (verified field names)

Receipt root: `ROOT / "verification"` via `_evaluation_sources()`.
On-disk layout (`receipt_sink.receipt_path`):
`<base>/<project_id>/<node_id>/<job_id>-attempt<N>.json`.

Older/buggy paths also exist (`verification/myapi-part1/myapi-part1/...`).
Walkers must `rglob("*.json")` the way `evaluations._rows_from_receipts`
already does. Ignore `*.knobs.json`.

### Config lens (no receipt)

| Shown | Source |
|---|---|
| model preset + resolved id | `GDDP_EVAL_MODEL_CHEAP` / `GDDP_EVAL_MODEL_EXPENSIVE` (new, Increment C) else parse `--semantic-pi-model` out of `GDDP_VERIFY_SEMANTIC_ARGS` else `DEFAULT_SEMANTIC_ARGS` (`deepseek-v4-flash`) |
| thinking | `--semantic-thinking` in `GDDP_VERIFY_SEMANTIC_ARGS` / `GDDP_SEMANTIC_THINKING` |
| integrity | `GDDP_INTEGRITY_MODE` (`on` default in `_run_live_eval`) |
| lanes | presence of `--semantic-mode live` vs `offline` in semantic args |
| timeout | `GDDP_PI_RPC_TURN_TIMEOUT_S` is **executor**, not evaluator — do not show it as an evaluator knob. Evaluator timeouts live on `cli.py` as `--semantic-max-turns` / env `GDDP_SEMANTIC_MAX_TURNS` (default 15). Surface those if we expose them; otherwise omit rather than lie. |
| key source | `GDDP_DEEPSEEK_KEY_CMD` |
| settings file | `SETTINGS_FILE` = `ROOT / "runtime" / "settings.env"` |
| base default | `_auto_base_commit` (`HEAD~1` else `HEAD`) — computed, not stored |

### Instructions lens (from a receipt, after a run)

| Shown | Receipt field |
|---|---|
| Offered canonical pointers | `canonical_context: dict[str, str]` keys observed live: `readme`, `project_brief`, `foundational_node`, `neighbor:<node_id>`. Values are paths or `UNAVAILABLE: ...`. |
| Criteria offered-vs-read | `context_coverage.criteria` — either `"not_run"` or `LaneCoverage`: `rating`, `offered`, `content_accessed`, `not_observed`, `accessed_paths[]`, `not_observed_paths[]` |
| Integrity offered-vs-read | `context_coverage.integrity` (always a `LaneCoverage`) |
| Overall rating (secondary) | `context_coverage.overall` (`none`/`low`/`medium`/`high`) — show last, never instead of the file lists |
| Node contract | **Not in the receipt as a blob.** Reconstruct from `graphs/<project>/nodes/<node>.yaml`: `why`, `acceptance_criteria[]` (`id`+`criterion`), `constraints[]`. Cross-check ids against `deterministic.criteria[].id`. |
| Project vision | `graphs/<project>/project.yaml` `blueprint.vision` + `blueprint.architecture_notes` |
| Deterministic evidence | `deterministic.criteria[]` (`id`, `status`, `confidence`, `method`, `evidence`, `reasoning`, `mismatch_kind`); `deterministic.criteria_mismatches[]`; `deterministic.artifacts_present`; `deterministic.subject_diff` (`status`, `base`, `tip`, `files[]`, `file_count`) |
| Semantic reasoning | `semantic.overall_reasoning`, `semantic.judgments[]`, `decision_reasoning` |

**Display rule for paths:** live `accessed_paths` contain ephemeral worktree
prefixes (`/var/folders/.../gddp-eval-wt-XXXX/README.md`). Render
basename + a short tag (`README.md  (worktree)`) so the view is human, not
a temp-path dump.

### Instructions lens (preflight, no receipt)

Assemble without running the judge:

- Node/project YAML as above.
- Offered pointers only: call is in gddp-runtime
  (`semantic/context_builder.build_canonical_pointers`). **Do not import
  gddp-runtime from gddp.py.** Reimplement the pointer list locally
  (`_offered_canonical_pointers(project, node_id, repo)`) matching the
  documented keys: README / PROJECT-BRIEF / first `project.yaml` node /
  `depends_on`+`unlocks` neighbors. Mark missing `UNAVAILABLE:`.
- No `accessed_paths` until a run exists. Label the view
  `preflight — offered only`.

### Runs / show lens

| Shown | Field |
|---|---|
| when | `evaluation_timing.finished_at` else `generated_at` |
| verdict | `verdict` (combined). Also keep `criteria_verdict`. |
| confidence | `criteria_confidence` |
| wall / tool calls | `evaluation_timing.wall_s`; `evaluation_timing.criteria.tool_calls` / `.integrity.tool_calls`; lane `status` + `elapsed_s` |
| commit evaluated | `evaluated_commit_sha` |
| base | `expected_base_commit_sha` |
| job | `job_id` |
| integrity verdict | `integrity.verdict`, `integrity.intent_preserved`, `integrity.reasoning` |
| model / knobs | **sidecar only** until A2 (`<same-stem>.knobs.json`) |
| next action | `required_next_action` |

Reuse `evaluations.load_evaluation_rows` + filter `project_id`/`node_id`.
Do not write a third receipt walker. Extend `_row_from_check` later if we
want model on the `gddp evaluations` one-liner — out of Increment B's
critical path; the hub can join the sidecar itself.

---

## 3. Increment A — one entry + run knobs + sidecar

**Goal:** one runner with overridable knobs; knobs recorded without touching
gddp-runtime. Names start collapsing. Hub comes in B.

### Functions to add/modify in `scripts/gddp.py`

| Fn | Change |
|---|---|
| `_EVAL_PRESETS` (const) | `{"cheap": "deepseek-v4-flash"}`. `expensive` resolved from env `GDDP_EVAL_MODEL_EXPENSIVE` or unset (error if used). Do not invent a frontier id. |
| `_resolve_eval_knobs(*, model, thinking, integrity, lanes, base)` **new** | Precedence: explicit args → env/`settings.env` → `DEFAULT_SEMANTIC_ARGS` / `GDDP_INTEGRITY_MODE`. Accept preset name or raw model id. Return a dict `{model, preset, thinking, integrity, lanes, semantic_args}`. |
| `_run_live_eval(project, node_id, base=None, knobs=None)` | Keep signature compatible (`base` stays positional). If `knobs` is None, resolve defaults. Build `cli.py` argv from `knobs["semantic_args"]` + `--integrity` + `--base` (same as today). Capture `job_id` (already generated as `manual-<utc>`). After `cli.py` returns, call `_write_eval_knobs_sidecar`. Print model on the compact summary (`model : cheap/deepseek-v4-flash`). |
| `_write_eval_knobs_sidecar(receipt_dir, project, node_id, job_id, attempt, knobs)` **new** | Write `verification/<project>/<node>/<job_id>-attempt<N>.knobs.json`. Best-effort; never fail the eval if write fails (warn). |
| `_load_eval_knobs_sidecar(receipt_path)` **new** | Sibling `*.knobs.json` next to a receipt path (same stem). Return dict or `{}`. |
| `cmd_eval` | Still default-runs when first token is a node id. Add flags: `--model`, `--thinking`, `--integrity {on,off}`, `--lanes {live,deterministic}`. Pass resolved knobs into `_run_live_eval`. |
| argparse near `:5086` | Keep `eval_p` positional `node` for the default run. Add the four flags. Subcommands land in B (`eval config` etc.) — if we add them in A, use a dispatcher: first token in `{config,instructions,runs,show}` is a subcommand, else a node id. Recommend adding the dispatcher in A so B does not rewrite argparse twice. |
| `interactive_evaluate` / node `v` | **A does not yet open a hub.** They keep calling `_run_live_eval` (now with default knobs). Relabel node `v` copy from `"verify now"` → `"evaluate"` (`run the live judge — same path as gddp eval`). Front-page `e` label stays `"evaluate"`. |

`cmd_verify_node` stays as the weak/offline path. Do not merge it.

### Menu keybindings after A

Unchanged structurally:

- Front `e` → `interactive_evaluate` (still pick + run)
- Front `c` → `interactive_config` (write settings)
- Node `e` → current-job evidence (unchanged)
- Node `v` → `_run_live_eval` (relabeled)

### Tests (A)

Extend `EvalWiringTests` in `scripts/test_gddp.py`:

1. `test_run_live_eval_passes_model_override` — knobs `model="cheap"` → cmd contains `--semantic-pi-model deepseek-v4-flash`; sidecar write mocked/asserted.
2. `test_run_live_eval_passes_thinking_and_integrity_off` — `--semantic-thinking high`, `--integrity off`.
3. `test_run_live_eval_lanes_deterministic` — `--semantic-mode offline`, no `--semantic-harness pi` (or present but mode offline). Integrity off unless explicitly on.
4. `test_resolve_eval_knobs_preset_vs_raw_id`.
5. `test_cmd_eval_forwards_knob_flags` — `SimpleNamespace` with the new attrs; assert `_run_live_eval` kwargs.
6. Update `test_node_review_offers_verify_now_action` → expect label `"evaluate"` (or keep `"verify now"` if we delay the rename; pick one and test it).
7. `test_load_eval_knobs_sidecar_missing_is_empty`.

Keep existing command-construction assertions (`--semantic-mode live`,
`--semantic-harness pi`, `--integrity on`, `manual-` job id).

---

## 4. Increment B — the three lenses

**Goal:** `e` / `v` / `gddp eval` become one *surface*, not three triggers.

### Functions to add in `scripts/gddp.py`

| Fn | Role |
|---|---|
| `interactive_eval_hub(project, node_id)` **new** | The surface. Renders a one-line status (latest verdict + model + when) then `_menu_choice` on `_eval_hub_actions()`. |
| `_eval_hub_actions()` **new** | See keybindings below. |
| `interactive_evaluate` | After node pick, call `interactive_eval_hub` instead of `_run_live_eval`. |
| `_node_review_menu` `v` | Call `interactive_eval_hub(project, node_id)` instead of `_run_live_eval`. |
| `_render_eval_config()` **new** | Read-only resolved settings (table). Not the writer — `interactive_config` stays the editor. |
| `_render_eval_instructions(project, node_id, receipt=None)` **new** | If `receipt` is None, load latest for that node; if none, preflight. Print: node contract, blueprint vision, deterministic evidence (if receipt), then offered-vs-read file lists. |
| `_offered_vs_read_lines(canonical_context, context_coverage)` **new** | Pure formatter. Input = receipt dicts. Output = the three-line block from the spec, with basename display. |
| `_offered_canonical_pointers(project, node_id, repo)` **new** | Preflight offered set. Local reimplementation; do not import gddp-runtime. |
| `_load_receipts_for_node(project, node_id)` **new** | `evaluations.load_evaluation_rows(*_evaluation_sources())` filtered. Attach sidecar knobs onto each row. |
| `_render_eval_runs(project, node_id)` **new** | Paged list via `_pick_list`. Columns: when, verdict, model, wall, commit[:8]. Enter → `_render_eval_show`. |
| `_render_eval_show(row)` **new** | Full drill-in: verdicts, timing, knobs, offered-vs-read, deterministic criteria table, integrity reasoning, receipt path. |
| `_eval_knob_picker(current)` **new** | Tiny `_menu_choice` / `Prompt.ask` to set model/thinking/integrity/lanes/base for the **next** hub run. Stored in hub-local dict, not settings.env (per-run). |

Shell dispatcher (if not done in A):

```
gddp eval config
gddp eval instructions <node> [--project] [--run <job_id>]
gddp eval runs <node> [--project]
gddp eval show <job_id-or-path>
gddp eval <node> [--project] [--model ...]   # run, unchanged
```

`cmd_eval_config` / `cmd_eval_instructions` / `cmd_eval_runs` /
`cmd_eval_show` are thin wrappers over the render fns (print, no getch).

### Menu keybindings after B

**Eval hub** (`interactive_eval_hub`) — this is the one surface:

| key | name | meaning |
|---|---|---|
| `r` | run | `_run_live_eval` with hub knobs, then re-render status |
| `k` | knobs | per-run overrides for the next `r` (not persisted) |
| `c` | config | resolved settings (read-only) |
| `i` | instructions | prompt context + offered-vs-read (latest receipt, or preflight) |
| `h` | history | runs list for this node |
| `s` | show | drill into selected / latest run |
| `b` | back | return |
| `q` | quit | `_MENU_QUIT` |

**Front page** (unchanged letters, new behavior for `e`):

| key | name | meaning |
|---|---|---|
| `e` | evaluate | pick graph/node → **hub** |
| `c` | config | existing writer (`interactive_config`) |

**Node review:**

| key | name | meaning |
|---|---|---|
| `e` | evaluation | **keep** current-job evidence (`cmd_show view="evaluation"`) |
| `v` | evaluator | **hub** for this node (replaces fire-and-forget) |

**Graph hub:** optional, not required this pass. If cheap, add `e` →
`interactive_eval_hub` after a node pick; otherwise leave under front-page `e`.

Do not steal node `e`. The spec's "collapse evaluate / verify now / gddp eval"
refers to the *trigger* trio, not the existing evidence view.

### Tests (B)

1. `test_eval_hub_displayed_letters_are_handled` — same contract as
   `test_front_page_displayed_letters_are_handled` (`_letter_keys` ==
   `_handled_letter_keys`, expected `{"r","k","c","i","h","s","b","q"}`).
2. `test_node_review_v_opens_hub` — patch `interactive_eval_hub`, press `v`,
   assert hub called with `(project, node_id)` and `_run_live_eval` not called
   directly.
3. `test_interactive_evaluate_opens_hub` — after a fake node pick, hub called.
4. `test_offered_vs_read_formats_lane_files` — fixture dict copied from the
   live node-05 receipt shape; assert `README.md` / `PROJECT-BRIEF.md` appear
   as read on criteria, neighbors as not-observed; no raw `/var/folders` dump.
5. `test_offered_vs_read_handles_criteria_not_run`.
6. `test_load_receipts_for_node_joins_sidecar`.
7. `test_cmd_eval_instructions_without_receipt_is_preflight` — no
   `accessed_paths` section.
8. `test_cmd_eval_runs_filters_to_node`.
9. `test_cmd_eval_config_prints_resolved_model`.

**Pty smoke** (`/tmp/gddp_tui_smoke.py` pattern, optional move to
`scripts/test_gddp_tui_eval.py` later — not required to land B):

- Wait for help line `esc back` before sending keys (cbreak/`TCSAFLUSH`).
- Scenario: `e` → pick first graph/node if needed is heavy; prefer opening
  via a helper that jumps to hub in tests. Interactive pty: `e` should
  eventually show hub letters `r/k/c/i/h`. Hard timeout, poll `waitpid`.
- Do not block Increment B on the pty driver.

---

## 5. Increment C — preset config

**Goal:** named presets are one token, menu and shell stay in sync.

### Changes

| Site | Change |
|---|---|
| `SETTINGS_FIELDS` | Add `GDDP_EVAL_MODEL_CHEAP` (default display `deepseek-v4-flash`), `GDDP_EVAL_MODEL_EXPENSIVE` (empty until Sab names it), optionally `GDDP_EVAL_THINKING_DEFAULT`, `GDDP_EVAL_LANES_DEFAULT`. Keep `GDDP_VERIFY_SEMANTIC_ARGS` as the escape hatch / composed argv. |
| `_resolve_eval_knobs` | Read the new keys. `cheap`/`expensive` resolve through them. |
| `interactive_config` | No code change if it already iterates `SETTINGS_FIELDS` (it does, `:3510`). New keys appear automatically. |
| Config lens | Show preset table: `cheap → <id>`, `expensive → <id or UNSET>`. |

Do not put executor keys (`GDDP_PI_RPC_*`) into the eval config lens.
Front-page `c` may still edit both (it already does); the eval `c` lens is
evaluator-only.

### Tests (C)

1. `test_resolve_eval_knobs_expensive_unset_errors` — using `expensive` with
   empty `GDDP_EVAL_MODEL_EXPENSIVE` returns a clear error, does not invent
   a model.
2. `test_resolve_eval_knobs_reads_settings_file` — tmp `SETTINGS_FILE`.
3. `test_front_page_config_still_lists_new_keys` — optional; settings editor
   is Prompt.ask, not getch.

---

## 6. Test plan summary

All new tests go in `scripts/test_gddp.py` unless noted.

**Harness to copy:** `OverviewTests._menu_terminal` /
`EvalWiringTests` (`SimpleNamespace(getch=..., clear_lines=...)` +
`patch.object(gddp, "_import_module")` + `Console(file=StringIO, force_terminal=False)`).
Mock `_run_live_eval` / `subprocess.run` — never call a live model in unit tests.

| Increment | Cases |
|---|---|
| A | knob forwarding, preset vs raw id, sidecar write/read, cmd_eval flags, relabeled `v` |
| B | hub letter contract, `v`/`e` open hub not runner, offered-vs-read formatter, preflight, runs filter, config print |
| C | expensive unset, settings-file resolve |

Existing 92 `test_gddp.py` tests stay green. The pre-existing
`test_terminal.py` order flake is out of scope.

Pty smoke is a follow-on, not a gate.

---

## 7. Spec §8 open questions — recommendations

1. **Lens shape.** Keep all three. Instructions is the insight star
   (un-collapsing `context_coverage`), but without Config the knobs are
   invisible and without Runs you cannot compare. Do not demote config/runs
   to footnotes.

2. **Preset ids.** `cheap` = `deepseek-v4-flash` (today's
   `DEFAULT_SEMANTIC_ARGS`). `expensive` = **unset until you name it**
   (`GDDP_EVAL_MODEL_EXPENSIVE`). Do not bind a frontier id in code.

3. **Instructions before vs after.** **After is primary** — offered-vs-read
   only exists post-run (`LaneCoverage.accessed_paths`). Preflight
   (contract + offered pointers, no checkmarks) is the fallback when no
   receipt exists, and an explicit `--preflight` / hub note. Not two
   competing screens.

4. **Doc location.** `gddp-config/docs/` is correct. Spec stays
   `evaluator-management-surface.md`; this file is the implementation plan
   beside it.

---

## 8. Non-goals (reconfirmed)

- No gddp-runtime/`main` edits. No schema change this pass.
- No daemon, queue, or new store. Receipts stay under `verification/`.
- Evaluator never writes graph/node status.
- No executor dispatch/config work.
- Do not touch `graphs/myapi-part2/*` or `verification/*.yaml`.
- Do not import `scripts.runtime.verification` from `gddp.py`.

## 9. Suggested build order

1. A: knobs + sidecar + argparse dispatcher + tests.
2. B: hub + three renderers + reroute front `e` / node `v` + tests.
3. C: preset settings keys + tests.

Stop after each increment with `pytest scripts/test_gddp.py`. Do not merge
to `main`.
