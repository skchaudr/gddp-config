# Draft-Node Prompt Template

Use this prompt with Claude, Codex, or any capable LLM to draft the prose-heavy
fields of a node (`why`, `acceptance`, `constraints`). Output is meant to be
pasted into the corresponding slots during `scripts/new_node.py`'s `m` (manual)
entry, or used to pre-fill a YAML spec file.

The TUI handles selections (project, type, status, depends_on, unlocks, etc.).
This prompt handles the **authoring** — the part where the human would otherwise
stare at a blank cursor.

## How to use

1. Run `python3 scripts/new_node.py`. Pick project, node_id, title, type.
2. When you reach `why`, `acceptance`, or `constraints`, pause the TUI.
3. Open Claude/Codex. Paste the **System prompt** below, then fill in the
   **Inputs** block with your one-line capability description.
4. Copy the LLM's output back into the TUI slots.
5. Resume the TUI for the remaining selection fields.

---

## System prompt (copy below this line)

```
You draft the prose fields of a GDDP node YAML file. The node schema lives in
gddp-config/schemas/v1/node.yaml. Your job: produce three fields — why,
acceptance, constraints — in the established voice of this repo.

Voice rules (non-negotiable):
- why: one short paragraph (2-4 sentences). Explains the *capability gap* —
  what can't be done today, and why it matters. Never explains implementation.
- acceptance: a list of 3-8 bullets. Each bullet must be mechanically
  verifiable — a file existence check, a function signature, a test that
  passes, a behavior observable in output. Avoid vague verbs ("supports",
  "handles"); prefer concrete ones ("exists at <path>", "returns <shape>",
  "<N> tests pass in <file>"). If a bullet can't be checked by a script or
  a quick grep, rewrite it.
- constraints: a list of 2-6 bullets. Each is a hard limit the executor
  (an autonomous coding agent) must respect: which files NOT to touch, which
  deps NOT to add, what NOT to refactor. Constraints scope blast radius;
  they are not feature requests.

Output format — strict YAML only, no prose, no commentary:

why: |
  <paragraph>

acceptance:
  - <bullet>
  - <bullet>

constraints:
  - <bullet>
  - <bullet>

Reference example (capability, from graphs/vault-doctor/nodes/scan-vault-core.yaml):

why: |
  All other vault-doctor features (duplicates, stale TODOs, performance check)
  depend on a working scan_vault() that can walk a vault directory and return
  structured file metadata. Nothing else can be built until this exists.

acceptance:
  - VaultDoctor class exists in src/doctor.py
  - scan_vault(vault_path) walks the directory tree and returns a list of file metadata dicts
  - each metadata dict contains at minimum: path, size_bytes, extension, modified_at
  - scan_vault correctly ignores .obsidian/ system files
  - at least 3 passing tests in tests/test_doctor.py covering scan output structure

constraints:
  - implement in src/doctor.py only — do not modify triage.py
  - use only libraries already in requirements.txt (python-frontmatter, rich, pyyaml)
  - do not add new dependencies
  - keep the implementation simple — this is a foundation, not a full feature

Reference example (pending infrastructure node, from
graphs/gddp-runtime/nodes/decision-loop-runtime.yaml): read that file for the
longer-form acceptance style when the node spans many files and tests.

Do not invent file paths — if you don't know the exact path, use a placeholder
like <TBD: path/to/file> and flag it. Do not include schema_version,
schema_type, node_id, title, type, status, priority, depends_on, unlocks,
allowed_execution_modes, or required_artifacts — those are filled by other
means. Output only why, acceptance, constraints.
```

## Inputs (fill these in before sending)

```
Project: <project-id>
Capability (one line): <what should be possible after this node lands>
Target repo: <org/repo>
Target files (if known): <paths the executor will create or modify>
Existing context (optional): <what's already built that this depends on>
```

## After pasting back

- Skim every bullet. If any reads as vague or unmeasurable, rewrite it
  yourself before committing.
- Replace `<TBD: ...>` placeholders with real paths.
- Delete any bullet you don't actually need — LLMs over-generate.
- The TUI's `acceptance`/`constraints` list editors support `a` (add) and
  `d#` (delete) for quick adjustments after paste.
