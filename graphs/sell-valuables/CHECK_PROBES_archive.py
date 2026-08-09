"""Inert archive of CHECK_PROBES extracted from gddp-runtime.

Source: scripts/runtime/verification/deterministic/probes.py (Phase 1 trim)
This file is reference-only — not imported by runtime.
"""

CHECK_PROBES = {
    # ── common-core ──
    "aa-root-and-state-paths": {
        "type": "symbol",
        "files": ["lib/common.zsh"],
        "patterns": [r"\bAA_ROOT\b", r"\bAA_DATA_HOME\b",
                     r"\bAA_STATE_HOME\b", r"\bAA_SCHEMA\b"],
        "all": True,
    },
    "aa-init-dirs-creates-state": {
        "type": "func",
        "files": ["lib/common.zsh", "lib/fire.zsh"],
        "name": "aa_init_dirs",
        "patterns": [r"aa_packet_dir", r"aa_runs_dir"],
    },
    "aa-validate-packet-schema": {
        "type": "func",
        "files": ["lib/common.zsh"],
        "name": "aa_validate_packet",
        "patterns": [r"aa_require_jq", r"jq .*-f", r"AA_SCHEMA"],
    },
    "aa-require-jq-errors": {
        "type": "func",
        "files": ["lib/common.zsh"],
        "name": "aa_require_jq",
        "patterns": [r"command -v jq", r"aa_die"],
    },
    "slug-and-iso-helpers": {
        "type": "symbol",
        "files": ["lib/common.zsh"],
        "patterns": [r"aa_slug", r"aa_now_iso", r"aa_now_id",
                     r"aa_title_from_prompt"],
        "all": True,
    },

    # ── dispatch-grok ──
    # grk tiers must be distinct: graph says speed + frontier resolve to
    # distinct variants incl --model grok-frontier. In the real targets.conf
    # the speed tier is identical to default (no --model), which is a genuine
    # criteria_mismatch this probe surfaces deterministically.
    "grk-tier-variants": {
        "type": "tier_distinct",
        "target": "grk",
        "file": "targets.conf",
        "require_distinct": ["default", "speed", "frontier"],
        "marker": r"--model grok-frontier",
        "mismatch_kind": "tier_distinct",
        "human_question": ("grk speed tier is identical to default in "
                           "targets.conf (no --model). Is that intended, or "
                           "should speed map to a distinct grok variant?"),
    },
    "grk-default-tier": {
        "type": "tier_distinct",
        "target": "grk",
        "file": "targets.conf",
        "require_present": ["default"],
        "also_check_files": ["lib/targets.zsh"],
        "patterns": [r"aa_target_lookup"],
        "mismatch_kind": "source_path",
    },
    "acceptance-test-covers-grk": {
        "type": "path",
        "path": "tests/acceptance.zsh",
        "also_grep": [r"\bgrk\b|grok"],
        "needs_evidence_when_absent": True,
        "evidence_what": "tests/acceptance.zsh grk/sync-target smoke path",
    },

    # ── dispatch-codex ──
    # cdx and codex are aliases; reconciliation must handle both.
    "cdx-async-placeholder": {
        "type": "tier_distinct",
        "target": "cdx",
        "file": "targets.conf",
        "require_present": ["default"],
        "alias_of": "cdx",
        "aliases": ["codex"],
        "mismatch_kind": "alias_integration",
        "human_question": ("cdx and codex are aliases for __codex_async. "
                           "Does reconciliation handle both refs cleanly?"),
    },

    # ── sell-valuables: intake + listing ──
    "incoming-readme-documents-layout": {
        "type": "symbol",
        "files": ["incoming/README.md"],
        "patterns": [r"description\.txt", r"photos/", r"meta\.yaml",
                     r"YYYY-MM-DD-short-slug"],
        "all": True,
    },
    "example-folder-present": {
        "type": "paths",
        "paths": ["incoming/_example/description.txt",
                  "incoming/_example/meta.yaml",
                  "incoming/_example/photos/.gitkeep"],
    },
    "meta-yaml-fields-documented": {
        "type": "symbol",
        "files": ["incoming/README.md"],
        "patterns": [r"price_hint", r"shipping", r"condition",
                     r"category_hint"],
        "all": True,
    },
    "underscore-folders-ignored": {
        "type": "symbol",
        "files": ["src/sell_valuables/generate_listing.py"],
        "patterns": [r"not d\.name\.startswith\(\"_\"\)"],
        "all": True,
    },
    "gitignore-incoming-artifacts": {
        "type": "symbol",
        "files": ["incoming/.gitignore"],
        "patterns": [r"\*", r"!README\.md", r"!_example/", r"!_example/\*\*"],
        "all": True,
    },
    "item-intake-dataclass": {
        "type": "symbol",
        "files": ["src/sell_valuables/intake.py"],
        "patterns": [r"@dataclass\(frozen=True\)", r"class ItemIntake",
                     r"item_id: str", r"root: Path", r"description: str",
                     r"photos: tuple\[Path, \.\.\.\]", r"meta: dict"],
        "all": True,
    },
    "load-item-requires-description": {
        "type": "func",
        "files": ["src/sell_valuables/intake.py"],
        "name": "load_item",
        "patterns": [r"description\.txt", r"FileNotFoundError",
                     r"if not description", r"ValueError"],
    },
    "photos-filtered-by-extension": {
        "type": "symbol",
        "files": ["src/sell_valuables/intake.py"],
        "patterns": [r"PHOTO_EXTENSIONS", r"\.jpg", r"\.jpeg", r"\.png",
                     r"\.heic", r"\.webp", r"suffix\.lower\(\)"],
        "all": True,
    },
    "meta-yaml-parsed": {
        "type": "func",
        "files": ["src/sell_valuables/intake.py"],
        "name": "load_item",
        "patterns": [r"meta\.yaml", r"yaml\.safe_load",
                     r"isinstance\(meta, dict\)", r"ValueError"],
    },
    "resolve-incoming-root": {
        "type": "func",
        "files": ["src/sell_valuables/intake.py"],
        "name": "resolve_incoming_root",
        "patterns": [r"parents\[2\]", r"return root / \"incoming\""],
    },
    "build-title-first-line": {
        "type": "func",
        "files": ["src/sell_valuables/listing.py"],
        "name": "build_title",
        "patterns": [r"splitlines\(\)\[0\]", r"max_len: int = 80",
                     r"\.\.\."],
    },
    "build-body-condition-shipping": {
        "type": "func",
        "files": ["src/sell_valuables/listing.py"],
        "name": "build_body",
        "patterns": [r"condition", r"shipping", r"Local pickup only",
                     r"Shipping available"],
    },
    "build-body-photo-count": {
        "type": "func",
        "files": ["src/sell_valuables/listing.py"],
        "name": "build_body",
        "patterns": [r"if item\.photos", r"Photos:", r"len\(item\.photos\)"],
    },
    "listing-markdown-structure": {
        "type": "func",
        "files": ["src/sell_valuables/listing.py"],
        "name": "build_listing_markdown",
        "patterns": [r"\*\*Price:\*\*", r"FB_MARKETPLACE_CREATE_URL",
                     r"build_body"],
    },
    "fb-create-url-constant": {
        "type": "symbol",
        "files": ["src/sell_valuables/listing.py"],
        "patterns": [r"FB_MARKETPLACE_CREATE_URL",
                     r"facebook\.com/marketplace/create/item"],
        "all": True,
    },
    "listing-cli:console-script-entrypoint": {
        "type": "symbol",
        "files": ["pyproject.toml"],
        "patterns": [r"sell-listing\s*=\s*\"sell_valuables\.generate_listing:main\""],
        "all": True,
    },
    "generate-listing-writes-file": {
        "type": "func",
        "files": ["src/sell_valuables/generate_listing.py"],
        "name": "generate_listing",
        "patterns": [r"load_item", r"listing\.md", r"build_listing_markdown",
                     r"write_text"],
    },
    "item-id-argument": {
        "type": "func",
        "files": ["src/sell_valuables/generate_listing.py"],
        "name": "main",
        "patterns": [r"item_id", r"incoming/ not found", r"incoming / args\.item_id"],
    },
    "auto-single-candidate": {
        "type": "symbol",
        "files": ["src/sell_valuables/generate_listing.py"],
        "patterns": [r"candidates", r"not d\.name\.startswith\(\"_\"\)",
                     r"len\(candidates\) != 1"],
        "all": True,
    },
    "incoming-override-flag": {
        "type": "symbol",
        "files": ["src/sell_valuables/generate_listing.py"],
        "patterns": [r"--incoming", r"args\.incoming or resolve_incoming_root"],
        "all": True,
    },

    # ── sell-valuables: FB hook + Playwright ──
    "fb-post-hook:console-script-entrypoint": {
        "type": "symbol",
        "files": ["pyproject.toml"],
        "patterns": [r"sell-post-fb\s*=\s*\"sell_valuables\.post_to_fb:main\""],
        "all": True,
    },
    "generates-listing-first": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "main",
        "patterns": [r"generate_listing\(item_dir\)", r"Wrote"],
    },
    "open-flag-browser": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"--open", r"webbrowser\.open", r"FB_MARKETPLACE_CREATE_URL",
                     r"subprocess\.run\(\[\"open\""],
        "all": True,
    },
    "playwright-flag-skeleton": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"--playwright", r"post_with_playwright", r"dry_run=True",
                     r"print\(result\)"],
        "all": True,
    },
    "default-manual-instructions": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"Open manually:", r"--open or --playwright"],
        "all": True,
    },
    "optional-browser-extra": {
        "type": "symbol",
        "files": ["pyproject.toml", "src/sell_valuables/post_to_fb.py"],
        "patterns": [r"browser\s*=", r"playwright",
                     r"pip install -e '\.\[browser\]'"],
        "all": True,
    },
    "storage-state-path": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"\.fb-session", r"storage_state\.json",
                     r"storage_state"],
        "all": True,
    },
    "playwright-import-error": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"except ImportError", r"RuntimeError",
                     r"Playwright not installed"],
    },
    "chromium-launch": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"chromium\.launch\(headless=headless\)",
                     r"page\.goto\(FB_MARKETPLACE_CREATE_URL"],
    },
    "session-dir-created": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"session_dir\.mkdir\(parents=True, exist_ok=True\)"],
    },
    "result-dict-fields": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"\"item_id\"", r"\"title\"", r"\"photo_count\"",
                     r"\"dry_run\"", r"\"submitted\""],
    },
    "title-from-build-title": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"\"title\": build_title\(item\)"],
    },
    "form-fill-selectors-scaffold": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "_fill_marketplace_form",
        "patterns": [r"_try_fill\(\"Title\"", r"_try_fill\(\"Price\"",
                     r"_try_fill\(\"Description\"",
                     r"set_input_files"],
        "human_question": ("Selectors are active code now, but live Facebook "
                           "selector drift still needs a headed logged-in run."),
    },
    "photo-loop-scaffold": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "_fill_marketplace_form",
        "patterns": [r"if item\.photos", r"for p in item\.photos",
                     r"set_input_files"],
        "human_question": ("Photo upload path is wired; live headed run should "
                           "confirm Facebook accepts the selector."),
    },
    "dry-run-stops-before-submit": {
        "type": "func",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "name": "post_with_playwright",
        "patterns": [r"dry_run", r"submitted\": False",
                     r"Stopped before submit"],
    },
    "dry-run-default-true": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"dry_run: bool = True", r"dry_run=True"],
        "all": True,
    },
    "submit-not-implemented-guard": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"Submit not implemented", r"decision\.md selector approval"],
        "all": True,
    },
    "publish-click-scaffold": {
        "type": "human_review",
        "reason": ("No Publish click scaffold should be enabled until selector "
                   "approval exists; confirm whether a commented final-step "
                   "placeholder is desired before treating this as missing."),
        "human_question": ("Should the graph require a commented Publish-click "
                           "placeholder, or is the stronger not-implemented "
                           "submit guard the intended evidence?"),
    },
    "submitted-flag-false-until-wired": {
        "type": "symbol",
        "files": ["src/sell_valuables/post_to_fb.py"],
        "patterns": [r"\"submitted\": False", r"Submit not implemented"],
        "all": True,
    },
    "human-review-required-policy": {
        "type": "project_policy",
        "path": "graphs/sell-valuables/project.yaml",
        "patterns": [r"require_human_review_before_overnight:\s*true"],
    },

    # ── sell-valuables: docs + tests ──
    "imessage-shortcuts-doc-exists": {
        "type": "symbol",
        "files": ["docs/imessage-shortcuts.md"],
        "patterns": [r"Apple does not expose iMessage to Python",
                     r"manual folder workflow|Manual"],
        "all": True,
    },
    "manual-steps-documented": {
        "type": "symbol",
        "files": ["docs/imessage-shortcuts.md"],
        "patterns": [r"incoming/YYYY-MM-DD-slug", r"photos/",
                     r"description\.txt", r"sell-listing", r"sell-post-fb"],
        "all": True,
    },
    "shortcuts-recommended-flow": {
        "type": "symbol",
        "files": ["docs/imessage-shortcuts.md"],
        "patterns": [r"Shortcuts", r"Share sheet", r"slug", r"iCloud Drive",
                     r"description\.txt"],
        "all": True,
    },
    "later-options-noted": {
        "type": "symbol",
        "files": ["docs/imessage-shortcuts.md"],
        "patterns": [r"Twilio", r"BlueBubbles"],
        "all": True,
    },
    "incoming-readme-cross-link": {
        "type": "symbol",
        "files": ["incoming/README.md"],
        "patterns": [r"docs/imessage-shortcuts\.md"],
        "all": True,
    },
    "sample-item-fixture": {
        "type": "paths",
        "paths": ["tests/fixtures/sample-item/description.txt",
                  "tests/fixtures/sample-item/meta.yaml"],
    },
    "test-load-item-fixture": {
        "type": "symbol",
        "files": ["tests/test_listing.py"],
        "patterns": [r"def test_load_item_fixture", r"item_id",
                     r"description", r"price_hint"],
        "all": True,
    },
    "test-build-title-first-line": {
        "type": "symbol",
        "files": ["tests/test_listing.py"],
        "patterns": [r"def test_build_title_from_first_line", r"build_title"],
        "all": True,
    },
    "test-listing-markdown-content": {
        "type": "symbol",
        "files": ["tests/test_listing.py"],
        "patterns": [r"test_listing_markdown_includes_price_and_fb_url",
                     r"\*\*Price:\*\*", r"facebook\.com/marketplace/create",
                     r"pickup"],
        "all": True,
    },
    "pytest-dev-extra": {
        "type": "symbol",
        "files": ["pyproject.toml", "README.md"],
        "patterns": [r"dev\s*=", r"pytest", r"pip install -e '\.\[dev\]'"],
        "all": True,
    },
}
