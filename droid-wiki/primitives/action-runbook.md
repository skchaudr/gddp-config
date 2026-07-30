# Action runbook

An action runbook documents a repeatable sequence of human or agent steps for a bounded operational task (for example running validation, exporting a vault, or reconciling a graph). Runbooks live in documentation and handoffs; they are not executable runtime primitives like [jobs](job.md).

## When to author a runbook

Use a runbook when the same procedure is performed across sessions and needs explicit ordering, verification gates, and rollback notes. Pair runbooks with acceptance criteria in node YAML when the procedure implements graph capabilities.

## Structure

A minimal runbook includes: goal, prerequisites, numbered steps with expected outputs, failure handling, and links to the scripts or schemas involved. Prefer linking to `scripts/` entry points rather than duplicating CLI flags.

## Related pages

- [Primitives index](index.md)
- [how-to-contribute/development-workflow.md](../how-to-contribute/development-workflow.md)
- [systems/validation-engine.md](../systems/validation-engine.md)