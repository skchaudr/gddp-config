#!/usr/bin/env python3
"""import_node.py — validate and import a node YAML into a project graph.

Designed for agent pipelines: accepts a node YAML (file or stdin), validates it,
writes it to the project's nodes/ directory, and patches project.yaml.

Usage:
    python3 scripts/gddp.py node import --file draft.yaml --project my-app
    echo '<yaml>' | python3 scripts/gddp.py node import --stdin --project my-app

    --auto-approve   skip interactive review, just validate + write
    --dry-run        validate only, don't write

Exit codes:
    0   node imported successfully
    1   validation errors (node not written)
    2   node already exists
    3   project not found

Output:
    Always prints JSON findings to stdout for machine consumption.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Install: pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent

VALID_TYPES = {"capability", "milestone", "constraint"}
VALID_STATUSES = {"pending", "ready", "complete", "deferred"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_EXEC_MODES = {"jules", "vertex", "pi_worker", "vm_worker", "human"}
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

KEBAB_RE = __import__("re").compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def validate_node_yaml(doc: dict, source_label: str = "input") -> list[dict]:
    """Validate a parsed YAML dict against the node schema. Returns findings list."""
    findings = []

    if doc.get("schema_version") != "1.0":
        findings.append({"severity": "error", "rule": "schema_version",
                          "message": f"expected '1.0', got {doc.get('schema_version')!r}",
                          "source": source_label})
    if doc.get("schema_type") != "node":
        findings.append({"severity": "error", "rule": "schema_type",
                          "message": f"expected 'node', got {doc.get('schema_type')!r}",
                          "source": source_label})

    for name, typ in REQUIRED_FIELDS.items():
        if name not in doc:
            findings.append({"severity": "error", "rule": "missing_field",
                              "message": f"{name} not present",
                              "source": source_label})
        elif not isinstance(doc[name], typ):
            findings.append({"severity": "error", "rule": "type_error",
                              "message": f"{name} must be {typ.__name__}, got {type(doc[name]).__name__}",
                              "source": source_label})

    if isinstance(doc.get("type"), str) and doc["type"] not in VALID_TYPES:
        findings.append({"severity": "error", "rule": "type_enum",
                          "message": f"type {doc['type']!r} not in {sorted(VALID_TYPES)}",
                          "source": source_label})
    if isinstance(doc.get("status"), str) and doc["status"] not in VALID_STATUSES:
        findings.append({"severity": "error", "rule": "status_enum",
                          "message": f"status {doc['status']!r} not in {sorted(VALID_STATUSES)}",
                          "source": source_label})
    if isinstance(doc.get("priority"), str) and doc["priority"] not in VALID_PRIORITIES:
        findings.append({"severity": "error", "rule": "priority_enum",
                          "message": f"priority {doc['priority']!r} not in {sorted(VALID_PRIORITIES)}",
                          "source": source_label})

    modes = doc.get("allowed_execution_modes") or []
    if isinstance(modes, list):
        bad = [m for m in modes if not isinstance(m, str) or m not in VALID_EXEC_MODES]
        if bad:
            findings.append({"severity": "error", "rule": "exec_mode_enum",
                              "message": f"unknown execution modes: {bad}",
                              "source": source_label})

    node_id = doc.get("node_id")
    if isinstance(node_id, str):
        if not KEBAB_RE.match(node_id):
            findings.append({"severity": "error", "rule": "id_format",
                              "message": f"node_id {node_id!r} not kebab-case",
                              "source": source_label})

    acceptance = doc.get("acceptance_criteria")
    if acceptance is not None:
        if not isinstance(acceptance, list):
            findings.append({"severity": "error", "rule": "acceptance_type",
                              "message": f"acceptance must be a list, got {type(acceptance).__name__}",
                              "source": source_label})
        elif not acceptance:
            findings.append({"severity": "error", "rule": "acceptance_empty",
                              "message": "acceptance must have at least one entry",
                              "source": source_label})
        else:
            for idx, entry in enumerate(acceptance):
                if not isinstance(entry, dict):
                    findings.append({"severity": "error", "rule": "acceptance_shape",
                                      "message": f"acceptance[{idx}] must be a dict with id and criterion",
                                      "source": source_label})
                    continue
                if "id" not in entry or "criterion" not in entry:
                    findings.append({"severity": "error", "rule": "acceptance_shape",
                                      "message": f"acceptance[{idx}] missing 'id' or 'criterion' key",
                                      "source": source_label})
                    continue
                acc_id = entry["id"]
                if not isinstance(acc_id, str):
                    findings.append({"severity": "error", "rule": "acceptance_id_type",
                                      "message": f"acceptance[{idx}].id must be string",
                                      "source": source_label})
                elif not KEBAB_RE.match(acc_id):
                    findings.append({"severity": "error", "rule": "acceptance_id_format",
                                      "message": f"acceptance[{idx}].id {acc_id!r} not kebab-case",
                                      "source": source_label})
                if not isinstance(entry["criterion"], str):
                    findings.append({"severity": "error", "rule": "acceptance_criterion_type",
                                      "message": f"acceptance[{idx}].criterion must be string",
                                      "source": source_label})

    for fname in LIST_FIELDS:
        val = doc.get(fname)
        if isinstance(val, list):
            non_str = [(i, x) for i, x in enumerate(val) if not isinstance(x, str)]
            if non_str:
                for idx, item in non_str:
                    if isinstance(item, dict) and len(item) == 1:
                        recovered = next(iter(item.keys())) + ": " + next(iter(item.values()))
                        findings.append({"severity": "warning", "rule": "implicit_mapping_in_list",
                                          "message": f"{fname}[{idx}] parsed as dict — quote: {recovered[:80]}",
                                          "source": source_label})
                    else:
                        findings.append({"severity": "error", "rule": "list_of_strings",
                                          "message": f"{fname}[{idx}] must be string, got {type(item).__name__}",
                                          "source": source_label})

    return findings


def check_conflicts(root: Path, project_id: str, node_id: str) -> list[dict]:
    findings = []
    node_file = root / "graphs" / project_id / "nodes" / f"{node_id}.yaml"
    if node_file.exists():
        findings.append({"severity": "error", "rule": "node_exists",
                          "message": f"node file already exists: {node_id}.yaml",
                          "source": "filesystem"})
    project_yaml = root / "graphs" / project_id / "project.yaml"
    if project_yaml.exists():
        with open(project_yaml) as f:
            proj = yaml.safe_load(f) or {}
        for n in proj.get("nodes", []):
            if n.get("id") == node_id:
                findings.append({"severity": "error", "rule": "node_in_index",
                                  "message": f"node {node_id!r} already in project.yaml index",
                                  "source": "project.yaml"})
                break
    return findings


def check_deps_exist(root: Path, project_id: str, depends_on: list[str]) -> list[dict]:
    findings = []
    nodes_dir = root / "graphs" / project_id / "nodes"
    existing = {p.stem for p in nodes_dir.glob("*.yaml")} if nodes_dir.exists() else set()
    for dep in depends_on:
        if isinstance(dep, str) and dep not in existing:
            findings.append({"severity": "warning", "rule": "dangling_depends_on",
                              "message": f"depends_on {dep!r} not found in project (may be future node)",
                              "source": "cross_ref"})
    return findings


def write_node_file(root: Path, project_id: str, doc: dict) -> Path:
    field_order = [
        "schema_version", "schema_type",
        "node_id", "title", "type", "why",
        "depends_on", "acceptance_criteria", "constraints",
        "allowed_execution_modes", "required_artifacts",
        "status", "priority", "unlocks",
    ]
    ordered = {k: doc[k] for k in field_order if k in doc}
    nodes_dir = root / "graphs" / project_id / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    path = nodes_dir / f"{doc['node_id']}.yaml"
    path.write_text(
        yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def patch_project_index(root: Path, project_id: str, doc: dict) -> bool:
    project_yaml = root / "graphs" / project_id / "project.yaml"
    if not project_yaml.exists():
        return False

    original = project_yaml.read_text(encoding="utf-8")
    backup = project_yaml.with_suffix(".yaml.bak")
    backup.write_text(original, encoding="utf-8")

    try:
        proj = yaml.safe_load(original) or {}
        nodes_list = proj.setdefault("nodes", [])
        if any(n.get("id") == doc["node_id"] for n in nodes_list):
            raise RuntimeError(f"node {doc['node_id']!r} already in index")
        nodes_list.append({
            "id": doc["node_id"],
            "title": doc["title"],
            "status": doc["status"],
            "type": doc["type"],
        })
        proj["last_updated"] = datetime.date.today().isoformat()
        project_yaml.write_text(
            yaml.dump(proj, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return True
    except Exception:
        project_yaml.write_text(original, encoding="utf-8")
        return False


def import_node(doc: dict, project_id: str, root: Path,
                auto_approve: bool = False, dry_run: bool = False) -> int:
    project_dir = root / "graphs" / project_id
    if not project_dir.exists() or not (project_dir / "project.yaml").exists():
        print(json.dumps({"error": f"project '{project_id}' not found"},
                          indent=2))
        return 3

    source_label = doc.get("node_id", "unknown")
    all_findings = []

    all_findings.extend(validate_node_yaml(doc, source_label))
    all_findings.extend(check_conflicts(root, project_id, doc.get("node_id", "")))

    deps = doc.get("depends_on") or []
    all_findings.extend(check_deps_exist(root, project_id, deps))

    errors = [f for f in all_findings if f["severity"] == "error"]
    warnings = [f for f in all_findings if f["severity"] == "warning"]

    result = {
        "node_id": doc.get("node_id"),
        "status": "imported" if not errors else "rejected",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
        },
    }

    if errors:
        print(json.dumps(result, indent=2))
        return 1

    if dry_run:
        result["status"] = "dry_run_pass"
        print(json.dumps(result, indent=2))
        return 0

    path = write_node_file(root, project_id, doc)
    patched = patch_project_index(root, project_id, doc)

    result["file_written"] = str(path.relative_to(root))
    result["project_patched"] = patched
    print(json.dumps(result, indent=2))
    return 0


def main(file_path=None, use_stdin=False, project=None,
         auto_approve=False, dry_run=False, root=None) -> int:
    root = root or ROOT

    if use_stdin:
        text = sys.stdin.read()
    elif file_path:
        path = Path(file_path)
        if not path.exists():
            print(json.dumps({"error": f"file not found: {file_path}"}, indent=2))
            return 1
        text = path.read_text(encoding="utf-8")
    else:
        print(json.dumps({"error": "specify --file or --stdin"}, indent=2))
        return 1

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(json.dumps({"error": f"YAML parse error: {e}"}, indent=2))
        return 1

    if not isinstance(doc, dict):
        print(json.dumps({"error": "YAML top-level must be a mapping"}, indent=2))
        return 1

    return import_node(doc, project, root, auto_approve, dry_run)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=Path, help="YAML file to import")
    src.add_argument("--stdin", action="store_true", help="Read YAML from stdin")
    p.add_argument("--project", required=True)
    p.add_argument("--auto-approve", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    sys.exit(main(
        file_path=p.parse_args().file,
        use_stdin=p.parse_args().stdin,
        project=p.parse_args().project,
        auto_approve=p.parse_args().auto_approve,
        dry_run=p.parse_args().dry_run,
    ))
