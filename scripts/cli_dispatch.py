"""Positional and interactive dispatch for gddp."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

import graph_io

_ABSTRACT_EXECUTION_MODES = frozenset({"agent", "human"})

SCRIPTS_DIR = Path(__file__).resolve().parent


def _root() -> Path:
    import gddp
    return gddp.ROOT


def _import_module(name: str):
    import gddp
    return gddp._import_module(name)


def resolve_runtime_root() -> Path:
    import gddp
    return gddp.resolve_runtime_root()


from gddp_proxy import console


def _menu_choice(*args, **kwargs):
    import gddp
    return gddp._menu_choice(*args, **kwargs)

class DispatchError(Exception):
    """Operator-facing dispatch validation failure."""

def _executor_allowed(executor: str, modes: list[str]) -> bool:
    """Treat `agent` as executor-neutral, never as a runnable adapter name."""
    return executor not in _ABSTRACT_EXECUTION_MODES and (
        executor in modes or "agent" in modes
    )

def _configured_executor(project_doc: dict, modes: list[str]) -> str:
    policy = project_doc.get("execution_policy") or {}
    default = policy.get("default_executor") or "jules"
    if not modes or _executor_allowed(default, modes):
        return default
    concrete_modes = [mode for mode in modes if mode != "agent"]
    if concrete_modes:
        return concrete_modes[0]
    raise DispatchError(
        "executor-neutral mode 'agent' requires a concrete "
        "execution_policy.default_executor"
    )

def _node_status_pairs(config_root: Path, project_id: str) -> dict:
    """node_id -> {summary, yaml, modes} across both graph status surfaces.

    project.yaml summaries are the readiness authority (the same contract
    GraphReader reads); node YAMLs carry modes. A summary/YAML disagreement
    is graph drift and must be shown, never silently resolved.
    """
    project_doc = _import_module("node_cli").load_project_doc(config_root, project_id)
    summary = {
        n.get("id"): n.get("status")
        for n in project_doc.get("nodes", [])
        if n.get("id")
    }
    out = {}
    nodes_dir = Path(config_root) / "graphs" / project_id / "nodes"
    for path in sorted(nodes_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        nid = data.get("node_id") or path.stem
        out[nid] = {
            "summary": summary.get(nid),
            "yaml": data.get("status"),
            "modes": list(data.get("allowed_execution_modes") or []),
        }
    for nid in summary:
        out.setdefault(nid, {"summary": summary[nid], "yaml": None, "modes": []})
    return out

def build_dispatch_plan(config_root, target, executor, project_hint=None):
    """Resolve target graph-first, validate everything, return a plan dict.

    Exact-node errors refuse that node. Graph dispatch excludes and explains
    invalid members while preserving the valid frontier. Unknown or ambiguous
    targets remain hard errors.
    project_hint (menu path) qualifies a node lookup to one graph. When the
    target is that same graph ID, the hint came from the graph-wide menu path
    and the target must remain a graph frontier, not be reinterpreted as a node.
    """
    config_root = Path(config_root)
    projects = graph_io._graph_projects(config_root)
    plan_excluded = []
    if target in projects and project_hint in (None, target):
        project_id = target
        nodes = []
        pairs = _node_status_pairs(config_root, project_id)
        for nid, pair in sorted(pairs.items()):
            if pair["summary"] != "ready":
                continue
            node = {"node_id": nid, "modes": pair["modes"]}
            if pair["yaml"] is None:
                plan_excluded.append((node, "no — graph drift: node YAML missing"))
                continue
            if pair["yaml"] != "ready":
                plan_excluded.append((
                    node,
                    "no — graph drift: summary ready / yaml {}".format(pair["yaml"]),
                ))
                continue
            if executor and not _executor_allowed(executor, pair["modes"]):
                plan_excluded.append((
                    node,
                    "no — executor {!r} not allowed".format(executor),
                ))
                continue
            nodes.append(node)
        if not nodes and not plan_excluded:
            raise DispatchError(f"graph {target!r} has no ready nodes")
    else:
        if project_hint is not None:
            matches = [project_hint] if (
                config_root / "graphs" / project_hint / "nodes" / f"{target}.yaml"
            ).is_file() else []
        else:
            matches = [
                p for p in projects
                if (config_root / "graphs" / p / "nodes" / f"{target}.yaml").is_file()
            ]
        if not matches:
            raise DispatchError(
                f"no graph or node named '{target}' "
                f"(graphs: {', '.join(projects) or 'none'})"
            )
        if len(matches) > 1:
            raise DispatchError(
                f"node '{target}' exists in multiple graphs: {', '.join(matches)}; "
                "dispatch is exact — qualify from the interactive menu"
            )
        project_id = matches[0]
        pair = _node_status_pairs(config_root, project_id).get(
            target, {"summary": None, "yaml": None, "modes": []}
        )
        if pair["summary"] != pair["yaml"]:
            raise DispatchError(
                f"graph drift for '{target}': project.yaml summary is "
                f"'{pair['summary']}', node YAML is '{pair['yaml']}' — "
                "reconcile before dispatch"
            )
        if pair["summary"] != "ready":
            raise DispatchError(
                f"node '{target}' is '{pair['summary']}', not ready"
            )
        modes = pair["modes"]
        if executor and not _executor_allowed(executor, modes):
            raise DispatchError(
                f"executor '{executor}' not in {target}.allowed_execution_modes: "
                f"{modes or []}"
            )
        nodes = [{"node_id": target, "modes": modes}]

    project_doc = _import_module("node_cli").load_project_doc(config_root, project_id)

    def resolve_item(node):
        return {
            "node_id": node["node_id"],
            "executor": executor or _configured_executor(project_doc, node["modes"]),
        }

    items = [resolve_item(node) for node in nodes]
    return {
        "project_id": project_id,
        "repo": project_doc.get("repo") or "",
        "items": items,
        "excluded": [
            (resolve_item(node), reason) for node, reason in plan_excluded
        ],
    }

def insert_dispatch_events(con, project_id, repo, items, *, actor=None):
    """Insert one schema-valid intake event per node; the heartbeat pipeline
    claims, classifies (via the node: tag in url), scopes, reserves, and
    dispatches. Each item already contains the concrete executor resolved by
    the dispatch plan; persist it so runtime never re-plans operator intent."""
    now = datetime.now(timezone.utc)
    event_ids = []
    for item in items:
        event_id = (
            f"evt_dispatch_{now.strftime('%Y%m%dT%H%M%S')}_"
            f"{item['node_id']}_{secrets.token_hex(3)}"
        )
        routing = json.dumps({"selected_executor": item["executor"]})
        con.execute(
            "INSERT INTO events (event_id, schema_version, received_at, source, "
            "event_type, actor, url, project_id, project_node_candidates, "
            "scope_status, priority, risk_level, routing, status, repo) "
            "VALUES (?, '1.0', ?, 'manual_inject', 'issue.opened', ?, ?, ?, ?, "
            "'pending', 'pending', 'pending', ?, 'received', ?)",
            (
                event_id,
                now.isoformat(),
                actor or os.environ.get("USER") or "operator",
                f"manual-dispatch://node: {item['node_id']}",
                project_id,
                json.dumps([item["node_id"]]),
                routing,
                repo,
            ),
        )
        event_ids.append(event_id)
    con.commit()
    return event_ids

def _connect_events_db(db_path: Path):
    if not db_path.is_file():
        raise DispatchError(f"runtime DB not initialized at {db_path}")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    try:
        con.execute("SELECT 1 FROM events LIMIT 1")
    except sqlite3.OperationalError as exc:
        con.close()
        raise DispatchError(f"runtime DB missing events table: {exc}") from exc
    return con

def _classify_dispatch_items(con, config_root, plan):
    """Return the plan's genuinely dispatchable and blocked items.

    This is the single truth path for both the interactive frontier display and
    the final dispatch gate: graph-ready status alone is never presented as
    dispatchable when dependencies or live runtime motion still block a node.
    """
    frontier = _import_module("frontier")
    try:
        blockers = frontier.dispatch_blockers(con, plan["project_id"])
    except sqlite3.Error as exc:
        raise DispatchError(
            f"runtime state unreadable ({exc}); "
            "refusing to dispatch without duplicate-checking"
        ) from exc
    graph = frontier.load_graph(config_root, plan["project_id"])
    movable, excluded = [], list(plan.get("excluded", []))
    for item in plan["items"]:
        if item["node_id"] in blockers:
            excluded.append((item, "no — in flight"))
            continue
        deps = frontier.unsatisfied_deps(graph, item["node_id"])
        if deps:
            detail = ", ".join(f"{dep} [{status}]" for dep, status in deps)
            excluded.append((item, f"no — dep-blocked: {detail}"))
            continue
        movable.append(item)
    return movable, excluded

def _confirm_dispatch(count: int) -> bool:
    """Confirm insert. Enter / y = yes. n = abort. Never default to no.

    TTY uses the same one-key menu as the rest of the control plane. Pipes
    and tests fall back to a line prompt defaulting to y.
    """
    console.print(
        Text(
            f"Dispatch {count} event(s) through the heartbeat pipeline?",
            style="bold",
        )
    )
    try:
        if sys.stdin.isatty() and sys.stdout.isatty():
            actions = {
                "y": ("yes", f"insert {count} event(s) — start heartbeat work"),
                "n": ("no", "abort — insert nothing"),
                "b": ("back", "abort — insert nothing"),
            }
            choice = _menu_choice(actions, default="y")
            return choice == "y"
        answer = Prompt.ask(
            f"Dispatch {count} event(s)? [Y/n]",
            default="y",
        )
        return answer.strip().lower() in {"", "y", "yes"}
    except (EOFError, KeyboardInterrupt):
        console.print("\naborted; no events inserted")
        return False

def _dispatch_flow(con, config_root, target, executor, project_hint=None,
                   yes=False) -> int:
    """Shared shell/menu path: validate, exclude in-flight nodes, preview once,
    confirm once, insert. A node executing, being evaluated, or awaiting
    review is never offered for duplicate dispatch."""
    try:
        plan = build_dispatch_plan(config_root, target, executor, project_hint)
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    try:
        movable, excluded = _classify_dispatch_items(con, config_root, plan)
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    if not movable:
        console.print(
            "[bold red]ERROR:[/] nothing dispatchable; requested nodes were excluded:"
        )
        for item, reason in excluded:
            console.print(f"  {item['node_id']}: {reason}", markup=False)
        return 2
    table = Table(title=f"dispatch preview — {plan['project_id']}")
    table.add_column("node", style="bold")
    table.add_column("executor")
    table.add_column("dispatch?", style="yellow")
    for item in movable:
        table.add_row(item["node_id"], item["executor"], "yes")
    for item, reason in excluded:
        table.add_row(item["node_id"], item["executor"], Text(reason))
    console.print(table)
    if not yes:
        import gddp
        if not gddp._confirm_dispatch(len(movable)):
            console.print("aborted; no events inserted")
            return 1
    event_ids = insert_dispatch_events(
        con,
        plan["project_id"],
        plan["repo"],
        movable,
    )
    for event_id in event_ids:
        console.print(f"  event [cyan]{event_id}[/] → received")
    console.print("next heartbeat tick claims, scopes, reserves, and dispatches.")
    return 0

def cmd_dispatch(argv, *, config_root=None, db_path=None) -> int:
    """Positional dispatch: gddp <graph|node> [executor] [--yes]."""
    yes = False
    positional = []
    for arg in argv:
        if arg == "--yes":
            yes = True
            continue
        if arg.startswith("-"):
            console.print("[bold red]usage:[/] gddp <graph|node> [executor] [--yes]")
            return 2
        positional.append(arg)
    if len(positional) not in (1, 2):
        console.print("[bold red]usage:[/] gddp <graph|node> [executor] [--yes]")
        return 2
    target = positional[0]
    executor = positional[1] if len(positional) == 2 else None
    config_root = Path(config_root) if config_root else _root()
    try:
        con = _connect_events_db(
            Path(db_path) if db_path else resolve_runtime_root() / "db" / "queue.db"
        )
    except DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        return 2
    try:
        return _dispatch_flow(con, config_root, target, executor, yes=yes)
    finally:
        con.close()
