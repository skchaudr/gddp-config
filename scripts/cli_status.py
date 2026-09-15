"""Status and validate interactive/CLI surfaces for gddp."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.text import Text

import graph_io

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent



def _menu_back():
    import gddp
    return gddp._MENU_BACK


def _menu_quit():
    import gddp
    return gddp._MENU_QUIT

def _import_module(name: str):
    import gddp
    return gddp._import_module(name)


from gddp_proxy import console


def _graph_status_style(status: str) -> str:
    import gddp
    return gddp._graph_status_style(status)


def _node_status_label(doc: dict, entry: dict | None) -> str:
    import gddp
    return gddp._node_status_label(doc, entry)


def _node_menu_phase(*args, **kwargs) -> str:
    import gddp
    return gddp._node_menu_phase(*args, **kwargs)


def _verdict_chip(verdict: str | None) -> str:
    import gddp
    return gddp._verdict_chip(verdict)


def _format_node_columns(**kwargs):
    import gddp
    return gddp._format_node_columns(**kwargs)


def _runtime_label(*args, **kwargs) -> str:
    import gddp
    return gddp._runtime_label(*args, **kwargs)


def _menu_choice(*args, **kwargs):
    import gddp
    return gddp._menu_choice(*args, **kwargs)


def _clear_screen() -> None:
    import gddp
    gddp._clear_screen()


def _pick_graph(*args, **kwargs):
    import gddp
    return gddp._pick_graph(*args, **kwargs)


def _pick_list(*args, **kwargs):
    import gddp
    return gddp._pick_list(*args, **kwargs)


def _node_review_menu(*args, **kwargs):
    import gddp
    return gddp._node_review_menu(*args, **kwargs)

def _list_status_projects() -> list[str]:
    import gddp
    graphs = gddp.ROOT / "graphs"
    if not graphs.exists():
        return []
    return sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )

def _graph_status_counts(nodes: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        s = str(n.get("status") or "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts

def _pct_style(pct: int) -> str:
    if pct >= 100:
        return "bold green"
    if pct > 0:
        return "bold yellow"
    return "dim"

def _status_counts_text(counts: dict[str, int]) -> Text:
    out = Text()
    for i, (status, count) in enumerate(sorted(counts.items())):
        if i:
            out.append(", ", style="dim")
        out.append(status, style=_graph_status_style(status))
        out.append(f"={count}")
    return out

def _print_status_project_row(project_id: str, nodes: list, *, indent: str = "") -> tuple[int, int]:
    """Print one project summary line. Returns (complete, total)."""
    counts = _graph_status_counts(nodes)
    total = sum(counts.values())
    complete = counts.get("complete", 0)
    pct = int(complete / total * 100) if total else 0
    row = Text(indent)
    row.append(f"{project_id:<25}", style="bold")
    row.append(f" {total:>3} nodes  ", style="dim")
    row.append(f"{pct:>3}% done", style=_pct_style(pct))
    row.append("  (", style="dim")
    row.append_text(_status_counts_text(counts))
    row.append(")", style="dim")
    console.print(row)
    return complete, total

def show_status(project_id: str | None = None) -> None:
    """Rich graph completion summary — all projects or one project with nodes."""
    import gddp
    projects = gddp._list_status_projects()
    if not projects:
        console.print(Text("No graphs/ directory found", style="yellow"))
        return
    if project_id:
        if project_id not in projects:
            console.print(Text(f"Project '{project_id}' not found", style="red"))
            return
        _render_project_status_detail(project_id)
        return

    console.print(Text("status · all projects", style="bold"))
    total_complete = 0
    grand = 0
    for pid in projects:
        proj = gddp._load_project_doc(pid)
        complete, total = _print_status_project_row(pid, proj.get("nodes") or [])
        total_complete += complete
        grand += total
    gpct = int(total_complete / grand * 100) if grand else 0
    footer = Text()
    footer.append(f"{'TOTAL':<25}", style="bold")
    footer.append(f" {grand:>3} nodes  ", style="dim")
    footer.append(f"{gpct:>3}% done", style=_pct_style(gpct))
    console.print()
    console.print(footer)

def _render_project_status_detail(project_id: str) -> None:
    """One project: colored counts + each node with runtime phase."""
    import gddp
    node_cli = _import_module("node_cli")
    proj = gddp._load_project_doc(project_id)
    nodes_index = proj.get("nodes") or []
    console.print(Text(f"status · {project_id}", style="bold"))
    _print_status_project_row(project_id, nodes_index)
    console.print()

    try:
        node_rows = node_cli.iter_nodes(ROOT, project_id)
    except Exception as exc:
        console.print(Text(f"Could not load nodes: {exc}", style="red"))
        return
    if not node_rows:
        console.print(Text("(no nodes)", style="dim"))
        return

    phase_counts: dict[str, int] = {}
    verdict_counts: dict[str, int] = {}
    for node_id, doc, entry in node_rows:
        graph_status = _node_status_label(doc, entry)
        queue_state = "-"
        job_status = "-"
        verdict = "-"
        try:
            ev = node_cli.fetch_runtime_evidence(ROOT, project_id, node_id)
            queue_state = getattr(ev, "queue_state", "-") or "-"
            job_status = getattr(ev, "job_status", "-") or "-"
            verdict = getattr(ev, "verdict", "-") or "-"
        except Exception:
            pass
        phase = _node_menu_phase(graph_status, queue_state, job_status)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        chip = _verdict_chip(verdict)
        if chip:
            key = chip.lower()
            verdict_counts[key] = verdict_counts.get(key, 0) + 1
        title = str(doc.get("title") or (entry or {}).get("title") or "")
        line = Text()
        line.append(f"  {node_id:<36}", style="bold")
        line.append_text(_format_node_columns(
            graph=graph_status,
            runtime=_runtime_label(queue_state, job_status),
            verdict=verdict,
            title=title,
            room=max(24, (console.width or 80) - 40),
        ))
        console.print(line)

    console.print()
    scan = Text("  operator scan  ")
    scan.append_text(_status_counts_text(phase_counts))
    console.print(scan)
    if verdict_counts:
        ev_scan = Text("  evaluator       ")
        ev_scan.append_text(_status_counts_text(verdict_counts))
        console.print(ev_scan)

def _status_node_items(project_id: str) -> list[tuple[str, dict]]:
    """Node rows for status drill-in picker."""
    node_cli = _import_module("node_cli")
    try:
        node_rows = node_cli.iter_nodes(ROOT, project_id)
    except Exception:
        return []
    items: list[tuple[str, dict]] = []
    for node_id, doc, entry in node_rows:
        graph_status = _node_status_label(doc, entry)
        queue_state = job_status = verdict = "-"
        try:
            ev = node_cli.fetch_runtime_evidence(ROOT, project_id, node_id)
            queue_state = getattr(ev, "queue_state", "-") or "-"
            job_status = getattr(ev, "job_status", "-") or "-"
            verdict = getattr(ev, "verdict", "-") or "-"
        except Exception:
            pass
        title = str(doc.get("title") or (entry or {}).get("title") or "")
        items.append((
            node_id,
            {
                "graph": graph_status,
                "runtime": _runtime_label(queue_state, job_status),
                "verdict": verdict,
                "title": title,
            },
        ))
    return items

def _status_after_show(project_id: str | None, *, back_label: str = "more") -> str:
    """Refresh/back menu or pick a graph/node after status render."""
    current = project_id
    while True:
        if current:
            pick_name = "pick node"
            pick_desc = "open one node in review"
        else:
            pick_name = "pick graph"
            pick_desc = "drill into one project"
        actions = {
            "p": (pick_name, pick_desc),
            "r": ("refresh", "reload status"),
            "b": ("back", ""),
            "q": ("quit", ""),
        }
        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _menu_quit()
        if choice == "b":
            return _menu_back()
        if choice == "r":
            _clear_screen()
            gddp.show_status(current)
            continue
        if not current:
            picked = _pick_graph("status · graphs", back_label=back_label)
            if picked is _menu_quit():
                return _menu_quit()
            if picked is _menu_back():
                continue
            current = str(picked)
            _clear_screen()
            gddp.show_status(current)
            continue
        items = _status_node_items(current)
        if not items:
            console.print(Text("No nodes to open.", style="yellow"))
            continue
        picked = _pick_list(
            f"status · {current}",
            items,
            back_label=back_label,
        )
        if picked is _menu_quit():
            return _menu_quit()
        if picked is _menu_back():
            continue
        siblings = [value for value, _ in items]
        outcome = _node_review_menu(current, str(picked), siblings)
        if outcome is _menu_quit():
            return _menu_quit()
        _clear_screen()
        gddp.show_status(current)

def _collect_validate_failures(
    projects: list[str],
) -> list[tuple[str, str]]:
    """Node-scoped validation failures as pick keys ``project\\tnode_id``."""
    import gddp
    graphs = gddp.ROOT / "graphs"
    failures: list[tuple[str, str]] = []
    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}
        node_ids = {
            n["id"]
            for n in (proj.get("nodes") or [])
            if isinstance(n, dict) and n.get("id")
        }
        nodes_dir = graphs / pid / "nodes"
        yaml_ids = {p.stem for p in nodes_dir.glob("*.yaml")} if nodes_dir.exists() else set()
        for nid in sorted(node_ids - yaml_ids):
            failures.append((f"{pid}\t{nid}", f"{pid}/{nid} · missing nodes/{nid}.yaml"))
        for nid in sorted(yaml_ids - node_ids):
            failures.append((
                f"{pid}\t{nid}",
                f"{pid}/{nid} · orphan nodes/{nid}.yaml",
            ))
        seen: set[str] = set()
        for n in proj.get("nodes") or []:
            if not isinstance(n, dict):
                continue
            nid = n.get("id")
            if not nid or nid in seen:
                if nid:
                    failures.append((
                        f"{pid}\t{nid}",
                        f"{pid}/{nid} · duplicate in project.yaml",
                    ))
                continue
            seen.add(nid)
    return failures

def _validate_after_show(
    project_id: str | None,
    projects: list[str],
    *,
    back_label: str = "more",
) -> str:
    """Refresh/back menu or pick failing nodes after validate render."""
    while True:
        import gddp
        failures = gddp._collect_validate_failures(projects)
        actions = {
            "r": ("refresh", "re-run validation"),
            "b": ("back", ""),
            "q": ("quit", ""),
        }
        if failures:
            actions = {
                "p": ("pick node", "open a failing node in review"),
                **actions,
            }
        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _menu_quit()
        if choice == "b":
            return _menu_back()
        if choice == "r":
            _clear_screen()
            gddp.validate_project(project_id)
            continue
        picked = _pick_list(
            "validate · failures",
            [(key, label) for key, label in failures],
            back_label=back_label,
        )
        if picked is _menu_quit():
            return _menu_quit()
        if picked is _menu_back():
            continue
        pid, node_id = str(picked).split("\t", 1)
        node_cli = _import_module("node_cli")
        try:
            siblings = [nid for nid, _, _ in node_cli.iter_nodes(ROOT, pid)]
        except Exception:
            siblings = [node_id]
        outcome = _node_review_menu(pid, node_id, siblings)
        if outcome is _menu_quit():
            return _menu_quit()
        _clear_screen()
        gddp.validate_project(project_id)

def interactive_status(project: str | None = None):
    """Status for one graph, or all/one picker when no project is fixed."""
    if project:
        _clear_screen()
        gddp.show_status(project)
        return _status_after_show(project, back_label="more")
    actions = {
        "a": ("all", "every project completion summary"),
        "o": ("one", "pick one project — counts + node phases"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    import gddp
    projects = gddp._list_status_projects()
    while True:
        _clear_screen()
        console.print(Text("status", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _menu_quit()
        if choice == "b":
            return _menu_back()
        if choice == "a":
            _clear_screen()
            gddp.show_status()
            outcome = _status_after_show(None, back_label="status")
            if outcome is _menu_quit():
                return _menu_quit()
            continue
        picked = _pick_graph("status · graphs", back_label="status")
        if picked is _menu_quit():
            return _menu_quit()
        if picked is _menu_back():
            continue
        _clear_screen()
        gddp.show_status(str(picked))
        outcome = _status_after_show(str(picked), back_label="status")
        if outcome is _menu_quit():
            return _menu_quit()

def interactive_validate(project: str | None = None):
    """Validate one graph, or all/one picker when no project is fixed."""
    import gddp
    if project:
        _clear_screen()
        gddp.validate_project(project)
        return _validate_after_show(project, [project], back_label="more")
    actions = {
        "a": ("all", "validate every project"),
        "o": ("one", "pick one project"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    import gddp
    projects = gddp._list_status_projects()
    while True:
        _clear_screen()
        console.print(Text("validate", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _menu_quit()
        if choice == "b":
            return _menu_back()
        if choice == "a":
            _clear_screen()
            gddp.validate_project(None)
            outcome = _validate_after_show(None, projects, back_label="validate")
            if outcome is _menu_quit():
                return _menu_quit()
            continue
        picked = _pick_graph("validate · graphs", back_label="validate")
        if picked is _menu_quit():
            return _menu_quit()
        if picked is _menu_back():
            continue
        picked_project = str(picked)
        _clear_screen()
        gddp.validate_project(picked_project)
        outcome = _validate_after_show(
            picked_project, [picked_project], back_label="validate",
        )
        if outcome is _menu_quit():
            return _menu_quit()

def validate_project(project_id: str | None):
    import gddp
    graphs = gddp.ROOT / "graphs"
    if not graphs.exists():
        console.print(Text("No graphs/ directory found", style="yellow"))
        return

    import gddp
    projects = gddp._list_status_projects()
    if project_id:
        if project_id not in projects:
            console.print(Text(f"Project '{project_id}' not found", style="red"))
            return
        projects = [project_id]

    errors = 0
    for pid in projects:
        proj_yaml = graphs / pid / "project.yaml"
        with open(proj_yaml) as f:
            proj = yaml.safe_load(f) or {}

        pid_errors = []

        if proj.get("schema_version") != "1.0":
            pid_errors.append("schema_version != 1.0")
        if not proj.get("project_id"):
            pid_errors.append("missing project_id")
        if proj.get("project_id") != pid:
            pid_errors.append(f"project_id '{proj.get('project_id')}' != directory '{pid}'")
        if not proj.get("repo"):
            pid_errors.append("missing repo")
        nodes = proj.get("nodes")
        if not isinstance(nodes, list):
            pid_errors.append("nodes is not a list")
        else:
            node_ids = set()
            for n in nodes:
                if not isinstance(n, dict):
                    pid_errors.append(f"nodes entry is not a dict: {n}")
                    continue
                nid = n.get("id")
                if not nid:
                    pid_errors.append("nodes entry missing id")
                    continue
                if nid in node_ids:
                    pid_errors.append(f"duplicate node id in project.yaml: {nid}")
                node_ids.add(nid)

            nodes_dir = graphs / pid / "nodes"
            yaml_ids = set()
            if nodes_dir.exists():
                yaml_ids = {p.stem for p in nodes_dir.glob("*.yaml")}

            missing_yaml = node_ids - yaml_ids
            orphan_yaml = yaml_ids - node_ids
            if missing_yaml:
                for nid in sorted(missing_yaml):
                    pid_errors.append(f"project.yaml lists {nid} but no nodes/{nid}.yaml exists")
            if orphan_yaml:
                for nid in sorted(orphan_yaml):
                    pid_errors.append(f"nodes/{nid}.yaml exists but not listed in project.yaml")

        if pid_errors:
            console.print(Text(pid, style="bold red"))
            for e in pid_errors:
                console.print(Text(f"  ERROR: {e}", style="red"))
            errors += len(pid_errors)
        else:
            line = Text()
            line.append(pid, style="bold green")
            line.append(" OK", style="green")
            console.print(line)

    summary = Text()
    summary.append(f"\n{errors} error(s)", style="bold red" if errors else "bold green")
    summary.append(f" across {len(projects)} project(s)", style="dim")
    console.print(summary)
    return 1 if errors else 0
