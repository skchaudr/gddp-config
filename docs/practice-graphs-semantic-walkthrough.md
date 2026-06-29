# Practice graphs — semantic walkthrough

Verifier guide for `graphs/sell-valuables` and `graphs/album-production`.  
Purpose: show what semantic verification requires beyond schema validation — plain meaning, pass conditions, evidence, tools, and likely verdicts **as of 2026-06-29**.

---

## Executive summary

| Graph | Nodes | Shape | Repo | Verdict today (rough) |
|-------|-------|-------|------|------------------------|
| **sell-valuables** | 10 | Main line + parallel doc branch + test convergence | `skchaudr/Automating-Selling-Random-Valuables` | ~7 pass, ~2 needs-more-evidence, ~1 needs-human-review |
| **album-production** | 10 | Linear audio chain + two parallel branches converging at distribution/release | `sab-mini/album-production` (fictional) | All **blocked** or **needs-human-review** — no repo artifacts to inspect |

**sell-valuables** maps cleanly to a real Python CLI. Most intake/listing nodes are implementable and largely done. Playwright nodes are intentionally scaffolded; submit is gated.

**album-production** is a creative pipeline graph. Verification is artifact-based (WAVs, PDFs, decision.md), not code grep. Every node expects human-owned evidence on disk.

---

# Graph 1: sell-valuables

## Blueprint

Turn iMessage photos + descriptions into `incoming/<item-id>/` folders, generate `listing.md`, then hook Facebook Marketplace (manual open or Playwright skeleton with dry_run).

**Execution policy:** human review before overnight; artifact gate enforced.

## Dependency map

```
intake-folder-convention ──┬──► intake-loader ──► listing-text-builder ──► listing-cli ──► fb-post-hook ──┬──► fb-playwright-session ──► fb-playwright-form-fill ──► fb-submit-gate
                           │                                                                                  │
                           └──► imessage-intake-path (parallel doc)                                            └──► test-suite (converges: intake-loader + listing-text-builder + fb-post-hook)
```

### Branch / convergence points

| Point | What happens |
|-------|----------------|
| **Fork after convention** | `intake-loader` (code path) and `imessage-intake-path` (operator doc path) both depend only on folder layout. |
| **Main spine** | Loader → listing text → CLI → FB hook. |
| **FB sub-chain** | Playwright session → form-fill scaffold → submit gate (human-only executor). |
| **Test convergence** | `test-suite` waits for loader, listing builder, and fb-post-hook — but pytest only covers intake/listing today. |

## Running the loop (sell-valuables)

1. Start at `intake-folder-convention` (no deps).
2. Complete convention → unlocks `intake-loader` and `imessage-intake-path` (parallel).
3. `intake-loader` → `listing-text-builder` → `listing-cli` → `fb-post-hook` (strict sequence).
4. In parallel: operator can satisfy `imessage-intake-path` anytime after convention.
5. After `fb-post-hook`: fork into Playwright chain **or** satisfy `test-suite` (needs fb-post-hook for graph deps, not for pytest).
6. Playwright: session → form-fill → submit-gate (terminal; no unlocks).
7. Verifier re-walks deps before marking a node complete; graph status stays human-owned.

---

## Node-by-node: sell-valuables

### `intake-folder-convention`

| Field | Detail |
|-------|--------|
| **Plain English** | Define how Chris's stuff lands on disk: one folder per item with `description.txt`, optional `meta.yaml`, and `photos/`. |
| **Must be true to pass** | README documents layout and slug format; `_example/` exists; meta fields documented; CLIs ignore `_` folders; `.gitignore` keeps real photos out of git. |
| **Evidence needed** | `incoming/README.md`, `incoming/_example/`, `incoming/.gitignore`, grep for `startswith("_")` in CLIs. |
| **Inspect** | `incoming/README.md`, `incoming/_example/*`, `incoming/.gitignore`, `src/sell_valuables/generate_listing.py` |
| **Commands** | `grep startswith._ graphs/` repo; `ls incoming/_example` |
| **Likely verdict** | **pass** — all artifacts present in reference repo. |

