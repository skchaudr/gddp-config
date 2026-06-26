#!/usr/bin/env python3
"""Node scaffold TUI for gddp-config.

Interactive, keyboard-driven creator for node YAML files. Modeled on the
V4SchemaPass TUI from context_refinery — number keys, paginated picks,
single-letter commands (s/q/m, Enter = default).

Writes graphs/<project>/nodes/<node_id>.yaml + patches the project.yaml index
(with .bak backup). Runs validate.py post-write: loud globally, exits non-zero
only if the new node or the project.yaml patch is the cause. Pre-existing repo
drift won't block the scaffold.

Usage:
    python3 scripts/new_node.py

Self-contained — schema constants inline, no shared module with validate.py.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
    from rich.panel import Panel
    from rich.rule import Rule
except ImportError:
    print("Install deps:  pip install rich pyyaml")
    sys.exit(1)

# Sibling terminal helper
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance_items import acceptance_text, normalize_acceptance_items
from terminal import console, getch, getline


# ── Schema constants (mirror schemas/v1/node.yaml) ─────────────────────────

VALID_TYPES = ["capability", "milestone", "constraint"]
VALID_STATUSES = ["pending", "ready", "complete", "deferred"]
VALID_PRIORITIES = ["low", "medium", "high", "critical"]
VALID_EXEC_MODES = ["jules", "vertex", "pi_worker", "vm_worker", "human"]
ALL_ARTIFACTS = ["decision.md", "result-summary.md", "patch.diff",
                  "graph-update.yaml", "merged_pr"]
DEFAULT_ARTIFACTS = ["decision.md", "result-summary.md", "graph-update.yaml"]

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
PAGE_SIZE = 9  # number keys 1-9


# ── Pre-scan ───────────────────────────────────────────────────────────────

def list_projects(root: Path) -> list[str]:
    graphs = root / "graphs"
    if not graphs.exists():
        return []
    return sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "nodes").exists()
    )


def list_node_ids(root: Path, project_id: str) -> list[str]:
    nodes_dir = root / "graphs" / project_id / "nodes"
    if not nodes_dir.exists():
        return []
    return sorted(p.stem for p in nodes_dir.glob("*.yaml"))


def gather_inspiration_bullets(root: Path, project_id: str) -> list[str]:
    """Lift existing acceptance/constraints bullets for inspiration."""
    bullets: list[str] = []
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
                text = acceptance_text(item) if field == "acceptance" else item
                if isinstance(text, str) and text not in seen:
                    seen.add(text)
                    bullets.append(text)
    return bullets


# ── Pickers ────────────────────────────────────────────────────────────────

def manual_text(label: str, multi_line: bool = False) -> Optional[str]:
    """Freeform text input. multi_line allows continuation until blank line."""
    console.print(f"\n[bold cyan]{label}[/bold cyan]")
    if multi_line:
        console.print("[dim]  blank line to finish; \\ at end for hard break[/dim]")
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


def pick_from_list(label: str, options: list[str],
                   default: Optional[str] = None,
                   current: Optional[str] = None) -> Optional[str]:
    """Single-select picker. Returns chosen value, None (skip), or '__quit__'."""
    console.print(f"\n[bold cyan]{label}[/bold cyan]", end="")
    if default:
        console.print(f"  [dim](Enter = {default})[/dim]", end="")
    if current:
        console.print(f"  [dim](current: {current})[/dim]", end="")
    console.print()
    visible = options[:PAGE_SIZE]
    for i, opt in enumerate(visible, start=1):
        marker = "[green]✓[/green]" if opt == current else " "
        console.print(f"  [bold]{i}[/bold] {marker} {opt}")
    if len(options) > PAGE_SIZE:
        console.print(f"  [dim]... {len(options) - PAGE_SIZE} more (use m to type)[/dim]")
    console.print("  [bold]m[/bold] manual    [bold]s[/bold] skip    [bold]q[/bold] quit")

    while True:
        ch = getch()
        if ch == "\x03":
            sys.exit(0)
        if ch.lower() == "q":
            console.print("  [dim]quit[/dim]")
            return "__quit__"
        if ch.lower() == "s":
            console.print("  [dim]skipped[/dim]")
            return None
        if ch.lower() == "m":
            return manual_text(label)
        if ch in ("\r", "\n"):
            if default:
                console.print(f"  → [blue]{default}[/blue]")
                return default
            console.print("  [yellow]no default — pick a number or m[/yellow]")
            continue
        if ch.isdigit() and 1 <= int(ch) <= len(visible):
            picked = visible[int(ch) - 1]
            console.print(f"  → [green]{picked}[/green]")
            return picked


def pick_many(label: str, options: list[str], current: list[str],
              defaults: Optional[list[str]] = None,
              allow_future: bool = False) -> Optional[list[str]]:
    """Multi-select picker with pagination. Returns list, None (skip), or '__quit__'."""
    selected = list(current) if current else []
    if not selected and defaults:
        selected = list(defaults)
    page = 0
    notice = None

    while True:
        total_pages = max(1, (len(options) + PAGE_SIZE - 1) // PAGE_SIZE)
        start = page * PAGE_SIZE
        visible = options[start:start + PAGE_SIZE]

        console.clear()
        body_lines = [
            f"[bold cyan]{label}[/bold cyan]",
            f"Selected: {', '.join(selected) if selected else '[dim]none[/dim]'}",
        ]
        if notice:
            body_lines.append(f"[yellow]{notice}[/yellow]")
        keys = "[dim]Enter done  m manual"
        if allow_future:
            keys += "  f future-id"
        if total_pages > 1:
            keys += "  ←/→ page"
        keys += "  s skip  q quit[/dim]"
        body_lines.append(keys)
        console.print(Panel("\n".join(body_lines), border_style="cyan", expand=False))

        if total_pages > 1:
            console.print(f"[dim]page {page + 1}/{total_pages}[/dim]")
        for i, opt in enumerate(visible, start=1):
            marker = "[green]✓[/green]" if opt in selected else " "
            console.print(f"  [bold]{i}[/bold] {marker} {opt}")
        console.print()

        notice = None
        ch = getch()
        if ch == "\x03":
            sys.exit(0)
        if ch.lower() == "q":
            return "__quit__"
        if ch.lower() == "s":
            return None
        if ch in ("\r", "\n"):
            return selected
        if ch.lower() == "m" or (ch.lower() == "f" and allow_future):
            val = manual_text(f"add to {label}")
            if val:
                if val not in selected:
                    selected.append(val)
                    notice = f"added {val}"
                else:
                    notice = f"{val} already selected"
            continue
        if ch in ("RIGHT", "DOWN") and total_pages > 1:
            page = (page + 1) % total_pages
            continue
        if ch in ("LEFT", "UP") and total_pages > 1:
            page = (page - 1) % total_pages
            continue
        if ch.isdigit() and visible:
            idx = int(ch) - 1
            if 0 <= idx < len(visible):
                picked = visible[idx]
                if picked in selected:
                    selected.remove(picked)
                    notice = f"removed {picked}"
                else:
                    selected.append(picked)
                    notice = f"added {picked}"
            continue
        notice = "key not mapped"


def edit_list_items(label: str, items: list[str], suggestions: list[str]) -> Optional[list[str]]:
    """List editor: add (suggestion or manual), delete by number, Enter done."""
    items = list(items)
    while True:
        console.clear()
        body = f"[bold cyan]{label}[/bold cyan]  ({len(items)} item{'s' if len(items) != 1 else ''})\n"
        if items:
            for i, x in enumerate(items, 1):
                body += f"  [bold]{i}[/bold] {x}\n"
        else:
            body += "[dim]none yet[/dim]\n"
        body += "[dim]a add  d# delete  Enter done  q quit[/dim]"
        console.print(Panel(body, border_style="cyan", expand=False))

        ch = getch()
        if ch == "\x03":
            sys.exit(0)
        if ch.lower() == "q":
            return "__quit__"
        if ch in ("\r", "\n"):
            return items
        if ch.lower() == "d":
            n_ch = getch()
            if n_ch.isdigit() and 1 <= int(n_ch) <= len(items):
                removed = items.pop(int(n_ch) - 1)
                console.print(f"  [dim]removed: {removed}[/dim]")
            else:
                console.print("  [yellow]invalid number[/yellow]")
            continue
        if ch.lower() == "a":
            console.clear()
            console.print(f"[bold cyan]Add to {label}[/bold cyan]")
            for i, s in enumerate(suggestions[:PAGE_SIZE], 1):
                console.print(f"  [bold]{i}[/bold] {s}")
            if suggestions:
                console.print(f"  [dim]... {len(suggestions)} suggestion(s); showing first {min(len(suggestions), PAGE_SIZE)}[/dim]")
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


# ── Main flow ──────────────────────────────────────────────────────────────

def gather_fields(root: Path) -> tuple[Optional[str], Optional[dict]]:
    """Run the full TUI flow. Returns (project_id, node_dict) or (None, None) if quit."""
    console.print(Rule("[bold cyan]GDDP NODE SCAFFOLD[/bold cyan]"))
    console.print("[dim]s=skip  q=quit  m=manual  Enter=default  numbers pick  ←/→ paginate[/dim]\n")

    projects = list_projects(root)
    if not projects:
        console.print("[red]No projects found under graphs/[/red]")
        return None, None

    project = pick_from_list("Project", projects)
    if project in (None, "__quit__"):
        console.print("[dim]aborted[/dim]")
        return None, None

    existing_ids = list_node_ids(root, project)
    suggestions = gather_inspiration_bullets(root, project)

    # node_id
    while True:
        node_id = manual_text("node_id (kebab-case, unique in project)")
        if node_id is None:
            console.print("[red]node_id required[/red]")
            continue
        if not KEBAB_RE.match(node_id):
            console.print(f"[red]  {node_id!r} is not kebab-case[/red]")
            continue
        if node_id in existing_ids:
            console.print(f"[red]  {node_id!r} already exists in {project}[/red]")
            continue
        break

    # title
    title = manual_text("Title (short)")
    while not title:
        console.print("[red]title required[/red]")
        title = manual_text("Title")

    # type
    type_val = pick_from_list("Type", VALID_TYPES, default="capability")
    if type_val == "__quit__":
        return None, None

    # why
    why = manual_text("Why (one sentence: why this capability must exist)", multi_line=True)
    while not why:
        console.print("[red]why required[/red]")
        why = manual_text("Why", multi_line=True)

    # depends_on
    depends = pick_many("Depends_on", existing_ids, current=[])
    if depends == "__quit__":
        return None, None

    # acceptance
    acceptance = edit_list_items("Acceptance (verifiable bullets)", [], suggestions)
    if acceptance == "__quit__":
        return None, None
    while not acceptance:
        console.print("[red]at least one acceptance bullet required[/red]")
        acceptance = edit_list_items("Acceptance", [], suggestions)
        if acceptance == "__quit__":
            return None, None

    # constraints
    constraints = edit_list_items("Constraints (hard limits)", [], suggestions)
    if constraints == "__quit__":
        return None, None
    while not constraints:
        console.print("[red]at least one constraint required[/red]")
        constraints = edit_list_items("Constraints", [], suggestions)
        if constraints == "__quit__":
            return None, None

    # exec modes
    modes = pick_many("Allowed execution modes", VALID_EXEC_MODES, current=[],
                      defaults=["jules"])
    if modes == "__quit__":
        return None, None

    # required_artifacts
    artifacts = pick_many("Required artifacts", ALL_ARTIFACTS, current=[],
                          defaults=DEFAULT_ARTIFACTS)
    if artifacts == "__quit__":
        return None, None

    # status
    status_val = pick_from_list("Status", VALID_STATUSES, default="pending")
    if status_val == "__quit__":
        return None, None

    # priority
    priority_val = pick_from_list("Priority", VALID_PRIORITIES, default="medium")
    if priority_val == "__quit__":
        return None, None

    # unlocks
    unlocks = pick_many("Unlocks (existing node_ids + m for future-id)",
                        existing_ids, current=[], allow_future=True)
    if unlocks == "__quit__":
        return None, None

    return project, {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": node_id,
        "title": title,
        "type": type_val or "capability",
        "why": why,
        "depends_on": depends or [],
        "acceptance": normalize_acceptance_items(acceptance),
        "constraints": constraints,
        "allowed_execution_modes": modes or ["jules"],
        "required_artifacts": artifacts or DEFAULT_ARTIFACTS,
        "status": status_val or "pending",
        "priority": priority_val or "medium",
        "unlocks": unlocks or [],
    }


def render_node_yaml(node: dict) -> str:
    """Render node dict as YAML matching templates/node-template.yaml field order."""
    field_order = [
        "schema_version", "schema_type",
        "node_id", "title", "type", "why",
        "depends_on", "acceptance", "constraints",
        "allowed_execution_modes", "required_artifacts",
        "status", "priority", "unlocks",
    ]
    ordered = {k: node[k] for k in field_order if k in node}
    return yaml.dump(ordered, default_flow_style=False, sort_keys=False, allow_unicode=True)


def review_screen(node: dict) -> str:
    """Show the YAML and ask y/e/q. Returns 'write', 'edit', or 'quit'."""
    console.clear()
    yaml_text = render_node_yaml(node)
    console.print(Panel(
        yaml_text,
        title=f"[bold]Review — graphs/<project>/nodes/{node['node_id']}.yaml[/bold]",
        subtitle="[dim]y write  e edit field  q quit[/dim]",
        border_style="green",
        expand=False,
    ))
    ch = getch()
    if ch == "\x03":
        sys.exit(0)
    if ch.lower() == "q":
        return "quit"
    if ch.lower() == "y":
        return "write"
    if ch.lower() == "e":
        return "edit"
    console.print("[yellow]y / e / q[/yellow]")
    return review_screen(node)


EDITABLE_PICKER_FIELDS = {
    "type": VALID_TYPES,
    "status": VALID_STATUSES,
    "priority": VALID_PRIORITIES,
}


def edit_one_field(node: dict, field: str, root: Path, project: str) -> None:
    """Re-run the appropriate picker for one field, mutating node in place."""
    if field in EDITABLE_PICKER_FIELDS:
        v = pick_from_list(field, EDITABLE_PICKER_FIELDS[field],
                           current=node.get(field), default=node.get(field))
        if v and v != "__quit__":
            node[field] = v
    elif field == "why":
        v = manual_text("Why", multi_line=True)
        if v:
            node[field] = v
    elif field == "title":
        v = manual_text("Title")
        if v:
            node[field] = v
    elif field == "node_id":
        existing = list_node_ids(root, project)
        while True:
            v = manual_text("node_id (kebab-case)")
            if v and KEBAB_RE.match(v) and v not in existing:
                node[field] = v
                break
            if v:
                console.print(f"[red]  {v!r} invalid or already exists[/red]")
    elif field in ("depends_on", "unlocks"):
        existing = list_node_ids(root, project)
        v = pick_many(field, existing, current=node.get(field) or [],
                      allow_future=(field == "unlocks"))
        if v and v != "__quit__":
            node[field] = v
    elif field == "allowed_execution_modes":
        v = pick_many(field, VALID_EXEC_MODES, current=node.get(field) or [])
        if v and v != "__quit__":
            node[field] = v
    elif field == "required_artifacts":
        v = pick_many(field, ALL_ARTIFACTS, current=node.get(field) or [])
        if v and v != "__quit__":
            node[field] = v
    elif field in ("acceptance", "constraints"):
        suggestions = gather_inspiration_bullets(root, project)
        current = node.get(field) or []
        if field == "acceptance":
            current = [text for text in (acceptance_text(item) for item in current) if text]
        v = edit_list_items(field, current, suggestions)
        if v and v != "__quit__":
            node[field] = normalize_acceptance_items(v) if field == "acceptance" else v
    else:
        console.print(f"[yellow]no inline editor for {field}[/yellow]")


def write_node_file(root: Path, project: str, node: dict) -> Path:
    nodes_dir = root / "graphs" / project / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    path = nodes_dir / f"{node['node_id']}.yaml"
    path.write_text(render_node_yaml(node), encoding="utf-8")
    return path


def patch_project_yaml(root: Path, project: str, node: dict) -> Optional[Path]:
    """Insert node into project.yaml's nodes: list. .bak first. Returns path or None."""
    project_yaml = root / "graphs" / project / "project.yaml"
    if not project_yaml.exists():
        return None

    original = project_yaml.read_text(encoding="utf-8")
    backup = project_yaml.with_suffix(".yaml.bak")
    backup.write_text(original, encoding="utf-8")

    try:
        doc = yaml.safe_load(original) or {}
        if not isinstance(doc, dict):
            raise RuntimeError("project.yaml top-level is not a mapping")

        entry = {
            "id": node["node_id"],
            "title": node["title"],
            "status": node["status"],
            "type": node["type"],
        }
        nodes_list = doc.setdefault("nodes", [])
        if not isinstance(nodes_list, list):
            raise RuntimeError("project.yaml nodes: is not a list")
        nodes_list.append(entry)
        doc["last_updated"] = datetime.date.today().isoformat()

        new_text = yaml.dump(doc, default_flow_style=False, sort_keys=False,
                             allow_unicode=True)
        project_yaml.write_text(new_text, encoding="utf-8")

        # Round-trip verify
        verify = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
        if entry not in (verify or {}).get("nodes", []):
            raise RuntimeError("patch round-trip failed: entry missing from re-parsed nodes")
    except Exception as e:
        # Rollback
        project_yaml.write_text(original, encoding="utf-8")
        console.print(f"[red]project.yaml patch failed, rolled back: {e}[/red]")
        return None

    return project_yaml


