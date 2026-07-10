# Getting started

## Prerequisites

- Python 3.11+
- `pyyaml` and `rich` Python packages (installed in the venv below)

## Setup

```bash
cd gddp-config
python3 -m venv .venv
.venv/bin/pip install pyyaml rich
```

Or use your system Python if it is not PEP-668-locked.

## Validate graphs

The strict global validator checks every node YAML against the schema:

```bash
.venv/bin/python scripts/validate.py                 # human report
.venv/bin/python scripts/validate.py --json          # machine-readable
.venv/bin/python scripts/validate.py --project vault-doctor  # one project
.venv/bin/python scripts/validate.py --strict        # warnings as errors
```

Exit code 1 means errors. The validator checks schema compliance, enum values, cross-references (depends_on/unlocks symmetry), node_id/filename matching, and kebab-case conventions.

## Scaffold a new node

Two options:

**TUI scaffold** (field-by-field editor):

```bash
.venv/bin/python scripts/new_node.py
```

**Rapid adder** (minimal keystrokes, designed for hand preservation):

```bash
.venv/bin/python scripts/gddp.py node rapid --project my-app --repo org/repo
```

Both write the node YAML file and patch the project's `project.yaml` index (with `.bak` backup). Post-write, `validate.py` runs automatically.

## Create a new project

```bash
# Empty shell
.venv/bin/python scripts/gddp.py project new --project-id my-app --repo org/repo

# From a markdown outline
.venv/bin/python scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo

# From graphify AST output (brownfield adoption)
.venv/bin/python scripts/gddp.py project new --from-graphify graph.json --project-id my-app --repo org/repo
```

Or manually:

```bash
cp -r graphs/_template graphs/<project-id>
# edit graphs/<project-id>/project.yaml
# add node files to graphs/<project-id>/nodes/
```

## Run the verifier

The deterministic node evaluation harness checks acceptance criteria against the source repo:

```bash
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core --json
```

Source repo resolution: the project's `repo:` field resolves to a local checkout at `--repo-path`, `$GDDP_REPO_ROOT/<name>`, or `../<name>` relative to this repo root.

## Check project status

```bash
.venv/bin/python scripts/gddp.py node status    # all projects
.venv/bin/python scripts/gddp.py node list --project aa-cli  # one project
```

## Branch protection

`main` is protected. No agent can push to `main`. All changes go through a PR. The human is the only merge authority. See [Development workflow](../how-to-contribute/development-workflow.md) for the PR process.
