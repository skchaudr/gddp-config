# Lore

Timeline and history of the gddp-config repository, derived from git commit dates. Dates reflect when commits landed on the main branch. Where interpretation is speculative, hedging language is used.

## Eras

### Era 1: Schema and first graph (2026-03-12 to 2026-03-15)

The repository began on 2026-03-12 with "Phase 1 initial commit, GDAD schema and config repo." The original project name was GDAD (Graph-Driven agentic Development), later renamed to GDDP. The first project graph, `vault-doctor`, was added the same day with its `scan-vault-core` node. Over the next three days, all 7 vault-doctor nodes were completed: `find-duplicates` (2026-03-13, PR #32), `find-stale-todos` (2026-03-13, PR #38), `obsidian-audit` (2026-03-13, PR #41), `check-performance` and `performance-dashboard` (2026-03-14), `return-router` (2026-03-14), and `triage-cli-core` (2026-03-14). A second project graph, `gddp-runtime`, was added on 2026-03-14 with the `return-router` node. OpenClaw nodes were added to the gddp-runtime graph on 2026-03-15.

This was the most rapid feature-delivery period in the repository's history: 7 completed nodes in 3 days.

### Era 2: Normalization and documentation (2026-04-06 to 2026-05-29)

After the initial burst, activity dropped sharply. April saw only 3 commits. The focus shifted from building graphs to structuring the repository for review-driven development. On 2026-04-11, the config repo was "normalized for review-driven runtime boundary." A state and system report handoff was committed the same day.

May brought 8 commits, almost all documentation. On 2026-05-06, the April update transcript was archived. On 2026-05-09, the current graph state was added to the README. On 2026-05-25, runtime graph nodes were renamed to "decision loop" and the runtime verification note was refreshed. On 2026-05-29, `AGENTS.md` was added with a relay block and environment setup, followed by a fix the same day trimming the relay protocol.

### Era 3: Tooling and practice graphs (2026-06-14 to 2026-06-30)

June was the most active month with 40 commits. It began on 2026-06-14 with the Antigravity natural-bounded-autonomy guard. On 2026-06-21, the relay block was trimmed from `AGENTS.md` and the runtime brief was linked.

A tooling burst followed on 2026-06-22: a strict node validator (`scripts/validate.py`), a TUI node scaffold (`scripts/new_node.py`), `scripts/graphify_to_nodes.py` for bootstrapping from graphify graphs, `scripts/enrich_graph.py` for embedding GDDP metadata, and a draft-prompt template. On 2026-06-24, the node status enum was tightened to verdict-only values and acceptance was restructured to keyed entries with stable IDs.

On 2026-06-29, three practice graphs were added in a single day: `aa-cli`, `sell-valuables`, and `album-production`. A node verification harness and sell-valuables evaluation probes were also added that day. On 2026-06-30, the `shape_profile` v1 schema was introduced, harness-redesign nodes were added from the first live loop run, and an ANE edit-surface evaluation node was spiked and then re-scoped to verifier read tooling.

### Era 4: Verification and vocabulary standardization (2026-07-02 to 2026-07-09)

July saw 32 commits focused on verification infrastructure. On 2026-07-02, the verifier receipt contract node was defined, Obsidian vault export was added (and then moved out of the repo to `~/Obsidian/gddp`), and shareable graph bundle exports were introduced on 2026-07-03. On 2026-07-04, evaluator nodes (`pi-evaluator-harness`, `pi-evaluator-guard`, `evaluator-intent-integrity-verdict`, `evaluator-canonical-context`) were added.

Evidence runs began on 2026-07-05. Run-5 on 2026-07-05 achieved pass@0.975. Run-6 on 2026-07-06 was the first auto-triggered evaluation via a return-path bridge. Run-7 on 2026-07-06 achieved the first deterministic `command_proof` pass.

On 2026-07-08, two vocabulary changes landed: the node field `acceptance` was renamed to `acceptance_criteria`, and the project name GDAD was corrected to GDDP across live graph YAML and exports. On 2026-07-08, `graphify-out` and stale handoffs were archived to `_archive/`. On 2026-07-09, the `.vectorcode` local index was gitignored.

## Longest-standing features

- `graphs/vault-doctor/` has been in the repository since the first day (2026-03-12) and retains its original 7-node structure.
- `schemas/v1/node.yaml` and `schemas/v1/job.yaml` have been present since the initial commit and remain the two largest schemas.
- `AGENTS.md` was added on 2026-05-29 and has been the canonical agent instruction file since, updated multiple times but never removed.
- The handoff system (`.handoffs/`) was established on 2026-06-23 with a template and checkpoint policy, and has been in continuous use since.

## Deprecated features

- The relay protocol block in `AGENTS.md` was added on 2026-05-29 and trimmed on 2026-05-29 (same day) and again on 2026-06-21. The relay block no longer exists in its original form.
- `graphify-out/` artifacts were tracked temporarily, then archived to `_archive/` on 2026-07-08.
- The ANE edit-surface evaluation node was added on 2026-06-30 as a spike, then re-scoped the same day to verifier read tooling, suggesting the original design was short-lived.
- The original project name GDAD was deprecated in favor of GDDP on 2026-07-08.

## Major rewrites

- On 2026-03-14, the `return-router` node YAML was rewritten to remove inline dicts that broke the parser. This was an early parser-compatibility fix.
- On 2026-06-24, the acceptance field was restructured from a flat list to keyed entries with stable IDs. This was a structural change to the node schema that affected all graph nodes.
- On 2026-07-08, the vocabulary refactor renamed `acceptance` to `acceptance_criteria` and GDAD to GDDP across all live graph YAML and exports. This touched multiple files simultaneously.

## Growth trajectory

The repository grew from 16 commits in March to 3 in April, then 8 in May, 40 in June, and 32 in July (partial month, data through 2026-07-09). The April dip corresponds to the normalization phase where the repository structure was being settled rather than features added. The June spike marks the transition from graph definition to tooling and practice graphs. July sustained that pace with a shift toward verification infrastructure and evidence runs. The trajectory suggests increasing investment in automated verification rather than graph authoring, though this is speculative based on commit message patterns.
