# GDDP CLI reduction — implementation plan

**Status:** PLAN — not implemented  
**Date:** 2026-09-10  
**Pinned to:** `ba0e528` · `scripts/gddp.py` 6673 lines / 204 top-level defs  
**Repo:** `/home/sab-mini/gddp-config`  
**Do not edit:** inherited dirty `verification/pi-harness-execution/evaluations.yaml` and `verification/vault-doctor/auth-node.json`

This is the execution packet. Three Grok 4.6 read-only audits (modularization, usability, keep/cut) plus the parent session. An implementing agent should be able to start Phase 1 from this file without the originating chat.

`main` is protected. Work on a branch. Human merges.

---

## 0. How to start (any agent)

1. `git status --short --branch`. Classify existing dirt. Do not revert, restage, or “clean” the two `verification/` files above.
2. Read this plan end to end, then `scripts/gddp.py` at the cited functions. Line numbers drift; search the `def` name if a cite is stale.
3. Execute **one phase per PR**. Do not split files in Phase 1. Do not add hub letter `e` in Phase 1.
4. Run tests after each coherent change:

```bash
cd /home/sab-mini/gddp-config
.venv/bin/python -m pytest scripts/test_gddp.py scripts/test_terminal.py scripts/test_fzf_pick.py scripts/test_evaluations.py -q
```

5. Do not run the live TUI from an agent session as the sole verification. Drive `test_gddp.py` with fake `getch`.
6. Leave a `.handoffs/NNN-…md` from `.handoffs/000-template.md` (Agent Section only).

---

## 1. Operator product (do not renegotiate)

Daily path: `gddp` on PATH → graph picker → graph hub → nodes / dispatch / live. Rich columns and evaluator reports stay. Reject + retry stays in the TUI (`x` on node review).

Two hard requirements:

1. Any page that requires free-text typing of a **known value** gets a picker (`_pick_list` / `_paged_menu`, `f` = fzf). Prose reasons may still type after a picker of recent/canned reasons.
2. Any page that currently ends with nothing to do (`_pause`, “press any key”, or “now run `gddp …`”) gets a picker or action menu. `_pause` is allowed **only** after a destructive confirm.

Keep these TTY surfaces intact (do not flatten to shell dumps):

| Surface | Function | Why |
|---|---|---|
| Graph picker | `_pick_graph` `789`, `interactive_menu` `4510` | Front door |
| Graph hub truth block | `_print_graph_truth` `3638` | Nodes / warnings / events before keys |
| Paged node list | `interactive_nodes` `2913`, `_format_node_columns` `1109` | GRAPH / RUNTIME / EVAL / TITLE, `▶running` |
| Node review | `_node_review_menu` `2695`, `_node_review_pick_action` `2537` | `e` verdict, `v` hub, `u` status, `x` reject+retry |
| Verdict pager | `_page_view` `1380`, `_scroll_pause` `1311` | Scroll, `o` editor, `u` still updates |

**Must not break** (existing tests lock these):

- `test_node_columns_align_and_mark_running`
- `test_node_review_offers_reject_and_retry_action`
- `test_reject_and_retry_returns_graph_ready_then_retries_job`
- `test_node_review_v_opens_hub`
- `test_menu_choice_maps_escape_to_back`
- Pager scroll / `u` / `o` (`PagerWrapTests` / `_scroll_pause` cases)

---

## 2. What is true today

Bare `gddp` → `cmd_overview` `5335` → `interactive_menu` `4510`. Esc on the picker opens the plane (`interactive_controls` `4539`: live / heartbeat / config).

Graph hub (`interactive_graph_hub` `3704`) first-class keys: `n` nodes, `d` dispatch, `w` live, `m` more. Evaluations and the evaluator hub are **not** on that row.

Evaluator hub (`interactive_eval_hub` `4383`) keystrokes: **graph → `n` → node → `v`**. That is the only TUI path. `interactive_evaluate` `4443` is an orphan (tests only: `test_interactive_evaluate_opens_hub`). More `e` is `interactive_evaluations` `3262` — a receipt list, not the hub. Node `e` is the verdict pager (`cmd_show view="evaluation"`), not a run.

`_menu_choice` `1822`: Esc → `b` if present, else `q`, else **the default**. Confirms without `b`/`q` therefore treat Esc as yes: dispatch (`_confirm_dispatch` `468`), merge (`_offer_acceptance_merge` `2450`), publish (`_offer_publish_graph_status` `2259`).

`_pause` `1219` swallows every key including Esc (Ctrl-C raises). Watch (`interactive_watch` `5032` → `cmd_watch` `4965`) exits only on Ctrl-C.

