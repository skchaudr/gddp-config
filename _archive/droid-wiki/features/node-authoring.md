# Node authoring

Creating a node YAML file is the most frequent human activity in gddp-config. The repo provides four authoring modes, each tuned to a different point on the speed-versus-completeness spectrum. All four write to `graphs/<project>/nodes/<node_id>.yaml` and patch the project's `project.yaml` index. The YAML stays source of truth, human-owned.

## The four authoring modes

### Full TUI scaffold (`scripts/new_node.py`)

A field-by-field interactive editor invoked with `gddp node new`. The TUI walks through every node field in order: project, `node_id`, `title`, `type`, `why`, `depends_on`, `acceptance_criteria`, `constraints`, `allowed_execution_modes`, `required_artifacts`, `status`, `priority`, and `unlocks`. Each field uses a paginated picker where number keys (1-9) select, `m` switches to manual text entry, `s` skips, `q` quits, and Enter accepts the default. Multi-select fields (dependencies, artifacts, execution modes) support toggle and pagination with arrow keys. A review screen shows the rendered YAML before writing, with an `e` edit option that re-runs the picker for a single field.

The scaffold gathers "inspiration bullets" from existing nodes in the project, lifting prior `acceptance_criteria` and `constraints` text as suggestions when filling list fields. After writing the node file and patching `project.yaml` (with a `.bak` backup), it runs `scripts/validate.py` globally. The exit gate only fails if the new node or the project index patch introduced issues. Pre-existing repo drift is reported but does not block the scaffold.

### Rapid adder (`scripts/rapid_add.py`)

Designed for hand preservation. Invoked with `gddp node rapid --project <id>`. The flow is: type a short node name, press Enter, the name is auto-slugified to kebab-case, pick dependencies from numbered existing nodes (toggle with number keys), the node is written immediately with `REPLACE_ME` placeholders for `why`, `acceptance_criteria`, and `constraints`. No review screen between nodes. A blank line signals done.

The rapid adder will create a minimal `project.yaml` shell if the project directory does not yet exist. An optional `--llm-draft` flag activates hybrid mode, where `scripts/llm_draft.py` drafts the prose fields from project context before writing. After a rapid session, the next step is `gddp node batch --project <id>` to fill the placeholders.

### Batch fill (`scripts/batch_fill.py`)

A sequential field-by-field walker for nodes that contain `REPLACE_ME` placeholders. Invoked with `gddp node batch --project <id>`. The script scans every node YAML in the project and filters to those where `why`, `acceptance_criteria`, or `constraints` still have placeholder values or are empty. For each qualifying node, it shows a node card summarizing which fields need input, then walks through those fields one at a time using the same picker vocabulary as the full TUI (`1-9` pick, `m` manual, `s` skip, `q` skip node).

A review screen offers `y` write, `e` edit a single field, `r` redo all fields, or `q` skip. The writer refuses to save a node with zero acceptance criteria. After writing, it runs the validator inline and prints findings. The batch fill is the natural second step after a rapid-add session or an outline bootstrap.

### Import pipeline (`scripts/import_node.py`)

An agent-facing tool with no TUI. Invoked with `gddp node import --file draft.yaml --project <id>` or piped via stdin. The pipeline parses the YAML, validates it against the node schema inline (field presence, types, enums, kebab-case `node_id`, acceptance criteria shape), checks for file and index conflicts, and warns on dangling `depends_on` references. It writes the node file and patches `project.yaml` only if no errors are found.

Output is always JSON on stdout for machine consumption. The `--dry-run` flag validates without writing. The `--auto-approve` flag skips any interactive review. Exit codes are explicit: `0` imported, `1` validation errors, `2` node already exists, `3` project not found.

## The node template

`templates/node-template.yaml` is the canonical blank node. It documents every field with inline comments explaining allowed values. Copy it to `graphs/<project>/nodes/<node-id>.yaml` and fill in the fields manually if you prefer a text editor over the TUI. The template uses `REPLACE_ME` as the placeholder convention, which is the same marker the batch filler scans for.

## The draft-node prompt

`templates/draft-node-prompt.md` is an LLM prompt template for drafting the prose-heavy fields: `why`, `acceptance_criteria`, and `constraints`. The prompt encodes the repo's voice rules. The `why` field must explain the capability gap, not implementation. Acceptance criteria must be mechanically verifiable (file existence, function signature, test pass), not vague. Constraints must scope blast radius (which files not to touch, which deps not to add).

The intended workflow is: run the TUI scaffold, pause when you reach the prose fields, paste the system prompt into Claude or Codex with a one-line capability description, copy the LLM output back into the TUI manual entry slots, then resume. The prompt includes a reference example from `graphs/vault-doctor/nodes/scan-vault-core.yaml` to ground the output style.

## Comparison of authoring modes

| Mode | Command | Keystrokes | Prose fields | Best for |
|---|---|---|---|---|
| Full TUI | `gddp node new` | Number keys, `m/s/q/Enter`, review | Filled inline | One careful node at a time |
| Rapid add | `gddp node rapid --project X` | Type name, Enter, number keys | `REPLACE_ME` placeholders | Scaffolding many nodes fast |
| Batch fill | `gddp node batch --project X` | Walk fields per placeholder node | Filled sequentially | Completing rapid-add or outline output |
| Import | `gddp node import --file F --project X` | None (no TUI) | Pre-filled by agent | Agent pipelines, CI |

## Key source files

| File | Role |
|---|---|
| `scripts/new_node.py` | Full TUI scaffold, field-by-field editor with review screen |
| `scripts/rapid_add.py` | Minimal-keystroke adder with auto-slugify and dep picker |
| `scripts/batch_fill.py` | `REPLACE_ME` walker, sequential field fill per node |
| `scripts/import_node.py` | Agent-facing validator and writer, JSON output |
| `scripts/gddp.py` | Unified CLI dispatching to all four modes |
| `templates/node-template.yaml` | Canonical blank node with inline field comments |
| `templates/draft-node-prompt.md` | LLM prompt for drafting prose fields |
| `scripts/acceptance_items.py` | Shared helper for acceptance criteria normalization |

## Related pages

- [Project bootstrapping](project-bootstrapping.md): How nodes get created in bulk at project start
- [systems/cli-tooling.md](../systems/cli-tooling.md): The gddp.py unified CLI
- [systems/schemas.md](../systems/schemas.md): The schema system that defines node fields
- [systems/validation-engine.md](../systems/validation-engine.md): The validation engine that checks node files
