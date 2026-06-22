# AGENTS.md — gddp-config

Configuration repo for the GDDP pipeline. Contains YAML schemas, rules,
templates, workflows, and graphs. No runtime code — purely declarative.
Companion repo: `gddp-runtime` (the execution engine).

Portfolio brief + system narrative: [`../gddp-runtime/PROJECT-BRIEF.md`](../gddp-runtime/PROJECT-BRIEF.md).

## Project snapshot

- **Language:** YAML / Markdown only — no code to build or test
- **Install:** none
- **Validate schemas:** `python3 -c "import yaml; yaml.safe_load(open('rules/*.yml'))"` (manual)
- **Key dirs:** `rules/`, `schemas/`, `templates/`, `workflows/`, `graphs/`
