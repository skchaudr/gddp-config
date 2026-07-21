#!/usr/bin/env python3
"""Strict global validator for gddp-config node YAML files.

Walks graphs/*/nodes/*.yaml (skips graphs/_template/) and checks every file
against the schema documented in schemas/v1/node.yaml.

Modes:
  default    — human-readable, errors + warnings
  --json     — machine-readable findings (for new_node.py post-write hook)
  --strict   — warnings count as errors
  --project  — only check one project
  --quiet    — only print summary line

Exit code: 1 if any errors (or warnings in --strict), else 0.

Constants are inline (mirrored from schemas/v1/node.yaml) — keeps this file
self-contained and understandable top-to-bottom.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    print("This script needs `pyyaml`. Install:  pip install pyyaml")
    sys.exit(1)


# ── Schema constants (mirror schemas/v1/node.yaml) ─────────────────────────

VALID_TYPES = {"capability", "milestone", "constraint"}
VALID_STATUSES = {"pending", "ready", "complete", "deferred"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_EXEC_MODES = {"agent", "jules", "vertex", "pi_worker", "vm_worker", "human"}
KNOWN_ARTIFACTS = {"decision.md", "result-summary.md", "patch.diff",
                    "graph-update.yaml", "merged_pr"}

REQUIRED_FIELDS = {
    "node_id": str,
    "title": str,
    "type": str,
    "why": str,
    "depends_on": list,
    "acceptance_criteria": list,
    "constraints": list,
    "allowed_execution_modes": list,
    "required_artifacts": list,
    "status": str,
    "priority": str,
    "unlocks": list,
}

LIST_FIELDS = ("depends_on", "unlocks", "constraints",
                "allowed_execution_modes", "required_artifacts")

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


@dataclass
class Finding:
    path: str
    line: int  # best-effort, 0 if unknown
    severity: str  # "error" or "warning"
    rule: str
    message: str


def validate_node(path: Path, rel: str, doc: dict) -> list[Finding]:
    findings: list[Finding] = []

    # Envelope (documented but enforced)
    if doc.get("schema_version") != "1.0":
        findings.append(Finding(rel, 1, "error", "schema_version",
                                 f"expected '1.0', got {doc.get('schema_version')!r}"))
    if doc.get("schema_type") != "node":
        findings.append(Finding(rel, 1, "error", "schema_type",
                                 f"expected 'node', got {doc.get('schema_type')!r}"))

    # Required fields + types
    for name, typ in REQUIRED_FIELDS.items():
        if name not in doc:
            findings.append(Finding(rel, 0, "error", "missing_field",
                                     f"{name} not present"))
        elif not isinstance(doc[name], typ):
            findings.append(Finding(rel, 0, "error", "type_error",
                                     f"{name} must be {typ.__name__}, "
                                     f"got {type(doc[name]).__name__}"))

    # Enum checks
    if isinstance(doc.get("type"), str) and doc["type"] not in VALID_TYPES:
        findings.append(Finding(rel, 0, "error", "type_enum",
                                 f"type {doc['type']!r} not in {sorted(VALID_TYPES)}"))
    if isinstance(doc.get("status"), str) and doc["status"] not in VALID_STATUSES:
        findings.append(Finding(rel, 0, "error", "status_enum",
                                 f"status {doc['status']!r} not in {sorted(VALID_STATUSES)}"))
    if isinstance(doc.get("priority"), str) and doc["priority"] not in VALID_PRIORITIES:
        findings.append(Finding(rel, 0, "error", "priority_enum",
                                 f"priority {doc['priority']!r} not in {sorted(VALID_PRIORITIES)}"))

    # exec modes subset
    modes = doc.get("allowed_execution_modes") or []
    if isinstance(modes, list):
        bad = [m for m in modes if not isinstance(m, str) or m not in VALID_EXEC_MODES]
        if bad:
            findings.append(Finding(rel, 0, "error", "exec_mode_enum",
                                     f"unknown execution modes: {bad}"))

    # artifacts — warn on unknown (forward-compat for future artifact types)
    artifacts = doc.get("required_artifacts") or []
    if isinstance(artifacts, list):
        unknown = [a for a in artifacts if isinstance(a, str) and a not in KNOWN_ARTIFACTS]
        if unknown:
            findings.append(Finding(rel, 0, "warning", "unknown_artifact",
                                     f"not in known set: {unknown}"))

    # Identity: node_id matches filename, kebab-case
    node_id = doc.get("node_id")
    if isinstance(node_id, str):
        expected = path.stem
        if node_id != expected:
            findings.append(Finding(rel, 0, "error", "id_filename_mismatch",
                                     f"node_id {node_id!r} doesn't match filename {expected!r}"))
        if not KEBAB_RE.match(node_id):
            findings.append(Finding(rel, 0, "error", "id_format",
                                     f"node_id {node_id!r} not kebab-case"))

    # Acceptance shape: list of {id: str, criterion: str}
    acceptance = doc.get("acceptance_criteria")
    if acceptance is not None:
        if not isinstance(acceptance, list):
            findings.append(Finding(rel, 0, "error", "acceptance_type",
                                     f"acceptance must be a list, got {type(acceptance).__name__}"))
        elif not acceptance:
            findings.append(Finding(rel, 0, "error", "acceptance_empty",
                                     "acceptance must have at least one entry"))
        else:
            for idx, entry in enumerate(acceptance):
                if not isinstance(entry, dict):
                    findings.append(Finding(rel, 0, "error", "acceptance_shape",
                                             f"acceptance[{idx}] must be a dict with id and criterion, "
                                             f"got {type(entry).__name__}"))
                    continue
                if "id" not in entry or "criterion" not in entry:
                    findings.append(Finding(rel, 0, "error", "acceptance_shape",
                                             f"acceptance[{idx}] missing 'id' or 'criterion' key"))
                    continue
                acc_id = entry["id"]
                if not isinstance(acc_id, str):
                    findings.append(Finding(rel, 0, "error", "acceptance_id_type",
                                             f"acceptance[{idx}].id must be string"))
                elif not KEBAB_RE.match(acc_id):
                    findings.append(Finding(rel, 0, "error", "acceptance_id_format",
                                             f"acceptance[{idx}].id {acc_id!r} not kebab-case"))
                if not isinstance(entry["criterion"], str):
                    findings.append(Finding(rel, 0, "error", "acceptance_criterion_type",
                                             f"acceptance[{idx}].criterion must be string"))

    # Lists must contain only strings (unquoted colon mid-item parses as dict)
    for fname in LIST_FIELDS:
        val = doc.get(fname)
        if isinstance(val, list):
            non_str = [(i, x) for i, x in enumerate(val) if not isinstance(x, str)]
            if non_str:
                for idx, item in non_str:
                    if isinstance(item, dict) and len(item) == 1:
                        recovered = next(iter(item.keys())) + ": " + next(iter(item.values()))
                        findings.append(Finding(rel, 0, "warning",
                                                 "implicit_mapping_in_list",
                                                 f"{fname}[{idx}] parsed as dict (unquoted colon) — "
                                                 f"quote the string: {recovered[:80]}"))
                    else:
                        findings.append(Finding(rel, 0, "error", "list_of_strings",
                                                 f"{fname}[{idx}] must be string, "
                                                 f"got {type(item).__name__}"))

    return findings


def cross_node_findings(project_id: str, node_docs: dict[str, dict]) -> list[Finding]:
    """Check depends_on/unlocks references within a project."""
    findings: list[Finding] = []
    known_ids = set(node_docs.keys())  # filename stems == node_ids (validator enforces elsewhere)

    for filename, doc in node_docs.items():
        rel = f"graphs/{project_id}/nodes/{filename}.yaml"
        depends = doc.get("depends_on") or []
        unlocks = doc.get("unlocks") or []

        for ref in depends:
            if isinstance(ref, str) and ref not in known_ids:
                findings.append(Finding(rel, 0, "warning", "dangling_depends_on",
                                         f"depends_on {ref!r} not found in project"))
        for ref in unlocks:
            if isinstance(ref, str) and ref not in known_ids:
                findings.append(Finding(rel, 0, "warning", "dangling_unlocks",
                                         f"unlocks {ref!r} not found (may be future node)"))

        # Symmetry: A unlocks B implies B depends_on A
        for ref in unlocks:
            if isinstance(ref, str) and ref in node_docs:
                peer_depends = node_docs[ref].get("depends_on") or []
                if filename not in peer_depends:
                    findings.append(Finding(rel, 0, "warning", "asymmetric_edge",
                                             f"unlocks {ref!r} but {ref}.yaml doesn't "
                                             f"list this node in depends_on"))

    return findings


def iter_node_files(graphs_dir: Path, project_filter: str | None):
    """Yield (project_id, file_path) pairs."""
    if not graphs_dir.exists():
        return
    for project_dir in sorted(graphs_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name == "_template":
            continue
        if project_filter and project_dir.name != project_filter:
            continue
        nodes_dir = project_dir / "nodes"
        if not nodes_dir.exists():
            continue
        for path in sorted(nodes_dir.glob("*.yaml")):
            yield project_dir.name, path


def run(root: Path, project_filter: str | None = None) -> list[Finding]:
    graphs_dir = root / "graphs"
    project_nodes: dict[str, dict[str, dict]] = {}
    all_findings: list[Finding] = []

    for project_id, path in iter_node_files(graphs_dir, project_filter):
        rel = f"graphs/{project_id}/nodes/{path.name}"
        try:
            with open(path) as f:
                doc = yaml.safe_load(f)
        except yaml.YAMLError as e:
            all_findings.append(Finding(rel, 0, "error", "yaml_parse", str(e)))
            continue
        except OSError as e:
            all_findings.append(Finding(rel, 0, "error", "io_error", str(e)))
            continue

        if not isinstance(doc, dict):
            all_findings.append(Finding(rel, 0, "error", "not_mapping",
                                         "top-level YAML must be a mapping"))
            continue

        all_findings.extend(validate_node(path, rel, doc))
        project_nodes.setdefault(project_id, {})[path.stem] = doc

    # Cross-node per project
    for project_id, node_docs in project_nodes.items():
        all_findings.extend(cross_node_findings(project_id, node_docs))

    # Uniqueness of node_ids within project
    for project_id, node_docs in project_nodes.items():
        seen: dict[str, str] = {}
        for filename, doc in node_docs.items():
            nid = doc.get("node_id")
            if isinstance(nid, str):
                if nid in seen:
                    rel = f"graphs/{project_id}/nodes/{filename}.yaml"
                    all_findings.append(Finding(rel, 0, "error", "duplicate_id",
                                                 f"node_id {nid!r} also in {seen[nid]}.yaml"))
                else:
                    seen[nid] = filename

    return all_findings


def render_human(findings: list[Finding], strict: bool) -> str:
    if not findings:
        return "[green]✓ all nodes valid[/green]"

    lines = []
    for f in findings:
        if f.severity == "error":
            sev_str = "ERROR"
        elif strict:
            sev_str = "ERROR*"
        else:
            sev_str = "WARN"
        loc = f.path if f.line == 0 else f"{f.path}:{f.line}"
        lines.append(f"{loc} — {sev_str} — {f.rule} — {f.message}")

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    effective_errors = errors + warnings if strict else errors
    files = len({f.path for f in findings})

    lines.append("")
    parts = []
    if effective_errors:
        parts.append(f"{effective_errors} error{'s' if effective_errors != 1 else ''}")
    if warnings and not strict:
        parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
    lines.append(f"{', '.join(parts)} across {files} file{'s' if files != 1 else ''}")
    return "\n".join(lines)


def render_json(findings: list[Finding]) -> str:
    return json.dumps({
        "errors": [f.__dict__ for f in findings if f.severity == "error"],
        "warnings": [f.__dict__ for f in findings if f.severity == "warning"],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "files_checked": len({f.path for f in findings}),
        },
    }, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", default=None,
                        help="Only check this project")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable output")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print summary line")
    parser.add_argument("--root", type=Path, default=None,
                        help="gddp-config root (default: parent of this script's dir)")
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent

    findings = run(root, args.project)

    if args.json:
        print(render_json(findings))
    elif args.quiet:
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if args.strict:
            errors += warnings
        print(f"errors={errors} warnings={warnings}")
    else:
        # Plain text — no rich here so output is greppable
        for f in findings:
            if f.severity == "error":
                sev = "ERROR"
            elif args.strict:
                sev = "ERROR*"
            else:
                sev = "WARN"
            loc = f.path if f.line == 0 else f"{f.path}:{f.line}"
            print(f"{loc} — {sev} — {f.rule} — {f.message}")
        if not findings:
            print("OK — all nodes valid")
        else:
            errors = sum(1 for f in findings if f.severity == "error")
            warnings = sum(1 for f in findings if f.severity == "warning")
            if args.strict:
                errors += warnings
            files = len({f.path for f in findings})
            print()
            print(f"{errors} error(s), {warnings if not args.strict else 0} warning(s) "
                  f"across {files} file(s)")

    errors = sum(1 for f in findings if f.severity == "error")
    if args.strict:
        errors += sum(1 for f in findings if f.severity == "warning")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
