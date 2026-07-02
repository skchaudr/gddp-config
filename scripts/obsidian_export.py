#!/usr/bin/env python3
"""obsidian_export.py — one-way YAML nodes → Obsidian markdown vault.

YAML in graphs/ stays source of truth. Generated notes land in
obsidian-vault/GDDP/graphs/<project>/<node>.md for Graph View filtering
(e.g. path:GDDP/graphs/aa-cli).

The only user-owned field preserved across regeneration is frontmatter
`verified` (and optional `owned`). Do not edit status/type/priority here —
that is graph drift.

Usage:
    .venv/bin/python scripts/obsidian_export.py
    .venv/bin/python scripts/obsidian_export.py --project aa-cli
    .venv/bin/python scripts/gddp.py obsidian export --project aa-cli
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Install deps:  pip install pyyaml")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DEFAULT_VAULT = ROOT / "obsidian-vault"
GENERATED_ROOT = "GDDP/graphs"
PRESERVE_KEYS = ("verified", "owned")
BANNER = "> **Auto-generated** from `graphs/` YAML. Regenerate with `gddp obsidian export`. Only edit `verified` / `owned` in frontmatter."

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def iter_node_files(graphs_dir: Path, project_filter: str | None):
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


def load_project_meta(graphs_dir: Path, project_id: str) -> dict:
    path = graphs_dir / project_id / "project.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        doc = yaml.safe_load(f) or {}
    return doc if isinstance(doc, dict) else {}


def read_preserved_frontmatter(note_path: Path) -> dict:
    if not note_path.exists():
        return {}
    match = FM_RE.match(note_path.read_text())
    if not match:
        return {}
    fm = yaml.safe_load(match.group(1))
    if not isinstance(fm, dict):
        return {}
    return {k: fm[k] for k in PRESERVE_KEYS if k in fm and fm[k] not in (None, "")}


def wikilink(node_id: str) -> str:
    return f"[[{node_id}]]"


def yaml_quote(value: str) -> str:
    if not value:
        return '""'
    if any(c in value for c in ':\n"#[]{}&*!|>%@`'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def format_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {yaml_quote(str(item))}")
        else:
            lines.append(f"{key}: {yaml_quote(str(value))}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def load_receipt_summary(root: Path, project_id: str, node_id: str) -> dict | None:
    receipt = root / "verification" / project_id / node_id / "result.json"
    if not receipt.exists():
        return None
    try:
        with open(receipt) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "verdict": data.get("verdict"),
        "evaluated_at": data.get("evaluated_at"),
        "path": receipt.relative_to(root).as_posix(),
    }


def render_node_note(
    *,
    project_id: str,
    node: dict,
    project_meta: dict,
    preserved: dict,
    root: Path,
    generated_at: str,
) -> str:
    node_id = node.get("node_id", "unknown")
    title = node.get("title", node_id)
    repo = project_meta.get("repo", "")
    yaml_path = f"graphs/{project_id}/nodes/{node_id}.yaml"

    fm = {
        "node_id": node_id,
        "project": project_id,
        "title": title,
        "type": node.get("type", ""),
        "status": node.get("status", ""),
        "priority": node.get("priority", ""),
        "verified": preserved.get("verified"),
        "owned": preserved.get("owned"),
        "repo": repo,
        "tags": ["gddp/auto-generated", f"gddp/project/{project_id}"],
        "source_yaml": yaml_path,
        "generated_at": generated_at,
    }

    depends = node.get("depends_on") or []
    unlocks = node.get("unlocks") or []
    acceptance = node.get("acceptance") or []
    constraints = node.get("constraints") or []
    modes = node.get("allowed_execution_modes") or []
    artifacts = node.get("required_artifacts") or []
    why = (node.get("why") or "").strip()

    parts = [format_frontmatter(fm), BANNER, "", f"# {title}", ""]
    if why:
        parts.extend([why, ""])

    parts.append("## Dependencies")
    if depends:
        parts.extend(f"- {wikilink(dep)}" for dep in depends if isinstance(dep, str))
    else:
        parts.append("- _(none)_")
    parts.append("")

    parts.append("## Unlocks")
    if unlocks:
        parts.extend(f"- {wikilink(uid)}" for uid in unlocks if isinstance(uid, str))
    else:
        parts.append("- _(none)_")
    parts.append("")

    parts.append("## Acceptance criteria")
    for item in acceptance:
        if not isinstance(item, dict):
            continue
        cid = item.get("id", "?")
        criterion = (item.get("criterion") or "").strip()
        parts.append(f"- [ ] **{cid}** — {criterion}")
    if not acceptance:
        parts.append("- _(none)_")
    parts.append("")

    if constraints:
        parts.append("## Constraints")
        for c in constraints:
            if isinstance(c, str) and c.strip():
                parts.append(f"- {c.strip()}")
        parts.append("")

    parts.append("## Evidence")
    parts.append(f"- **YAML source:** `{yaml_path}`")
    if repo:
        parts.append(f"- **Repo:** `{repo}`")
    receipt = load_receipt_summary(root, project_id, node_id)
    if receipt:
        verdict = receipt.get("verdict") or "unknown"
        when = receipt.get("evaluated_at") or "unknown"
        rpath = receipt.get("path")
        parts.append(f"- **Verification receipt:** `{rpath}` — verdict **{verdict}** ({when})")
    else:
        rel = f"verification/{project_id}/{node_id}/result.json"
        parts.append(f"- **Verification receipt:** `{rel}` _(not generated — run `gddp verify node`)_")
    parts.append("")

    parts.append("## Execution")
    if modes:
        parts.append(f"- **Modes:** {', '.join(str(m) for m in modes)}")
    if artifacts:
        parts.append(f"- **Required artifacts:** {', '.join(str(a) for a in artifacts)}")
    parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def render_project_index(
    *,
    project_id: str,
    project_meta: dict,
    node_ids: list[str],
    generated_at: str,
) -> str:
    name = project_meta.get("project_name", project_id)
    description = (project_meta.get("description") or "").strip()
    repo = project_meta.get("repo", "")
    fm = {
        "project": project_id,
        "title": name,
        "type": "project-index",
        "status": "index",
        "tags": ["gddp/auto-generated", "gddp/project-index", f"gddp/project/{project_id}"],
        "repo": repo,
        "generated_at": generated_at,
    }
    parts = [
        format_frontmatter(fm),
        BANNER,
        "",
        f"# {name}",
        "",
        f"`{project_id}` — {len(node_ids)} nodes",
        "",
    ]
    if description:
        parts.extend([description, ""])
    if repo:
        parts.append(f"**Repo:** `{repo}`")
        parts.append("")
    parts.append("## Nodes")
    for nid in sorted(node_ids):
        parts.append(f"- {wikilink(nid)}")
    parts.append("")
    return "\n".join(parts)


def export_vault(
    *,
    root: Path,
    vault_dir: Path,
    project_filter: str | None = None,
    dry_run: bool = False,
) -> dict:
    graphs_dir = root / "graphs"
    out_root = vault_dir / GENERATED_ROOT
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written: set[Path] = set()
    counts = {"projects": 0, "nodes": 0, "preserved": 0}

    projects_seen: dict[str, list[str]] = {}

    for project_id, yaml_path in iter_node_files(graphs_dir, project_filter):
        with open(yaml_path) as f:
            node = yaml.safe_load(f) or {}
        if not isinstance(node, dict):
            continue

        node_id = node.get("node_id") or yaml_path.stem
        projects_seen.setdefault(project_id, []).append(node_id)

        note_path = out_root / project_id / f"{node_id}.md"
        preserved = read_preserved_frontmatter(note_path)
        if preserved:
            counts["preserved"] += 1

        project_meta = load_project_meta(graphs_dir, project_id)
        content = render_node_note(
            project_id=project_id,
            node=node,
            project_meta=project_meta,
            preserved=preserved,
            root=root,
            generated_at=generated_at,
        )

        if dry_run:
            print(f"would write {note_path.relative_to(vault_dir)}")
        else:
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text(content)
        written.add(note_path)
        counts["nodes"] += 1

    for project_id, node_ids in sorted(projects_seen.items()):
        counts["projects"] += 1
        index_path = out_root / project_id / "_project.md"
        content = render_project_index(
            project_id=project_id,
            project_meta=load_project_meta(graphs_dir, project_id),
            node_ids=node_ids,
            generated_at=generated_at,
        )
        if dry_run:
            print(f"would write {index_path.relative_to(vault_dir)}")
        else:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(content)
        written.add(index_path)

    if not dry_run and out_root.exists():
        for path in out_root.rglob("*.md"):
            if path not in written:
                path.unlink()

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export graph nodes to Obsidian markdown vault")
    parser.add_argument("--root", type=Path, default=ROOT, help="gddp-config root")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help="Obsidian vault directory")
    parser.add_argument("--project", default=None, help="Only export this project")
    parser.add_argument("--dry-run", action="store_true", help="Print paths without writing")
    args = parser.parse_args(argv)

    counts = export_vault(
        root=args.root,
        vault_dir=args.vault,
        project_filter=args.project,
        dry_run=args.dry_run,
    )
    action = "Would export" if args.dry_run else "Exported"
    scope = args.project or "all projects"
    print(
        f"{action} {counts['nodes']} node(s) across {counts['projects']} project(s) "
        f"→ {args.vault / GENERATED_ROOT} ({scope})"
    )
    if counts["preserved"]:
        print(f"Preserved verified/owned on {counts['preserved']} note(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())