---

### `intake-loader`

| Field | Detail |
|-------|--------|
| **Plain English** | Python loads one intake folder into a typed `ItemIntake` object. |
| **Must be true to pass** | `ItemIntake` dataclass; `load_item` validates description; photo extension filter; optional `meta.yaml`; `resolve_incoming_root`. |
| **Evidence needed** | `src/sell_valuables/intake.py` + unit test loading fixture. |
| **Inspect** | `intake.py`, `tests/test_listing.py::test_load_item_fixture` |
| **Commands** | `pytest tests/test_listing.py::test_load_item_fixture` |
| **Likely verdict** | **pass** |

---

### `listing-text-builder`

| Field | Detail |
|-------|--------|
| **Plain English** | Turn `ItemIntake` into title, body, and markdown listing text for FB. |
| **Must be true to pass** | `build_title` (80-char trim), `build_body` (condition/shipping/photos), `build_listing_markdown`, `FB_MARKETPLACE_CREATE_URL`. |
| **Evidence needed** | `listing.py` + tests asserting price, URL, pickup wording. |
| **Inspect** | `src/sell_valuables/listing.py`, `tests/test_listing.py` |
| **Commands** | `pytest tests/test_listing.py` |
| **Likely verdict** | **pass** |

---

### `listing-cli`

| Field | Detail |
|-------|--------|
| **Plain English** | `sell-listing` command writes `listing.md` for an item folder. |
| **Must be true to pass** | Entry point in `pyproject.toml`; `generate_listing()` writes file; item_id arg; auto-single-folder rule; `--incoming` override. |
| **Evidence needed** | `generate_listing.py`, `pyproject.toml`, manual CLI run against fixture. |
| **Inspect** | `src/sell_valuables/generate_listing.py`, `pyproject.toml` |
| **Commands** | `sell-listing sample-item --incoming tests/fixtures` |
| **Likely verdict** | **pass** (CLI exists; manual run recommended for extra evidence). |

---

### `fb-post-hook`

| Field | Detail |
|-------|--------|
| **Plain English** | `sell-post-fb` regenerates listing then opens browser or starts Playwright skeleton. |
| **Must be true to pass** | `sell-post-fb` entry point; always generates listing first; `--open` / `--playwright` / default manual hints. |
| **Evidence needed** | `post_to_fb.py`, `pyproject.toml`, optional manual run with `--open`. |
| **Inspect** | `src/sell_valuables/post_to_fb.py` |
| **Commands** | `sell-post-fb sample-item --incoming tests/fixtures` (dry manual path) |
| **Likely verdict** | **pass** on code; **needs-more-evidence** for live browser open. |

---

### `fb-playwright-session`

| Field | Detail |
|-------|--------|
| **Plain English** | Bootstrap Chromium with optional `storage_state.json` for FB login reuse. |
| **Must be true to pass** | `[browser]` extra in pyproject; load `.fb-session/storage_state.json`; clear error if Playwright missing; launch + goto create URL. |
| **Evidence needed** | `post_to_fb.py::post_with_playwright`, `.gitignore` for `.fb-session`, optional run with `pip install -e '.[browser]'`. |
| **Inspect** | `post_to_fb.py`, `pyproject.toml`, `.gitignore` |
| **Commands** | `pip install -e '.[browser]' && playwright install chromium`; `sell-post-fb <id> --playwright` |
| **Likely verdict** | **needs-more-evidence** — code present; needs Playwright install + non-headless/manual session save to prove session reuse. |

---

### `fb-playwright-form-fill`

