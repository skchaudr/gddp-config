# Verification Transcript — sell-valuables/test-suite

- generated_at: 2026-06-30T03:34:35Z
- verdict: **blocked**
- confidence: 0.9

## Reasoning summary

deps: intake-loader=pending, listing-text-builder=pending, fb-post-hook=pending; criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Dependencies not complete: intake-loader, listing-text-builder, fb-post-hook. Complete or unblock them before this node can be verified.

## Acceptance criteria

### [pass] `sample-item-fixture`  (confidence 0.95)

> tests/fixtures/sample-item/ contains description.txt and meta.yaml usable by load_item

- method: `paths`
- reasoning: All required paths exist.
- evidence:
  - tests/fixtures/sample-item/description.txt exists
  - tests/fixtures/sample-item/meta.yaml exists

### [pass] `test-load-item-fixture`  (confidence 0.9)

> test_load_item_fixture asserts item_id, description content, and meta price_hint from fixture

- method: `symbol`
- reasoning: Probed tests/test_listing.py for all of ['def test_load_item_fixture', 'item_id', 'description', 'price_hint']. All present.
- evidence:
  - in tests/test_listing.py
  - def test_load_item_fixture -> line 9: 'def test_load_item_fixture'
  - item_id -> line 11: 'item_id'
  - description -> line 12: 'description'
  - price_hint -> line 13: 'price_hint'

### [pass] `test-build-title-first-line`  (confidence 0.9)

> test_build_title_from_first_line asserts build_title matches first description line for fixture

- method: `symbol`
- reasoning: Probed tests/test_listing.py for all of ['def test_build_title_from_first_line', 'build_title']. All present.
- evidence:
  - in tests/test_listing.py
  - def test_build_title_from_first_line -> line 16: 'def test_build_title_from_first_line'
  - build_title -> line 4: 'build_title'

### [pass] `test-listing-markdown-content`  (confidence 0.9)

> test_listing_markdown_includes_price_and_fb_url asserts price line, FB URL, and pickup wording in markdown

- method: `symbol`
- reasoning: Probed tests/test_listing.py for all of ['test_listing_markdown_includes_price_and_fb_url', '\\*\\*Price:\\*\\*', 'facebook\\.com/marketplace/create', 'pickup']. All present.
- evidence:
  - in tests/test_listing.py
  - test_listing_markdown_includes_price_and_fb_url -> line 21: 'test_listing_markdown_includes_price_and_fb_url'
  - \*\*Price:\*\* -> line 24: '**Price:**'
  - facebook\.com/marketplace/create -> line 25: 'facebook.com/marketplace/create'
  - pickup -> line 26: 'pickup'

### [pass] `pytest-dev-extra`  (confidence 0.9)

> pyproject.toml dev optional extra includes pytest and README quick start documents pip install -e '.[dev]' && pytest

- method: `symbol`
- reasoning: Probed pyproject.toml, README.md for all of ['dev\\s*=', 'pytest', "pip install -e '\\.\\[dev\\]'"]. All present.
- evidence:
  - in pyproject.toml
  - in README.md
  - dev\s*= -> line 12: 'dev ='
  - pytest -> line 13: 'pytest'
  - pip install -e '\.\[dev\]' -> line 8: "pip install -e '.[dev]'"

## Constraints

### [clear] (confidence 0.85)

> tests must not require Playwright or live Facebook access

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> use tests/fixtures/sample-item only — do not depend on real incoming/ item folders

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> keep testpaths limited to tests/ per pyproject.toml

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/README.md`
- `Automating-Selling-Random-Valuables/pyproject.toml`
- `Automating-Selling-Random-Valuables/tests/fixtures/sample-item/description.txt`
- `Automating-Selling-Random-Valuables/tests/fixtures/sample-item/meta.yaml`
- `Automating-Selling-Random-Valuables/tests/test_listing.py`
- `graphs/sell-valuables/nodes/test-suite.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] sample-item-fixture: All required paths exist.
[pass] test-load-item-fixture: Probed tests/test_listing.py for all of ['def test_load_item_fixture', 'item_id', 'description', 'price_hint']. All present.
[pass] test-build-title-first-line: Probed tests/test_listing.py for all of ['def test_build_title_from_first_line', 'build_title']. All present.
[pass] test-listing-markdown-content: Probed tests/test_listing.py for all of ['test_listing_markdown_includes_price_and_fb_url', '\\*\\*Price:\\*\\*', 'facebook\\.com/marketplace/create', 'pickup']. All present.
[pass] pytest-dev-extra: Probed pyproject.toml, README.md for all of ['dev\\s*=', 'pytest', "pip install -e '\\.\\[dev\\]'"]. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
