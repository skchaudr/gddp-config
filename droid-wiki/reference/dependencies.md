# Dependencies

`gddp-config` is intentionally minimal. There are two external Python dependencies and one Python version requirement. No runtime code, no build tools, no frameworks.

## External dependencies

| Dependency | Purpose | Required by |
|---|---|---|
| `pyyaml` | YAML parsing for all schema and config files | `scripts/validate.py`, `scripts/gddp.py`, all scripts that read or write YAML |
| `rich` | Terminal output for TUI scripts (colors, panels, prompts) | `scripts/new_node.py`, `scripts/rapid_add.py`, `scripts/batch_fill.py`, `scripts/verify_node.py` |

## Python version

Python 3.11+ is required. Scripts use modern type hints (`from __future__ import annotations`, `str | None` union syntax) and f-string formatting that depend on 3.10+ syntax at minimum. The 3.11 floor provides a stable baseline.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install pyyaml rich
```

Or use the setup script:

```bash
./setup.sh
```

If `pyyaml` is missing, `scripts/validate.py` prints a helpful message and exits. If both `pyyaml` and `rich` are missing, `scripts/gddp.py` prints `Install deps: pip install pyyaml rich` and exits.

## Standard library usage

Beyond the two external packages, scripts use only the Python standard library: `argparse`, `json`, `re`, `sys`, `pathlib`, `dataclasses`, `tempfile`, `pty`, `fcntl`, `select`, `termios`, `struct`, `subprocess`, `shutil`, `os`, `time`. No additional packages are needed for any script in the repo.

## No runtime dependencies

This repo has no runtime code and no runtime dependencies beyond the two packages above. The repo is purely declarative YAML configuration plus a small Python tooling package for validation, scaffolding, and deterministic verification. The execution engine lives in the companion repo.

## Companion repo: gddp-runtime

`gddp-runtime` is the execution engine that reads configs from this repo and dispatches executors (Jules, Codex, Vertex, etc.). The relationship is one-directional:

- `gddp-config` defines what projects are and what done means (schemas, graphs, templates)
- `gddp-runtime` reads those configs, maps events to nodes, creates jobs, dispatches executors, and produces review receipts
- `gddp-runtime` never writes to `gddp-config`. Graph truth stays human-owned.

The system narrative and portfolio brief live at `../gddp-runtime/PROJECT-BRIEF.md` (relative to this repo root).

## Related pages

- [Configuration](configuration.md): how schemas and config files are structured
- [Tooling](../how-to-contribute/tooling.md): venv setup and scripts package structure
- [Architecture](../overview/architecture.md): system design and the config/runtime boundary
- [Getting started](../overview/getting-started.md): install and first commands