| Field | Detail |
|-------|--------|
| **Plain English** | Fill FB Marketplace create form from intake data (title, price, description, photos). |
| **Must be true to pass** | Result dict fields; title from `build_title`; **commented** selector scaffold for fields and photos; dry_run stops before submit. |
| **Evidence needed** | `post_to_fb.py` commented lines; result dict shape on `--playwright` run. |
| **Inspect** | `post_to_fb.py` lines 58–63 |
| **Commands** | `sell-post-fb sample-item --playwright` → inspect printed `result` dict |
| **Likely verdict** | **needs-human-review** — criteria explicitly allow scaffold-only, but "form fill" is not live. Verifier must decide if scaffold satisfies node title or only acceptance IDs. |

**Unclear criteria:** Node title says "Wire … form fill" but acceptance only requires commented scaffold. Title vs criteria tension.

---

### `fb-submit-gate`

| Field | Detail |
|-------|--------|
| **Plain English** | Hard stop before Publish — no accidental live posts. |
| **Must be true to pass** | `dry_run=True` default; `dry_run=False` returns "not implemented"; commented Publish click; `submitted` stays False; graph policy `require_human_review_before_overnight: true`. |
| **Evidence needed** | `post_to_fb.py`, `graphs/sell-valuables/project.yaml` execution_policy, future `decision.md` for selector approval. |
| **Inspect** | `post_to_fb.py`, `project.yaml` |
| **Commands** | Code review only unless `dry_run=False` path is tested |
| **Likely verdict** | **pass** — repo intentionally stops before submit; matches acceptance. |

---

### `imessage-intake-path`

| Field | Detail |
|-------|--------|
| **Plain English** | Document how Chris's iMessage content gets into `incoming/` (manual v0 + Shortcuts plan). |
| **Must be true to pass** | `docs/imessage-shortcuts.md` + cross-link from `incoming/README.md`; manual steps; Shortcuts outline; later options noted. |
| **Evidence needed** | Markdown docs only (no Python). |
| **Inspect** | `docs/imessage-shortcuts.md`, `incoming/README.md` |
| **Commands** | `grep imessage-shortcuts incoming/README.md` |
| **Likely verdict** | **pass** |

---

### `test-suite`

| Field | Detail |
|-------|--------|
| **Plain English** | Pytest proves intake + listing builders work on a fixture. |
| **Must be true to pass** | `tests/fixtures/sample-item/`; three tests; dev extra includes pytest; README documents `pytest`. |
| **Evidence needed** | `tests/test_listing.py`, `pyproject.toml`, green pytest run. |
| **Inspect** | `tests/`, `pyproject.toml`, `README.md` |
| **Commands** | `pip install -e '.[dev]' && pytest` |
| **Likely verdict** | **pass** (3/3 tests pass). |

**Likely missing evidence:** Graph depends on `fb-post-hook` but no FB/post tests exist. Dependency is structural, not tested.

---

## sell-valuables — unclear criteria & missing evidence

| Issue | Nodes | Note |
|-------|-------|------|
| Title vs acceptance mismatch | `fb-playwright-form-fill` | Title implies live fill; criteria require comments only. |
| No automated FB coverage | `test-suite`, `fb-post-hook` | Pytest does not exercise post path despite graph edge. |
| Playwright session save | `fb-playwright-session` | `context.storage_state(path=...)` is commented; session persistence not proven. |
| Human artifacts absent | All | Nodes are `status: pending`; no `decision.md` / `result-summary.md` in graph repo (expected — those live in execution artifacts). |

---

# Graph 2: album-production

## Blueprint

Fictional end-to-end album release: songwriting through mastering, with parallel artwork (after demo) and marketing (after arrangement), converging at distribution and release day.

**Repo:** `sab-mini/album-production` — treat as creative/fictional; verify via artifacts, not code.

## Dependency map

```
songwriting ──► demo-recording ──┬──► arrangement ──┬──► studio-recording ──► mixing ──► mastering ──┐
                                 │                    │                                                ├──► distribution ──► album-release
                                 │                    └──► marketing-campaign ────────────────────────┘
                                 └──► album-art-design ──────────────────────────────────────────────┘
```

### Branch / convergence points

