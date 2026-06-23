#!/usr/bin/env python3
"""rapid_add.py — minimal-keystroke TUI for adding nodes to a project.

Designed for hand preservation: most interactions are single keypresses.
Node names are the only freeform typing (~10-15 chars). Dependencies are
picked from numbered existing nodes (1-9).

Flow:
    1. Type node name → Enter (auto-kebab-cased to node_id)
    2. Pick deps from existing nodes (number keys toggle, Enter done)
    3. Node created immediately (no review screen between nodes)
    4. Blank input = done, jump to batch fill

    With --llm-draft:
    2b. Agent drafts why/acceptance/constraints from project context
    3b. Review draft → y accept / e edit / q skip-draft
    4. Node created, next

Usage:
    python3 scripts/gddp.py node rapid --project my-app
    python3 scripts/gddp.py node rapid --project my-app --llm-draft
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
    from rich.panel import Panel
    from rich.rule import Rule
except ImportError:
    print("Install deps:  pip install rich pyyaml")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from terminal import console, getch, getline

ROOT = Path(__file__).resolve().parent.parent

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
DEFAULT_ARTIFACTS = ["decision.md", "result-summary.md", "graph-update.yaml"]

NAME_TO_KEBAB_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = NAME_TO_KEBAB_RE.sub("-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    if not KEBAB_RE.match(s):
        return None
    return s


def kebab_to_title(node_id: str) -> str:
    return node_id.replace("-", " ").title()


def list_existing_nodes(root: Path, project_id: str) -> list[str]:
    nodes_dir = root / "graphs" / project_id / "nodes"
    if not nodes_dir.exists():
        return []
    return sorted(p.stem for p in nodes_dir.glob("*.yaml"))


def pick_deps(existing: list[str], page_size: int = 9) -> list[str]:
    """Number-key picker for dependencies. Returns selected node_ids."""
    selected = []
    page = 0

    if not existing:
        return selected

    while True:
        total_pages = max(1, (len(existing) + page_size - 1) // page_size)
        start = page * page_size
        visible = existing[start:start + page_size]

        console.print(f"\n[bold cyan]Dependencies[/bold cyan]  (selected: {len(selected)})")
        if total_pages > 1:
            console.print(f"[dim]page {page+1}/{total_pages}  ←/→ paginate[/dim]")
        for i, nid in enumerate(visible, 1):
            marker = "[green]✓[/green]" if nid in selected else " "
            title = kebab_to_title(nid)
            console.print(f"  [bold]{i}[/bold] {marker} {nid:<35} {title}")
        console.print("[dim]Enter done  q skip deps[/dim]")

        ch = getch()
        if ch == "\x03":
            sys.exit(0)
        if ch.lower() == "q":
            return selected
        if ch in ("\r", "\n"):
            return selected
        if ch in ("RIGHT", "DOWN"):
            page = (page + 1) % total_pages
            continue
        if ch in ("LEFT", "UP"):
            page = (page - 1) % total_pages
            continue
        if ch.isdigit() and visible:
            idx = int(ch) - 1
            if 0 <= idx < len(visible):
                picked = visible[idx]
                if picked in selected:
                    selected.remove(picked)
                else:
                    selected.append(picked)
            continue


def make_node_dict(node_id: str, title: str, depends_on: list[str],
                   status: str = "pending", priority: str = "medium") -> dict:
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node_id,
        "title": title,
        "type": "capability",
        "why": "REPLACE_ME",
        "depends_on": depends_on,
        "acceptance": ["REPLACE_ME"],
        "constraints": ["REPLACE_ME"],
        "allowed_execution_modes": ["jules"],
        "required_artifacts": list(DEFAULT_ARTIFACTS),
        "status": status,
        "priority": priority,
        "unlocks": [],
    }


def render_node_yaml(node: dict) -> str:
    field_order = [
        "schema_version", "schema_type",
        "node_id", "title", "type", "why",
        "depends_on", "acceptance", "constraints",
        "allowed_execution_modes", "required_artifacts",
        "status", "priority", "unlocks",
    ]
    ordered = {k: node[k] for k in field_order if k in node}
    return yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)


def write_node(root: Path, project_id: str, node: dict) -> Path:
    nodes_dir = root / "graphs" / project_id / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    path = nodes_dir / f"{node['node_id']}.yaml"
    path.write_text(render_node_yaml(node), encoding="utf-8")
    return path


def patch_project_yaml(root: Path, project_id: str, node: dict) -> bool:
    import datetime
    project_yaml = root / "graphs" / project_id / "project.yaml"
    if not project_yaml.exists():
        return False

    original = project_yaml.read_text(encoding="utf-8")
    backup = project_yaml.with_suffix(".yaml.bak")
    backup.write_text(original, encoding="utf-8")

    try:
        doc = yaml.safe_load(original) or {}
        if not isinstance(doc, dict):
            raise RuntimeError("project.yaml not a mapping")

        entry = {
            "id": node["node_id"],
            "title": node["title"],
            "status": node["status"],
            "type": node["type"],
        }
        nodes_list = doc.setdefault("nodes", [])
        if not isinstance(nodes_list, list):
            raise RuntimeError("nodes is not a list")
        if any(n.get("id") == node["node_id"] for n in nodes_list):
            raise RuntimeError(f"node {node['node_id']!r} already in project.yaml")
        nodes_list.append(entry)
        doc["last_updated"] = datetime.date.today().isoformat()

        new_text = yaml.dump(doc, default_flow_style=False, sort_keys=False,
                             allow_unicode=True)
        project_yaml.write_text(new_text, encoding="utf-8")
        return True
    except Exception as e:
        project_yaml.write_text(original, encoding="utf-8")
        console.print(f"[red]project.yaml patch failed, rolled back: {e}[/red]")
        return False


def ensure_project_shell(root: Path, project_id: str, repo: str,
                         project_name: str | None = None) -> bool:
    """Create minimal project.yaml if it doesn't exist."""
    import datetime
    project_dir = root / "graphs" / project_id
    project_yaml = project_dir / "project.yaml"

    if project_yaml.exists():
        return True

    project_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    project = {
        "schema_version": "1.0",
        "schema_type": "project_graph",
        "project_id": project_id,
        "project_name": project_name or project_id,
        "description": "REPLACE_ME",
        "repo": repo or "REPLACE_ME",
        "blueprint": {
            "vision": "REPLACE_ME",
            "architecture_notes": "REPLACE_ME",
            "major_capabilities": ["REPLACE_ME"],
        },
        "graph_version": "1.0",
        "created_at": today,
        "last_updated": today,
        "nodes_dir": "nodes/",
        "nodes": [],
        "execution_policy": {
            "default_executor": "jules",
            "max_concurrent_jobs": 1,
            "require_human_review_before_overnight": True,
            "artifact_gate_enforced": True,
        },
    }
    text = yaml.dump(project, default_flow_style=False, sort_keys=False,
                     allow_unicode=True)
    project_yaml.write_text(text, encoding="utf-8")
    return True


