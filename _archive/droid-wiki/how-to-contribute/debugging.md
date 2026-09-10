# Debugging

The strict global validator (`scripts/validate.py`) is the primary debugging surface in this repo. It produces structured findings with a rule name, severity, and message. This page covers common validation errors, output modes, and how to scope validation.

## Common validation errors and how to fix them

### schema_version mismatch

**Rule:** `schema_version`

**Error:** `expected '1.0', got '2.0'`

Every document must have `schema_version: "1.0"` as the first envelope field. The value must be a string, not a float. If you write `schema_version: 1.0` without quotes, YAML may parse it as a float. Fix: quote the value: `schema_version: "1.0"`.

### schema_type mismatch

**Rule:** `schema_type`

**Error:** `expected 'node', got 'Node'`

The `schema_type` field must match the document type. For node files, it must be `node` (lowercase). This is an envelope field checked on every document.

### Missing fields

**Rule:** `missing_field`

**Error:** `node_id not present`

All required fields from the `REQUIRED_FIELDS` set in `scripts/validate.py` must be present. For nodes, these are: `node_id`, `title`, `type`, `why`, `depends_on`, `acceptance_criteria`, `constraints`, `allowed_execution_modes`, `required_artifacts`, `status`, `priority`, `unlocks`. Use `templates/node-template.yaml` as a starting point to avoid missing fields.

### Enum violations

**Rules:** `type_enum`, `status_enum`, `priority_enum`, `exec_mode_enum`

**Error:** `type 'feature' not in ['capability', 'constraint', 'milestone']`

The validator enforces closed enum sets. If you use a value outside the allowed set, the error names the invalid value and the valid alternatives.

| Field | Valid values |
|---|---|
| `type` | `capability`, `milestone`, `constraint` |
| `status` | `pending`, `ready`, `complete`, `deferred` |
| `priority` | `low`, `medium`, `high`, `critical` |
| `allowed_execution_modes` | `jules`, `vertex`, `pi_worker`, `vm_worker`, `human` |

### id/filename mismatch

**Rule:** `id_filename_mismatch`

**Error:** `node_id 'auth-boundary' doesn't match filename 'authboundary'`

The `node_id` field must exactly match the YAML filename (without the `.yaml` extension). If the file is `auth-boundary.yaml`, then `node_id` must be `auth-boundary`. This is a hard error.

### id_format (not kebab-case)

**Rule:** `id_format`

**Error:** `node_id 'AuthBoundary' not kebab-case`

The `node_id` must match the regex `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`. This means lowercase letters and digits, with hyphens separating words. No uppercase, no underscores, no leading hyphens.

### Dangling depends_on

**Rule:** `dangling_depends_on` (warning)

**Error:** `depends_on 'missing-node' not found in project`

A `depends_on` reference points to a node_id that does not exist in the project's `nodes/` directory. This is a warning, not an error, because the node may not be created yet. Under `--strict` mode it becomes an error.

### Dangling unlocks

**Rule:** `dangling_unlocks` (warning)

**Error:** `unlocks 'future-node' not found (may be future node)`

An `unlocks` reference points to a node that does not exist yet. This is expected for forward-looking graph definitions. Warnings only, unless `--strict` is used.

### Asymmetric edge

**Rule:** `asymmetric_edge` (warning)

**Error:** `unlocks 'node-b' but node-b.yaml doesn't list this node in depends_on`

If node A declares `unlocks: [node-b]`, then `node-b.yaml` should declare `depends_on: [node-a]`. The validator checks this symmetry. A mismatch is a warning because it may be intentional during graph construction.

### Unquoted colons in lists

**Rule:** `implicit_mapping_in_list` (warning)

**Error:** `constraints[0] parsed as dict (unquoted colon), quote the string: do: not`

If a list item contains a colon, YAML parses it as a dict unless it is quoted. For example, `constraints: [do: something]` becomes a dict `{"do": "something"}` instead of a string. Fix by quoting: `constraints: ["do: something"]`.

### Empty acceptance_criteria

**Rule:** `acceptance_empty`

**Error:** `acceptance must have at least one entry`

Every node must have at least one acceptance criterion. An empty list is a hard error. The `batch_fill.py` tool also refuses to write a node with empty acceptance criteria (VAL-CLI-001).

### Duplicate node_id

**Rule:** `duplicate_id`

**Error:** `node_id 'auth-boundary' also in other-file.yaml`

Two node files in the same project have the same `node_id`. Node ids must be unique within a project.

## Using --json output for machine-readable findings

The `--json` flag produces structured output for tooling and agent pipelines:

```bash
.venv/bin/python scripts/validate.py --json
```

Output structure:

```json
{
  "errors": [
    {"path": "graphs/my-app/nodes/bad-node.yaml", "line": 0, "severity": "error", "rule": "missing_field", "message": "node_id not present"}
  ],
  "warnings": [
    {"path": "graphs/my-app/nodes/bad-node.yaml", "line": 0, "severity": "warning", "rule": "dangling_depends_on", "message": "depends_on 'x' not found in project"}
  ],
  "summary": {
    "errors": 1,
    "warnings": 1,
    "files_checked": 1
  }
}
```

The `import_node.py` pipeline uses this JSON output as a post-write hook to report validation findings.

## Scoping validation with --project

To validate a single project instead of all projects:

```bash
.venv/bin/python scripts/validate.py --project vault-doctor
```

This only checks node YAML files in `graphs/vault-doctor/nodes/`. Useful for focused debugging after editing one project's graph.

## Strict mode for CI gates

The `--strict` flag treats warnings as errors and changes the exit code accordingly:

```bash
.venv/bin/python scripts/validate.py --strict
```

Under strict mode, dangling dependencies, asymmetric edges, unknown artifacts, and implicit mappings in lists all count as errors. Use this in CI gates or pre-commit hooks when warnings should block a merge. The exit code is 1 if any errors or warnings (under strict) are present, 0 otherwise.

## Related pages

- [Testing](testing.md): test coverage and how to run tests
- [Patterns and conventions](patterns-and-conventions.md): validation patterns
- [Validation engine](../systems/validation-engine.md): how the validator works internally
- [CLI tooling](../systems/cli-tooling.md): the gddp.py unified CLI