`gddp.py` already has siblings. Do not re-implement them: `node_cli.py` 2122, `timeline.py` 594, `frontier.py` 396, `evaluations.py` 196, `terminal.py` 222, `fzf_pick.py` 144, `validate.py` 404, `new_node.py` 662.

`test_gddp.py` (2689) imports `gddp` and patches **private** names (`_paged_menu`, `_menu_choice`, `_run_live_eval`, `interactive_*`). After any split, re-export the old names from `gddp.py` until tests are retargeted.

---

## 3. Target information architecture (after Phase 3)

```
gddp (TTY)
└─ graphs  [_pick_graph]
   ├─ Esc / b → plane
   │    w live-all · h heartbeat · c config · b graphs · q quit
   └─ <graph> hub
        truth: nodes · warnings · recent events
        n  nodes → picker → node review
        │    e  evaluation (verdict pager)     KEEP
        │    v  evaluator hub                  KEEP
        │    x  reject + retry                 KEEP
        │    u  update graph status
        │    m  contract · diff · trace
        d  dispatch
        w  live (this graph)
        e  evaluations                         Phase 3 only
        │    picker of this graph's receipts
        │    row: “evaluate a node…” → hub
        m  more
             j jobs · f frontier · s status · v validate
             t timeline (in-tool pager) · d deliver
```

Do not put knobs/run/config on the graph hub. Hub `e` is receipts first; the hub is one pick away. Node `v` stays.

---

## 4. Navigation contract (all phases)

- Every screen is `_pick_list` / `_paged_menu` or `_menu_choice`.
- Esc = back. `q` = quit.
- `_pause` only after a mutating confirm (reject+retry, status write, dispatch, deliver).
- Free-text `Prompt.ask` only for prose (fix-list, status/job reasons), and then after a picker of recent/canned values when one exists.
- Ban footers whose only next step is a shell command (`full story: gddp timeline {project}` at `3700`; `drill in: gddp watch …` in `cmd_watch`).
- Every confirm that can mutate must register `b` (and usually `n`). Never leave Esc bound to the mutating default.

---

## 5. KEEP / DEMOTE / CUT

| Surface | Verdict | Notes |
|---|---|---|
| Graph picker, hub, nodes, review, reject+retry, verdict pager | KEEP (primary) | Daily |
| Hub `d` dispatch, `w` live | KEEP (primary) | Daily |
| Node `v` evaluator hub | KEEP (primary) | Keep; make findable in Phase 3 |
| More: jobs, frontier, status, validate, deliver | KEEP (secondary) | Already one step down |
| More `e` evaluations list | KEEP (secondary) until Phase 3 | Then fold into hub `e` |
| Plane: live / heartbeat / config | KEEP (secondary) | |
| `gddp node list/show/status/frontier`, `jobs *`, `eval`, `watch`, `timeline`, positional dispatch | KEEP (secondary) | Shell twins |
| `interactive_evaluate` | DEMOTE | Duplicate; tests only |
| `gddp verify node --live` | DEMOTE | Same `_run_live_eval` as `gddp eval` |
| `gddp runs`, `steer`, `receipt`, `jobs adopt` | DEMOTE | CLI/pipeline; not on TUI |
| `gddp node new/rapid/batch/import` | CUT from unified CLI (Phase 3) | Bodies already in other scripts |
| `gddp project new`, `obsidian export` | CUT from unified CLI (Phase 3) | Same |

`node_cli.py` formatting stays. That is the rich output, not fat.

---

## 6. Phase 1 — usability only (first PR)

**Goal:** Kill dead-ends and free-text-of-known-values. No new files. No hub letter `e`. No argparse surgery.

**Files:** `scripts/gddp.py`, `scripts/test_gddp.py` (new/updated fake-getch cases).

### 1a. Dead-end pages → menu or picker

| Function | Today | Change |
|---|---|---|
| `interactive_frontier` `841` | `_show_frontier` then `_pause` `846`/`870`/`879` | After render: `_menu_choice` refresh/back, or `_pick_list` of ready/in-flight/blocked nodes → `_node_review_menu` |
| `interactive_status` `6142` | `show_status` then `_pause` `6147`/`6166`/`6175` | Same: menu, or picker of nodes (graph-scoped) / graphs (`a`) |
| `interactive_validate` `6178` | `validate_project` then `_pause` `6183`/`6202`/`6211` | Picker of failing node ids when errors exist; else refresh/back |
| `_print_graph_truth` `3700` | Footer `full story: gddp timeline {project}` | Drop the CLI string. Add More `t` that `_page_view`s existing `timeline` render (`cmd_timeline` / `timeline.build`). Do **not** add hub `e` here. |
| `cmd_watch` / `_render_fleet` ~`4865`–`4962` | Prints `drill in: gddp watch …`, `tail -F …` | Replace command hints with an in-TUI pick (reuse `cmd_runs` catalog / `_pick_list` of attempts). Esc = back to hub/plane. Ctrl-C must still quit. |
| `interactive_eval_hub` `r/c/i/s` `4416`–`4440` | `_pause` after each lens | `_page_view` or stay on hub menu; Esc/back without `_pause` |
| `_render_eval_runs` `4313` | Empty and after-show `_pause` `4317`/`4342` | Empty → hub menu. After show → `_page_view` then back to the runs picker |
| `interactive_jobs` empty open `3434`–`3439` | `Prompt.ask("job or node ID")` | If no jobs, stay on the jobs menu. Do not ask for a typed id |
| `_paged_menu` empty `2016`–`2020` | `_pause` | Return `_MENU_BACK` |
| Dispatch after-action | `_pause` in `_dispatch_for_project` `965` **and** hub `3728` | One ack, not two. Prefer return to hub with the result still visible |

