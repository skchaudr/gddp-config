# scripts/

CLI tools and utilities for `gddp-config`. Entry point: `gddp.py`.

## Setup

Python 3.11+. Scripts need `pyyaml` and `rich`:

```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml rich
```

Or use your system Python if it's not PEP-668-locked.

## gddp.py — unified CLI

```bash
.venv/bin/python scripts/gddp.py node rapid --project my-app --repo org/repo
.venv/bin/python scripts/gddp.py node import --file draft.yaml --project my-app
.venv/bin/python scripts/gddp.py node validate
.venv/bin/python scripts/gddp.py node status
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core
.venv/bin/python scripts/gddp.py obsidian export
.venv/bin/python scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
```

### node subcommands

| Command | What | Keystrokes |
|---|---|---|
| `node rapid` | Minimal-keystroke adder | Type name, Enter, number keys for deps |
| `node new` | Full TUI scaffold (field-by-field editor) | Number keys, m/s/q/Enter |
| `node batch` | Walk through REPLACE_ME nodes | Edit acceptance/constraints/why |
| `node import` | Import YAML from file or stdin | No TUI — JSON output, exit codes |
| `node validate` | Validate all nodes against schema | No TUI |
| `node list` | List nodes in a project | No TUI |
| `node status` | Completion summary for all projects | No TUI |

### obsidian subcommand

| Command | What |
|---|---|
| `obsidian export` | One-way YAML → Obsidian markdown in `obsidian-vault/GDDP/graphs/` |
| `obsidian export --project X` | Export one project only |

YAML stays source of truth. Re-export overwrites generated notes but preserves
frontmatter `verified` and `owned`. Open `obsidian-vault/` as its own vault in
Obsidian; filter Graph View with `path:GDDP/graphs/aa-cli`.

### verify subcommand

| Command | What |
|---|---|
| `verify node --project X --node Y` | Run deterministic evaluation for one node; write `verification/X/Y/result.json` + `transcript.md` |

`verify node` (`scripts/verify_node.py`) is the node evaluation harness:
deterministic, repeatable, no LLM, no network. It maps each acceptance
criterion id to a deterministic check (symbol/function presence in the
referenced source files), scans each constraint for forbidden patterns, checks
the graph dependency context and required artifacts, and emits a transparent
receipt. Semantic evaluation remains a later judgment layer; this command only
records what the deterministic layer can prove.

Source repo resolution: the project's `repo:` field (e.g. `skchaudr/aa-cli`)
resolves to a local checkout in order: `--repo-path`, `$GDDP_REPO_ROOT/<name>`,
or `../<name>` relative to this repo root.

Verdicts: `pass` · `fail` · `blocked` · `needs-human-review` ·
`needs-more-evidence` · `out-of-scope-change-detected`. Exit code 0 on `pass`,
1 on any other verdict, 2 on setup error (missing node/project).

```bash
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core --json
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core --repo-path /path/to/aa-cli
```

### project subcommands

| Command | What |
|---|---|
| `project new --project-id X --repo Y` | Create empty project shell |
| `project new --from-outline outline.md --project-id X --repo Y` | Bootstrap from markdown outline |
| `project new --from-graphify graph.json --project-id X --repo Y` | Bootstrap from graphify AST output |
| `project validate` | Check project.yaml integrity |

## rapid_add.py — minimal-keystroke node adder

Designed for hand preservation. Most interactions are single keypresses.

```bash
.venv/bin/python scripts/gddp.py node rapid --project my-app --repo org/repo
.venv/bin/python scripts/gddp.py node rapid --project my-app --llm-draft   # hybrid mode
```

Flow: type short name → Enter → auto-kebab → pick deps with number keys → next node. Blank line = done. No markdown, no YAML.

## import_node.py — agent pipeline node import

For agent-assisted workflows. Accepts YAML, validates, writes, patches.

```bash
.venv/bin/python scripts/gddp.py node import --file draft.yaml --project my-app
echo '<yaml>' | .venv/bin/python scripts/gddp.py node import --stdin --project my-app
.venv/bin/python scripts/gddp.py node import --file draft.yaml --project my-app --dry-run
```

Returns JSON findings on stdout. Exit codes: 0=imported, 1=validation errors, 2=exists, 3=project not found.

## new_node.py — full TUI scaffold

Field-by-field interactive editor. Number keys, paginated pickers, review screen.

```bash
.venv/bin/python scripts/new_node.py
```

## batch_fill.py — walk through REPLACE_ME nodes

Sequential field-by-field fill for nodes with placeholder values.

```bash
.venv/bin/python scripts/gddp.py node batch --project my-app
```

## outline_to_nodes.py — markdown outline to project skeleton

Converts a markdown checklist with dependency arrows into node YAMLs.

```bash
.venv/bin/python scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
```

Outline format:
```markdown
- [ ] node-name
- [ ] dependent-node -> node-name
- [ ] multi-dep -> node-a, node-b
```

## validate.py — strict global validator

Walks all node YAMLs, checks schema compliance, enum values, cross-references.

```bash
.venv/bin/python scripts/validate.py                  # human report
.venv/bin/python scripts/validate.py --json           # machine-readable
.venv/bin/python scripts/validate.py --project vault-doctor
.venv/bin/python scripts/validate.py --strict         # warnings -> errors
```

## graphify_to_nodes.py — bootstrap from graphify AST output

Extracts a graph skeleton from code, creates project nodes. Best for brownfield adoption.

```bash
.venv/bin/python scripts/graphify_to_nodes.py \
    --input graphify-out/graph.json \
    --project-id my-project \
    --repo org/repo \
    --dry-run
```

## llm_draft.py — LLM-assisted field drafting (stub)

Drafts `why`, `acceptance`, `constraints` via LLM. Used by `node rapid --llm-draft`.

Env vars: `GDDP_LLM_PROVIDER` (deepseek|openai|anthropic|ollama), `GDDP_LLM_API_KEY`, `GDDP_LLM_MODEL`.

## enrich_graph.py — add GDDP metadata to graphify output

Post-processes graphify output with node semantics for visualization.

## terminal.py — shared keypress helper

Single keypress + arrow key decoding. Used by all TUI scripts.
