# Verification Transcript — aa-cli/common-core

- generated_at: 2026-06-29T22:43:02Z
- verdict: **needs-more-evidence**
- confidence: 0.5

## Reasoning summary

criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Required artifacts missing: decision.md, result-summary.md, patch.diff. Run/review the node so its completion artifacts are produced, then re-run.

## Acceptance criteria

### [pass] `aa-root-and-state-paths`  (confidence 0.9)

> AA_ROOT, AA_DATA_HOME, AA_STATE_HOME, and AA_SCHEMA resolve to repo-local defaults with env override support in lib/fire.zsh

- method: `symbol`
- reasoning: Probed lib/common.zsh for all of ['\\bAA_ROOT\\b', '\\bAA_DATA_HOME\\b', '\\bAA_STATE_HOME\\b', '\\bAA_SCHEMA\\b']. All present.
- evidence:
  - in lib/common.zsh
  - \bAA_ROOT\b -> line 3: 'AA_ROOT'
  - \bAA_DATA_HOME\b -> line 4: 'AA_DATA_HOME'
  - \bAA_STATE_HOME\b -> line 5: 'AA_STATE_HOME'
  - \bAA_SCHEMA\b -> line 7: 'AA_SCHEMA'

### [pass] `aa-init-dirs-creates-state`  (confidence 0.9)

> aa_init_dirs creates packets and runs directories under AA_DATA_HOME and AA_STATE_HOME

- method: `func`
- reasoning: Looked for function `aa_init_dirs()` plus body markers ['aa_packet_dir', 'aa_runs_dir'] in lib/common.zsh, lib/fire.zsh. Defined and uses expected helpers.
- evidence:
  - in lib/common.zsh
  - in lib/fire.zsh
  - \baa_init_dirs\s*\( -> line 55: 'aa_init_dirs('
  - aa_packet_dir -> line 18: 'aa_packet_dir'
  - aa_runs_dir -> line 22: 'aa_runs_dir'

### [pass] `aa-validate-packet-schema`  (confidence 0.9)

> aa_validate_packet rejects missing packets and invalid JSON against schema/packet.schema.json via jq

- method: `func`
- reasoning: Looked for function `aa_validate_packet()` plus body markers ['aa_require_jq', 'jq .*-f', 'AA_SCHEMA'] in lib/common.zsh. Defined and uses expected helpers.
- evidence:
  - in lib/common.zsh
  - \baa_validate_packet\s*\( -> line 59: 'aa_validate_packet('
  - aa_require_jq -> line 14: 'aa_require_jq'
  - jq .*-f -> line 63: 'jq -e -f'
  - AA_SCHEMA -> line 7: 'AA_SCHEMA'

### [pass] `aa-require-jq-errors`  (confidence 0.9)

> aa_require_jq prints a clear error and returns non-zero when jq is not installed

- method: `func`
- reasoning: Looked for function `aa_require_jq()` plus body markers ['command -v jq', 'aa_die'] in lib/common.zsh. Defined and uses expected helpers.
- evidence:
  - in lib/common.zsh
  - \baa_require_jq\s*\( -> line 14: 'aa_require_jq('
  - command -v jq -> line 15: 'command -v jq'
  - aa_die -> line 9: 'aa_die'

### [pass] `slug-and-iso-helpers`  (confidence 0.9)

> aa_slug, aa_now_iso, aa_now_id, and aa_title_from_prompt produce filesystem-safe slugs and UTC timestamps

- method: `symbol`
- reasoning: Probed lib/common.zsh for all of ['aa_slug', 'aa_now_iso', 'aa_now_id', 'aa_title_from_prompt']. All present.
- evidence:
  - in lib/common.zsh
  - aa_slug -> line 118: 'aa_slug'
  - aa_now_iso -> line 109: 'aa_now_iso'
  - aa_now_id -> line 113: 'aa_now_id'
  - aa_title_from_prompt -> line 102: 'aa_title_from_prompt'

## Constraints

### [clear] (confidence 0.85)

> implement helpers in lib/fire.zsh and lib/common.zsh only — do not add runtime dependencies beyond jq and zsh builtins

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> keep AA_TARGETS_CONF default pointing at repo targets.conf

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - lib/common.zsh: AA_TARGETS_CONF default points at targets.conf (preserved)

### [clear] (confidence 0.85)

> do not source executor-specific modules from common-core

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:aa-cli>`
- `aa-cli/lib/common.zsh`
- `aa-cli/lib/context.zsh`
- `aa-cli/lib/deck.zsh`
- `aa-cli/lib/fire.zsh`
- `aa-cli/lib/generate-path.zsh`
- `aa-cli/lib/generate.zsh`
- `aa-cli/lib/inventory.zsh`
- `aa-cli/lib/jules.zsh`
- `aa-cli/lib/ledger.zsh`
- `aa-cli/lib/pi.zsh`
- `aa-cli/lib/reconcile.zsh`
- `aa-cli/lib/targets.zsh`
- `aa-cli/lib/validate.zsh`
- `aa-cli/lib/vault.zsh`
- `aa-cli/lib/verbs.zsh`
- `graphs/aa-cli/nodes/common-core.yaml`
- `graphs/aa-cli/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 0)

```

```

## Evidence summary

```
[pass] aa-root-and-state-paths: Probed lib/common.zsh for all of ['\\bAA_ROOT\\b', '\\bAA_DATA_HOME\\b', '\\bAA_STATE_HOME\\b', '\\bAA_SCHEMA\\b']. All present.
[pass] aa-init-dirs-creates-state: Looked for function `aa_init_dirs()` plus body markers ['aa_packet_dir', 'aa_runs_dir'] in lib/common.zsh, lib/fire.zsh. Defined and uses expected helpers.
[pass] aa-validate-packet-schema: Looked for function `aa_validate_packet()` plus body markers ['aa_require_jq', 'jq .*-f', 'AA_SCHEMA'] in lib/common.zsh. Defined and uses expected helpers.
[pass] aa-require-jq-errors: Looked for function `aa_require_jq()` plus body markers ['command -v jq', 'aa_die'] in lib/common.zsh. Defined and uses expected helpers.
[pass] slug-and-iso-helpers: Probed lib/common.zsh for all of ['aa_slug', 'aa_now_iso', 'aa_now_id', 'aa_title_from_prompt']. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
