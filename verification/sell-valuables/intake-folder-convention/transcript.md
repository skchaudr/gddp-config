# Verification Transcript — sell-valuables/intake-folder-convention

- generated_at: 2026-06-30T03:34:35Z
- verdict: **needs-more-evidence**
- confidence: 0.5

## Reasoning summary

criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Required artifacts missing: decision.md, result-summary.md, patch.diff. Run/review the node so its completion artifacts are produced, then re-run.

## Acceptance criteria

### [pass] `incoming-readme-documents-layout`  (confidence 0.9)

> incoming/README.md documents description.txt (required), photos/, meta.yaml (optional), and item-id slug format YYYY-MM-DD-short-slug

- method: `symbol`
- reasoning: Probed incoming/README.md for all of ['description\\.txt', 'photos/', 'meta\\.yaml', 'YYYY-MM-DD-short-slug']. All present.
- evidence:
  - in incoming/README.md
  - description\.txt -> line 10: 'description.txt'
  - photos/ -> line 12: 'photos/'
  - meta\.yaml -> line 11: 'meta.yaml'
  - YYYY-MM-DD-short-slug -> line 19: 'YYYY-MM-DD-short-slug'

### [pass] `example-folder-present`  (confidence 0.95)

> incoming/_example/ demonstrates the layout with description.txt, meta.yaml, and photos/.gitkeep

- method: `paths`
- reasoning: All required paths exist.
- evidence:
  - incoming/_example/description.txt exists
  - incoming/_example/meta.yaml exists
  - incoming/_example/photos/.gitkeep exists

### [pass] `meta-yaml-fields-documented`  (confidence 0.9)

> incoming/README.md documents price_hint, shipping, condition, and category_hint meta fields

- method: `symbol`
- reasoning: Probed incoming/README.md for all of ['price_hint', 'shipping', 'condition', 'category_hint']. All present.
- evidence:
  - in incoming/README.md
  - price_hint -> line 24: 'price_hint'
  - shipping -> line 25: 'shipping'
  - condition -> line 26: 'condition'
  - category_hint -> line 27: 'category_hint'

### [pass] `underscore-folders-ignored`  (confidence 0.9)

> CLIs skip directories whose names start with underscore when auto-selecting a single intake folder

- method: `symbol`
- reasoning: Probed src/sell_valuables/generate_listing.py for all of ['not d\\.name\\.startswith\\(\\"_\\"\\)']. All present.
- evidence:
  - in src/sell_valuables/generate_listing.py
  - not d\.name\.startswith\(\"_\"\) -> line 45: 'not d.name.startswith("_")'

### [pass] `gitignore-incoming-artifacts`  (confidence 0.9)

> incoming/.gitignore excludes real item photos while keeping _example and README tracked

- method: `symbol`
- reasoning: Probed incoming/.gitignore for all of ['\\*', '!README\\.md', '!_example/', '!_example/\\*\\*']. All present.
- evidence:
  - in incoming/.gitignore
  - \* -> line 1: '*'
  - !README\.md -> line 2: '!README.md'
  - !_example/ -> line 3: '!_example/'
  - !_example/\*\* -> line 4: '!_example/**'

## Constraints

### [clear] (confidence 0.85)

> do not require a database or API for intake — filesystem folders are the source of truth

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> item-id must stay lowercase kebab-case with date prefix

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> do not store Facebook credentials inside intake folders

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/incoming/.gitignore`
- `Automating-Selling-Random-Valuables/incoming/README.md`
- `Automating-Selling-Random-Valuables/incoming/_example/description.txt`
- `Automating-Selling-Random-Valuables/incoming/_example/meta.yaml`
- `Automating-Selling-Random-Valuables/incoming/_example/photos/.gitkeep`
- `Automating-Selling-Random-Valuables/src/sell_valuables/generate_listing.py`
- `graphs/sell-valuables/nodes/intake-folder-convention.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] incoming-readme-documents-layout: Probed incoming/README.md for all of ['description\\.txt', 'photos/', 'meta\\.yaml', 'YYYY-MM-DD-short-slug']. All present.
[pass] example-folder-present: All required paths exist.
[pass] meta-yaml-fields-documented: Probed incoming/README.md for all of ['price_hint', 'shipping', 'condition', 'category_hint']. All present.
[pass] underscore-folders-ignored: Probed src/sell_valuables/generate_listing.py for all of ['not d\\.name\\.startswith\\(\\"_\\"\\)']. All present.
[pass] gitignore-incoming-artifacts: Probed incoming/.gitignore for all of ['\\*', '!README\\.md', '!_example/', '!_example/\\*\\*']. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
