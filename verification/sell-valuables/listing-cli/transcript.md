# Verification Transcript — sell-valuables/listing-cli

- generated_at: 2026-06-30T03:34:35Z
- verdict: **blocked**
- confidence: 0.9

## Reasoning summary

deps: listing-text-builder=pending; criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Dependencies not complete: listing-text-builder. Complete or unblock them before this node can be verified.

## Acceptance criteria

### [pass] `console-script-entrypoint`  (confidence 0.9)

> pyproject.toml registers sell-listing entry point to sell_valuables.generate_listing:main

- method: `symbol`
- reasoning: Probed pyproject.toml for all of ['sell-listing\\s*=\\s*\\"sell_valuables\\.generate_listing:main\\"']. All present.
- evidence:
  - in pyproject.toml
  - sell-listing\s*=\s*\"sell_valuables\.generate_listing:main\" -> line 20: 'sell-listing = "sell_valuables.generate_listing:main"'

### [pass] `generate-listing-writes-file`  (confidence 0.9)

> generate_listing loads the item and writes listing.md inside the item folder using build_listing_markdown

- method: `func`
- reasoning: Looked for function `generate_listing()` plus body markers ['load_item', 'listing\\.md', 'build_listing_markdown', 'write_text'] in src/sell_valuables/generate_listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/generate_listing.py
  - \bgenerate_listing\s*\( -> line 13: 'generate_listing('
  - load_item -> line 9: 'load_item'
  - listing\.md -> line 1: 'listing.md'
  - build_listing_markdown -> line 10: 'build_listing_markdown'
  - write_text -> line 16: 'write_text'

### [pass] `item-id-argument`  (confidence 0.9)

> CLI accepts item_id folder name under incoming/ and errors when incoming/ is missing

- method: `func`
- reasoning: Looked for function `main()` plus body markers ['item_id', 'incoming/ not found', 'incoming / args\\.item_id'] in src/sell_valuables/generate_listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/generate_listing.py
  - \bmain\s*\( -> line 20: 'main('
  - item_id -> line 23: 'item_id'
  - incoming/ not found -> line 37: 'incoming/ not found'
  - incoming / args\.item_id -> line 41: 'incoming / args.item_id'

### [pass] `auto-single-candidate`  (confidence 0.9)

> when item_id is omitted CLI selects the sole non-underscore folder in incoming/ or errors if count is not exactly one

- method: `symbol`
- reasoning: Probed src/sell_valuables/generate_listing.py for all of ['candidates', 'not d\\.name\\.startswith\\(\\"_\\"\\)', 'len\\(candidates\\) != 1']. All present.
- evidence:
  - in src/sell_valuables/generate_listing.py
  - candidates -> line 43: 'candidates'
  - not d\.name\.startswith\(\"_\"\) -> line 45: 'not d.name.startswith("_")'
  - len\(candidates\) != 1 -> line 47: 'len(candidates) != 1'

### [pass] `incoming-override-flag`  (confidence 0.9)

> --incoming flag overrides default resolve_incoming_root path for fixtures and tests

- method: `symbol`
- reasoning: Probed src/sell_valuables/generate_listing.py for all of ['--incoming', 'args\\.incoming or resolve_incoming_root']. All present.
- evidence:
  - in src/sell_valuables/generate_listing.py
  - --incoming -> line 28: '--incoming'
  - args\.incoming or resolve_incoming_root -> line 35: 'args.incoming or resolve_incoming_root'

## Constraints

### [clear] (confidence 0.85)

> CLI must exit non-zero on FileNotFoundError and ValueError from load_item

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> print the output path on success to stdout

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> do not open a browser from sell-listing

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/pyproject.toml`
- `Automating-Selling-Random-Valuables/src/sell_valuables/generate_listing.py`
- `graphs/sell-valuables/nodes/listing-cli.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] console-script-entrypoint: Probed pyproject.toml for all of ['sell-listing\\s*=\\s*\\"sell_valuables\\.generate_listing:main\\"']. All present.
[pass] generate-listing-writes-file: Looked for function `generate_listing()` plus body markers ['load_item', 'listing\\.md', 'build_listing_markdown', 'write_text'] in src/sell_valuables/generate_listing.py. Defined and uses expected helpers.
[pass] item-id-argument: Looked for function `main()` plus body markers ['item_id', 'incoming/ not found', 'incoming / args\\.item_id'] in src/sell_valuables/generate_listing.py. Defined and uses expected helpers.
[pass] auto-single-candidate: Probed src/sell_valuables/generate_listing.py for all of ['candidates', 'not d\\.name\\.startswith\\(\\"_\\"\\)', 'len\\(candidates\\) != 1']. All present.
[pass] incoming-override-flag: Probed src/sell_valuables/generate_listing.py for all of ['--incoming', 'args\\.incoming or resolve_incoming_root']. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
