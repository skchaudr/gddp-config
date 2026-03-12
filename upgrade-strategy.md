# Upgrade Strategy

How schema changes, config changes, and executor adapter changes are managed.

---

## Schema Versioning

Each schema file has a `schema_version` field using `major.minor` format.

| Change type | Version bump |
|---|---|
| Add optional field | minor |
| Add new enum value | minor |
| Rename a field | major |
| Remove a field | major |
| Change field semantics | major |
| Change required vs optional | major |

When a schema version bumps:
1. Update the schema file in `schemas/v1/`
2. Add an entry to `CHANGELOG.md`
3. Tag the commit: `schema/<type>@<version>` (e.g., `schema/node@1.1`)

---

## Rollback Procedure

To roll back a schema change:

```bash
git log --oneline                    # find the stable commit
git checkout <commit-sha> -- schemas/v1/<schema>.yaml
git commit -m "rollback: schema/<type> to <version>"
```

In-flight jobs on the old schema continue normally.
New jobs use the restored schema.
The Pi reads schema versions at startup — if a job's `schema_version` does not match the live schema, route it to `awaiting_review`.

---

## Adding a New Executor Adapter

1. Add the executor name to the controlled values in `schemas/v1/event.yaml` and `job.yaml`
2. Create an adapter contract doc in `docs/executor-adapters/<executor>.md`
3. Update the executor routing matrix in `docs/executor-routing.md`
4. Bump `schema_version` minor on affected schemas
5. Add a `CHANGELOG.md` entry
6. Test against a dry-run job before enabling in production

---

## Protecting Against Upstream API Changes

Jules CLI / Codex CLI / any executor can change their interfaces.

Mitigation:
- All dispatch goes through an adapter layer (`JulesCliAdapter`, `JulesApiAdapter`, etc.)
- Adapters are the only code that speaks to external executors
- Adapters normalize into the internal `task_packet` and `result` schemas
- When an upstream API changes, only the adapter changes — schemas and graph logic do not

If an upstream API change is detected:
1. Pause dispatch to the affected executor (set to `awaiting_review`)
2. Update the adapter
3. Run one manual test job to verify
4. Re-enable dispatch

---

## Branch Protection Rules (to configure on GitHub)

- `main` is protected
- Direct pushes to `main` are blocked
- All changes require a PR
- No agent (OpenClaw, Jules, Codex) is authorized to push to `main`
- The human is the only merge authority for this repo

This is the most important security control in the system.
The config repo defines how agents behave.
Agents must not be able to rewrite the rules of their own execution.