| Point | What happens |
|-------|----------------|
| **After demo** | Audio continues (`arrangement`); art starts (`album-art-design`). |
| **After arrangement** | Studio chain continues; marketing starts (`marketing-campaign`). |
| **Distribution convergence** | Needs **both** `mastering` and `album-art-design`. |
| **Release convergence** | Needs **both** `distribution` and `marketing-campaign`. |

## Running the loop (album-production)

1. `songwriting` (root) → unlocks `demo-recording`.
2. `demo-recording` → unlocks `arrangement` + `album-art-design` (parallel).
3. `arrangement` → unlocks `studio-recording` + `marketing-campaign` (parallel).
4. Linear audio: studio → mix → master.
5. `album-art-design` and `mastering` both complete → `distribution`.
6. `distribution` + `marketing-campaign` both complete → `album-release`.
7. Verifier checks **human artifacts** (audio files, images, decision.md) at each gate; no pytest.

---

## Node-by-node: album-production

*Likely verdict for all nodes today: **blocked** (no `sab-mini/album-production` artifact tree) or **needs-human-review** if operator claims progress without files.*

### `songwriting`

| Field | Detail |
|-------|--------|
| **Plain English** | Lock the album: track list, lyrics, chord charts, concept note. |
| **Must be true to pass** | Track list with keys/tempos; lyric sheets per track; chord charts; one-page concept; `decision.md` signoff on lyric freeze. |
| **Evidence** | `docs/songwriting/track-list.md`, per-track lyric/chord files, `decision.md` |
| **Inspect** | Version-controlled docs only |
| **Likely verdict** | **blocked** |

---

### `demo-recording`

| Field | Detail |
|-------|--------|
| **Plain English** | Reference demos for every song before arrangement spend. |
| **Must be true to pass** | 24-bit WAV per track under `audio/demos/`; BPM match; scratch vocals; session notes; review signoff. |
| **Evidence** | WAV files, `result-summary.md`, `decision.md` |
| **Inspect** | Audio files + DAW/session metadata |
| **Commands** | `ffprobe audio/demos/*.wav`; manual listening |
| **Likely verdict** | **blocked** |

---

### `arrangement`

| Field | Detail |
|-------|--------|
| **Plain English** | Final parts, click tracks, studio session plan. |
| **Must be true to pass** | Arrangement charts; click exports; session plan doc; form preserved from demos unless documented change. |
| **Evidence** | `docs/arrangement/`, `audio/clicks/`, `decision.md` |
| **Likely verdict** | **blocked** |

---

### `studio-recording`

| Field | Detail |
|-------|--------|
| **Plain English** | Final multitrack captures for every song. |
| **Must be true to pass** | Labeled stem folders; consistent sample rate; no clipping; session logs; producer signoff. |
| **Evidence** | Multitrack archives, `result-summary.md`, `decision.md` |
| **Likely verdict** | **blocked** |

---

### `mixing`

| Field | Detail |
|-------|--------|
| **Plain English** | Stereo mixes approved by artist, pre-master. |
| **Must be true to pass** | 24-bit mix WAVs; version labels; vocal clarity; no mastering chain; per-track artist approval in `decision.md`. |
| **Evidence** | `audio/mixes/*.wav`, `decision.md` |
| **Likely verdict** | **blocked** |

---

### `mastering`

| Field | Detail |
|-------|--------|
| **Plain English** | Distribution-ready masters (loudness, format). |
| **Must be true to pass** | Master WAVs; -14 to -10 LUFS; true peak ≤ -1 dBTP; sequence doc; QC listen signoff. |
| **Evidence** | `audio/masters/*.wav`, loudness meter screenshots/logs, `decision.md` |
| **Commands** | `ffmpeg`, `ebur128` or similar loudness analysis |
| **Likely verdict** | **blocked** |

---

### `album-art-design`

