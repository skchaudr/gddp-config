# Graph Report - gddp-config  (2026-07-09)

## Corpus Check
- 55 files · ~79,226 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 666 nodes · 948 edges · 47 communities (46 shown, 1 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 17 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `642a663c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]

## God Nodes (most connected - your core abstractions)
1. `verify()` - 18 edges
2. `scripts/` - 14 edges
3. `evaluate_pre_tool_use()` - 13 edges
4. `normalize_acceptance_items()` - 13 edges
5. `gather_fields()` - 12 edges
6. `edit_one_field()` - 12 edges
7. `main()` - 11 edges
8. `evaluate_criterion()` - 11 edges
9. `Node-by-node: sell-valuables` - 11 edges
10. `Node-by-node: album-production` - 11 edges

## Surprising Connections (you probably didn't know these)
- `draft_fields()` --calls--> `normalize_acceptance_items()`  [INFERRED]
  scripts/llm_draft.py → scripts/acceptance_items.py
- `edit_one_field()` --calls--> `normalize_acceptance_items()`  [INFERRED]
  scripts/new_node.py → scripts/acceptance_items.py
- `gather_fields()` --calls--> `normalize_acceptance_items()`  [INFERRED]
  scripts/new_node.py → scripts/acceptance_items.py
- `main()` --calls--> `normalize_acceptance_items()`  [INFERRED]
  scripts/rapid_add.py → scripts/acceptance_items.py
- `make_node_dict()` --calls--> `normalize_acceptance_items()`  [INFERRED]
  scripts/rapid_add.py → scripts/acceptance_items.py

## Import Cycles
- None detected.

## Communities (47 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (53): check_artifacts(), collect_constraint_files(), CommandRecord, ConstraintCheck, CriterionCheck, CriterionMismatch, decide_verdict(), dependency_status() (+45 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (40): `album-art-design`, album-production, album-production — unclear criteria & missing evidence, `album-release`, `arrangement`, Blueprint, Blueprint, Branch / convergence points (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (37): Any, Path, audit(), _checkpoint_marker(), classify_command(), _contains_auth_verb(), _contains_negation(), _decision() (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.10
Nodes (30): acceptance_has_placeholder(), make_acceptance_item(), normalize_acceptance_items(), Helpers for node acceptance criteria.  Acceptance criteria are human-authored te, slugify_acceptance_id(), edit_list_items(), fill_node_fields(), gather_inspiration_bullets() (+22 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (29): 1. System Topology, 2. Repo Reality, 3. GDAD Runtime Shape, 4. Project Graph Status, 5. VM State, 6. Workstream Status, 7. Key Identifiers, ACTION_PACKET_HANDOFF (+21 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (28): acceptance_text(), edit_list_items(), edit_one_field(), gather_fields(), gather_inspiration_bullets(), list_node_ids(), list_projects(), main() (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (18): batch_fill.py — walk through REPLACE_ME nodes, enrich_graph.py — add GDDP metadata to graphify output, export_graph_bundles.py — create shareable one-file graph exports, gddp.py — unified CLI, graphify_to_nodes.py — bootstrap from graphify AST output, import_node.py — agent pipeline node import, llm_draft.py — LLM-assisted field drafting (stub), new_node.py — full TUI scaffold (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (17): Current state, Design decisions made this session (do not undo without asking), Environment, Files created/modified this session, Goal, Gotchas, Handoff: GDDP Node + Graph Pipeline — Next Session, Next phase: Start creating nodes and graphs (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.25
Nodes (16): cmd_node_batch(), cmd_node_import(), cmd_node_list(), cmd_node_new(), cmd_node_rapid(), cmd_node_status(), cmd_node_validate(), cmd_obsidian_export() (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.20
Nodes (14): build_edge_maps(), filter_nodes(), main(), make_node_dict(), Pick which graphify nodes become our nodes., Return (depends_on_map, unlocks_map): graphify_id -> list of graphify_ids., Build a node dict with REPLACE_ME placeholders for human-only fields., Mirror templates/node-template.yaml field order. (+6 more)

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (14): ensure_vault_scaffold(), export_graph(), format_frontmatter(), iter_graph_nodes(), load_project_meta(), load_receipt_summary(), main(), Path (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (13): 014 — First Live Loop Run: Shakeout, Verification Proof, and Harness Redesign, Addendum (post-session), Artifacts (filepath - description, 1 line max), Chronological Walkthrough (Agent — experiential log, as if you were watching), Current Git state (2-3 sentences max), Empirical Reality (2-3 sentences max), Friction experienced or anticipated, Intent going into/at start of session (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.24
Nodes (3): _init_repo(), PasteMarkerTests, ToolGateTests

### Community 13 - "Community 13"
Cohesion: 0.30
Nodes (13): ensure_project_shell(), kebab_to_title(), list_existing_nodes(), main(), make_node_dict(), patch_project_yaml(), pick_deps(), Path (+5 more)

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (12): drive(), make_placeholder_yaml(), make_project(), Path, Return (exit_code, error_count) for `validate.py --project <p> --json`., VAL-CLI-002 + VAL-CLI-010 via the real CLI., VAL-CLI-001 via the real CLI., Run batch_fill.py under a pty, feed tokens, return ANSI-stripped output. (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.15
Nodes (12): 000 — *Session Name / Stopping Point*, Artifacts (Filepath - Description, 1 line max per artifact), Constrained areas touched (none / list + justification), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (12): 020 - Shareable graph bundles, Artifacts (Filepath - Description, 1 line max per artifact), Constrained areas touched (none / list + justification), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (11): 002 — Build the First Real Graphs, Artifacts, CLI Quick Reference, Critical Rules (carry into next session), Current Git state, Current Schema Contract, Empirical Reality, Environment (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.17
Nodes (11): 003 — Practice Graphs & Running the Loop, Artifacts, Current Git state, Empirical Reality (2-3 sentences max), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (11): 004 — Minimal node verification harness, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (11): 005 — Sell-valuables deterministic evaluation probes, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (11): 015 — Verifier Contract and Portfolio Priorities, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (11): 016 - Verifier Contract Reconciliation, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (11): 017 - Verifier Contract Target, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (11): 019 - Runtime graph reconciliation, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.36
Nodes (11): cross_node_findings(), Finding, iter_node_files(), main(), Path, Check depends_on/unlocks references within a project., Yield (project_id, file_path) pairs., render_human() (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (5): audit_obsidian_config(), is_obsidian_running(), LiveDashboard, Perform an audit of the .obsidian configuration directory., Check if Obsidian is currently running.

### Community 27 - "Community 27"
Cohesion: 0.36
Nodes (10): enrich_graph(), enrich_node(), is_node_yaml(), is_project_yaml(), load_yaml(), main(), Any, Path (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (9): Current state (post-hygiene), gddp-config, gddp-runtime, Gotchas, Handoff for Pi README Agent, Pi agent deliverables, Portfolio framing (Pi agent voice — quote verbatim), Project identity (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.20
Nodes (9): Branch Protection, Core Principle, Creating a New Project, Current Graph State, gddp-config, Node Tooling, Related, Schema Index (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.44
Nodes (9): check_conflicts(), check_deps_exist(), import_node(), main(), patch_project_index(), Path, Validate a parsed YAML dict against the node schema. Returns findings list., validate_node_yaml() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.33
Nodes (9): kebab_to_title(), main(), make_node_dict(), parse_outline(), Validate and return node_id -> [depends_on] using only known node ids., Parse outline markdown into structured data.      Returns:         {, render_node_yaml(), render_project_yaml() (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.22
Nodes (8): Agent-driven development workflow, AGENTS.md — gddp-config, During-work rules, End-of-session contract, Handoff requirement, Not-done triggers, Project snapshot, Start-of-session contract

### Community 33 - "Community 33"
Cohesion: 0.25
Nodes (7): [1.0.0] - 2026-03-12, [1.0.1] - 2026-04-07, Added, Changed, Changelog, Notes, Notes

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (7): Current Ground Truth, Current VM Friction, One-Hour Pickup Path, Stupid-Simple Productive Tasks, Suggested Next Commit Sequence, Verification Runway - 2026-07-01, Verification Understanding Map

### Community 35 - "Community 35"
Cohesion: 0.25
Nodes (7): Agent Section, Design rules enforced, Git state at handoff, Handoff 015 — Obsidian vault export, Next (b) — custom visibility UI, Resume, What shipped

### Community 36 - "Community 36"
Cohesion: 0.57
Nodes (7): build_bundle(), dump_yaml(), find_projects(), load_yaml(), main(), ordered_node_paths(), Path

### Community 37 - "Community 37"
Cohesion: 0.43
Nodes (5): draft_fields(), _extract_json(), _load_existing_node_summaries(), _load_project_context(), Path

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (6): 018 - aa-cli graph hygiene, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Resume point (2-3 sentences max, anything more must be critically justifiable), Scope touched (One file per line, +/- for only what was changed)

### Community 39 - "Community 39"
Cohesion: 0.29
Nodes (6): Adding a New Executor Adapter, Protecting Against Upstream API Changes, Rollback Procedure, Schema Versioning, Upgrade Strategy, Write Access Control (Credential Isolation)

### Community 40 - "Community 40"
Cohesion: 0.29
Nodes (6): Autonomous Chunks, Natural Bounded Autonomy, Paste Markers, Planning, Receipts, Version Control as the Safety Net

### Community 41 - "Community 41"
Cohesion: 0.57
Nodes (6): analyze(), find_cycles(), load_nodes(), main(), print_report(), Path

### Community 42 - "Community 42"
Cohesion: 0.33
Nodes (5): getch(), getline(), Minimal terminal input helpers — single keypress + arrow decode.  Ported verbati, Read one keypress without Enter. Arrow keys decoded to UP/DOWN/LEFT/RIGHT., Read one line of normal text input with a colored prompt.      Uses cbreak mode

### Community 43 - "Community 43"
Cohesion: 0.33
Nodes (5): After pasting back, Draft-Node Prompt Template, How to use, Inputs (fill these in before sending), System prompt (copy below this line)

### Community 44 - "Community 44"
Cohesion: 0.40
Nodes (4): Explicit Non-Goals, Portfolio Graph Priorities - 2026-07-02, Priority Order, Why MyAPI First

### Community 45 - "Community 45"
Cohesion: 0.50
Nodes (3): Agent Section, Do NOT edit this file past this point, Handoff 021 - evaluator three-graph run

## Knowledge Gaps
- **238 isolated node(s):** `Any`, `Path`, `setup.sh script`, `Paste Markers`, `Planning` (+233 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `normalize_acceptance_items()` connect `Community 3` to `Community 5`, `Community 13`, `Community 37`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 13` to `Community 3`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Why does `edit_one_field()` connect `Community 5` to `Community 3`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `normalize_acceptance_items()` (e.g. with `fill_node_fields()` and `review_and_write()`) actually correct?**
  _`normalize_acceptance_items()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Return (kind, text, start_line) segments where kind is operator|paste.`, `Return the git toplevel for path's directory, or None if not in a repo.`, `Return a short-circuit decision if the write is unsafe, else None to proceed.` to the rest of the system?**
  _303 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07686932215234102 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.04878048780487805 - nodes in this community are weakly interconnected._