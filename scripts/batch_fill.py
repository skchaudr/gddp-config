#!/usr/bin/env python3
"""batch_fill.py — walk through pending/REPLACE_ME nodes field by field.

For each node in a project that has REPLACE_ME placeholders, presents the node
card, then walks through each field that needs human input. Inspired by
V4SchemaPass's sequential field-by-field flow.

Usage:
    python3 scripts/gddp.py node batch --project my-project

Keys (same as new_node.py):
    1-9    pick from suggestions
    m      manual text entry
    s      skip field
    q      quit (abandon current node, continue to next)
    Enter  accept default / move to next field
    e      edit after review
"""

from __future__ import annotations

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

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent

VALID_TYPES = ["capability", "milestone", "constraint"]
VALID_STATUSES = ["pending", "ready", "complete", "deferred"]
VALID_PRIORITIES = ["low", "medium", "high", "critical"]
VALID_EXEC_MODES = ["jules", "vertex", "pi_worker", "vm_worker", "human"]
ALL_ARTIFACTS = ["decision.md", "result-summary.md", "patch.diff",
                  "graph-update.yaml", "merged_pr"]
DEFAULT_ARTIFACTS = ["decision.md", "result-summary.md", "graph-update.yaml"]

KEBAB_RE_PLACEHOLDER = "REPLACE_ME"
PAGE_SIZE = 9

PLACEHOLDER_FIELDS = {"why", "acceptance", "constraints"}


def list_node_ids(root: Path, project_id: str) -> list[str]:
    nodes_dir = root / "graphs" / project_id / "nodes"
    if not nodes_dir.exists():
        return []
    return sorted(p.stem for p in nodes_dir.glob("*.yaml"))


def gather_inspiration_bullets(root: Path, project_id: str) -> list[str]:
    bullets = []
    seen = set()
    nodes_dir = root / "graphs" / project_id / "nodes"
    if not nodes_dir.exists():
        return bullets
    for path in sorted(nodes_dir.glob("*.yaml")):
        try:
            with open(path) as f:
                doc = yaml.safe_load(f) or {}
        except Exception:
            continue
        for field in ("acceptance", "constraints"):
            for item in doc.get(field) or []:
                if isinstance(item, str) and "REPLACE_ME" not in item and item not in seen:
                    seen.add(item)
                    bullets.append(item)
    return bullets


def needs_batch(node: dict) -> bool:
    for field in PLACEHOLDER_FIELDS:
        val = node.get(field)
        if isinstance(val, str) and "REPLACE_ME" in val:
            return True
        if isinstance(val, list):
            if any("REPLACE_ME" in str(x) for x in val if isinstance(x, str)):
                return True
            if not val and field in ("acceptance", "constraints"):
                return True
    return False


def show_node_card(node: dict, idx: int, total: int):
    console.clear()
    lines = [
        f"[bold cyan][{idx}/{total}] {node['node_id']}[/bold cyan]",
        f"[dim]title: {node.get('title', '')}[/dim]",
        f"[dim]type: {node.get('type', '')}  status: {node.get('status', '')}  priority: {node.get('priority', '')}[/dim]",
        "",
    ]
    needs = []
    for field in PLACEHOLDER_FIELDS:
        val = node.get(field)
        if isinstance(val, str) and "REPLACE_ME" in val:
            needs.append(f"{field}: needs input")
        elif isinstance(val, list):
            if any("REPLACE_ME" in str(x) for x in val if isinstance(x, str)):
                needs.append(f"{field}: has REPLACE_ME items")
            elif not val and field in ("acceptance", "constraints"):
                needs.append(f"{field}: empty")
            else:
                count = len([x for x in val if isinstance(x, str)])
                needs.append(f"{field}: {count} items [green]✓[/green]")
    lines.append("[bold]Fields:[/bold]")
    for n in needs:
        lines.append(f"  {n}")

    deps = node.get("depends_on", [])
    unlocks = node.get("unlocks", [])
    if deps:
        lines.append(f"\n  [dim]depends_on: {', '.join(deps)}[/dim]")
    if unlocks:
        lines.append(f"  [dim]unlocks: {', '.join(unlocks)}[/dim]")

    lines.append("")
    lines.append("[dim]Enter proceed  q skip node  Ctrl+C quit[/dim]")
    console.print(Panel("\n".join(lines), border_style="blue", expand=False))


def manual_text(label: str, multi_line: bool = False):
    console.print(f"\n[bold cyan]{label}[/bold cyan]")
    if multi_line:
        console.print("[dim]  blank line to finish[/dim]")
        lines = []
        while True:
            console.print("  [bold]>[/bold] ", end="")
            line = getline("")
            if line == "":
                break
            lines.append(line)
        return "\n".join(lines) if lines else None
    console.print("  [bold]>[/bold] ", end="")
    return getline("") or None