| Field | Detail |
|-------|--------|
| **Plain English** | Final cover and packaging assets (parallel to audio after demo). |
| **Must be true to pass** | 3000×3000 cover; social crops; layered source; concept alignment; explicit variant if needed. |
| **Evidence** | `assets/art/`, source files, `decision.md` |
| **Likely verdict** | **blocked** |

---

### `marketing-campaign`

| Field | Detail |
|-------|--------|
| **Plain English** | Pre-release calendar, copy, teasers (parallel after arrangement). |
| **Must be true to pass** | Release calendar; social copy for singles; press one-sheet; teaser clips; budget note. |
| **Evidence** | `docs/marketing/`, audio teasers, `result-summary.md` |
| **Likely verdict** | **blocked** |

**Unclear criteria:** "Do not announce final release date publicly until distribution confirms window" — verifier needs access to unpublished marketing drafts vs public posts.

---

### `distribution`

| Field | Detail |
|-------|--------|
| **Plain English** | Upload to aggregator; ISRC/UPC; territories — **convergence** of audio + art. |
| **Must be true to pass** | Upload complete; `docs/distribution/isrc-registry.yaml`; UPC doc; territories/date; preview QC on mobile + desktop. |
| **Evidence** | Distributor dashboard screenshots (redacted), registry YAML, `decision.md` |
| **Likely verdict** | **blocked** |

---

### `album-release`

| Field | Detail |
|-------|--------|
| **Plain English** | Release day: streams live + marketing posts published — **final convergence**. |
| **Must be true to pass** | Playable on 2+ platforms; release posts live; link page updated; Day-0 metrics; retro scheduled. |
| **Evidence** | Public URLs, screenshots, analytics export, `decision.md`, `result-summary.md` |
| **Likely verdict** | **blocked** |

---

## album-production — unclear criteria & missing evidence

| Issue | Nodes | Note |
|-------|-------|------|
| No code repo | All | Entire graph is artifact-verified; `sab-mini/album-production` may not exist yet. |
| Subjective audio QC | mixing, mastering | "Vocal intelligibility" and "QC listen" need human ears. |
| External platform state | distribution, album-release | Verifier needs distributor dashboard + live streaming links. |
| Calendar sync | marketing-campaign, distribution | Cross-node date alignment is semantic, not machine-checkable from YAML alone. |
| LUFS / true peak | mastering | Criteria cite numbers; verifier needs meter evidence. |
| All executors `human` | Most nodes | Loop is human-driven by design — Grok verifies artifacts, not PRs. |

---

# Cross-graph: what semantic verification requires

1. **Read** `project.yaml` + node YAML (why, acceptance ids, constraints, deps/unlocks).
2. **Walk dependency order** — do not verify children before parents unless checking partial implementation.
3. **Map criteria → evidence type** — code grep, test run, doc presence, binary artifact, or human signoff.
4. **Run commands** where cheap (pytest, CLI smoke, ffprobe); flag **needs-more-evidence** when tools/binaries missing.
5. **Record** files inspected, commands run, and criterion-level outcomes.
6. **Branch points** — verify parallel tracks independently; **convergence nodes** need all parents satisfied.
7. **Distinguish** schema-valid graphs from semantically complete implementations.

---

# Quick reference: likely verdicts today

## sell-valuables

| Node | Verdict |
|------|---------|
| intake-folder-convention | pass |
| intake-loader | pass |
| listing-text-builder | pass |
| listing-cli | pass |
| fb-post-hook | pass / needs-more-evidence (browser) |
| fb-playwright-session | needs-more-evidence |
| fb-playwright-form-fill | needs-human-review |
| fb-submit-gate | pass |
| imessage-intake-path | pass |
| test-suite | pass |

## album-production

| Node | Verdict |
|------|---------|
| songwriting | blocked |
| demo-recording | blocked |
| arrangement | blocked |
| studio-recording | blocked |
| mixing | blocked |
| mastering | blocked |
| album-art-design | blocked |
| marketing-campaign | blocked |
| distribution | blocked |
| album-release | blocked |