# Verification Transcript — sell-valuables/listing-text-builder

- generated_at: 2026-06-30T03:34:35Z
- verdict: **blocked**
- confidence: 0.9

## Reasoning summary

deps: intake-loader=pending; criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Dependencies not complete: intake-loader. Complete or unblock them before this node can be verified.

## Acceptance criteria

### [pass] `build-title-first-line`  (confidence 0.9)

> build_title uses the first line of description trimmed to max_len default 80 with ellipsis when truncated

- method: `func`
- reasoning: Looked for function `build_title()` plus body markers ['splitlines\\(\\)\\[0\\]', 'max_len: int = 80', '\\.\\.\\.'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/listing.py
  - \bbuild_title\s*\( -> line 10: 'build_title('
  - splitlines\(\)\[0\] -> line 12: 'splitlines()[0]'
  - max_len: int = 80 -> line 10: 'max_len: int = 80'
  - \.\.\. -> line 15: '...'

### [pass] `build-body-condition-shipping`  (confidence 0.9)

> build_body appends Condition and pickup/shipping lines from meta.condition and meta.shipping when present

- method: `func`
- reasoning: Looked for function `build_body()` plus body markers ['condition', 'shipping', 'Local pickup only', 'Shipping available'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/listing.py
  - \bbuild_body\s*\( -> line 18: 'build_body('
  - condition -> line 20: 'condition'
  - shipping -> line 22: 'shipping'
  - Local pickup only -> line 23: 'Local pickup only'
  - Shipping available -> line 25: 'Shipping available'

### [pass] `build-body-photo-count`  (confidence 0.9)

> build_body includes a photo count line when item.photos is non-empty

- method: `func`
- reasoning: Looked for function `build_body()` plus body markers ['if item\\.photos', 'Photos:', 'len\\(item\\.photos\\)'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/listing.py
  - \bbuild_body\s*\( -> line 18: 'build_body('
  - if item\.photos -> line 26: 'if item.photos'
  - Photos: -> line 28: 'Photos:'
  - len\(item\.photos\) -> line 28: 'len(item.photos)'

### [pass] `listing-markdown-structure`  (confidence 0.9)

> build_listing_markdown outputs title heading, price from meta.price_hint default TBD, FB create URL, and body text

- method: `func`
- reasoning: Looked for function `build_listing_markdown()` plus body markers ['\\*\\*Price:\\*\\*', 'FB_MARKETPLACE_CREATE_URL', 'build_body'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/listing.py
  - \bbuild_listing_markdown\s*\( -> line 32: 'build_listing_markdown('
  - \*\*Price:\*\* -> line 38: '**Price:**'
  - FB_MARKETPLACE_CREATE_URL -> line 7: 'FB_MARKETPLACE_CREATE_URL'
  - build_body -> line 18: 'build_body'

### [pass] `fb-create-url-constant`  (confidence 0.9)

> FB_MARKETPLACE_CREATE_URL constant points to facebook.com/marketplace/create/item

- method: `symbol`
- reasoning: Probed src/sell_valuables/listing.py for all of ['FB_MARKETPLACE_CREATE_URL', 'facebook\\.com/marketplace/create/item']. All present.
- evidence:
  - in src/sell_valuables/listing.py
  - FB_MARKETPLACE_CREATE_URL -> line 7: 'FB_MARKETPLACE_CREATE_URL'
  - facebook\.com/marketplace/create/item -> line 7: 'facebook.com/marketplace/create/item'

## Constraints

### [clear] (confidence 0.85)

> keep listing builders pure functions in src/sell_valuables/listing.py

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> do not embed Playwright or browser code in listing.py

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> price_hint stays a string hint — no payment processing

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/src/sell_valuables/listing.py`
- `graphs/sell-valuables/nodes/listing-text-builder.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] build-title-first-line: Looked for function `build_title()` plus body markers ['splitlines\\(\\)\\[0\\]', 'max_len: int = 80', '\\.\\.\\.'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
[pass] build-body-condition-shipping: Looked for function `build_body()` plus body markers ['condition', 'shipping', 'Local pickup only', 'Shipping available'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
[pass] build-body-photo-count: Looked for function `build_body()` plus body markers ['if item\\.photos', 'Photos:', 'len\\(item\\.photos\\)'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
[pass] listing-markdown-structure: Looked for function `build_listing_markdown()` plus body markers ['\\*\\*Price:\\*\\*', 'FB_MARKETPLACE_CREATE_URL', 'build_body'] in src/sell_valuables/listing.py. Defined and uses expected helpers.
[pass] fb-create-url-constant: Probed src/sell_valuables/listing.py for all of ['FB_MARKETPLACE_CREATE_URL', 'facebook\\.com/marketplace/create/item']. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
