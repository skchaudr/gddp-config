# Verification Transcript — sell-valuables/fb-post-hook

- generated_at: 2026-06-30T03:34:35Z
- verdict: **blocked**
- confidence: 0.9

## Reasoning summary

deps: listing-cli=pending; criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Dependencies not complete: listing-cli. Complete or unblock them before this node can be verified.

## Acceptance criteria

### [pass] `console-script-entrypoint`  (confidence 0.9)

> pyproject.toml registers sell-post-fb entry point to sell_valuables.post_to_fb:main

- method: `symbol`
- reasoning: Probed pyproject.toml for all of ['sell-post-fb\\s*=\\s*\\"sell_valuables\\.post_to_fb:main\\"']. All present.
- evidence:
  - in pyproject.toml
  - sell-post-fb\s*=\s*\"sell_valuables\.post_to_fb:main\" -> line 21: 'sell-post-fb = "sell_valuables.post_to_fb:main"'

### [pass] `generates-listing-first`  (confidence 0.9)

> sell-post-fb always calls generate_listing before any browser action and prints Wrote listing.md path

- method: `func`
- reasoning: Looked for function `main()` plus body markers ['generate_listing\\(item_dir\\)', 'Wrote'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - \bmain\s*\( -> line 143: 'main('
  - generate_listing\(item_dir\) -> line 177: 'generate_listing(item_dir)'
  - Wrote -> line 178: 'Wrote'

### [pass] `open-flag-browser`  (confidence 0.9)

> --open opens FB_MARKETPLACE_CREATE_URL via webbrowser.open and on macOS reveals photos/ with open command

- method: `symbol`
- reasoning: Probed src/sell_valuables/post_to_fb.py for all of ['--open', 'webbrowser\\.open', 'FB_MARKETPLACE_CREATE_URL', 'subprocess\\.run\\(\\[\\"open\\"']. All present.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - --open -> line 153: '--open'
  - webbrowser\.open -> line 20: 'webbrowser.open'
  - FB_MARKETPLACE_CREATE_URL -> line 13: 'FB_MARKETPLACE_CREATE_URL'
  - subprocess\.run\(\[\"open\" -> line 200: 'subprocess.run(["open"'

### [pass] `playwright-flag-skeleton`  (confidence 0.9)

> --playwright invokes post_with_playwright with dry_run=True and prints result dict

- method: `symbol`
- reasoning: Probed src/sell_valuables/post_to_fb.py for all of ['--playwright', 'post_with_playwright', 'dry_run=True', 'print\\(result\\)']. All present.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - --playwright -> line 158: '--playwright'
  - post_with_playwright -> line 69: 'post_with_playwright'
  - dry_run=True -> line 77: 'dry_run=True'
  - print\(result\) -> line 191: 'print(result)'

### [pass] `default-manual-instructions`  (confidence 0.9)

> when neither --open nor --playwright is passed CLI prints manual Marketplace URL and rerun hints

- method: `symbol`
- reasoning: Probed src/sell_valuables/post_to_fb.py for all of ['Open manually:', '--open or --playwright']. All present.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - Open manually: -> line 202: 'Open manually:'
  - --open or --playwright -> line 203: '--open or --playwright'

## Constraints

### [clear] (confidence 0.85)

> require explicit item_id argument — no auto-single-folder selection in sell-post-fb

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> do not submit listings from the default CLI path

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> keep post_to_fb.py separate from generate_listing.py concerns

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/pyproject.toml`
- `Automating-Selling-Random-Valuables/src/sell_valuables/post_to_fb.py`
- `graphs/sell-valuables/nodes/fb-post-hook.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] console-script-entrypoint: Probed pyproject.toml for all of ['sell-post-fb\\s*=\\s*\\"sell_valuables\\.post_to_fb:main\\"']. All present.
[pass] generates-listing-first: Looked for function `main()` plus body markers ['generate_listing\\(item_dir\\)', 'Wrote'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
[pass] open-flag-browser: Probed src/sell_valuables/post_to_fb.py for all of ['--open', 'webbrowser\\.open', 'FB_MARKETPLACE_CREATE_URL', 'subprocess\\.run\\(\\[\\"open\\"']. All present.
[pass] playwright-flag-skeleton: Probed src/sell_valuables/post_to_fb.py for all of ['--playwright', 'post_with_playwright', 'dry_run=True', 'print\\(result\\)']. All present.
[pass] default-manual-instructions: Probed src/sell_valuables/post_to_fb.py for all of ['Open manually:', '--open or --playwright']. All present.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
