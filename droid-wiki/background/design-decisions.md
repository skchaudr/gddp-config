# Design decisions

This page documents the key design decisions behind `gddp-config`, the rationale for each, and when the decision was made or codified. The sources are `README.md`, `AGENTS.md`, `docs/verification-runway-2026-07-01.md`, and `.handoffs/upgrade-strategy.md`.

## Why graph truth is human-owned

The core principle of GDDP is: graphs define projects, agents do not. Nodes in `graphs/` define what a project is, what order it progresses, and what counts as done. The runtime maps events to nodes and dispatches bounded work. It does not invent direction, and it does not mutate graph truth on the return path.

If the runtime could self-certify completion, an agent would evaluate its own work and advance its own graph. This creates a feedback loop where agents rewrite the rules of their own execution. Human ownership of graph truth breaks this loop: the runtime produces evidence (receipts), and a human decides whether to advance.

## Why the return path produces receipts, not auto-advancement

The return path flows from executor result to review receipt to human decision. The runtime produces a result (changed files, acceptance check, risks), creates artifact verification records, and emits a receipt. A human reviews the receipt and decides whether to change node status to `complete`.

The verification runway document (`docs/verification-runway-2026-07-01.md`) identifies four separate questions that a receipt must answer without blending them:

| Question | Owner | Good signal |
|---|---|---|
| Did the code satisfy acceptance criteria? | Runtime verifier | Per-criterion pass/fail with file or command evidence |
| Is the execution trail complete? | Artifact gate | Required artifacts present when required |
| Should graph truth advance? | Human | Evidence PR or explicit review decision |
| What should happen next? | Decision loop / operator | Accept, retry, block, defer, or dispatch next node |

The live bug from handoff 014 was exactly a blended signal: criteria looked like a pass, artifacts were missing, and confidence collapsed even though the semantic judgment was strong. Keeping these questions separate prevents that failure mode.

## Why verification is deterministic-first

`scripts/verify_node.py` is deterministic: no LLM, no network, fully repeatable. Each acceptance criterion id maps to a deterministic check (symbol presence, function definition, path existence, pattern matching). Constraints are scanned for forbidden patterns.

Semantic evaluation (LLM-based judgment) is a separate, later layer. The deterministic layer comes first because:

- It produces transparent, reproducible evidence that a human can audit.
- It does not depend on model availability, cost, or nondeterminism.
- It catches the common case (does the function exist, does the file exist) without reasoning.
- Semantic evaluation can build on top of deterministic findings rather than replacing them.

## Why schemas use YAML, not JSON

Schemas are YAML documents with inline comments that serve as canonical documentation. YAML was chosen over JSON because:

- Comments are first-class. Each schema file is self-documenting with inline explanations of enum values, field semantics, and design intent.
- Human authoring is the primary activity. Node files, project files, and schemas are written and edited by humans. YAML is more readable and less punctuation-heavy than JSON.
- The repo is declarative, not programmatic. There is no need for machine-only interchange formats. YAML is consumed by `pyyaml` at validation time and by humans at authoring time.

## Why the repo has no runtime code

`gddp-config` contains no runtime code. It is purely declarative YAML configuration plus a small `scripts/` Python package for validation, scaffolding, and deterministic verification. The execution engine lives in `gddp-runtime`.

This separation enforces the config/runtime boundary:

- The config repo defines what projects are and what done means. It cannot execute anything.
- The runtime repo reads configs, dispatches executors, and produces receipts. It cannot mutate graph truth.
- Neither repo can do the other's job. The boundary is structural, not conventional.

If runtime code lived in the config repo, the temptation to let configs influence execution directly (or vice versa) would erode the boundary. Physical separation makes the boundary impossible to accidentally cross.

## Why main is branch-protected

`main` is protected. No agent can push to `main`. All changes go through a PR. The human is the only merge authority.

This is enforced at the credential layer, which is stronger than GitHub branch protection alone. Branch protection blocks unauthorized pushes. Credential isolation means agents cannot even attempt a push, because they never receive tokens with write access to this repo.

The rationale from `.handoffs/upgrade-strategy.md`: the config repo defines how agents behave. Agents must not be able to rewrite the rules of their own execution. If an agent could push to `main`, it could modify the schemas, graphs, or guard rules that constrain its own behavior. Credential isolation prevents this at the root.

## Decision summary table

| Decision | Rationale | Date |
|---|---|---|
| Graph truth is human-owned | Prevents runtime from self-certifying completion and rewriting its own rules | Foundational (v1 schemas, March 2026) |
| Return path produces receipts, not auto-advancement | Separates evidence from decision, prevents blended signal failures | Codified in verification runway 2026-07-01 |
| Verification is deterministic-first | Transparent, reproducible evidence before semantic judgment | Verification runway 2026-07-01, hardened in handoffs 015-017 |
| Schemas use YAML, not JSON | Human authoring is primary, comments are first-class documentation | Foundational (v1 schemas, March 2026) |
| No runtime code in this repo | Structural separation of config from execution | Foundational, companion repo established at repo creation |
| main is branch-protected via credential isolation | Agents cannot rewrite the rules of their own execution | Upgrade strategy, codified March 2026 |

## Related pages

- [Background](index.md): overview of background material
- [Architecture](../overview/architecture.md): system design and data flow
- [Overview](../overview/index.md): project overview and core principle
- [Development workflow](../how-to-contribute/development-workflow.md): the PR process in practice
