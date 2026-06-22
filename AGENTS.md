# AGENTS.md — gddp-config

Configuration repo for the GDDP pipeline. Contains YAML schemas, rules,
templates, workflows, and graphs. No runtime code — purely declarative.
Companion repo: `gddp-runtime` (the execution engine).

Portfolio brief + system narrative: [`../gddp-runtime/PROJECT-BRIEF.md`](../gddp-runtime/PROJECT-BRIEF.md).

## Project snapshot

- **Language:** YAML / Markdown (primary) + a small `scripts/` Python package (validator + TUI scaffold). No runtime code, no build step.
- **Install:** `python3 -m venv .venv && .venv/bin/pip install pyyaml rich` (for `scripts/` tooling only)
- **Validate schemas:** `.venv/bin/python scripts/validate.py` (strict, global, exits 1 on drift)
- **Scaffold a node:** `.venv/bin/python scripts/new_node.py` (TUI; writes node + patches project.yaml)
- **Key dirs:** `schemas/`, `templates/`, `graphs/`, `scripts/` (active) · `rules/`, `workflows/` (future)