Ack-after-mutation `_pause` sites may stay: reject+retry `2781`, status write `2901`, batch `1662`/`1739`, job set `3496`, deliver `6132`/`6139`. Esc on those `_pause`s should mean back, not “ignored continue” if you touch `_pause`.

### 1b. Free-text of known values → pickers

| Function | Today | Picker offers | Type-in still? |
|---|---|---|---|
| `_eval_knob_picker` `4346` | 5× `Prompt.ask` | cheap/expensive; thinking enum; integrity on/off; lanes live/deterministic; base auto / recent SHAs | Raw model id and empty/custom SHA as last row |
| `interactive_config` `4476` | Sequential `Prompt.ask` over `SETTINGS_FIELDS` `127`–`172` | Executor enum; integrity; lanes; cheap/expensive model ids | Timeouts, tool allowlist, key cmd after “other” |
| Launchd `interactive_heartbeat` `3933`–`3952` | `Prompt.ask` arm/disarm | Same `_menu_choice` as systemd (`_interactive_heartbeat_systemd` `3875`) | No |
| Reasons: `1610`, `1710`, `2192`, `3236`, `2669` | Bare `Prompt.ask` | Recent reasons + canned (“accepted”, “retrying”, …) | Yes — operator prose, especially reject fix-list |

### 1c. Esc must not mean yes

Add `b`/`n` to every mutating confirm that currently defaults Esc to the destructive action:

- `_confirm_dispatch` `468`
- `_offer_acceptance_merge` `2450` (default today `y`)
- `_offer_publish_graph_status` `2259` (default today `p` = commit+push)

Watch: Esc = back (`interactive_watch` `5032`). Pager: Esc = back even when `b` is PgUp (`_scroll_pause` `1366`).

### 1d. Tests to add or extend

- Frontier / status / validate no longer end on `_pause` as the only exit (fake getch `b` returns `_MENU_BACK`).
- Eval knobs: letter or list pick, not `Prompt.ask` for cheap/expensive.
- Jobs empty open: no `Prompt.ask`.
- Hub footer: string `gddp timeline` absent from `_print_graph_truth` output.
- Esc on dispatch/merge/publish confirm ≠ mutate.
- Existing: `test_eval_hub_getch_run_then_back`, `test_eval_hub_displayed_letters_are_handled`, `test_interactive_watch_keeps_failure_visible`, `test_interactive_status_all_and_one`.

**Phase 1 done when:** no operator path ends on “press any key” except post-confirm; knobs/config/heartbeat enums are pickers; hub footer has no shell command; Esc leaves watch and confirm-no.

**Phase 1 risk:** low. Fake-getch tests are the regression net.

---

## 7. Phase 2 — split `gddp.py`, same UX

**Goal:** `gddp.py` is entry + argparse + re-exports. Behavior unchanged. Do this only after Phase 1 is merged or explicitly stacked.

**Keep in `gddp.py`:** `main` `6292`, `_CLI_COMMANDS` `97`, `_MENU_*` `93`–`95`, `console` `92`, thin `cmd_node_*` wrappers, re-exports of every name `test_gddp.py` patches.

**Move (new files under `scripts/`):**

| File | Move | Approx lines | Risk |
|---|---|---|---|
| `cli_dispatch.py` | `build_dispatch_plan` `289` … `cmd_dispatch` `544` | 420–480 | med — `test_gddp_dispatch.py` imports `gddp.build_dispatch_plan` |
| `cli_watch.py` | `_recorded_attempt_dirs` `4574` … `cmd_steer` `5234` | 650–720 | med — attempt-shape documented in `timeline.py` |
| `cli_eval.py` | knobs + `_run_live_eval` + `cmd_eval*` (`4009`–`4380`, `5483`–`5892`) | 700–850 | med — `EvalWiringTests` patches `gddp._run_live_eval` |
| `cli_heartbeat.py` | `_launchd_status` `3743` … `interactive_heartbeat` `3892` | 210–230 | low |
| `cli_status.py` | `_list_status_projects` `5953` … `show_status` | 180–220 | low |
| `cli_parser.py` | argparse body of `main` | 350–380 | med — keep `gddp.main` |
| `graph_io.py` | project list / YAML / repo resolve | 80–120 | low — do **not** merge the three repo-resolve predicates |

