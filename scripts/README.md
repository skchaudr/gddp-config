# scripts/

Utility scripts for `gddp-config`. Two tools, both standalone Python.

## Setup

Python 3.11+. Scripts need `pyyaml` and `rich`:

```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml rich
```

Or use your system Python if it's not PEP-668-locked.

## validate.py — strict global validator

Walks `graphs/*/nodes/*.yaml` (skips `graphs/_template/`) and checks every
node against `schemas/v1/node.yaml`. Catches schema drift before it ships.

```bash
.venv/bin/python scripts/validate.py                  # human report
.venv/bin/python scripts/validate.py --json           # machine-readable
.venv/bin/python scripts/validate.py --project vault-doctor
.venv/bin/python scripts/validate.py --strict         # warnings -> errors
```

Exit code 1 if any errors. Usable as a pre-commit hook.

The schema constants are mirrored inline from `schemas/v1/node.yaml`. If the
schema changes, update both files.

## new_node.py — TUI scaffold for new node YAML

Interactive, keyboard-driven creator. Modeled on the V4SchemaPass TUI from
`context_refinery`. Writes `graphs/<project>/nodes/<node_id>.yaml` + patches
`project.yaml` (with `.bak` backup).

```bash
.venv/bin/python scripts/new_node.py
```

Keymap:
- Number keys `1-9` — pick from list
- `←`/`→` or `↑`/`↓` — paginate long lists
- `m` — manual text entry
- `s` — skip field
- `q` — quit
- `Enter` — accept default
- `y`/`e`/`q` at review screen — write / edit / quit

Post-write: runs `validate.py` globally. Loud on all findings, but exits
non-zero only if the new node or `project.yaml` regression is the cause.
Pre-existing repo drift won't block the scaffold.

## graphify_to_nodes.py — bootstrap a project from graphify output

Takes any `graphify-out/graph.json` and emits a starter `graphs/<project-id>/`
skeleton. Lifts `depends_on` / `unlocks` edges graphify extracted from your
code; leaves semantic fields (`why`, `acceptance`, `constraints`) as
`REPLACE_ME` placeholders. Best for adopting existing repos into GDDP form.

```bash
.venv/bin/python scripts/graphify_to_nodes.py \
    --input graphify-out/graph.json \
    --project-id my-project \
    --repo org/repo \
    --dry-run
```

Filter modes (default: `smart`):
- `smart` — one node per source_file (collapses functions/classes into their
  containing file) + concept nodes; drops rationale
- `files` — one node per source_file, no concepts
- `documents` — only graphify `file_type=document`
- `all` — every graphify node (noisy)

Always run with `--dry-run` first to inspect the plan. Add `--force` to
overwrite an existing project dir. Cap output size with `--max-nodes 20`.

**What it cannot infer:** `why`, `acceptance`, `constraints` are human-only.
The tool gives you the edge skeleton; you fill in execution semantics.

## terminal.py — ported from context_refinery

Single keypress reader with arrow-key decoding. Pure stdlib (`tty`,
`termios`) + `rich`. Verbatim port of the battle-tested original.
