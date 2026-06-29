#!/usr/bin/env python3
"""Minimal node verification harness for gddp-config.

Runs semantic verification for ONE graph node against the node's source repo
and writes a transparent receipt (result.json + transcript.md).

Inputs:
    graphs/<project>/project.yaml        — graph context + repo pointer
    graphs/<project>/nodes/<node>.yaml   — acceptance criteria + constraints
    the source repo checkout             — files the criteria describe

Outputs:
    verification/<project>/<node>/result.json
    verification/<project>/<node>/transcript.md

Verdicts:
    pass | fail | blocked | needs-human-review | needs-more-evidence |
    out-of-scope-change-detected

This is a *harness*: deterministic, repeatable, no LLM, no network. It maps
each acceptance criterion id to a deterministic check (keyword/symbol presence
in the referenced source files), maps each constraint to a forbidden-pattern
scan, and records everything it looked at so a human (or later agent) can audit
the verdict without re-running it.

Source repo resolution:
    project.yaml has `repo: <owner>/<name>`. The harness resolves the local
    checkout to, in order: --repo-path flag, $GDDP_REPO_ROOT/<name>, or
    ../<name> relative to the gddp-config root. The first that exists wins.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("This script needs `pyyaml`. Install:  pip install pyyaml")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent

VERDICTS = (
    "pass",
    "fail",
    "blocked",
    "needs-human-review",
    "needs-more-evidence",
    "out-of-scope-change-detected",
)


# ── Data model ─────────────────────────────────────────────────────────────

@dataclass
class CriterionCheck:
    """One acceptance criterion, evaluated against the source repo."""
    id: str
    criterion: str
    status: str               # pass | fail | indeterminate
    confidence: float         # 0.0–1.0
    method: str               # how we checked (e.g. "symbol_present")
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""
    # Semantic classification of uncertainty (populated when status != pass).
    # These let the receipt say what KIND of uncertainty a finding is, not
    # just that it failed. See the addendum.
    mismatch_kind: str = ""   # wording | source_path | alias_integration | tier_distinct | ""
    mismatch_detail: str = ""
    needs_evidence: bool = False   # code exists but no test/live coverage
    human_question: str = ""       # a question a human must answer


@dataclass
class CriterionMismatch:
    """A structured criteria mismatch for the receipt.

    Flat list form so the JSON stays grep-able: {criterion_id, kind, detail}.
    """
    criterion_id: str
    kind: str
    detail: str


@dataclass
class MissingEvidence:
    """A 'code exists but not proven' finding for the receipt."""
    criterion_id: str
    what_is_missing: str   # e.g. "tests/acceptance.zsh grk smoke path"
    what_exists: str       # e.g. "grk sync dispatch path in lib/fire.zsh"


@dataclass
class HumanReviewQuestion:
    """A question that requires a human decision (not determinable by probe)."""
    criterion_id: str
    question: str


@dataclass
class ConstraintCheck:
    """One constraint, scanned for violations."""
    constraint: str
    status: str               # clear | violated | indeterminate
    confidence: float
    method: str
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class CommandRecord:
    """A command the harness actually ran, with its outcome."""
    command: str
    exit_code: int | None
    stdout_tail: str          # last few lines, for the transcript


@dataclass
class VerificationResult:
    project_id: str
    node_id: str
    verdict: str
    confidence: float
    criteria_checked: list[CriterionCheck]
    constraints_checked: list[ConstraintCheck]
    files_inspected: list[str]
    commands_run: list[CommandRecord]
    evidence_summary: str
    reasoning_summary: str
    required_next_action: str
    # Addendum fields — classify what KIND of uncertainty the findings are.
    criteria_mismatches: list[CriterionMismatch] = field(default_factory=list)
    missing_evidence: list[MissingEvidence] = field(default_factory=list)
    human_review_questions: list[HumanReviewQuestion] = field(default_factory=list)


# ── Probe registry (deterministic semantic checks) ─────────────────────────

# Map a criterion id (node.yaml) -> probe. Probe types:
#   symbol       — regex(s) must appear in named files (all=True: every pattern)
#   func         — a `name()` def must exist, plus body marker patterns
#   path         — a path must exist relative to repo root
#   tier_distinct — parse targets.conf; named target's tiers must resolve to
#                  DISTINCT commands (catches "speed tier == default tier").
#                  `alias_of` lists alias rows that must point at the same
#                  command as the canonical target.
#
# This is the semantic layer: it says what "met" means in code terms.
# Each probe can also carry a `mismatch_kind` so the receipt can classify the
# uncertainty (wording | source_path | alias_integration | tier_distinct).
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
}


def _slug_keywords(criterion_text: str) -> list[str]:
    """Fallback probe targets derived from the criterion text itself.

    Used when CHECK_PROBES has no explicit entry: extract the identifiers
    named in the criterion (aa_*/AA_*) and look for them in lib/*.zsh.
    Deterministic and conservative — if nothing matches, the check is
    `indeterminate`, not `fail`.
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", criterion_text)
    stop = {"the", "and", "for", "with", "from", "when", "not", "are",
            "must", "via", "into", "only", "that", "this", "under",
            "clear", "error", "returns", "non-zero", "installed", "against",
            "missing", "invalid", "filesystem", "produce", "helpers"}
    return [t for t in tokens if t.lower() not in stop and
            ("_" in t or t.startswith(("aa", "AA")))]


# ── Repo resolution ────────────────────────────────────────────────────────

def resolve_repo_path(project_yaml: dict, explicit: str | None) -> Path | None:
    """Resolve the source repo checkout for a project.

    Order: explicit flag > $GDDP_REPO_ROOT/<name> > ../<name> (sibling of
    gddp-config root). Returns the first existing dir, else None.
    """
    repo = project_yaml.get("repo", "")
    name = repo.split("/")[-1] if repo else ""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT")
    if env_root and name:
        candidates.append(Path(env_root).expanduser() / name)
    if name:
        candidates.append(ROOT.parent / name)
    for c in candidates:
        if c.is_dir():
            return c
    return None


# ── File + command helpers ─────────────────────────────────────────────────

def read_repo_file(repo: Path, rel: str) -> str | None:
    p = repo / rel
    if not p.is_file():
        return None
    try:
        return p.read_text(errors="replace")
    except OSError:
        return None


def run_command(repo: Path, argv: list[str]) -> CommandRecord:
    """Run a command (cwd=repo), capture tail of stdout + exit code."""
    display = " ".join(argv)
    try:
        proc = subprocess.run(
            argv, cwd=str(repo), capture_output=True, text=True, timeout=30,
        )
        out = (proc.stdout + proc.stderr).rstrip()
    except FileNotFoundError:
        return CommandRecord(display, None, f"<command not found: {argv[0]}>")
    except subprocess.TimeoutExpired:
        return CommandRecord(display, None, "<timed out after 30s>")
    tail = "\n".join(out.splitlines()[-6:])
    return CommandRecord(display, proc.returncode, tail)


def _grep_all(haystacks: list[str], patterns: list[str], want_all: bool):
    """Return (matched: bool, evidence: list[str])."""
    hits: dict[str, list[str]] = {p: [] for p in patterns}
    for p in patterns:
        rx = re.compile(p)
        for hay in haystacks:
            for m in rx.finditer(hay):
                line_no = hay.count("\n", 0, m.start()) + 1
                hits[p].append(f"line {line_no}: {m.group(0)!r}")
    if want_all:
        matched = all(hits[p] for p in patterns)
    else:
        matched = any(hits[p] for p in patterns)
    evidence: list[str] = []
    for p in patterns:
        if hits[p]:
            evidence.append(f"{p} -> {hits[p][0]}")
    return matched, evidence


def parse_targets_conf(text: str) -> dict[str, dict[str, str]]:
    """Parse aa-cli targets.conf into {target: {tier: command}}.

    Rows look like: `grk  default  sync  grk` or `codex default async __codex_async # alias`.
    Comment lines (start with #) and blank lines are skipped. An inline
    trailing comment (after the command) is stripped.
    """
    out: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        # Support both 3-column (target mode command, tier=default) and
        # 4-column (target tier mode command) legacy shapes.
        if len(parts) >= 4 and parts[1] in ("default", "speed", "frontier"):
            target, tier, _mode, command = parts[0], parts[1], parts[2], parts[3]
        else:
            target, _mode, command = parts[0], parts[1], parts[2]
            tier = "default"
        out.setdefault(target, {})[tier] = command
    return out


# ── Criterion evaluation ───────────────────────────────────────────────────

def evaluate_criterion(item: dict, repo: Path) -> CriterionCheck:
    cid = item.get("id", "<no-id>")
    text = item.get("criterion", "")
    probe = CHECK_PROBES.get(cid)

    if probe is None:
        # Fallback: keyword probe across lib/*.zsh
        kws = _slug_keywords(text)
        if not kws:
            return CriterionCheck(
                id=cid, criterion=text, status="indeterminate",
                confidence=0.1, method="no_probe", evidence=[],
                reasoning=("No deterministic probe is registered for this "
                           "criterion and no usable identifiers were found "
                           "in its text. Needs a human or an explicit probe."),
            )
        lib_dir = repo / "lib"
        lib_files = sorted(lib_dir.glob("*.zsh")) if lib_dir.is_dir() else []
        named = [(f.relative_to(repo).as_posix(),
                  read_repo_file(repo, f.relative_to(repo).as_posix()) or "")
                 for f in lib_files]
        patterns = [re.escape(k) for k in kws]
        matched, evidence = _grep_all([h for _, h in named], patterns,
                                      want_all=False)
        status = "pass" if matched else "indeterminate"
        files_with_hits = [name for (name, body), _ in
                           zip(named, [re.search(p, b) for p in patterns
                                       for _, b in named])
                           ] if matched else []
        return CriterionCheck(
            id=cid, criterion=text, status=status,
            confidence=0.5 if matched else 0.2,
            method="keyword_scan_lib",
            evidence=(evidence or ["no hit in any lib/*.zsh"])[:6],
            reasoning=(f"Scanned lib/*.zsh for identifiers named in the "
                       f"criterion ({', '.join(kws)}). "
                       + ("Found." if matched else "No match — but absence "
                          "could mean rewording, not failure.")),
        )

    ptype = probe["type"]
    mk = probe.get("mismatch_kind", "")
    hq = probe.get("human_question", "")
    mismatch_detail = ""
    needs_evidence = False

    if ptype == "tier_distinct":
        return _eval_tier_distinct(cid, text, probe, repo, mk, hq)

    if ptype == "path":
        rel = probe["path"]
        exists = (repo / rel).exists()
        also_grep = probe.get("also_grep", [])
        evidence: list[str] = [f"{rel} {'exists' if exists else 'absent'}"]
        grep_ok = True
        if exists and also_grep:
            body = read_repo_file(repo, rel) or ""
            gm, gev = _grep_all([body], also_grep, want_all=False)
            grep_ok = gm
            evidence.extend(gev or [f"none of {also_grep} found in {rel}"])
        if exists and grep_ok:
            status, conf, reasoning = "pass", 0.9, (
                f"Path {rel} exists and contains expected marker(s) "
                f"{also_grep or '(none required)'}.")
        elif exists and not grep_ok:
            status, conf, reasoning = "indeterminate", 0.5, (
                f"Path {rel} exists but none of {also_grep} found in it.")
            mk = mk or "wording"
            mismatch_detail = f"{rel} exists but lacks marker(s) {also_grep}"
        else:
            status, conf = "indeterminate", 0.4
            reasoning = f"Path {rel} absent."
            if probe.get("needs_evidence_when_absent"):
                needs_evidence = True
                reasoning += (f" Needs {probe.get('evidence_what', 'evidence')} "
                              "which was not found.")
        return CriterionCheck(
            id=cid, criterion=text, status=status, confidence=conf,
            method=ptype, evidence=evidence[:12], reasoning=reasoning,
            mismatch_kind=mk, mismatch_detail=mismatch_detail,
            needs_evidence=needs_evidence, human_question=hq)

    files = probe["files"]
    contents = [(f, read_repo_file(repo, f)) for f in files]
    missing = [f for f, c in contents if c is None]
    present = [(f, c) for f, c in contents if c is not None]
    evidence: list[str] = []
    if missing:
        evidence.append(f"missing files: {', '.join(missing)}")
        mk = mk or "source_path"
        mismatch_detail = (f"expected files not found in repo: "
                           f"{', '.join(missing)}")
    bodies = [c for _, c in present]

    if ptype in ("symbol", "any_of"):
        patterns = probe["patterns"]
        want_all = probe.get("all", ptype == "symbol")
        matched, ev = _grep_all(bodies, patterns, want_all=want_all)
        for fname, _ in present:
            evidence.append(f"in {fname}")
        evidence.extend(ev)
        status = "pass" if matched else "fail"
        conf = 0.9 if matched else (0.3 if not present else 0.7)
        reasoning = (f"Probed {', '.join(files)} for "
                     f"{'all of' if want_all else 'any of'} "
                     f"{patterns}. " + ("All present." if matched
                                        else "Pattern(s) missing."))
    elif ptype == "func":
        fname = probe["name"]
        patterns = [rf"\b{re.escape(fname)}\s*\(\)", *probe.get("patterns", [])]
        matched, ev = _grep_all(bodies, patterns, want_all=True)
        for f, _ in present:
            evidence.append(f"in {f}")
        evidence.extend(ev)
        status = "pass" if matched else "fail"
        conf = 0.9 if matched else 0.4
        reasoning = (f"Looked for function `{fname}()` plus body markers "
                     f"{probe.get('patterns', [])} in {', '.join(files)}. "
                     + ("Defined and uses expected helpers." if matched
                        else "Function or markers not found."))
    else:
        status, conf, matched, reasoning = ("indeterminate", 0.0, False,
                                            "unknown probe type")

    return CriterionCheck(
        id=cid, criterion=text, status=status, confidence=conf,
        method=ptype, evidence=evidence[:12], reasoning=reasoning,
        mismatch_kind=mk, mismatch_detail=mismatch_detail,
        needs_evidence=needs_evidence, human_question=hq)
def _eval_tier_distinct(cid, text, probe, repo, mk, hq):
    """Evaluate a tier_distinct probe against targets.conf.

    Checks the named target exists with required tiers, that tiers in
    require_distinct resolve to DISTINCT commands, and that aliases resolve
    to the same command as the canonical target. Surfaces tier_distinct and
    alias_integration mismatches specifically (not flat pass/fail).
    """
    rel = probe.get("file", "targets.conf")
    target = probe["target"]
    body = read_repo_file(repo, rel)
    evidence = []
    mismatch_detail = ""

    if body is None:
        return CriterionCheck(
            id=cid, criterion=text, status="indeterminate", confidence=0.3,
            method="tier_distinct", evidence=[rel + " absent"],
            reasoning=rel + " not found in repo.",
            mismatch_kind="source_path", mismatch_detail=rel + " not found",
            needs_evidence=False, human_question=hq)

    targets = parse_targets_conf(body)
    tiers = targets.get(target, {})
    tier_parts = []
    for t in sorted(tiers):
        tier_parts.append(t + "=" + str(tiers[t]))
    tier_str = ", ".join(tier_parts) if tier_parts else "NOT FOUND"
    evidence.append(rel + ": " + target + " -> " + tier_str)

    if not tiers:
        return CriterionCheck(
            id=cid, criterion=text, status="fail", confidence=0.5,
            method="tier_distinct", evidence=evidence,
            reasoning="Target '" + target + "' not registered in " + rel + ".",
            mismatch_kind=(mk or "source_path"),
            mismatch_detail=target + " has no rows in " + rel,
            needs_evidence=False, human_question=hq)

    require_present = probe.get("require_present", [])
    missing_tiers = [t for t in require_present if t not in tiers]
    if missing_tiers:
        evidence.append("missing tiers for " + target + ": "
                        + ", ".join(missing_tiers))
        return CriterionCheck(
            id=cid, criterion=text, status="fail", confidence=0.5,
            method="tier_distinct", evidence=evidence,
            reasoning=(target + " missing required tier(s) "
                       + str(missing_tiers) + "."),
            mismatch_kind=(mk or "source_path"),
            mismatch_detail=(target + " missing tiers " + str(missing_tiers)),
            needs_evidence=False, human_question=hq)
    require_distinct = probe.get("require_distinct")
    marker = probe.get("marker")
    nondistinct = []
    if require_distinct:
        cmds = {}
        for t in require_distinct:
            if t in tiers:
                cmds[t] = tiers[t]
        by_cmd = {}
        for t in cmds:
            key = cmds[t] if cmds[t] else "none"
            by_cmd.setdefault(key, []).append(t)
        for cmd in by_cmd:
            ts = by_cmd[cmd]
            if len(ts) > 1:
                nondistinct.append("+".join(ts) + " -> " + cmd)
        if marker:
            has_marker = any(c and re.search(marker, c) for c in cmds.values())
            if not has_marker:
                evidence.append("required marker " + marker + " not in any " + target + " tier command")
    aliases = probe.get("aliases", [])
    alias_problems = []
    if aliases:
        canon_cmd = tiers.get("default")
        for al in aliases:
            al_tiers = targets.get(al, {})
            al_cmd = al_tiers.get("default")
            if not al_tiers:
                alias_problems.append("alias " + al + " not in " + rel)
            elif al_cmd != canon_cmd:
                alias_problems.append("alias " + al + " default=" + str(al_cmd) + " != " + target + " default=" + str(canon_cmd))
    marker_ok = True
    if marker:
        marker_ok = any(c and re.search(marker, c) for c in tiers.values())
    ok = (not nondistinct) and (not alias_problems) and marker_ok
    if ok:
        status = "pass"
        conf = 0.85
        reasoning = target + " tiers resolve as expected in " + rel + "; no distinctness, marker, or alias problems."
    else:
        status = "indeterminate"
        conf = 0.6
        parts = []
        if nondistinct:
            parts.append("non-distinct tiers: " + "; ".join(nondistinct))
        if alias_problems:
            parts.append("alias issues: " + "; ".join(alias_problems))
        mismatch_detail = "; ".join(parts) if parts else "tier/alias mismatch"
        joined = "; ".join(parts) if parts else "mismatch"
        reasoning = target + " in " + rel + ": " + joined + ". Code partially disagrees with the criterion; needs human decision on whether the gap is intended."
        if not mk:
            mk = "alias_integration" if alias_problems else "tier_distinct"
        if not hq:
            hq = target + " tier/alias config in " + rel + " does not fully match the criterion. Is the gap intended?"
    return CriterionCheck(
        id=cid, criterion=text, status=status, confidence=conf,
        method="tier_distinct", evidence=evidence[:12], reasoning=reasoning,
        mismatch_kind=mk, mismatch_detail=mismatch_detail,
        needs_evidence=False, human_question=hq)




# ── Constraint scan (out-of-scope detection) ───────────────────────────────

# Forbidden markers derived from common constraint shapes:
#   "do not source executor-specific modules from common-core"
#   "do not add runtime dependencies beyond jq and zsh builtins"
FORBIDDEN_PATTERNS = [
    (r"\bsource\b.*\b(grok|pi|gemini|droid|codex|jules)\b.*\.zsh",
     "sourcing an executor-specific module from a common-layer file"),
    (r"^\s*python3?\b", "introducing a python runtime dependency in a zsh lib"),
]


def evaluate_constraint(text: str, repo: Path,
                        constraint_files: list[str]) -> ConstraintCheck:
    """Scan referenced lib files for forbidden patterns; light preservation
    check for things the constraint says must be preserved."""
    bodies = [(f, c) for f in constraint_files
              if (c := read_repo_file(repo, f)) is not None]
    evidence: list[str] = []
    violated = False
    for rx, why in FORBIDDEN_PATTERNS:
        comp = re.compile(rx, re.MULTILINE)
        for fname, body in bodies:
            for m in comp.finditer(body):
                line_no = body.count("\n", 0, m.start()) + 1
                evidence.append(f"{fname}:{line_no}: {why} ({m.group(0)!r})")
                violated = True
    if "AA_TARGETS_CONF" in text or "targets.conf" in text:
        for fname, body in bodies:
            if re.search(r"AA_TARGETS_CONF=.*targets\.conf", body):
                evidence.append(f"{fname}: AA_TARGETS_CONF default points at "
                                f"targets.conf (preserved)")
                break
    status = "violated" if violated else "clear"
    return ConstraintCheck(
        constraint=text, status=status, confidence=0.85 if not violated else 0.75,
        method="forbidden_pattern_scan",
        evidence=evidence or ["no forbidden patterns matched"],
        reasoning=("Scanned referenced lib files for forbidden patterns "
                   "(executor sourcing, runtime deps). "
                   + ("No violations." if not violated
                      else f"{len(evidence)} violation(s).")),
    )


# ── Graph dependency context (blocked detection) ───────────────────────────

def dependency_status(project_yaml: dict, depends_on: list[str]) -> dict:
    """Return {dep_id: status} from the project graph index."""
    nodes = {n["id"]: n for n in project_yaml.get("nodes", [])
             if isinstance(n, dict) and "id" in n}
    return {d: nodes.get(d, {}).get("status", "unknown") for d in depends_on}


def _round(x: float) -> float:
    return round(x, 3)


def decide_verdict(criteria: list[CriterionCheck],
                   constraints: list[ConstraintCheck],
                   deps: dict, artifacts_present: dict,
                   required_artifacts: list[str]) -> tuple[str, float, str]:
    """Compute verdict, confidence, and required_next_action."""
    incomplete = [d for d, s in deps.items()
                  if s not in ("complete", "unknown")]
    if incomplete:
        return ("blocked", 0.9,
                f"Dependencies not complete: {', '.join(incomplete)}. "
                "Complete or unblock them before this node can be verified.")

    violated = [c for c in constraints if c.status == "violated"]
    if violated:
        return ("out-of-scope-change-detected", 0.8,
                "Constraint violation(s) detected: "
                + "; ".join(c.constraint[:60] for c in violated)
                + ". Review the source changes against node constraints.")

    missing_artifacts = [a for a in required_artifacts
                         if not artifacts_present.get(a, False)]
    crit_pass = [c for c in criteria if c.status == "pass"]
    crit_fail = [c for c in criteria if c.status == "fail"]
    crit_indet = [c for c in criteria if c.status == "indeterminate"]

    if crit_fail:
        conf = _round(sum(c.confidence for c in crit_fail) / len(crit_fail))
        return ("fail", conf,
                f"{len(crit_fail)} criterion/criteria not met: "
                + ", ".join(c.id for c in crit_fail)
                + ". Fix the failing acceptance criteria in the source repo.")

    if missing_artifacts and crit_indet:
        return ("needs-more-evidence", 0.5,
                f"Missing artifacts ({', '.join(missing_artifacts)}) and "
                f"{len(crit_indet)} criterion/criteria indeterminate. "
                "Provide the artifacts and re-run.")

    if missing_artifacts:
        return ("needs-more-evidence", 0.5,
                f"Required artifacts missing: {', '.join(missing_artifacts)}. "
                "Run/review the node so its completion artifacts are produced, "
                "then re-run.")

    if crit_indet and not crit_pass:
        return ("needs-more-evidence", 0.3,
                f"All {len(crit_indet)} criteria indeterminate — harness has "
                "no deterministic probe for them. Register probes or review "
                "manually.")

    if crit_indet:
        return ("needs-human-review", 0.6,
                f"{len(crit_pass)} pass, {len(crit_indet)} indeterminate. "
                "Passing criteria look good; the indeterminate ones need a "
                "human or an explicit probe.")

    conf = _round(min(1.0, sum(c.confidence for c in criteria) / len(criteria))
                  ) if criteria else 0.0
    return ("pass", conf,
            "All acceptance criteria met, no constraint violations, required "
            "artifacts present. Ready for human accept.")


# ── Main verification flow ─────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def collect_constraint_files(node_yaml: dict, repo: Path) -> list[str]:
    """Files the constraints scope: explicit probe files + all lib/*.zsh."""
    files: set[str] = set()
    for item in node_yaml.get("acceptance", []):
        probe = CHECK_PROBES.get(item.get("id", ""))
        if probe:
            files.update(probe.get("files", []))
            if probe.get("file"):
                files.add(probe["file"])
    if (repo / "lib").is_dir():
        for f in sorted((repo / "lib").glob("*.zsh")):
            files.add(f.relative_to(repo).as_posix())
    return sorted(files)


def check_artifacts(node_yaml: dict, repo: Path) -> dict:
    """Look for required_artifacts in repo root and a few likely spots.
    merged_pr needs network and is treated as not-present in this harness."""
    required = node_yaml.get("required_artifacts", [])
    present: dict[str, bool] = {}
    for a in required:
        if a == "merged_pr":
            present[a] = False
            continue
        spots = [repo / a, repo / ".gddp" / a, repo / "docs" / a]
        present[a] = any(s.is_file() for s in spots)
    return present


def verify(project_id: str, node_id: str, *,
           root: Path = ROOT, repo_path: str | None = None) -> VerificationResult:
    graphs = root / "graphs" / project_id
    proj_file = graphs / "project.yaml"
    node_file = graphs / "nodes" / f"{node_id}.yaml"
    if not proj_file.is_file():
        raise FileNotFoundError(f"project not found: {proj_file}")
    if not node_file.is_file():
        raise FileNotFoundError(f"node not found: {node_file}")

    project_yaml = load_yaml(proj_file)
    node_yaml = load_yaml(node_file)

    repo = resolve_repo_path(project_yaml, repo_path)
    commands: list[CommandRecord] = []
    files_inspected: set[str] = {
        f"graphs/{project_id}/project.yaml",
        f"graphs/{project_id}/nodes/{node_id}.yaml",
    }

    criteria: list[CriterionCheck] = []
    constraints: list[ConstraintCheck] = []

    if repo is None:
        repo_name = project_yaml.get("repo", "?").split("/")[-1]
        for item in node_yaml.get("acceptance", []):
            criteria.append(CriterionCheck(
                id=item.get("id", "?"), criterion=item.get("criterion", ""),
                status="indeterminate", confidence=0.0,
                method="repo_not_found", evidence=[],
                reasoning=(f"Source repo for {project_yaml.get('repo')} "
                           f"not found locally (tried ../{repo_name}, "
                           f"$GDDP_REPO_ROOT/{repo_name}, --repo-path)."),
            ))
        action = (f"Resolve the source repo for {project_yaml.get('repo')} "
                  f"(use --repo-path or set GDDP_REPO_ROOT) and re-run.")
        return VerificationResult(
            project_id=project_id, node_id=node_id,
            verdict="needs-more-evidence", confidence=0.2,
            criteria_checked=criteria, constraints_checked=constraints,
            files_inspected=sorted(files_inspected),
            commands_run=commands,
            evidence_summary="Source repo not found; no semantic checks ran.",
            reasoning_summary=action, required_next_action=action,
        )

    files_inspected.add(f"<repo:{repo.name}>")
    commands.append(run_command(repo, ["test", "-f", "schema/packet.schema.json"]))

    for item in node_yaml.get("acceptance", []):
        cc = evaluate_criterion(item, repo)
        criteria.append(cc)
        probe = CHECK_PROBES.get(item.get("id", ""))
        if probe:
            for f in probe.get("files", []):
                files_inspected.add(f"{repo.name}/{f}")
            for f in probe.get("also_check_files", []):
                files_inspected.add(f"{repo.name}/{f}")
            single = probe.get("file")
            if single:
                files_inspected.add(f"{repo.name}/{single}")

    constraint_files = collect_constraint_files(node_yaml, repo)
    for f in constraint_files:
        files_inspected.add(f"{repo.name}/{f}")
    for text in node_yaml.get("constraints", []):
        constraints.append(evaluate_constraint(text, repo, constraint_files))

    deps = dependency_status(project_yaml, node_yaml.get("depends_on", []))
    artifacts = check_artifacts(node_yaml, repo)

    verdict, conf, action = decide_verdict(
        criteria, constraints, deps, artifacts,
        node_yaml.get("required_artifacts", []))

    criteria_mismatches = [
        CriterionMismatch(criterion_id=c.id, kind=c.mismatch_kind, detail=c.mismatch_detail)
        for c in criteria if c.mismatch_kind and c.status != "pass"
    ]
    missing_evidence = [
        MissingEvidence(criterion_id=c.id,
                        what_is_missing=(c.mismatch_detail or c.reasoning),
                        what_exists=c.evidence[0] if c.evidence else "")
        for c in criteria if c.needs_evidence
    ]
    human_review_questions = [
        HumanReviewQuestion(criterion_id=c.id, question=c.human_question)
        for c in criteria if c.human_question
    ]

    ev_lines = [f"[{c.status}] {c.id}: {c.reasoning}" for c in criteria]
    ev_lines += [f"[{c.status}] constraint: {c.reasoning}" for c in constraints]
    evidence_summary = "\n".join(ev_lines) or "(no checks)"

    reason_lines = []
    if deps:
        reason_lines.append("deps: " +
                            ", ".join(f"{k}={v}" for k, v in deps.items()))
    reason_lines.append(f"criteria: "
                        f"{sum(1 for c in criteria if c.status=='pass')}/"
                        f"{len(criteria)} pass")
    reason_lines.append(f"constraints: "
                        f"{sum(1 for c in constraints if c.status=='clear')}/"
                        f"{len(constraints)} clear")
    reason_lines.append(f"artifacts: "
                        f"{sum(1 for v in artifacts.values() if v)}/"
                        f"{len(artifacts)} present")
    reasoning_summary = "; ".join(reason_lines)

    return VerificationResult(
        project_id=project_id, node_id=node_id, verdict=verdict,
        confidence=conf, criteria_checked=criteria,
        constraints_checked=constraints,
        files_inspected=sorted(files_inspected),
        commands_run=commands,
        evidence_summary=evidence_summary,
        reasoning_summary=reasoning_summary,
        required_next_action=action,
        criteria_mismatches=criteria_mismatches,
        missing_evidence=missing_evidence,
        human_review_questions=human_review_questions,
    )


# ── Receipt writers ────────────────────────────────────────────────────────

def _result_to_jsonable(r: VerificationResult) -> dict:
    return {
        "project_id": r.project_id,
        "node_id": r.node_id,
        "verdict": r.verdict,
        "confidence": r.confidence,
        "criteria_checked": [asdict(c) for c in r.criteria_checked],
        "constraints_checked": [asdict(c) for c in r.constraints_checked],
        "files_inspected": r.files_inspected,
        "commands_run": [asdict(c) for c in r.commands_run],
        "evidence_summary": r.evidence_summary,
        "reasoning_summary": r.reasoning_summary,
        "required_next_action": r.required_next_action,
        "criteria_mismatches": [asdict(m) for m in r.criteria_mismatches],
        "missing_evidence": [asdict(m) for m in r.missing_evidence],
        "human_review_questions": [asdict(q) for q in r.human_review_questions],
    }


def write_receipt(r: VerificationResult, root: Path = ROOT) -> tuple[Path, Path]:
    out_dir = root / "verification" / r.project_id / r.node_id
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "result.json"
    transcript_path = out_dir / "transcript.md"
    result_path.write_text(
        json.dumps(_result_to_jsonable(r), indent=2) + "\n",
        encoding="utf-8")
    transcript_path.write_text(_render_transcript(r), encoding="utf-8")
    return result_path, transcript_path


def _render_transcript(r: VerificationResult) -> str:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L: list[str] = []
    L.append(f"# Verification Transcript — {r.project_id}/{r.node_id}")
    L.append("")
    L.append(f"- generated_at: {now}")
    L.append(f"- verdict: **{r.verdict}**")
    L.append(f"- confidence: {r.confidence}")
    L.append("")
    L.append("## Reasoning summary")
    L.append("")
    L.append(r.reasoning_summary)
    L.append("")
    L.append("## Required next action")
    L.append("")
    L.append(r.required_next_action)
    L.append("")
    L.append("## Acceptance criteria")
    L.append("")
    for c in r.criteria_checked:
        L.append(f"### [{c.status}] `{c.id}`  (confidence {c.confidence})")
        L.append("")
        L.append(f"> {c.criterion}")
        L.append("")
        L.append(f"- method: `{c.method}`")
        L.append(f"- reasoning: {c.reasoning}")
        if c.evidence:
            L.append("- evidence:")
            for e in c.evidence:
                L.append(f"  - {e}")
        L.append("")
    L.append("## Constraints")
    L.append("")
    for c in r.constraints_checked:
        L.append(f"### [{c.status}] (confidence {c.confidence})")
        L.append("")
        L.append(f"> {c.constraint}")
        L.append("")
        L.append(f"- method: `{c.method}`")
        L.append(f"- reasoning: {c.reasoning}")
        if c.evidence:
            L.append("- evidence:")
            for e in c.evidence:
                L.append(f"  - {e}")
        L.append("")
    L.append("## Files inspected")
    L.append("")
    for f in r.files_inspected:
        L.append(f"- `{f}`")
    L.append("")
    L.append("## Commands run")
    L.append("")
    if r.commands_run:
        for c in r.commands_run:
            ec = c.exit_code if c.exit_code is not None else "n/a"
            L.append(f"### `{c.command}`  (exit {ec})")
            L.append("")
            L.append("```")
            L.append(c.stdout_tail)
            L.append("```")
            L.append("")
    else:
        L.append("_(none)_")
        L.append("")
    if r.criteria_mismatches:
        L.append("## Criteria mismatches")
        L.append("")
        for m in r.criteria_mismatches:
            L.append("- **" + m.kind + "** " + m.criterion_id + ": " + m.detail)
        L.append("")
    if r.missing_evidence:
        L.append("## Missing evidence")
        L.append("")
        for me in r.missing_evidence:
            L.append("- " + me.criterion_id + ": needs " + me.what_is_missing)
        L.append("")
    if r.human_review_questions:
        L.append("## Human review questions")
        L.append("")
        for q in r.human_review_questions:
            L.append("- " + q.criterion_id + ": " + q.question)
        L.append("")
    L.append("## Evidence summary")
    L.append("")
    L.append("```")
    L.append(r.evidence_summary)
    L.append("```")
    L.append("")
    return "\n".join(L)


# ── CLI ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="gddp verify",
        description=("Run semantic verification for one graph node; "
                     "emit a receipt."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("verb", choices=["node"], help="what to verify (only 'node')")
    p.add_argument("--project", required=True, help="project id")
    p.add_argument("--node", required=True, help="node id")
    p.add_argument("--repo-path", default=None,
                   help="path to the source repo checkout (overrides auto-resolve)")
    p.add_argument("--root", type=Path, default=ROOT,
                   help="gddp-config root (default: parent of scripts/)")
    p.add_argument("--json", action="store_true",
                   help="print result.json to stdout instead of summary")
    args = p.parse_args(argv)

    try:
        r = verify(args.project, args.node, root=args.root,
                   repo_path=args.repo_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result_path, transcript_path = write_receipt(r, args.root)

    if args.json:
        print(json.dumps(_result_to_jsonable(r), indent=2))
    else:
        print(f"verdict: {r.verdict}  (confidence {r.confidence})")
        print(f"  project: {r.project_id}   node: {r.node_id}")
        print(f"  criteria: "
              f"{sum(1 for c in r.criteria_checked if c.status=='pass')}/"
              f"{len(r.criteria_checked)} pass")
        print(f"  constraints: "
              f"{sum(1 for c in r.constraints_checked if c.status=='clear')}/"
              f"{len(r.constraints_checked)} clear")
        print(f"  receipt:    {result_path.relative_to(args.root)}")
        print(f"  transcript: {transcript_path.relative_to(args.root)}")
        print(f"  next: {r.required_next_action}")

    return 0 if r.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
