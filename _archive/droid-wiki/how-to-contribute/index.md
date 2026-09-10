# How to contribute

gddp-config is a solo-contributor repo (Saboor Khurshid Chaudry) where the default reader is often another agent. Contribution is YAML config authoring, schema maintenance, and Python tooling changes in `scripts/`. There is no runtime code, no build step, and no CI beyond validation.

## Work pickup

Work enters this repo through the agent-driven development workflow defined in `AGENTS.md`. An agent session starts by classifying the repository state (clean, uncommitted, branch divergence), picks up from a handoff in `.handoffs/` if one exists, and executes bounded work. See [Development workflow](development-workflow.md) for the full start-of-session and end-of-session contracts.

## PR process

`main` is protected. No agent can push to `main`. All changes go through a pull request. The human is the only merge authority. This is enforced at the credential layer: agents never receive tokens with write access to this repo. See the [upgrade strategy](../../.handoffs/upgrade-strategy.md) for the rationale.

## Review expectations

The primary quality gate is `scripts/validate.py`, the strict global validator. It must pass with zero errors before any merge. Warnings surface drift (dangling dependencies, asymmetric edges, unknown artifacts) and are acceptable in normal mode but become errors under `--strict`. See [Testing](testing.md) and [Debugging](debugging.md) for what the validator checks and how to fix common issues.

## Definition of done

The end-of-session contract in `AGENTS.md` defines done:

1. Run `scripts/validate.py` (or explain why it could not run).
2. Run `git status --short --branch`. The target is clean and synced with upstream.
3. Commit all intended changes. No staged, unstaged, or untracked task artifacts left behind.
4. Push the working branch. If the task lands on `main`, merge, push, and verify `local main == origin/main`.
5. Leave a handoff in `.handoffs/` if the repo had merges, branch changes, generated artifacts, failing validation, or any state the next agent would need to rediscover.

Do not report completion if uncommitted task changes remain, local commits are not pushed, the branch is diverged, merge conflicts exist, validation failed without a follow-up decision, or generated files are untracked and unclassified.

## Pages in this section

- [Development workflow](development-workflow.md): start-of-session contract, during-work rules, end-of-session contract, PR process
- [Testing](testing.md): test coverage, how to run tests, the deterministic verifier as a test layer
- [Debugging](debugging.md): common validation errors and how to fix them, JSON output, strict mode
- [Tooling](tooling.md): venv setup, scripts package structure, the agent guard system, handoff continuity
- [Patterns and conventions](patterns-and-conventions.md): YAML conventions, graph authoring, validation patterns, branch and PR policy

## Related pages

- [Project overview](../overview/index.md): what this repo is and why it exists
- [Getting started](../overview/getting-started.md): install, validate, scaffold
- [CLI tooling](../systems/cli-tooling.md): the gddp.py unified CLI reference
- [Validation engine](../systems/validation-engine.md): how the validator works internally
