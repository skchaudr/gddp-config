# Graph Report - gddp-config  (2026-06-24)

## Corpus Check
- 30 files · ~33,321 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 414 nodes · 613 edges · 36 communities (29 shown, 7 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `evaluate_pre_tool_use()` - 13 edges
2. `scripts/` - 13 edges
3. `gather_fields()` - 11 edges
4. `main()` - 11 edges
5. `edit_one_field()` - 10 edges
6. `getch()` - 10 edges
7. `README Document` - 10 edges
8. `ToolGateTests` - 9 edges
9. `main()` - 9 edges
10. `gddp-config` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Changelog Document` --references--> `Artifact Verification Schema v1.0`  [EXTRACTED]
  CHANGELOG.md → schemas/v1/artifact_verification.yaml
- `Changelog Document` --references--> `Event Schema v1.0`  [EXTRACTED]
  CHANGELOG.md → schemas/v1/event.yaml
- `Changelog Document` --references--> `Job Schema v1.0`  [EXTRACTED]
  CHANGELOG.md → schemas/v1/job.yaml
- `Changelog Document` --references--> `Node Schema v1.0`  [EXTRACTED]
  CHANGELOG.md → schemas/v1/node.yaml
- `Changelog Document` --references--> `Queue Record Schema v1.0`  [EXTRACTED]
  CHANGELOG.md → schemas/v1/queue_record.yaml

## Import Cycles
- None detected.

## Communities (36 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.15
Nodes (17): AGENTS Document, April Update Transcript, Decision Loop Review Gate Node, Decision Loop Runtime Node, Decision Loop Spec Node, First Overnight Run, GDDP_CONFIG_PATH Environment Variable, GDDP Config Repository (+9 more)

### Community 1 - "Community 1"
Cohesion: 0.21
Nodes (14): Artifact Verification Schema v1.0, Branch Protection, Changelog Document, Credential Isolation Policy, Event Schema v1.0, Graph-Driven Agentic Development System, Job Schema v1.0, Node Schema v1.0 (+6 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (8): _init_repo(), PasteMarkerTests, ToolGateTests, audit_obsidian_config(), is_obsidian_running(), LiveDashboard, Perform an audit of the .obsidian configuration directory., Check if Obsidian is currently running.

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (37): Any, Path, audit(), _checkpoint_marker(), classify_command(), _contains_auth_verb(), _contains_negation(), _decision() (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (32): edit_list_items(), edit_one_field(), gather_fields(), gather_inspiration_bullets(), list_node_ids(), list_projects(), main(), manual_text() (+24 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (29): 1. System Topology, 2. Repo Reality, 3. GDAD Runtime Shape, 4. Project Graph Status, 5. VM State, 6. Workstream Status, 7. Key Identifiers, ACTION_PACKET_HANDOFF (+21 more)

### Community 6 - "Community 6"
Cohesion: 0.64
Nodes (8): Check Performance Node, Find Duplicates Node, Find Stale TODOs Node, Obsidian Audit Node, Performance Dashboard Node, Scan Vault Core Node, Triage CLI Core Node, Vault Doctor Project Graph

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (17): Current state, Design decisions made this session (do not undo without asking), Environment, Files created/modified this session, Goal, Gotchas, Handoff: GDDP Node + Graph Pipeline — Next Session, Next phase: Start creating nodes and graphs (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (15): batch_fill.py — walk through REPLACE_ME nodes, enrich_graph.py — add GDDP metadata to graphify output, gddp.py — unified CLI, graphify_to_nodes.py — bootstrap from graphify AST output, import_node.py — agent pipeline node import, llm_draft.py — LLM-assisted field drafting (stub), new_node.py — full TUI scaffold, node subcommands (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.27
Nodes (14): cmd_node_batch(), cmd_node_import(), cmd_node_list(), cmd_node_new(), cmd_node_rapid(), cmd_node_status(), cmd_node_validate(), cmd_project_new() (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (14): build_edge_maps(), filter_nodes(), main(), make_node_dict(), Pick which graphify nodes become our nodes., Return (depends_on_map, unlocks_map): graphify_id -> list of graphify_ids., Build a node dict with REPLACE_ME placeholders for human-only fields., Mirror templates/node-template.yaml field order. (+6 more)

### Community 18 - "Community 18"
Cohesion: 0.30
Nodes (13): ensure_project_shell(), kebab_to_title(), list_existing_nodes(), main(), make_node_dict(), patch_project_yaml(), pick_deps(), Path (+5 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (11): 000 — *Session Name / Stopping Point*, Artifacts (Filepath - Description, 1 line max per artifact), Current Git state (2-3 sentences max, anything more must be critically justifiable), Empirical Reality (2-3 sentences max, anything more must be critically justifiable), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (11): 002 — Build the First Real Graphs, Artifacts, CLI Quick Reference, Critical Rules (carry into next session), Current Git state, Current Schema Contract, Empirical Reality, Environment (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (11): 003 — Practice Graphs & Running the Loop, Artifacts, Current Git state, Empirical Reality (2-3 sentences max), Friction experienced or anticipated, Intent going into/at start of session, Interpretation of how the session went, Narrative / Trajectory (SAB ONLY) (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.36
Nodes (11): cross_node_findings(), Finding, iter_node_files(), main(), Path, Check depends_on/unlocks references within a project., Yield (project_id, file_path) pairs., render_human() (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.40
Nodes (10): edit_list_items(), fill_node_fields(), gather_inspiration_bullets(), list_node_ids(), main(), manual_text(), needs_batch(), Path (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.36
Nodes (10): enrich_graph(), enrich_node(), is_node_yaml(), is_project_yaml(), load_yaml(), main(), Any, Path (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.20
Nodes (9): Current state (post-hygiene), gddp-config, gddp-runtime, Gotchas, Handoff for Pi README Agent, Pi agent deliverables, Portfolio framing (Pi agent voice — quote verbatim), Project identity (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.20
Nodes (9): Branch Protection, Core Principle, Creating a New Project, Current Graph State, gddp-config, Node Tooling, Related, Schema Index (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.44
Nodes (9): check_conflicts(), check_deps_exist(), import_node(), main(), patch_project_index(), Path, Validate a parsed YAML dict against the node schema. Returns findings list., validate_node_yaml() (+1 more)

### Community 28 - "Community 28"
Cohesion: 0.33
Nodes (9): kebab_to_title(), main(), make_node_dict(), parse_outline(), Validate and return node_id -> [depends_on] using only known node ids., Parse outline markdown into structured data.      Returns:         {, render_node_yaml(), render_project_yaml() (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (8): Agent-driven development workflow, AGENTS.md — gddp-config, During-work rules, End-of-session contract, Handoff requirement, Not-done triggers, Project snapshot, Start-of-session contract

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (7): [1.0.0] - 2026-03-12, [1.0.1] - 2026-04-07, Added, Changed, Changelog, Notes, Notes

### Community 31 - "Community 31"
Cohesion: 0.43
Nodes (5): draft_fields(), _extract_json(), _load_existing_node_summaries(), _load_project_context(), Path

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (6): Adding a New Executor Adapter, Protecting Against Upstream API Changes, Rollback Procedure, Schema Versioning, Upgrade Strategy, Write Access Control (Credential Isolation)

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (6): Autonomous Chunks, Natural Bounded Autonomy, Paste Markers, Planning, Receipts, Version Control as the Safety Net

### Community 34 - "Community 34"
Cohesion: 0.57
Nodes (6): analyze(), find_cycles(), load_nodes(), main(), print_report(), Path

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (5): After pasting back, Draft-Node Prompt Template, How to use, Inputs (fill these in before sending), System prompt (copy below this line)

## Knowledge Gaps
- **119 isolated node(s):** `Any`, `setup.sh script`, `Paste Markers`, `Planning`, `Autonomous Chunks` (+114 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `getline()` connect `Community 4` to `Community 18`, `Community 23`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Why does `getch()` connect `Community 4` to `Community 18`, `Community 23`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **Why does `Handoff for Pi README` connect `Community 0` to `Community 6`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **What connects `Return (kind, text, start_line) segments where kind is operator|paste.`, `Return the git toplevel for path's directory, or None if not in a repo.`, `Return a short-circuit decision if the write is unsafe, else None to proceed.` to the rest of the system?**
  _153 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.1337126600284495 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.12477718360071301 - nodes in this community are weakly interconnected._