def edit_list_items(label: str, items: list[str], suggestions: list[str]):
    items = [x for x in items if isinstance(x, str) and "REPLACE_ME" not in x]
    while True:
        console.clear()
        body = f"[bold cyan]{label}[/bold cyan]  ({len(items)} items)\n"
        if items:
            for i, x in enumerate(items, 1):
                body += f"  [bold]{i}[/bold] {x}\n"
        else:
            body += "[dim]none yet[/dim]\n"
        body += "[dim]a add  d# delete  Enter done[/dim]"
        console.print(Panel(body, border_style="cyan", expand=False))

        ch = getch()
        if ch == "\x03":
            sys.exit(0)
        if ch in ("\r", "\n"):
            return items
        if ch.lower() == "d":
            n_ch = getch()
            if n_ch.isdigit() and 1 <= int(n_ch) <= len(items):
                items.pop(int(n_ch) - 1)
            continue
        if ch.lower() == "a":
            console.clear()
            console.print(f"[bold cyan]Add to {label}[/bold cyan]")
            for i, s in enumerate(suggestions[:PAGE_SIZE], 1):
                console.print(f"  [bold]{i}[/bold] {s}")
            if suggestions:
                console.print(f"  [dim]... {len(suggestions)} suggestion(s)[/dim]")
            console.print("  [bold]m[/bold] manual    [bold]s[/bold] cancel")
            sub = getch()
            if sub.lower() == "m":
                val = manual_text(f"add to {label}")
                if val:
                    items.append(val)
            elif sub.lower() == "s":
                continue
            elif sub.isdigit() and 1 <= int(sub) <= min(len(suggestions), PAGE_SIZE):
                items.append(suggestions[int(sub) - 1])
            continue


def fill_node_fields(node: dict, root: Path, project: str) -> dict:
    suggestions = gather_inspiration_bullets(root, project)

    why = node.get("why", "")
    if isinstance(why, str) and "REPLACE_ME" in why:
        why = manual_text("Why (why this capability must exist)", multi_line=True)
        if why:
            node["why"] = why

    acceptance = node.get("acceptance", [])
    has_placeholder = any(isinstance(x, str) and "REPLACE_ME" in x for x in acceptance)
    if not acceptance or has_placeholder:
        result = edit_list_items("Acceptance (verifiable bullets)", [], suggestions)
        if result:
            node["acceptance"] = result

    constraints = node.get("constraints", [])
    has_placeholder = any(isinstance(x, str) and "REPLACE_ME" in x for x in constraints)
    if not constraints or has_placeholder:
        result = edit_list_items("Constraints (hard limits)", [], suggestions)
        if result:
            node["constraints"] = result

    return node


def review_and_write(node: dict, root: Path, project: str) -> bool:
    from validate import run as validate_run
    from validate import render_json as validate_json
    import json

    console.clear()
    field_order = [
        "schema_version", "schema_type",
        "node_id", "title", "type", "why",
        "depends_on", "acceptance", "constraints",
        "allowed_execution_modes", "required_artifacts",
        "status", "priority", "unlocks",
    ]
    ordered = {k: node[k] for k in field_order if k in node}
    yaml_text = yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)

    console.print(Panel(
        yaml_text,
        title=f"[bold]Review — {node['node_id']}[/bold]",
        subtitle="[dim]y write  e edit field  r redo fields  q skip[/dim]",
        border_style="green",
        expand=False,
    ))

    ch = getch()
    if ch == "\x03":
        sys.exit(0)
    if ch.lower() == "q":
        console.print("[dim]skipped[/dim]")
        return False
    if ch.lower() == "y":
        nodes_dir = root / "graphs" / project / "nodes"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        path = nodes_dir / f"{node['node_id']}.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        console.print(f"\n[green]WROTE[/green] {path.relative_to(root)}")

        validate_run(root)
        return True
    if ch.lower() == "e":
        field_name = getline("Edit which field:").strip()
        if field_name in PLACEHOLDER_FIELDS:
            node = fill_node_fields({**node, "why": "REPLACE_ME", "acceptance": ["REPLACE_ME"], "constraints": ["REPLACE_ME"]}, root, project)
        else:
            console.print(f"[yellow]only human fields editable in batch (why, acceptance, constraints)[/yellow]")
        return review_and_write(node, root, project)
    if ch.lower() == "r":
        node = fill_node_fields(node, root, project)
        return review_and_write(node, root, project)

    return review_and_write(node, root, project)


def main(project: str) -> int:
    nodes_dir = ROOT / "graphs" / project / "nodes"
    if not nodes_dir.exists():
        console.print(f"[red]No nodes directory for project: {project}[/red]")
        return 1

    all_nodes = []
    for path in sorted(nodes_dir.glob("*.yaml")):
        with open(path) as f:
            doc = yaml.safe_load(f)
        if doc and needs_batch(doc):
            all_nodes.append((path, doc))

    if not all_nodes:
        console.print(f"[green]All nodes in {project} are filled — nothing to batch.[/green]")
        return 0

    console.print(Rule(f"[bold cyan]BATCH FILL — {project} ({len(all_nodes)} nodes need input)[/bold cyan]"))
    console.print("[dim]s=skip  q=skip node  m=manual  Enter=proceed  Ctrl+C=quit[/dim]\n")

    written = 0
    skipped = 0

    for idx, (path, doc) in enumerate(all_nodes, 1):
        show_node_card(doc, idx, len(all_nodes))

        ch = getch()
        if ch == "\x03":
            console.print("[dim]quit[/dim]")
            break
        if ch.lower() == "q":
            console.print("[dim]skipped[/dim]")
            skipped += 1
            continue
        if ch in ("\r", "\n"):
            pass
        else:
            continue

        filled = fill_node_fields(dict(doc), ROOT, project)
        if review_and_write(filled, ROOT, project):
            written += 1
        else:
            skipped += 1

    console.print(f"\n[bold]Done: {written} written, {skipped} skipped, {len(all_nodes)} total[/bold]")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True)
    sys.exit(main(project=p.parse_args().project))