def main(project: str, repo: str = "", project_name: str | None = None,
         llm_draft: bool = False, dry_run: bool = False,
         root: Path | None = None) -> int:
    root = root or ROOT

    if not ensure_project_shell(root, project, repo, project_name):
        console.print(f"[red]Cannot create project shell for {project}[/red]")
        return 1

    console.print(Rule(f"[bold cyan]RAPID ADD — {project}[/bold cyan]"))
    console.print("[dim]Type node name → Enter. Number keys = pick deps. Blank = done.[/dim]\n")

    added = []
    existing = list_existing_nodes(root, project)

    while True:
        console.print(f"[bold cyan][{len(added)+1}][/bold cyan] Node name (blank to finish): ", end="")
        name = getline("")

        if not name.strip():
            break

        node_id = slugify(name)
        if not node_id:
            console.print(f"[yellow]  Can't slugify {name!r} to kebab-case. Try again.[/yellow]")
            continue
        if node_id in existing:
            console.print(f"[yellow]  {node_id!r} already exists. Try again.[/yellow]")
            continue

        title = kebab_to_title(node_id)
        console.print(f"  → [green]{node_id}[/green]  ({title})")

        if existing:
            deps = pick_deps(existing)
        else:
            deps = []

        node = make_node_dict(node_id, title, deps)

        if llm_draft:
            try:
                llm = __import__("llm_draft")
                console.print("  [dim]drafting with LLM...[/dim]")
                drafted = llm.draft_fields(
                    project_id=project,
                    root=root,
                    node_id=node_id,
                    node_title=title,
                    depends_on=deps,
                    existing_nodes=existing,
                )
                if drafted:
                    for k, v in drafted.items():
                        if v:
                            node[k] = v
                    console.print("  [green]draft applied[/green]")
            except Exception as e:
                console.print(f"  [yellow]LLM draft failed: {e} — using placeholders[/yellow]")

        if not dry_run:
            path = write_node(root, project, node)
            patched = patch_project_yaml(root, project, node)
            console.print(f"  [green]WROTE[/green] {path.relative_to(root)}" +
                          (f"  [dim]project.yaml patched[/dim]" if patched else ""))

        existing.append(node_id)
        added.append(node_id)
        console.print()

    if not added:
        console.print("[dim]No nodes added.[/dim]")
        return 0

    console.print(Rule(f"[bold green]{len(added)} node(s) added to {project}[/bold green]"))
    for nid in added:
        console.print(f"  [green]✓[/green] {nid}")
    console.print()
    if llm_draft:
        console.print("Next: [bold]gddp node validate --project {project}[/bold]")
    else:
        console.print("Next: [bold]gddp node batch --project {project}[/bold]  (fill why/acceptance/constraints)")
        console.print("      [bold]gddp node validate --project {project}[/bold]")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True)
    p.add_argument("--repo", default="")
    p.add_argument("--project-name", default=None)
    p.add_argument("--llm-draft", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    sys.exit(main(
        project=p.parse_args().project,
        repo=p.parse_args().repo,
        project_name=p.parse_args().project_name,
        llm_draft=p.parse_args().llm_draft,
        dry_run=p.parse_args().dry_run,
    ))