def run_post_write_validator(root: Path, new_node_path: Path,
                              project_yaml_path: Optional[Path],
                              project: str) -> int:
    """Run validate.py globally. Print all findings. Exit gate: only fail if
    findings touch the new node file or project.yaml."""
    validate_script = Path(__file__).resolve().parent / "validate.py"
    if not validate_script.exists():
        console.print("[yellow]validate.py not found; skipping post-write check[/yellow]")
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(validate_script), "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(root),
        )
    except FileNotFoundError:
        console.print("[yellow]could not run validate.py; skipping[/yellow]")
        return 0

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        console.print("[yellow]validate.py returned non-JSON. Raw output:[/yellow]")
        console.print(result.stdout)
        return 0

    all_findings = data.get("errors", []) + data.get("warnings", [])

    if all_findings:
        console.print("\n[bold]Post-write validation report (loud, non-blocking for pre-existing):[/bold]")
        for f in all_findings:
            sev = f.get("severity", "error")
            color = "red" if sev == "error" else "yellow"
            label = "ERROR" if sev == "error" else "WARN"
            loc = f["path"] if f.get("line", 0) == 0 else f"{f['path']}:{f['line']}"
            console.print(f"  [{color}]{label}[/{color}] {loc} — {f['rule']} — {f['message']}")

    new_rel = f"graphs/{project}/nodes/{new_node_path.name}"
    proj_rel = f"graphs/{project}/project.yaml"

    new_issues = [f for f in all_findings if f.get("path") == new_rel]
    proj_issues = [f for f in all_findings if f.get("path") == proj_rel]
    pre_existing = len(all_findings) - len(new_issues) - len(proj_issues)

    if new_issues:
        console.print(f"\n[red]✗ new node has {len(new_issues)} issue(s) — fix above, then re-run[/red]")
        return 1
    if proj_issues:
        console.print(f"\n[red]✗ project.yaml has {len(proj_issues)} issue(s) introduced by patch[/red]")
        return 1

    if pre_existing:
        console.print(
            f"\n[green]✓ new node valid[/green]  "
            f"[yellow]⚠ {pre_existing} pre-existing issue(s) in repo (shown above) "
            f"— not introduced by this scaffold[/yellow]"
        )
    else:
        console.print("\n[green]✓ new node valid · repo clean[/green]")
    return 0


def main() -> int:
    root = Path(__file__).resolve().parent.parent

    project, node = gather_fields(root)
    if project is None or node is None:
        return 0

    while True:
        action = review_screen(node)
        if action == "quit":
            console.print("[dim]no files written[/dim]")
            return 0
        if action == "write":
            break
        if action == "edit":
            field_name = getline("Edit which field:")
            field_name = field_name.strip()
            if field_name in node:
                edit_one_field(node, field_name, root, project)
            else:
                console.print(f"[red]unknown field: {field_name}[/red]")
                console.print(f"[dim]valid: {', '.join(k for k in node if k != 'schema_version' and k != 'schema_type')}[/dim]")

    node_path = write_node_file(root, project, node)
    console.print(f"\n[green]WROTE[/green] {node_path.relative_to(root)}")

    project_yaml_path = patch_project_yaml(root, project, node)
    if project_yaml_path:
        console.print(f"[green]PATCHED[/green] {project_yaml_path.relative_to(root)}  [dim](.bak saved)[/dim]")
    else:
        console.print("[yellow]project.yaml not found or patch failed — node file written, index not updated[/yellow]")

    return run_post_write_validator(root, node_path, project_yaml_path, project)


if __name__ == "__main__":
    raise SystemExit(main())