**Do not extract in Phase 2:** `_menu_choice`, `_paged_menu`, `_pick_list`, `_pick_graph`, `interactive_graph_hub`, `_print_graph_truth`, `_node_review_menu`, `_confirm_reject_and_retry`, `interactive_nodes`. Those are the product TTY.

Optional later (not required): `gddp_tui.py` for chrome `988`–`2173` once re-exports are proven.

**Duplication to delete only when a shared helper exists and both tests still pass:**

- `_ellipsize`: `gddp.py:1040` vs `node_cli.py:1052`
- `_ansi` / status colors: `gddp.py:1434` / `999` vs `node_cli.py:940` / `1605`
- Project listing: `_graph_projects` `230`, `_list_status_projects` `5953`, `node_cli.list_project_ids` `128`, `frontier.project_ids` — predicates differ (`_template` skip, `nodes/` required). Preserve behavior; name the variants.
- Repo resolve: `_resolve_project_repo` `2347` (needs `.git`), `_resolve_repo_for_project` `5442` (`is_dir`), `node_cli._resolve_repo_for_project` `65` (`_is_checkout`)

**Phase 2 done when:** `pytest scripts/test_gddp.py scripts/test_gddp_dispatch.py` green; TUI keystrokes unchanged; `gddp.py` roughly 2800–3200 lines.

**Honest size:** interactive path across modules stays ~2800–3800. `test_gddp.py` 2689 stays. This is not a 500-line product.

---

## 8. Phase 3 — find the hub, demote argparse fat

**Goal:** Interactive path is the operator path. Authoring leaves the unified CLI help.

1. `_graph_hub_actions` `3614`: add `e` evaluations → graph-scoped receipt picker (filter `interactive_evaluations` rows by project) + one extra row “evaluate a node…” → existing node picker → `interactive_eval_hub`. Keep node `v`.
2. Remove More `e` (duplicate). Keep More `t` timeline from Phase 1.
3. Drop argparse for `node new/rapid/batch/import`, `project new`, `obsidian` from `main` `6292`. Those scripts remain callable as themselves.
4. `static_overview` `3534`: hide `runs` / `steer` / `receipt` / `jobs adopt` / `verify` (point verify at `gddp eval`).
5. Stop treating `interactive_evaluate` as a peer; keep it as a test helper or delete once `test_interactive_evaluate_opens_hub` is rewritten against hub `e`.

**Phase 3 done when:** `gddp` help is graph / runtime / eval; hub `e` opens receipts without opening the hub first; `gddp node rapid` either still works as a hidden alias or the help tells you `scripts/rapid_add.py`; `test_node_review_v_opens_hub` still passes.

**Risk:** muscle memory for `gddp node rapid`. If you drop the subcommand, say so in the PR body.

---

## 9. Suggested PR sequence

| PR | Branch hint | Scope |
|---|---|---|
| 0 | `docs/gddp-cli-reduction-plan` | This file + handoff. No code. |
| 1 | `fix/gddp-tui-dead-ends` | Phase 1a + 1c (dead-ends, Esc) |
| 2 | `fix/gddp-tui-pickers` | Phase 1b (knobs, config, heartbeat, reasons) |
| 3 | `refactor/gddp-cli-modules` | Phase 2, one module group per commit |
| 4 | `feat/gddp-hub-evaluations` | Phase 3 hub `e` + argparse trim |

If the operator wants a single usability PR, 1+2 may land together. Never combine 2 (split) with 1 (behavior).

---

## 10. Out of scope

- gddp-runtime schema / `verification/cli.py` changes
- Rewriting `node_cli.py` show/list formatting
- Deleting `test_gddp.py` to “save lines”
- Running a long foreground eval from an agent thread (see `AGENTS.md` evaluation rules)
- Graph YAML edits, node status writes, or publishing from this work
- The two inherited dirty verification files

---

## 11. Resume point

Phase 0 is this document. Next implementing agent: branch from current `origin/main`, do Phase 1a on `interactive_frontier`, `interactive_status`, `interactive_validate`, and the hub timeline footer. Stop when those four no longer end on `_pause` / a shell tip. Then continue 1a watch + eval hub pauses, then 1b, then 1c.
