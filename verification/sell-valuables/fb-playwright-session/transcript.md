# Verification Transcript — sell-valuables/fb-playwright-session

- generated_at: 2026-06-30T03:34:35Z
- verdict: **blocked**
- confidence: 0.9

## Reasoning summary

deps: fb-post-hook=pending; criteria: 5/5 pass; constraints: 3/3 clear; artifacts: 0/3 present

## Required next action

Dependencies not complete: fb-post-hook. Complete or unblock them before this node can be verified.

## Acceptance criteria

### [pass] `optional-browser-extra`  (confidence 0.9)

> pyproject.toml browser optional extra installs playwright and documents pip install -e '.[browser]' requirement

- method: `symbol`
- reasoning: Probed pyproject.toml, src/sell_valuables/post_to_fb.py for all of ['browser\\s*=', 'playwright', "pip install -e '\\.\\[browser\\]'"]. All present.
- evidence:
  - in pyproject.toml
  - in src/sell_valuables/post_to_fb.py
  - browser\s*= -> line 15: 'browser ='
  - playwright -> line 16: 'playwright'
  - pip install -e '\.\[browser\]' -> line 79: "pip install -e '.[browser]'"

### [pass] `storage-state-path`  (confidence 0.9)

> post_with_playwright loads .fb-session/storage_state.json from repo root when the file exists

- method: `symbol`
- reasoning: Probed src/sell_valuables/post_to_fb.py for all of ['\\.fb-session', 'storage_state\\.json', 'storage_state']. All present.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - \.fb-session -> line 24: '.fb-session'
  - storage_state\.json -> line 16: 'storage_state.json'
  - storage_state -> line 16: 'storage_state'

### [pass] `playwright-import-error`  (confidence 0.9)

> missing playwright raises RuntimeError with install instructions instead of crashing import time

- method: `func`
- reasoning: Looked for function `post_with_playwright()` plus body markers ['except ImportError', 'RuntimeError', 'Playwright not installed'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - \bpost_with_playwright\s*\( -> line 69: 'post_with_playwright('
  - except ImportError -> line 84: 'except ImportError'
  - RuntimeError -> line 85: 'RuntimeError'
  - Playwright not installed -> line 86: 'Playwright not installed'

### [pass] `chromium-launch`  (confidence 0.9)

> post_with_playwright launches chromium with headless flag support and opens FB_MARKETPLACE_CREATE_URL

- method: `func`
- reasoning: Looked for function `post_with_playwright()` plus body markers ['chromium\\.launch\\(headless=headless\\)', 'page\\.goto\\(FB_MARKETPLACE_CREATE_URL'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - \bpost_with_playwright\s*\( -> line 69: 'post_with_playwright('
  - chromium\.launch\(headless=headless\) -> line 108: 'chromium.launch(headless=headless)'
  - page\.goto\(FB_MARKETPLACE_CREATE_URL -> line 114: 'page.goto(FB_MARKETPLACE_CREATE_URL'

### [pass] `session-dir-created`  (confidence 0.9)

> automation creates .fb-session parent directory when missing to support future storage_state save

- method: `func`
- reasoning: Looked for function `post_with_playwright()` plus body markers ['session_dir\\.mkdir\\(parents=True, exist_ok=True\\)'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
- evidence:
  - in src/sell_valuables/post_to_fb.py
  - \bpost_with_playwright\s*\( -> line 69: 'post_with_playwright('
  - session_dir\.mkdir\(parents=True, exist_ok=True\) -> line 94: 'session_dir.mkdir(parents=True, exist_ok=True)'

## Constraints

### [clear] (confidence 0.85)

> .fb-session/ must stay gitignored — never commit Facebook session cookies

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> session bootstrap must work with dry_run=True without submitting

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

### [clear] (confidence 0.85)

> do not hardcode operator credentials in source

- method: `forbidden_pattern_scan`
- reasoning: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
- evidence:
  - no forbidden patterns matched

## Files inspected

- `<repo:Automating-Selling-Random-Valuables>`
- `Automating-Selling-Random-Valuables/pyproject.toml`
- `Automating-Selling-Random-Valuables/src/sell_valuables/post_to_fb.py`
- `graphs/sell-valuables/nodes/fb-playwright-session.yaml`
- `graphs/sell-valuables/project.yaml`

## Commands run

### `test -f schema/packet.schema.json`  (exit 1)

```

```

## Evidence summary

```
[pass] optional-browser-extra: Probed pyproject.toml, src/sell_valuables/post_to_fb.py for all of ['browser\\s*=', 'playwright', "pip install -e '\\.\\[browser\\]'"]. All present.
[pass] storage-state-path: Probed src/sell_valuables/post_to_fb.py for all of ['\\.fb-session', 'storage_state\\.json', 'storage_state']. All present.
[pass] playwright-import-error: Looked for function `post_with_playwright()` plus body markers ['except ImportError', 'RuntimeError', 'Playwright not installed'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
[pass] chromium-launch: Looked for function `post_with_playwright()` plus body markers ['chromium\\.launch\\(headless=headless\\)', 'page\\.goto\\(FB_MARKETPLACE_CREATE_URL'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
[pass] session-dir-created: Looked for function `post_with_playwright()` plus body markers ['session_dir\\.mkdir\\(parents=True, exist_ok=True\\)'] in src/sell_valuables/post_to_fb.py. Defined and uses expected helpers.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
[clear] constraint: Scanned referenced lib files for forbidden patterns (executor sourcing, runtime deps). No violations.
```
