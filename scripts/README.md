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
.venv/bin/python scripts/gddp.py node list --project gddp-runtime --active
.venv/bin/python scripts/gddp.py node show --project gddp-runtime canary-retry-proof
.venv/bin/python scripts/gddp.py node set-status --project gddp-runtime canary-retry-proof ready --yes --reason "ready for dispatch after review"
.venv/bin/python scripts/gddp.py jobs list --state awaiting_review
.venv/bin/python scripts/gddp.py jobs show <job-id> --full
.venv/bin/python scripts/gddp.py jobs results --all
.venv/bin/python scripts/gddp.py jobs set <job-id> awaiting_review --reason "returned for review"
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core
.venv/bin/python scripts/gddp.py obsidian export --project aa-cli
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
| `node list` | List nodes: `ID \| GRAPH \| RUNTIME \| VERDICT` (width-aware) | No TUI |
| `node show` | Node detail + evaluator summary (read-only runtime) | No TUI |
| `node set-status` | Human graph-status change (node + project index); `--reason` required → runtime `node_status_history/` | Confirm unless `--yes` |
| `node status` | Completion summary for all projects | No TUI |

### jobs subcommands

`gddp-config` owns the human-facing `gddp` command. The `jobs` group delegates
to the sibling `gddp-runtime/scripts/node_status.py` CLI, so runtime queue state
and evaluator evidence remain runtime-owned while graph truth remains config-owned.

| Command | What |
|---|---|
| `jobs list [--state S]` | List runtime jobs and queue states |
| `jobs show <job-or-node> [--full]` | Show one job, results, decisions, and evidence |
| `jobs results [--all]` | Summarize evaluator output by project |
| `jobs set <job-or-node> <state> --reason ...` | Change runtime queue state with confirmation and an audit row |

Bare `gddp` opens the unified config-hosted menu in a terminal. Each submenu
clears and redraws as one screen. Its jobs section provides interactive runtime
list/filter/results/detail views, delegating each real command to
`node_status.py`. Redirected bare output prints a non-blocking command overview.
Resolution uses `GDDP_RUNTIME_ROOT`, defaulting
to the sibling `../gddp-runtime`; `GDDP_RUNTIME_PYTHON` can override the runtime
interpreter.

### Stage 1 operator commands

Graph status, runtime queue state, and evaluator verdict stay **distinct**.

```bash
# Active = graph status pending or ready
.venv/bin/python scripts/gddp.py node list --project gddp-runtime --active
.venv/bin/python scripts/gddp.py node list --project gddp-runtime --status ready

# Intent, criteria, deps, graph status + runtime/evaluator summary
.venv/bin/python scripts/gddp.py node show --project gddp-runtime canary-retry-proof
.venv/bin/python scripts/gddp.py node show --project gddp-runtime canary-retry-proof --trace

# Dual-write graph status only (node YAML top-level + matching project.yaml entry)
.venv/bin/python scripts/gddp.py node set-status --project gddp-runtime canary-retry-proof ready --reason "ready for dispatch"
.venv/bin/python scripts/gddp.py node set-status --project gddp-runtime canary-retry-proof complete --yes --reason "accepted after review"
```

- Valid graph statuses: `pending` | `ready` | `complete` | `deferred`
- `set-status` requires `--reason` (stored under runtime `node_status_history/`, not node YAML), previews `old -> new` for both files, confirms unless `--yes`, no-ops without rewrite when already at target
- `node list` uses terminal width (`COLUMNS` / `shutil.get_terminal_size`):
  - **&lt;120 cols:** each node is a blank-line-separated multi-line record — exact `node_id` alone on line 1 (copyable, never truncated); line 2+ carries distinct `GRAPH` / `RUNTIME` / `VERDICT`, then TYPE/TITLE soft-wrapped to width
  - **≥120 cols:** table-like scan; exact ID intact; TITLE is the only truncated field; no emitted line exceeds detected width
- `node show` groups details under `OVERVIEW`, `STATUS`, `INTENT`, `GRAPH`, `DELIVERY CONTRACT`, `EVALUATION`, and optional `TRACE` dividers; graph status, runtime state, and evaluator verdict appear once in `STATUS`
- Writes are surgical (status values only): staged per-file atomic replacements (`os.replace`) with rollback of both originals if either write or post-write validation fails (not a single joint atomic commit of both files)
- Candidates are `yaml.safe_load`ed and id/status-checked **before** any disk write; baseline `validate.py` failures abort cleanly with no write
- Runtime DB: `$GDDP_RUNTIME_ROOT` (default sibling `../gddp-runtime`) `db/queue.db` opened read-only (`mode=ro`); missing DB/receipts print `-` / `no evaluation evidence` and exit 0
- Runtime job without evaluator acceptance/receipt/verdict still shows runtime state and prints `no evaluation evidence`
- Receipt: latest `acceptance_check.receipt_path`, else `verification-runtime-live/<project>/<node>.json`
- Implementation: thin `gddp.py` + `scripts/node_cli.py`; portable launcher: `bin/gddp` (`GDDP_CONFIG_PATH` or `$HOME/repos/gddp-config`)

### obsidian subcommand

| Command | What |
|---|---|
| `obsidian export --project X` | Export one graph → `~/Obsidian/gdd-X/` |
| `obsidian export --project X --vault /path` | Override destination folder |

One graph per run. YAML stays source of truth. Re-export overwrites generated
notes but preserves frontmatter `verified` and `owned`. Open `~/Obsidian/gdd-aa-cli`
as a vault — Graph View shows that project's dependency graph only.

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

## export_graph_bundles.py — create shareable one-file graph exports

Expands each project graph into one YAML file with the project metadata and all
node documents inline. Useful when you want to share a whole graph without the
directory of per-node files.

```bash
.venv/bin/python scripts/export_graph_bundles.py \
    --output-dir exports/shareable-graphs
```

## llm_draft.py — LLM-assisted field drafting (stub)

Drafts `why`, `acceptance`, `constraints` via LLM. Used by `node rapid --llm-draft`.

Env vars: `GDDP_LLM_PROVIDER` (deepseek|openai|anthropic|ollama), `GDDP_LLM_API_KEY`, `GDDP_LLM_MODEL`.

## enrich_graph.py — add GDDP metadata to graphify output

Post-processes graphify output with node semantics for visualization.

## terminal.py — shared keypress helper

Single keypress + arrow key decoding. Used by all TUI scripts.
