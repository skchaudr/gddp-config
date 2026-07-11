# Testing

This repo has limited test coverage. The validator itself is the primary quality gate. There are two test files in `scripts/` that exercise specific tooling, and the deterministic verifier acts as a separate test layer for acceptance criteria.

## What tests exist

### Compliance tests (`scripts/test_compliance.py`)

`scripts/test_compliance.py` tests `batch_fill.py` bug fixes using simulated keystrokes and a fake input queue. It exercises four test cases:

| Test | What it checks |
|---|---|
| `test_refuses_empty_acceptance` | Empty acceptance_criteria produces no file write and an error message (VAL-CLI-001) |
| `test_prints_validation_findings` | Validation findings (OK/ERROR/WARN) are printed after a successful write (VAL-CLI-002) |
| `test_edit_handler_scopes_single_field` | The edit handler modifies only the named field, preserving the others (VAL-CLI-003) |
| `test_filled_node_passes_validation` | A node filled and written via batch_fill passes `validate.py` with zero errors (VAL-CLI-010) |

The test creates a temporary project root, monkeypatches `batch_fill.getch` and `batch_fill.getline` with scripted queues, and calls `validate.run()` to verify schema compliance. No real terminal interaction is needed.

### CLI tests (`scripts/test_batch_fill_cli.py`)

`scripts/test_batch_fill_cli.py` is an end-to-end test that drives `batch_fill.py` through a pseudo-terminal (pty). Since `batch_fill.py` reads keystrokes from `/dev/tty`, a plain stdin pipe is ignored. This test allocates a pty, makes it the child's controlling terminal via `pty.fork`, and feeds keystrokes to it. It covers two test cases:

| Test | What it checks |
|---|---|
| `test_filled_node_passes_validation` | A node filled through the real CLI passes `validate.py` with zero errors and no `REPLACE_ME` (VAL-CLI-002 + VAL-CLI-010) |
| `test_refuses_empty_acceptance` | The CLI refuses to write a node with empty acceptance_criteria (VAL-CLI-001) |

The CLI test creates a temporary project in `graphs/`, runs `batch_fill.py` under a pty with scripted keystrokes, strips ANSI codes from the output, and then runs `validate.py --project <name> --json` to confirm zero errors. It cleans up the temporary project afterward.

## How to run tests

Both test files use a simple custom test runner (no pytest or unittest framework). Run them directly:

```bash
.venv/bin/python scripts/test_compliance.py
.venv/bin/python scripts/test_batch_fill_cli.py
```

Each prints `PASS` or `FAIL` per test and a summary line (`N/M tests passed`). Exit code is 1 if any test fails, 0 if all pass.

## The deterministic verifier as a test layer

`scripts/verify_node.py` (invoked via `scripts/gddp.py verify node`) is a deterministic, no-LLM, no-network evaluation tool. It functions as a test layer for acceptance criteria against a project's source repo checkout.

```bash
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core
.venv/bin/python scripts/gddp.py verify node --project aa-cli --node common-core --json
```

Each acceptance criterion id maps to a registered probe (symbol presence, function definition, path existence, etc.). Constraints are scanned for forbidden patterns. The harness produces one of six verdicts: `pass`, `fail`, `blocked`, `needs-human-review`, `needs-more-evidence`, `out-of-scope-change-detected`. Exit code 0 on pass, 1 on any other verdict, 2 on setup error.

Receipts are written to `verification-runtime/` (archived) and `verification-runtime-live/` (current live runs). See [Validation engine](../systems/validation-engine.md) and the [verification harness](../systems/index.md) for more detail.

## The validator as the primary quality gate

The strict global validator (`scripts/validate.py`) is the main quality gate for this repo. It walks every node YAML across all projects (skipping `graphs/_template/`) and checks schema compliance, enum values, cross-references, id/filename matching, kebab-case formatting, list-of-strings integrity, and node id uniqueness. Run it before every commit:

```bash
.venv/bin/python scripts/validate.py          # human report
.venv/bin/python scripts/validate.py --strict  # CI gate: warnings become errors
```

See [Debugging](debugging.md) for common validation errors and how to fix them.

## Related pages

- [Debugging](debugging.md): common validation errors and fixes
- [Tooling](tooling.md): venv setup and scripts package structure
- [Validation engine](../systems/validation-engine.md): how the validator works internally
- [Patterns and conventions](patterns-and-conventions.md): validation patterns
