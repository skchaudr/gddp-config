# Fun facts

## The GDAD to GDDP rename

The project was originally called GDAD (Graph-Driven agentic Development). The initial commit on 2026-03-12 says "GDAD schema and config repo." The name persisted for nearly 4 months until 2026-07-08, when a commit titled "fix(vocab): GDAD -> GDDP in live graph YAML and exports" corrected the acronym across all live graph YAML and export files. The rename happened on the same day as the `acceptance` to `acceptance_criteria` field rename, making 2026-07-08 a vocabulary cleanup day. If you see "GDAD" in older commits or archived files, it refers to the same project.

## verify_node.py dwarfs everything else

`scripts/verify_node.py` is 1,549 lines. The next largest Python file, `scripts/new_node.py`, is 652 lines. That means the verification harness is 2.4x larger than the second-biggest script and accounts for 24% of all Python lines in `scripts/`. For a configuration repository with "no runtime code," the verification tooling is the single largest code investment. This may reflect the project's emphasis on deterministic verification, as evidenced by the evidence run commits in early July.

## vault-doctor is about Obsidian vaults

The first and longest-standing project graph, `graphs/vault-doctor/`, is not a medical tool. It is an Obsidian vault auditing CLI. Its 7 nodes scan vaults for duplicates, stale TODOs, performance issues, and plugin configuration problems. The name "vault-doctor" is a metaphor: it diagnoses vaults. The project was complete by 2026-03-14, making it the first fully built graph in the repository.

## TODOs in the codebase are about TODOs

A search for `TODO`, `FIXME`, and `HACK` across Python, YAML, and Markdown files (excluding `_archive/`) returns zero actual TODO markers. All matches are for the string "TODO" appearing in `vault-doctor` node definitions and exports, where "stale TODO identification" is a feature name. The vault-doctor graph is designed to find stale TODO items in Obsidian notes, so the word "TODO" appears throughout its acceptance criteria and descriptions. The codebase has no outstanding TODO or FIXME comments of its own.

## Practice graphs as pedagogical examples

Three practice graphs were added on 2026-06-29: `graphs/aa-cli/`, `graphs/sell-valuables/`, and `graphs/album-production/`. These are not production projects. They appear to be simplified graphs designed to demonstrate GDDP patterns. `aa-cli` is an argument-parsing CLI example. `sell-valuables` is a transactional flow. `album-production` is a creative pipeline. Each has a `project.yaml` and a small set of nodes, making them compact enough to read in one sitting. A semantic walkthrough for `sell-valuables` and `album-production` was committed the same day, suggesting these graphs serve as reference material for how to structure GDDP projects.
