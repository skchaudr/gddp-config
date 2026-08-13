#!/usr/bin/env python3
"""gddp — unified CLI for graph truth and runtime evidence.

Subcommands:
    node browse       Open the node review TUI, optionally at one project
    node new          Interactive TUI node scaffold (full field editor)
    node rapid        Minimal-keystroke rapid node adder
    node batch        Walk through pending/REPLACE_ME nodes in a project
    node import       Import a node YAML from file or stdin (agent pipeline)
    node validate     Validate all nodes (or one project)
    node list         List nodes (ID | GRAPH | RUNTIME | VERDICT)
    node show         Show one node + evaluator summary (read-only runtime)
    node status       Show status summary for all projects

    jobs list         List runtime jobs and queue states
    jobs show         Show one runtime job and its evidence
    jobs results      Summarize evaluator output
    jobs set          Change runtime job state with an audit reason

    evaluations       List evaluator receipts (verdict + timing)

    watch [target]    Live view: fleet of attempts, or one node's diff + events
    steer <target>    Send an operator message into a running attempt's session

    <graph> [executor] [--yes]  Dispatch the graph's ready frontier (positional)
    <node> [executor] [--yes]   Dispatch one ready node; --yes skips confirm

    verify node       Run deterministic node evaluation; emit a receipt
    receipt           Append a mission worker node receipt to GDDP_RECEIPTS_PATH

    obsidian export   Export one graph to ~/Obsidian/gdd-<project>/

    project new       Create project skeleton (from graphify, outline, or empty shell)
    project validate  Validate project.yaml structure

Usage:
    python3 scripts/gddp.py node browse --project gddp-runtime
    python3 scripts/gddp.py node rapid --project my-app --repo org/repo
    python3 scripts/gddp.py node validate --project vault-doctor
    python3 scripts/gddp.py node import --file draft.yaml --project my-app
    python3 scripts/gddp.py node import --file draft.yaml --project my-app --update
    python3 scripts/gddp.py gddp-runtime local_subprocess --yes
    python3 scripts/gddp.py node batch --project my-greenfield
    python3 scripts/gddp.py node list --project gddp-runtime --active
    python3 scripts/gddp.py node show --project gddp-runtime canary-retry-proof
    python3 scripts/gddp.py jobs list --state awaiting_review
    python3 scripts/gddp.py gddp-runtime
    python3 scripts/gddp.py verdict-confidence-split local_subprocess
    python3 scripts/gddp.py jobs show <job-id> --full
    python3 scripts/gddp.py project new --from-outline outline.md --project-id my-app --repo org/repo
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    from rich import box
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Install deps:  pip install pyyaml rich")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
_PIPE_WIDTH = None if sys.stdout.isatty() else 120
console = Console(soft_wrap=True, highlight=False, width=_PIPE_WIDTH)
_MENU_BACK = object()
_MENU_QUIT = object()
_RUNTIME_JOB_COMMANDS = frozenset({"list", "show", "results", "set"})
_CLI_COMMANDS = frozenset(
    {
        "node",
        "jobs",
        "evaluations",
        "verify",
        "review",
        "receipt",
        "obsidian",
        "project",
        "watch",
        "steer",
    }
)
_ABSTRACT_EXECUTION_MODES = frozenset({"agent", "human"})


# --------------------------------------------------------------------------- #
# Positional dispatch: gddp <graph|node> [executor]
# --------------------------------------------------------------------------- #

class DispatchError(Exception):
    """Operator-facing dispatch validation failure."""


def _graph_projects(config_root: Path) -> list[str]:
    graphs = Path(config_root) / "graphs"
    if not graphs.is_dir():
        return []
    return sorted(
        d.name for d in graphs.iterdir()
        if d.is_dir() and (d / "project.yaml").is_file()
    )


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
    projects = _graph_projects(config_root)
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
        try:
            answer = Prompt.ask(
                f"Dispatch {len(movable)} event(s) through the heartbeat pipeline? [y/N]",
                default="n",
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\naborted; no events inserted")
            return 1
        if answer.strip().lower() not in {"y", "yes"}:
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
    config_root = Path(config_root) if config_root else ROOT
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


def _print_frontier_text(text: str) -> None:
    """Color frontier section heads and phase tokens for scannable output."""
    section_styles = {
        "ready now (dispatchable):": "bold cyan",
        "in flight (not offered for dispatch):": "bold magenta",
        "awaiting correction (may be redispatched):": "bold yellow",
        "blocked (incomplete dependencies):": "yellow",
        "runtime/graph drift:": "bold red",
        "unlocks on acceptance:": "bold green",
    }
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            console.print()
            continue
        if line.startswith("frontier:"):
            t = Text()
            t.append("frontier: ", style="bold")
            t.append(line[len("frontier:"):].strip(), style="bold cyan")
            console.print(t)
            continue
        if line.strip() in section_styles:
            console.print(Text(line, style=section_styles[line.strip()]))
            continue
        if " — " in line:
            left, right = line.split(" — ", 1)
            t = Text(left + " — ")
            phase = right.split("  ", 1)[0]
            rest = right[len(phase):]
            t.append(phase, style=_graph_status_style(phase))
            if rest:
                t.append(rest, style="dim")
            console.print(t)
            continue
        if line.strip() == "(none)":
            console.print(Text(line, style="dim"))
            continue
        console.print(line)


def _show_frontier(selected: list[str]) -> None:
    frontier = _import_module("frontier")
    try:
        con = frontier.connect_readonly(resolve_runtime_root() / "db" / "queue.db")
        note = None
    except frontier.FrontierUnavailable as exc:
        con = None
        note = str(exc)
    try:
        for pid in selected:
            graph = frontier.load_graph(ROOT, pid)
            runtime = {}
            pid_note = note
            if con is not None:
                try:
                    runtime = frontier.load_runtime(con, pid)
                except sqlite3.Error as exc:
                    pid_note = str(exc)
            _print_frontier_text(
                frontier.render_text(
                    pid, frontier.derive(graph, runtime), runtime_note=pid_note
                )
            )
            console.print()
    finally:
        if con is not None:
            con.close()


def interactive_frontier():
    """Derived frontier view; recomputes from live graph + runtime on open."""
    frontier = _import_module("frontier")
    projects = frontier.project_ids(ROOT)
    if not projects:
        console.print(Text("no graphs found", style="yellow"))
        return _MENU_BACK
    actions = {
        "a": ("all", "frontier for every project"),
        "o": ("one", "pick one project"),
        "b": ("main menu", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("frontier", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            _show_frontier(projects)
            _pause()
            continue
        project = _pick_list(
            "frontier · graphs",
            [(pid, "") for pid in projects],
            preview_cmd=_project_preview_cmd(),
            back_label="frontier",
        )
        if project is _MENU_QUIT:
            return _MENU_QUIT
        if project is _MENU_BACK:
            continue
        _clear_screen()
        _show_frontier([project])
        _pause()


def interactive_dispatch():
    """Pick a graph and a genuinely dispatchable target with one-key menus."""
    projects = _graph_projects(ROOT)
    if not projects:
        console.print("no graphs found")
        return
    project_items = [(project_id, "") for project_id in projects]
    while True:
        project = _pick_list(
            "dispatch · graphs",
            project_items,
            preview_cmd=_project_preview_cmd(),
            back_label="main menu",
        )
        if project is _MENU_QUIT:
            return _MENU_QUIT
        if project is _MENU_BACK:
            return _MENU_BACK
        try:
            con = _connect_events_db(resolve_runtime_root() / "db" / "queue.db")
        except DispatchError as exc:
            console.print(f"[bold red]ERROR:[/] {exc}")
            return
        try:
            try:
                plan = build_dispatch_plan(
                    ROOT, project, None, project_hint=project
                )
                movable, excluded = _classify_dispatch_items(con, ROOT, plan)
            except DispatchError as exc:
                console.print(f"[bold red]ERROR:[/] {exc}")
                return

            _clear_screen()
            table = Table(title=f"dispatchability — {project}")
            table.add_column("node", style="bold")
            table.add_column("executor")
            table.add_column("state")
            for item in movable:
                table.add_row(
                    item["node_id"],
                    item["executor"],
                    Text("ready now", style="bold cyan"),
                )
            for item, reason in excluded:
                table.add_row(
                    item["node_id"],
                    item["executor"],
                    Text(str(reason), style="yellow"),
                )
            console.print(table)
            if not movable:
                console.print(
                    Text("No nodes are dispatchable now.", style="yellow")
                )
                return

            target_items = [
                (
                    project,
                    Text(
                        f"entire dispatchable frontier · {len(movable)} node"
                        f"{'s' if len(movable) != 1 else ''}",
                        style="bold cyan",
                    ),
                ),
                *[
                    (
                        item["node_id"],
                        Text(
                            f"{item['executor']} · ready now",
                            style="bold cyan",
                        ),
                    )
                    for item in movable
                ],
            ]
            target = _pick_list(
                f"dispatch · {project}",
                target_items,
                back_label="graphs",
            )
            if target is _MENU_QUIT:
                return _MENU_QUIT
            if target is _MENU_BACK:
                continue
            executor = Prompt.ask(
                "executor override (blank = configured routing)", default=""
            )
            _dispatch_flow(
                con,
                ROOT,
                target,
                executor.strip() or None,
                project_hint=project,
            )
            return
        finally:
            con.close()


def _import_module(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    return __import__(name)


def _clear_screen() -> None:
    """Start each interactive view at the top of a clean terminal."""
    if console.is_terminal:
        console.clear()


def _graph_status_style(status: str) -> str:
    """Bright styles so list rows are scannable — pass ≠ review ≠ ready."""
    plain = (status or "").strip().lower().replace("_", " ")
    if plain.startswith("desync"):
        return "bold red"
    if plain in {"pass", "passed"}:
        return "bold green"
    if plain in {"fail", "failed"}:
        return "bold red"
    if plain == "awaiting review":
        return "bold yellow"
    if plain == "awaiting result":
        return "bold cyan"
    key = plain.split()[0] if plain else ""
    return {
        "complete": "bold green",
        "ready": "bold cyan",
        "queued": "bold blue",
        "provisional": "bold yellow",
        "pending": "yellow",
        "deferred": "magenta",
        "running": "bold magenta",
        "failed": "bold red",
        "desync": "bold red",
        "cancelled": "dim",
        "blocked": "yellow",
        "intake": "dim",
        "classified": "dim",
    }.get(key, "bold white")


def _verdict_chip(verdict: str | None) -> str:
    """Uppercase evaluator chip, or empty when there is no verdict yet."""
    raw = str(verdict or "").strip().lower().replace("-", "_")
    if raw in {"pass", "passed"}:
        return "PASS"
    if raw in {"fail", "failed"}:
        return "FAIL"
    return ""


def _node_row_description(
    phase: str,
    title: str = "",
    verdict: str | None = None,
) -> Text:
    """List/status row: PASS/FAIL first, then runtime/graph phase, then title."""
    desc = Text()
    chip = _verdict_chip(verdict)
    if chip:
        desc.append(chip, style=_graph_status_style(chip))
        desc.append(" · ")
    desc.append(phase, style=_graph_status_style(phase))
    if title:
        desc.append(f" · {title}")
    return desc


def _node_menu_phase(
    graph_status: str,
    queue_state: str = "-",
    job_status: str = "-",
) -> str:
    """Picker label: waiting-for-review wins over bare graph ready.

    Graph complete/deferred stays graph truth. Active runtime phases
    (awaiting review, running, …) override a still-open graph status so the
    operator can tell human-review work from dispatchable ready.
    """
    graph = (graph_status or "").strip()
    if graph.upper().startswith("DESYNC"):
        return graph
    g = graph.lower()
    if g in {"complete", "deferred"}:
        return g
    runtime = queue_state if queue_state not in (None, "", "-") else job_status
    runtime = str(runtime or "-").strip().lower()
    if runtime == "awaiting_review":
        return "awaiting review"
    if runtime == "awaiting_result":
        return "awaiting result"
    if runtime == "running":
        return "running"
    if runtime == "ready":
        return "queued"
    if runtime == "failed":
        return "failed"
    return graph or "?"


def _pause(message: str = "press any key to continue") -> str:
    """Keep command output visible until the operator is ready to redraw."""
    console.print(Text(message, style="dim"))
    choice = _import_module("terminal").getch()
    if choice == "\x03":
        raise KeyboardInterrupt
    return choice.lower()


def _plain_desc(description: str | Text) -> str:
    """Strip Rich markup for fzf labels."""
    if isinstance(description, Text):
        return description.plain
    return str(description) if description is not None else ""


_RICH_TO_ANSI = {
    "bold green": "\033[1;32m",
    "bold yellow": "\033[1;33m",
    "bold cyan": "\033[1;36m",
    "bold blue": "\033[1;34m",
    "bold magenta": "\033[1;35m",
    "bold red": "\033[1;31m",
    "bold white": "\033[1;37m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "dim": "\033[2m",
}


def _ansi(text: str, style: str, width: int = 0) -> str:
    """Fixed-width ANSI span for fzf ``--ansi`` labels."""
    body = f"{text:<{width}}" if width else text
    return f"{_RICH_TO_ANSI.get(style, '')}{body}\033[0m"


def _split_list_desc(plain: str) -> tuple[str, str, str]:
    """chip, phase, rest — from ``PASS · ready · title`` or ``ready · title``."""
    if " · " not in plain:
        return "", "", plain
    parts = [p.strip() for p in plain.split(" · ", 2)]
    if parts[0] in {"PASS", "FAIL"}:
        return (
            parts[0],
            parts[1] if len(parts) > 1 else "",
            parts[2] if len(parts) > 2 else "",
        )
    return "", parts[0], parts[1] if len(parts) > 1 else ""


def _project_preview_cmd() -> str:
    """fzf preview: 4-line project card ({1} = project id).

    fzf shell-escapes placeholders (``{1}`` → ``'aa-cli'``). Never put
    ``{1}`` *inside* double quotes or the quotes become path characters:
    ``".../{1}/..."`` → ``".../'aa-cli'/..."`` → file not found.
    """
    return f"{sys.executable} {SCRIPTS_DIR}/fzf_preview.py project {ROOT} {{1}}"


def _node_preview_cmd(project: str) -> str:
    """fzf preview: title/status/why card ({1} = node id)."""
    return (
        f"{sys.executable} {SCRIPTS_DIR}/fzf_preview.py "
        f"node {ROOT} {project} {{1}}"
    )


def _job_preview_cmd() -> str:
    """fzf preview: runtime jobs show ({1} = job_id).

    ``{1}`` is a bare argv token so fzf's own quoting is correct.
    """
    try:
        runtime_root = resolve_runtime_root()
        py = runtime_python(runtime_root)
        script = runtime_root / "scripts" / "jobs_status.py"
        return (
            f'GDDP_RUNTIME_ROOT={runtime_root} {py} {script} show {{1}} '
            f'2>/dev/null | head -n 8 || echo "(job show failed)"'
        )
    except RuntimeError as exc:
        return f'echo "runtime unavailable: {exc}"'


def _fzf_items(
    items: list[tuple[str, str | Text]],
) -> list[tuple[str, str]]:
    """(value, ANSI label) — status column first so rows scan as columns."""
    out: list[tuple[str, str]] = []
    for value, description in items:
        lab = _plain_desc(description).strip()
        if not lab or lab == value:
            out.append((value, value))
            continue
        chip, phase, rest = _split_list_desc(lab)
        if phase:
            bits = []
            if chip:
                bits.append(_ansi(chip, _graph_status_style(chip), 4))
            bits.append(_ansi(phase, _graph_status_style(phase), 16))
            bits.append(str(value))
            if rest:
                bits.append(rest)
            out.append((value, "  ".join(bits)))
            continue
        out.append((value, f"{value}  {lab}"))
    return out


def _run_fzf(
    heading: str,
    items: list[tuple[str, str | Text]],
    *,
    preview_cmd: str | None = None,
    multi: bool = False,
) -> list[str] | None:
    """Step into fzf; return selected values or None (cancel / unavailable)."""
    fzf = _import_module("fzf_pick")
    if not fzf.available():
        console.print(
            Text("fzf not installed (brew install fzf)", style="yellow")
        )
        return None
    header = "tab multi · enter · esc" if multi else "enter · esc"
    return fzf.pick(
        _fzf_items(items),
        prompt=f"{heading}> ",
        header=header,
        preview_cmd=preview_cmd,
        multi=multi,
    )


def _pick_list(
    heading: str,
    items: list[tuple[str, str | Text]],
    *,
    preview_cmd: str | None = None,
    multi: bool = False,
    back_label: str = "back",
    fzf_header: str | None = None,
):
    """Rich paged list by default. Optional fzf via ``f``.

    multi=False → value | _MENU_BACK | _MENU_QUIT
    multi=True  → value | list[str] | _MENU_BACK | _MENU_QUIT
      (list when space/m has checked 2+ rows and Enter is pressed)
    """
    del fzf_header  # callers used to pass verbose fzf chrome; paged owns help now
    return _paged_menu(
        heading,
        items,
        back_label=back_label,
        fzf_preview_cmd=preview_cmd,
        fzf_multi=multi,
    )


def _batch_node_status(project: str, node_ids: list[str]):
    """One target status + shared reason → dual-write each selected node."""
    node_cli = _import_module("node_cli")
    _clear_screen()
    console.print(Text(f"batch status · {project}", style="bold"))
    console.print(Text(f"{len(node_ids)} node(s):", style="dim"))
    for nid in node_ids:
        console.print(f"  {nid}")
    console.print()

    status_items = [(s, s) for s in node_cli.GRAPH_STATUSES]
    status = _pick_list(
        "target status",
        status_items,
        multi=False,
        back_label="nodes",
    )
    if status in {_MENU_BACK, _MENU_QUIT}:
        return status

    try:
        reason = Prompt.ask(Text("shared reason", style="cyan")).strip()
    except EOFError:
        console.print(Text("Unchanged — reason required.", style="dim"))
        return _MENU_BACK
    if not reason:
        console.print(Text("Unchanged — need a short reason.", style="yellow"))
        return _MENU_BACK

    if status == "complete":
        console.print(
            Text(
                "Note: batch complete skips per-node acceptance merge prompts. "
                "Merge attempt branches yourself if needed.",
                style="yellow",
            )
        )

    actions = {
        "y": ("yes", f"set {len(node_ids)} node(s) → {status}"),
        "n": ("no", "leave graph truth unchanged"),
    }
    _print_action_menu(actions)
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return _MENU_BACK

    ok = 0
    failed = 0
    for node_id in node_ids:
        console.rule(f"{project} / {node_id}", style="dim")
        rc = node_cli.cmd_set_status(
            project=project,
            node_id=node_id,
            status=status,
            yes=True,
            reason=reason,
        )
        if rc == 0:
            ok += 1
        else:
            failed += 1
    console.print(
        Text(f"batch done — ok={ok} failed={failed}", style="bold green" if failed == 0 else "bold yellow")
    )
    # Offer publish once if any dual-write left dirty graph paths.
    dirty: list[str] = []
    for node_id in node_ids:
        dirty.extend(_dirty_graph_status_paths(project, node_id))
    dirty = sorted(set(dirty))
    if dirty and ok:
        # Reuse single-node publish on the first id; paths cover the batch.
        _offer_publish_graph_status(project, node_ids[0], status, reason)
    _pause()
    return _MENU_BACK


def _runtime_job_items(state_filter: str | None = None) -> list[tuple[str, str]]:
    """(job_id, scan label) from the runtime queue DB."""
    jobs_status = load_runtime_jobs_module()
    con = jobs_status.connect()
    try:
        q = (
            "SELECT job_id, node_id, queue_state, created_at FROM jobs"
        )
        params: tuple = ()
        if state_filter:
            q += " WHERE queue_state = ?"
            params = (state_filter,)
        q += " ORDER BY created_at DESC"
        rows = con.execute(q, params).fetchall()
        items: list[tuple[str, str]] = []
        for r in rows:
            created = str(r["created_at"] or "")[:10]
            state = str(r["queue_state"] or "?")
            node = str(r["node_id"] or "")
            items.append((str(r["job_id"]), f"{state}  {node}  {created}"))
        return items
    finally:
        con.close()


def _batch_job_state(job_ids: list[str], states: list[tuple[str, str | Text]]):
    """Set the same queue state on multiple runtime jobs with one reason."""
    _clear_screen()
    console.print(Text(f"batch job update · {len(job_ids)} job(s)", style="bold"))
    for jid in job_ids:
        console.print(f"  {jid}")
    state = _pick_list("job state", states, multi=False, back_label="jobs")
    if state in {_MENU_BACK, _MENU_QUIT}:
        return state
    try:
        reason = Prompt.ask(Text("shared reason", style="cyan")).strip()
    except EOFError:
        console.print(Text("Unchanged — reason required.", style="dim"))
        return _MENU_BACK
    if not reason:
        console.print(Text("Unchanged — need a short reason.", style="yellow"))
        return _MENU_BACK
    actions = {
        "y": ("yes", f"set {len(job_ids)} job(s) → {state}"),
        "n": ("no", "leave runtime jobs unchanged"),
    }
    _print_action_menu(actions)
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return _MENU_BACK
    ok = failed = 0
    for jid in job_ids:
        console.rule(jid, style="dim")
        rc = run_runtime_jobs(["set", jid, state, "--reason", reason, "--yes"])
        if rc == 0:
            ok += 1
        else:
            failed += 1
    console.print(
        Text(
            f"batch jobs done — ok={ok} failed={failed}",
            style="bold green" if failed == 0 else "bold yellow",
        )
    )
    _pause()
    return _MENU_BACK


# Named keys from terminal.getch — keep display short and match actions exactly.
_NAMED_KEY_LABELS = {
    "LEFT": "←",
    "RIGHT": "→",
    "UP": "↑",
    "DOWN": "↓",
    "HOME": "Home",
    "END": "End",
}


def _key_label(key: str) -> str:
    """Human-facing key glyph for menus and echoed choices."""
    return _NAMED_KEY_LABELS.get(key, key)


def _print_action_menu(actions: dict[str, tuple[str, str | Text]]) -> None:
    """Static action list (no cursor). Prefer ``_menu_choice`` for interactive pick."""
    for key, (name, description) in actions.items():
        row = Text()
        row.append(f"  {_key_label(key):<6}", style="bold cyan")
        row.append(f"{name:<16}", style="bold")
        if isinstance(description, Text):
            row.append_text(description)
        elif description:
            row.append(str(description), style="dim")
        console.print(row)


def _menu_choice(
    actions: dict[str, tuple[str, str | Text]],
    default: str,
    *,
    echo: bool = True,
) -> str:
    """Cursor action menu: ↑/↓ + Enter, letter shortcuts, optional 1–9.

    Cursor starts on ``default`` (top when default is the first item — main
    menu). Letter keys still jump. Named action keys (``LEFT``/``RIGHT``) still
    select when registered. Escape: ``b`` → ``q`` → default. Ctrl-C quits.

    ``echo`` is accepted for call-site compatibility; the cursor UI paints the
    selection in place, so nothing extra is printed on success.
    """
    del echo  # API compat; cursor paint replaces the old single-key echo.
    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = getattr(terminal, "clear_lines", lambda _n: None)

    selectables = [(key, name, desc) for key, (name, desc) in actions.items()]
    if not selectables:
        raise ValueError("menu has no actions")
    by_key = {key: i for i, (key, _, _) in enumerate(selectables)}
    cursor = by_key.get(default, 0)
    drawn = 0
    first_paint = True

    while True:
        lines: list[Text] = []
        for offset, (key, name, description) in enumerate(selectables):
            marker = "›" if offset == cursor else " "
            row = Text()
            row.append(f"{marker} {_key_label(key):<6}", style="bold cyan")
            row.append(f"{name:<16}", style="bold")
            if isinstance(description, Text):
                row.append_text(description)
            elif description:
                row.append(str(description), style="dim")
            lines.append(row)
        lines.append(
            Text(
                "  ↑/↓ move · enter open · letters jump · 1-9 pick · esc back",
                style="dim",
            )
        )

        if first_paint:
            first_paint = False
        else:
            clear_lines(drawn)
        for line in lines:
            console.print(line)
        drawn = len(lines)

        choice = getch()
        if choice == "\x03":
            raise KeyboardInterrupt
        if not choice:
            continue
        if choice == "\x1b":
            if "b" in by_key:
                return "b"
            if "q" in by_key:
                return "q"
            return default
        if choice in {"\r", "\n"}:
            return selectables[cursor][0]
        if choice == "UP":
            cursor = (cursor - 1) % len(selectables)
            continue
        if choice == "DOWN":
            cursor = (cursor + 1) % len(selectables)
            continue
        if choice == "HOME":
            cursor = 0
            continue
        if choice == "END":
            cursor = len(selectables) - 1
            continue
        # Registered named keys (e.g. LEFT/RIGHT sibling actions).
        if len(choice) > 1:
            if choice in by_key:
                return choice
            continue
        if choice.isdigit() and choice != "0":
            idx = int(choice) - 1
            if 0 <= idx < len(selectables):
                return selectables[idx][0]
            continue
        key = choice.lower()
        if key in by_key:
            return key
        console.print(Text(f"{key!r} is not an option", style="yellow"))
        drawn += 1


def _format_list_description(description: str | Text, room: int) -> Text:
    """One-line description: color status · title; truncate to keep redraw stable."""
    if isinstance(description, Text):
        plain = description.plain
        if len(plain) > room:
            plain = plain[: max(1, room - 1)] + "…"
            if " · " in plain:
                status, rest = plain.split(" · ", 1)
                out = Text()
                out.append(status, style=_graph_status_style(status))
                out.append(f" · {rest}")
                return out
            return Text(plain)
        return description.copy()

    plain = str(description)
    if len(plain) > room:
        plain = plain[: max(1, room - 1)] + "…"
    if " · " in plain:
        status, rest = plain.split(" · ", 1)
        out = Text()
        out.append(status, style=_graph_status_style(status))
        out.append(f" · {rest}")
        return out
    return Text(plain)


def _checked_values(
    items: list[tuple[str, str | Text]],
    checked: set[str],
):
    """Checked ids in list order. One id stays a scalar (opens that item)."""
    ordered = [value for value, _ in items if value in checked]
    if not ordered:
        return None
    return ordered if len(ordered) > 1 else ordered[0]


def _paged_menu(
    heading: str,
    items: list[tuple[str, str | Text]],
    *,
    page_size: int = 9,
    back_label: str = "back",
    fzf_preview_cmd: str | None = None,
    fzf_multi: bool = False,
):
    """Rich cursor list: ↑/↓, Enter, numbers; ←/→ page.

    Optional fzf step-in (does not replace this path):
      ``f`` / Ctrl-F  — fuzzy filter + preview (single)

    When ``fzf_multi`` is set, space / ``m`` toggles a checkbox on the
    current row. Enter with 2+ checked returns that list (batch);
    Enter with 0–1 checked opens that one item.

    Static list content is redrawn in place (clear-to-end), not via a full
    terminal clear on every arrow key.
    """
    if not items:
        _clear_screen()
        console.print(Text("No items found.", style="yellow"))
        _pause()
        return _MENU_BACK

    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = terminal.clear_lines
    try:
        fzf_ok = bool(_import_module("fzf_pick").available())
    except Exception:
        fzf_ok = False
    page = 0
    cursor = 0
    drawn = 0
    first_paint = True
    checked: set[str] = set()

    while True:
        page_count = (len(items) + page_size - 1) // page_size
        page = page % page_count
        start = page * page_size
        visible = items[start:start + page_size]
        cursor = min(cursor, len(visible) - 1)

        # One logical line per row so clear_lines stays accurate; truncate.
        width = console.width or 80
        title = Text(heading, style="bold")
        if page_count > 1:
            title.append(f"  ·  {page + 1}/{page_count}", style="dim")
        if fzf_multi:
            n = len(checked)
            title.append(
                f"  ·  {n} selected",
                style="green" if n else "dim",
            )
        lines: list[Text] = [title]
        for offset, (value, description) in enumerate(visible, start=1):
            marker = "›" if offset - 1 == cursor else " "
            row = Text()
            row.append(f"{marker} {offset}", style="bold cyan")
            if fzf_multi:
                on = value in checked
                row.append(" ✓" if on else "  ", style="green" if on else "dim")
            row.append(f"  {value}", style="bold")
            used = 4 + len(str(offset)) + (2 if fzf_multi else 0) + 2 + len(value) + 2
            room = max(12, width - used)
            row.append("  ")
            row.append_text(_format_list_description(description, room))
            lines.append(row)

        # One help line — no stacked chrome.
        help_bits = ["↑/↓"]
        if fzf_multi:
            help_bits.append("space")
        help_bits.extend(["enter", "1-9"])
        if page_count > 1:
            help_bits.append("←/→ page")
        if fzf_ok:
            help_bits.append("f filter")
        help_bits.extend([f"b {back_label}", "q quit"])
        lines.append(Text("  " + " · ".join(help_bits), style="dim"))

        if first_paint:
            _clear_screen()
            first_paint = False
        else:
            clear_lines(drawn)

        for line in lines:
            console.print(line, overflow="crop", crop=True, no_wrap=True)
        drawn = len(lines)

        # Read keys here so navigation does not echo "up"/"down" or full-clear.
        while True:
            choice = getch()
            if choice == "\x03":
                raise KeyboardInterrupt
            if not choice:
                continue
            if choice == "\x1b":
                choice = "b"
            if choice in {"\r", "\n"}:
                if fzf_multi:
                    picked = _checked_values(items, checked)
                    if picked is not None:
                        return picked
                return visible[cursor][0]
            if fzf_multi and choice in {" ", "\t", "m", "M"}:
                value = visible[cursor][0]
                if value in checked:
                    checked.discard(value)
                else:
                    checked.add(value)
                break
            if choice == "UP":
                cursor = (cursor - 1) % len(visible)
                break
            if choice == "DOWN":
                cursor = (cursor + 1) % len(visible)
                break
            if choice in {"LEFT", "p", "P"} and page_count > 1:
                page = (page - 1) % page_count
                cursor = 0
                break
            if choice in {"RIGHT", "n", "N"} and page_count > 1:
                page = (page + 1) % page_count
                cursor = 0
                break
            # f / Ctrl-F — opt-in fzf (single). Cancel returns to this menu.
            if choice in {"f", "F", "\x06"} and fzf_ok:
                selected = _run_fzf(
                    heading,
                    items,
                    preview_cmd=fzf_preview_cmd,
                    multi=False,
                )
                if selected:
                    return selected[0]
                first_paint = True  # fzf wrecked the screen; full redraw
                break
            if choice in {"f", "F", "\x06"} and not fzf_ok:
                console.print(
                    Text("  fzf not installed (brew install fzf)", style="yellow")
                )
                drawn += 1
                continue
            if choice in {"b", "B"}:
                return _MENU_BACK
            if choice in {"q", "Q"}:
                return _MENU_QUIT
            if choice.isdigit() and choice != "0":
                idx = int(choice) - 1
                if 0 <= idx < len(visible):
                    return visible[idx][0]
            # invalid key: stay put, no redraw needed


def _confirm_status_change(project: str, node_id: str, status: str) -> int:
    """Confirm with one key, collect a real reason, then dual-write + history."""
    node_cli = _import_module("node_cli")
    _clear_screen()
    console.rule(f"{project} / {node_id}", style="dim")
    actions = {
        "y": ("yes", f"set {node_id} to {status}"),
        "n": ("no", "leave graph truth unchanged"),
    }
    console.print(
        f"Set [bold]{project}/{node_id}[/bold] graph status to "
        f"[bold cyan]{status}[/bold cyan]?"
    )
    choice = _menu_choice(actions, default="n")
    if choice != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    try:
        reason = Prompt.ask(
            Text("reason", style="cyan"),
        ).strip()
    except EOFError:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not reason:
        console.print(Text("Unchanged — need a short reason for the history trail.", style="yellow"))
        return 1
    if status == "complete" and not _offer_acceptance_merge(project, node_id):
        console.print(
            Text(
                "Status not updated — result commit still off mainline "
                "(merge it, or choose skip on the merge prompt).",
                style="bold yellow",
            )
        )
        return 1
    rc = node_cli.cmd_set_status(
        project=project,
        node_id=node_id,
        status=status,
        yes=True,
        reason=reason,
    )
    if rc == 0:
        _offer_publish_graph_status(project, node_id, status, reason)
    return rc


def _config_git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run git in the gddp-config checkout (graph truth lives here)."""
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _graph_status_relpaths(project: str, node_id: str) -> list[str]:
    """Paths dual-written by set-status, relative to config ROOT."""
    return [
        f"graphs/{project}/nodes/{node_id}.yaml",
        f"graphs/{project}/project.yaml",
    ]


def _dirty_graph_status_paths(project: str, node_id: str) -> list[str]:
    """Which dual-write paths currently differ from HEAD."""
    rels = _graph_status_relpaths(project, node_id)
    proc = _config_git("status", "--porcelain", "--", *rels)
    if proc.returncode != 0:
        return []
    dirty: list[str] = []
    for line in proc.stdout.splitlines():
        # porcelain: XY PATH or XY ORIG -> PATH
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path in rels:
            dirty.append(path)
    return dirty


def _offer_publish_graph_status(
    project: str, node_id: str, status: str, reason: str
) -> None:
    """After graph YAML is written: commit/push it, or leave dirty on purpose.

    Status writes without a publish step is what leaves gddp-config full of
    modified node files. This is the real confirmation — not another scold.
    """
    dirty = _dirty_graph_status_paths(project, node_id)
    if not dirty:
        return

    console.print()
    console.print(Text("Graph YAML written — still only local until published:", style="bold"))
    for path in dirty:
        console.print(f"  {path}")
    diff = _config_git("diff", "--stat", "--", *dirty)
    if diff.stdout.strip():
        console.print(Text(diff.stdout.rstrip(), style="dim"))

    actions = {
        "p": ("commit + push", "add these files, commit, push to origin"),
        "c": ("commit only", "add + commit; you push later"),
        "s": ("skip", "leave the working tree dirty"),
    }
    choice = _menu_choice(actions, default="p")
    if choice == "s":
        console.print(Text(
            "Left dirty — remember to commit graphs/ when you're ready.",
            style="yellow",
        ))
        return

    add = _config_git("add", "--", *dirty)
    if add.returncode != 0:
        console.print(Text(
            f"git add failed:\n{(add.stderr or add.stdout).strip()}",
            style="bold red",
        ))
        return

    msg = (
        f"graph({project}): {node_id} → {status}\n\n"
        f"{reason.strip()}\n"
    )
    commit = _config_git("commit", "-m", msg)
    if commit.returncode != 0:
        console.print(Text(
            f"git commit failed:\n{(commit.stderr or commit.stdout).strip()}",
            style="bold red",
        ))
        return
    sha = _config_git("rev-parse", "--short", "HEAD").stdout.strip()
    console.print(Text(f"committed {sha} — {', '.join(dirty)}", style="green"))

    if choice != "p":
        console.print(Text("Not pushed (commit only).", style="dim"))
        return

    push = _config_git("push", timeout=120)
    if push.returncode != 0:
        console.print(Text(
            f"git push failed:\n{(push.stderr or push.stdout).strip()}",
            style="bold red",
        ))
        console.print(Text("Commit is local; push when the remote is ready.", style="yellow"))
        return
    branch = _config_git("branch", "--show-current").stdout.strip() or "HEAD"
    console.print(Text(f"pushed {sha} → origin/{branch}", style="bold green"))


def _latest_receipt(project: str, node_id: str) -> dict | None:
    """Newest receipt for the node (pipeline or manual), or None."""
    rdir = ROOT / "verification" / project / node_id
    if not rdir.is_dir():
        return None
    best: dict | None = None
    for path in sorted(rdir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            data["_receipt_path"] = str(path)
            best = data
    return best


def _resolve_project_repo(project: str, repo_path: str | None = None) -> Path | None:
    """Same candidate chain as verify node: flag, env root, sibling checkout."""
    import yaml

    repo_name = ""
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    if project_yaml.is_file():
        with open(project_yaml) as f:
            repo_name = str((yaml.safe_load(f) or {}).get("repo", "")).split("/")[-1]
    candidates: list[Path] = []
    if repo_path:
        candidates.append(Path(repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None


def _default_branch(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show-ref", "--verify", "refs/heads/main"],
        capture_output=True, timeout=30, check=False,
    )
    if proc.returncode == 0:
        return "main"
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return proc.stdout.strip() or "HEAD"


def _acceptance_merge_state(repo: Path, sha: str) -> str:
    """merged | pending | unavailable — is the result commit in the mainline?"""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=30, check=False,
        )

    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return "unavailable"
    if git("merge-base", "--is-ancestor", sha, _default_branch(repo)).returncode == 0:
        return "merged"
    return "pending"


def _render_evaluation_and_diff(
    project: str, node_id: str, repo_path: str | None = None, full: bool = False
) -> None:
    """Latest verdict + what the attempt actually changed + merge state."""
    receipt = _latest_receipt(project, node_id)
    if not receipt:
        console.print(Text("no receipts under verification/ — nothing evaluated yet", style="dim"))
        return
    console.print(Text(f"latest receipt: {receipt['_receipt_path']}", style="dim"))
    verdict = receipt.get("verdict")
    line = Text("verdict: ")
    line.append(str(verdict), style=_graph_status_style(str(verdict or "")))
    line.append(
        f"  criteria: {receipt.get('criteria_verdict')}  "
        f"confidence: {receipt.get('confidence')}  "
        f"generated: {receipt.get('generated_at')}"
    )
    console.print(line)
    subject_diff = (receipt.get("deterministic") or {}).get("subject_diff") or {}
    if subject_diff.get("status") == "ok":
        console.print(Text(
            f"subject diff {subject_diff['base'][:8]}..{subject_diff['tip'][:8]} "
            f"— {subject_diff.get('file_count')} file(s):",
            style="bold",
        ))
        for entry in subject_diff.get("files", []):
            console.print(f"  {entry['status']}  {entry['path']}")
        if subject_diff.get("truncated"):
            console.print("  … (truncated)")
    tip = receipt.get("merge_commit_sha") or receipt.get("evaluated_commit_sha")
    repo = _resolve_project_repo(project, repo_path)
    if not tip or repo is None:
        return
    state = _acceptance_merge_state(repo, tip)
    branch = _default_branch(repo)
    style = {"merged": "green", "pending": "yellow", "unavailable": "dim"}[state]
    console.print(Text(f"merge state: {state} ({repo.name} {branch})", style=style))
    if state == "merged":
        return
    base = receipt.get("expected_base_commit_sha") or branch
    diff_args = ["git", "-C", str(repo), "diff"]
    if not full:
        diff_args.append("--stat")
    diff_args.append(f"{base}..{tip}")
    proc = subprocess.run(diff_args, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        print(proc.stdout.rstrip())
    else:
        console.print(Text(f"(diff unavailable: {proc.stderr.strip()[:200]})", style="dim"))


def _offer_acceptance_merge(project: str, node_id: str) -> bool:
    """Merge the accepted result commit into the project repo's mainline.

    False only when the human aborts (``n``) or git merge fails.
    True when already merged, nothing to merge, unavailable tip (manual
    later), or the human explicitly skips the merge and still wants graph
    status advanced.
    """
    receipt = _latest_receipt(project, node_id) or {}
    tip = receipt.get("merge_commit_sha") or receipt.get("evaluated_commit_sha")
    repo = _resolve_project_repo(project)
    if not tip or repo is None:
        return True
    state = _acceptance_merge_state(repo, tip)
    if state == "merged":
        return True
    branch = _default_branch(repo)
    if state == "unavailable":
        console.print(Text(
            f"result commit {tip[:12]} not in {repo} — "
            "graph can still complete; merge the attempt branch yourself later",
            style="yellow",
        ))
        return True
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", f"{branch}..{tip}"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    console.print()
    console.print(Text(
        f"Result commit not on {repo.name} {branch} yet — "
        f"{tip[:12]} still on the attempt branch:",
        style="bold yellow",
    ))
    print(log.stdout.strip() or "(no log output)")
    console.print(
        Text("This is the last step before graph status updates.", style="dim")
    )
    actions = {
        "y": ("merge", f"ff/merge {tip[:12]} into {branch}, then set complete"),
        "s": ("skip merge", "set graph complete anyway (repo left as-is)"),
        "n": ("abort", "leave repo and graph unchanged"),
    }
    # Cursor starts on default ``y``; letters still jump. No silent Enter-abort.
    choice = _menu_choice(actions, default="y")
    if choice == "n":
        console.print(Text("Aborted — graph status not changed.", style="yellow"))
        return False
    if choice == "s":
        console.print(Text(
            f"Skipping merge — {tip[:12]} stays off {branch}; graph will still update.",
            style="yellow",
        ))
        return True
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge", "--ff-only", tip],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "-C", str(repo), "merge", "--no-ff", tip,
             "-m", f"accept({node_id}): human-approved result {tip[:12]}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if proc.returncode != 0:
            console.print(Text(f"merge failed:\n{proc.stderr.strip()}", style="bold red"))
            console.print(Text(
                "Graph status not updated. Fix the repo, then retry complete.",
                style="yellow",
            ))
            return False
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, timeout=30, check=False,
    ).stdout.strip()
    console.print(Text(f"merged — {repo.name} {branch} now at {head}", style="green"))
    return True


def cmd_review(args) -> int:
    """Human-gate review surface: node summary, latest verdict, diff, merge state."""
    node_cli = _import_module("node_cli")
    node_cli.cmd_show(project=args.project, node_id=args.node, trace=False, view="summary")
    _render_evaluation_and_diff(args.project, args.node, repo_path=args.repo_path, full=args.full)
    return 0


def _node_review_pick_action(
    *,
    has_siblings: bool,
    default_key: str = "e",
) -> str:
    """Pick a node-review action with split arrow roles.

    ↑/↓ move the action cursor (Enter activates). ←/→ mean previous/next
    sibling when the project has more than one node. Letter keys still work
    as direct shortcuts. Escape maps to back.
    """
    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = getattr(terminal, "clear_lines", lambda _n: None)

    # Cursor targets only — horizontal sibling nav is separate chrome.
    selectables: list[tuple[str, str, str]] = [
        ("e", "evaluation", "current-job evidence and any stale receipts"),
        ("c", "contract", "intent, dependencies, and acceptance criteria"),
        ("u", "update", "change graph status"),
        ("t", "trace", "full evaluator and job history"),
        ("d", "diff", "what the attempt actually changed + merge state"),
        ("b", "back", "choose another node"),
        ("p", "projects", "choose another project"),
        ("q", "quit", ""),
    ]
    by_key = {key: i for i, (key, _, _) in enumerate(selectables)}
    cursor = by_key.get(default_key, 0)
    drawn = 0
    first_paint = True

    while True:
        lines: list[Text] = []
        if has_siblings:
            for key, name, description in (
                ("LEFT", "prev", "previous node"),
                ("RIGHT", "next", "next node"),
            ):
                row = Text()
                row.append(f"  {_key_label(key):<8}", style="bold cyan")
                row.append(f"{name:<12}", style="bold")
                row.append(description, style="dim")
                lines.append(row)
        for offset, (key, name, description) in enumerate(selectables):
            marker = "›" if offset == cursor else " "
            row = Text()
            row.append(f"{marker} {key:<6}", style="bold cyan")
            row.append(f"{name:<12}", style="bold")
            row.append(description, style="dim")
            lines.append(row)
        help_bits = ["↑/↓ move", "enter open"]
        if has_siblings:
            help_bits.insert(0, "←/→ node")
        help_bits.extend(["letters jump", "esc back"])
        help_line = Text("  " + " · ".join(help_bits), style="dim")
        lines.append(help_line)

        if first_paint:
            first_paint = False
        else:
            clear_lines(drawn)
        for line in lines:
            console.print(line)
        drawn = len(lines)

        choice = getch()
        if choice == "\x03":
            raise KeyboardInterrupt
        if not choice:
            continue
        if choice == "\x1b":
            return "b"
        if choice in {"\r", "\n"}:
            return selectables[cursor][0]
        if choice == "UP":
            cursor = (cursor - 1) % len(selectables)
            continue
        if choice == "DOWN":
            cursor = (cursor + 1) % len(selectables)
            continue
        if choice == "LEFT" and has_siblings:
            return "LEFT"
        if choice == "RIGHT" and has_siblings:
            return "RIGHT"
        # Ignore vertical/horizontal arrows that don't apply (no scolding).
        if choice in {"LEFT", "RIGHT", "UP", "DOWN", "HOME", "END"}:
            continue
        if len(choice) == 1:
            key = choice.lower()
            if key in by_key:
                return key
            console.print(Text(f"{key!r} is not an option", style="yellow"))
            drawn += 1
            continue
        # Unknown multi-char: ignore.
        continue


def _node_review_menu(
    project: str,
    node_id: str,
    node_ids: list[str] | None = None,
):
    """Review one node and optionally update its human-owned graph status.

    When ``node_ids`` is the project's ordered list:
      ←/→  previous / next sibling node
      ↑/↓  move action cursor; Enter opens the highlighted action
    Letter keys remain direct shortcuts.
    """
    node_cli = _import_module("node_cli")
    siblings = list(node_ids) if node_ids else []
    if node_id not in siblings:
        siblings = [node_id, *[s for s in siblings if s != node_id]]

    while True:
        _clear_screen()
        position = ""
        if len(siblings) > 1:
            position = f" · {siblings.index(node_id) + 1}/{len(siblings)}"
        chip = ""
        try:
            ev = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
            chip = _verdict_chip(getattr(ev, "verdict", None))
        except Exception:
            chip = ""
        rule = f"{project} / {node_id}{position}"
        if chip:
            rule = f"{rule} · {chip}"
        rule_style = "bold green" if chip == "PASS" else (
            "bold red" if chip == "FAIL" else "dim"
        )
        console.rule(rule, style=rule_style)
        node_cli.cmd_show(
            project=project,
            node_id=node_id,
            trace=False,
            view="summary",
        )
        choice = _node_review_pick_action(has_siblings=len(siblings) > 1)
        if choice == "LEFT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx - 1) % len(siblings)]
            continue
        if choice == "RIGHT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx + 1) % len(siblings)]
            continue
        if choice == "q":
            return _MENU_QUIT
        if choice == "p":
            return "projects"
        if choice == "b":
            return _MENU_BACK
        if choice == "e":
            _clear_screen()
            node_cli.cmd_show(
                project=project,
                node_id=node_id,
                trace=False,
                view="evaluation",
            )
            if _pause("u update · any other key returns to the node") != "u":
                continue
        if choice == "c":
            _clear_screen()
            node_cli.cmd_show(
                project=project,
                node_id=node_id,
                trace=False,
                view="contract",
            )
            if _pause("u update · any other key returns to the node") != "u":
                continue
        if choice == "t":
            _clear_screen()
            node_cli.cmd_show(
                project=project,
                node_id=node_id,
                trace=True,
                view="evaluation",
            )
            if _pause("u update · any other key returns to the node") != "u":
                continue
        if choice == "d":
            _clear_screen()
            _render_evaluation_and_diff(project, node_id)
            if _pause("u update · any other key returns to the node") != "u":
                continue

        ready, gate_reason = node_cli.node_completion_readiness(project, node_id)
        complete_hint = (
            "evaluator passed — your call"
            if ready
            else gate_reason
        )
        complete_desc: str | Text = (
            Text(complete_hint, style="bold green")
            if ready
            else Text(complete_hint, style="yellow")
        )
        status_actions: dict[str, tuple[str, str | Text]] = {
            "p": ("pending", ""),
            "r": ("ready", ""),
            "c": ("complete", complete_desc),
            "d": ("deferred", ""),
            "b": ("back", ""),
            "q": ("quit", ""),
        }
        _clear_screen()
        status_rule = f"{project} / {node_id}"
        if chip:
            status_rule = f"{status_rule} · {chip}"
        console.rule(
            status_rule,
            style=(
                "bold green" if chip == "PASS"
                else "bold red" if chip == "FAIL"
                else "dim"
            ),
        )
        console.print(Text("graph status", style="bold"))
        status_choice = _menu_choice(status_actions, default="b")
        if status_choice == "q":
            return _MENU_QUIT
        if status_choice == "b":
            continue
        target_status = status_actions[status_choice][0]
        if target_status == "complete":
            if not ready:
                _clear_screen()
                console.print(
                    Text("Not ready to mark complete yet", style="bold yellow")
                )
                console.print(gate_reason)
                console.print()
                node_cli.cmd_show(
                    project=project,
                    node_id=node_id,
                    trace=False,
                    view="evaluation",
                )
                override_actions = {
                    "o": (
                        "override",
                        "accept anyway after you've checked the gaps",
                    ),
                    "b": ("back", "leave graph status unchanged"),
                    "q": ("quit", ""),
                }
                override_choice = _menu_choice(override_actions, default="b")
                if override_choice == "q":
                    return _MENU_QUIT
                if override_choice == "b":
                    continue
        _confirm_status_change(
            project,
            node_id,
            target_status,
        )
        _pause()


def _node_status_label(doc: dict, entry: dict | None) -> str:
    """Show node/index disagreement instead of silently choosing one copy."""
    node_status = str(doc.get("status") or "").strip()
    index_status = str((entry or {}).get("status") or "").strip()
    if node_status and index_status and node_status != index_status:
        return f"DESYNC node={node_status} index={index_status}"
    return node_status or index_status or "?"


def interactive_nodes(project: str | None = None):
    """Project → node → review/update loop for canonical graph truth.

    Default path is the rich paged menu. ``f`` steps into fzf (filter/preview).
    Space / ``m`` checks rows; Enter with 2+ checked opens batch graph-status.
    """
    node_cli = _import_module("node_cli")
    fixed_project = project is not None
    while True:
        if not fixed_project:
            projects = node_cli.list_project_ids(ROOT)
            project_items = []
            for project_id in projects:
                try:
                    count = len(node_cli.iter_nodes(ROOT, project_id))
                    description = f"{count} node{'s' if count != 1 else ''}"
                except Exception as exc:
                    description = f"unavailable: {exc}"
                project_items.append((project_id, description))

            project = _pick_list(
                "projects",
                project_items,
                preview_cmd=_project_preview_cmd(),
                back_label="main menu",
            )
            if project in {_MENU_BACK, _MENU_QUIT}:
                return project

        while True:
            try:
                nodes = node_cli.iter_nodes(ROOT, project)
            except Exception as exc:
                console.print(Text(f"Could not load {project}: {exc}", style="red"))
                if fixed_project:
                    _pause()
                    return _MENU_BACK
                break
            node_items = []
            for node_id, doc, entry in nodes:
                graph_status = _node_status_label(doc, entry)
                queue_state = "-"
                job_status = "-"
                verdict = "-"
                try:
                    ev = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
                    queue_state = getattr(ev, "queue_state", "-") or "-"
                    job_status = getattr(ev, "job_status", "-") or "-"
                    verdict = getattr(ev, "verdict", "-") or "-"
                except Exception:
                    pass
                phase = _node_menu_phase(graph_status, queue_state, job_status)
                title = str(doc.get("title") or (entry or {}).get("title") or "")
                node_items.append(
                    (node_id, _node_row_description(phase, title, verdict))
                )

            picked = _pick_list(
                f"nodes · {project}",
                node_items,
                preview_cmd=_node_preview_cmd(project),
                multi=True,
                back_label="projects",
            )
            if picked is _MENU_QUIT:
                return _MENU_QUIT
            if picked is _MENU_BACK:
                if fixed_project:
                    return _MENU_BACK
                break
            ordered_ids = [nid for nid, _ in node_items]
            if isinstance(picked, list) and len(picked) > 1:
                outcome = _batch_node_status(project, picked)
            else:
                node_id = picked[0] if isinstance(picked, list) else picked
                outcome = _node_review_menu(project, node_id, node_ids=ordered_ids)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            if outcome == "projects":
                if fixed_project:
                    return _MENU_BACK
                break


def cmd_node_browse(args):
    """Open the interactive node browser, optionally skipping project choice."""
    interactive_nodes(args.project)
    return 0


def cmd_node_new(args):
    new_node = _import_module("new_node")
    sys.exit(new_node.main())


def cmd_node_rapid(args):
    rapid = _import_module("rapid_add")
    sys.exit(rapid.main(
        project=args.project,
        repo=args.repo,
        project_name=args.project_name,
        llm_draft=args.llm_draft,
        dry_run=args.dry_run,
    ))


def cmd_node_batch(args):
    batch = _import_module("batch_fill")
    sys.exit(batch.main(project=args.project))


def cmd_node_import(args):
    import_node = _import_module("import_node")
    sys.exit(import_node.main(
        file_path=args.file,
        use_stdin=args.stdin,
        project=args.project,
        auto_approve=args.auto_approve,
        dry_run=args.dry_run,
        update=args.update,
    ))


def cmd_node_validate(args):
    validate = _import_module("validate")
    root = args.root or ROOT
    findings = validate.run(root, args.project)
    if args.json:
        print(validate.render_json(findings))
    elif args.quiet:
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if args.strict:
            errors += warnings
        print(f"errors={errors} warnings={warnings}")
    else:
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
            files = len({f.path for f in findings})
            print(f"\n{errors} error(s), {warnings} warning(s) across {files} file(s)")
    errors = sum(1 for f in findings if f.severity == "error")
    if args.strict:
        errors += sum(1 for f in findings if f.severity == "warning")
    sys.exit(1 if errors else 0)


def cmd_node_list(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_list(
        project=getattr(args, "project", None),
        status=getattr(args, "status", None),
        active=bool(getattr(args, "active", False)),
    ))


def cmd_node_show(args):
    node_cli = _import_module("node_cli")
    sys.exit(node_cli.cmd_show(
        project=args.project,
        node_id=args.node_id,
        trace=bool(getattr(args, "trace", False)),
        view=getattr(args, "view", "all"),
    ))


def cmd_node_status(args):
    show_status(getattr(args, "project", None))


def resolve_runtime_root() -> Path:
    """Resolve the runtime checkout that owns job and evaluator state."""
    configured = os.environ.get("GDDP_RUNTIME_ROOT")
    runtime_root = Path(configured).expanduser() if configured else ROOT.parent / "gddp-runtime"
    runtime_root = runtime_root.resolve()
    if not (runtime_root / "scripts" / "jobs_status.py").is_file():
        raise RuntimeError(
            f"gddp-runtime not found at {runtime_root}; set GDDP_RUNTIME_ROOT"
        )
    return runtime_root


def runtime_python(runtime_root: Path) -> str:
    """Prefer runtime's interpreter, with an explicit override for deployments."""
    configured = os.environ.get("GDDP_RUNTIME_PYTHON")
    if configured:
        return str(Path(configured).expanduser())
    runtime_venv = runtime_root / ".venv" / "bin" / "python"
    if runtime_venv.is_file() and os.access(runtime_venv, os.X_OK):
        return str(runtime_venv)
    return sys.executable


def run_runtime_jobs(argv: list[str]) -> int:
    """Delegate one jobs invocation through runtime's job-only CLI boundary."""
    if not argv or argv[0] not in _RUNTIME_JOB_COMMANDS:
        print(
            "ERROR: unsupported runtime jobs command.",
            file=sys.stderr,
        )
        return 2
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "jobs_status.py"),
        *argv,
    ]
    env = os.environ.copy()
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def load_runtime_jobs_module():
    """Load the job-only runtime backend used by the interactive menu."""
    runtime_root = resolve_runtime_root()
    path = runtime_root / "scripts" / "jobs_status.py"
    if not path.is_file():
        raise RuntimeError(f"runtime jobs backend not found at {path}")
    spec = importlib.util.spec_from_file_location("gddp_runtime_jobs_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load runtime jobs backend from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _confirm_job_state_change(ref: str, state: str) -> int:
    """Collect explicit menu confirmation and a durable reason, then write."""
    actions = {
        "y": ("yes", f"set {ref} to {state}"),
        "n": ("no", "leave runtime job state unchanged"),
    }
    console.print(
        f"Set [bold]{ref}[/bold] runtime job state to "
        f"[bold cyan]{state}[/bold cyan]?"
    )
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    try:
        reason = Prompt.ask(Text("reason", style="cyan")).strip()
    except EOFError:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not reason:
        console.print(Text("Unchanged — reason required.", style="yellow"))
        return 1
    try:
        jobs_status = load_runtime_jobs_module()
        return jobs_status.apply_state_change(ref=ref, state=state, reason=reason)
    except (RuntimeError, ValueError) as exc:
        console.print(Text(f"ERROR: {exc}", style="red"))
        return 1


def _evaluation_sources() -> tuple[Path | None, Path]:
    receipt_root = ROOT / "verification"
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError:
        return None, receipt_root
    db_path = runtime_root / "db" / "queue.db"
    return (db_path if db_path.is_file() else None), receipt_root


def interactive_evaluations():
    """Browse evaluator receipts as their own evidence stream."""
    evaluations = _import_module("evaluations")
    actions = {
        "r": ("refresh", "reload receipts"),
        "o": ("open", "open one evaluation"),
        "b": ("main menu", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("evaluations", style="bold").append(
            "  ·  evidence only — does not change graph status", style="dim"
        ))
        db_path, receipt_root = _evaluation_sources()
        rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
        if rows:
            for row in rows:
                print(evaluations.format_evaluation_row(row))
            print(f"\n{len(rows)} evaluation(s)")
        else:
            print("No evaluator receipts yet.")
        console.print()
        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "r":
            continue
        if not rows:
            _pause()
            continue
        items = [
            (str(index), evaluations.format_evaluation_row(row))
            for index, row in enumerate(rows)
        ]
        picked = _pick_list(
            "open evaluation",
            items,
            multi=False,
            back_label="evaluations",
        )
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        row = rows[int(picked)]
        _clear_screen()
        console.print(Text("evaluation", style="bold"))
        if row.get("job_id") and row.get("source") == "result":
            run_runtime_jobs(["show", str(row["job_id"])])
        else:
            evaluations.print_evaluation_detail(row)
        _pause()


def cmd_evaluations(_args) -> int:
    """Print the evaluator receipt list for non-interactive use and tests."""
    evaluations = _import_module("evaluations")
    db_path, receipt_root = _evaluation_sources()
    rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
    if not rows:
        print("No evaluator receipts yet.")
        return 0
    for row in rows:
        print(evaluations.format_evaluation_row(row))
    print(f"\n{len(rows)} evaluation(s)")
    return 0


def interactive_jobs():
    """Review and update runtime jobs inside the human-operated menu.

    open/update use the rich paged list; ``f`` filters via fzf, ``m`` multi-
    selects for batch queue-state changes. Empty queue falls back to typing an id.
    """
    state_filter: str | None = None
    actions = {
        "r": ("refresh", "show all runtime jobs"),
        "a": ("awaiting review", "show the human review queue"),
        "e": ("evaluations", "show evaluator result summary"),
        "o": ("open", "pick a job (f = filter)"),
        "u": ("update", "set queue state (space checks)"),
        "b": ("main menu", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        heading = "jobs" if state_filter is None else f"jobs · {state_filter}"
        console.print(Text(heading, style="bold"))
        argv = ["list"]
        if state_filter:
            argv.extend(["--state", state_filter])
        run_runtime_jobs(argv)
        console.print()

        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "r":
            state_filter = None
            continue
        if choice == "a":
            state_filter = "awaiting_review"
            continue
        if choice == "e":
            _clear_screen()
            console.print(Text("evaluator results", style="bold"))
            run_runtime_jobs(["results"])
            _pause()
            continue

        try:
            job_items = _runtime_job_items(state_filter)
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            _pause()
            continue

        if choice == "o":
            if job_items:
                ref = _pick_list(
                    "open job",
                    job_items,
                    preview_cmd=_job_preview_cmd(),
                    multi=False,
                    back_label="jobs",
                )
                if ref is _MENU_QUIT:
                    return _MENU_QUIT
                if ref is _MENU_BACK:
                    continue
            else:
                try:
                    ref = Prompt.ask(Text("job or node ID", style="cyan")).strip()
                except EOFError:
                    continue
                if not ref:
                    continue
            _clear_screen()
            console.print(Text(f"job · {ref}", style="bold"))
            run_runtime_jobs(["show", ref])
            _pause()
            continue

        # update — paged list; space/m checks rows for batch queue state
        if not job_items:
            console.print(Text("No jobs to update.", style="yellow"))
            _pause()
            continue
        selected = _pick_list(
            "update jobs",
            job_items,
            preview_cmd=_job_preview_cmd(),
            multi=True,
            back_label="jobs",
        )
        if selected is _MENU_QUIT:
            return _MENU_QUIT
        if selected is _MENU_BACK:
            continue
        refs = selected if isinstance(selected, list) else [selected]

        try:
            jobs_status = load_runtime_jobs_module()
            states = []
            for state in jobs_status.QUEUE_STATES:
                label = Text(state.replace("_", " "), style=_graph_status_style(state))
                states.append((state, label))
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            _pause()
            continue

        if len(refs) > 1:
            outcome = _batch_job_state(refs, states)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue

        ref = refs[0]
        _clear_screen()
        console.print(Text(f"job · {ref}", style="bold"))
        run_runtime_jobs(["show", ref])
        state = _pick_list("job state", states, multi=False, back_label="jobs")
        if state is _MENU_QUIT:
            return _MENU_QUIT
        if state is _MENU_BACK:
            continue
        _clear_screen()
        console.rule(f"job · {ref}", style="dim")
        _confirm_job_state_change(ref, state)
        _pause()


def cmd_jobs(args):
    argv = []
    command = getattr(args, "jobs_command", None)
    if command:
        argv.append(command)
    if command == "list" and args.state:
        argv.extend(["--state", args.state])
    elif command == "show":
        argv.append(args.ref)
        if args.full:
            argv.append("--full")
    elif command == "results" and args.all:
        argv.append("--all")
    elif command == "set":
        argv.extend([args.ref, args.state, "--reason", args.reason])
        if args.yes:
            argv.append("--yes")
    return run_runtime_jobs(argv)


def static_overview():
    """Render the unified command groups without blocking redirected output."""
    console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=False,
        pad_edge=False,
        padding=(0, 2, 0, 0),
    )
    table.add_column("group", style="bold cyan", no_wrap=True)
    table.add_column("owns")
    table.add_column("start with", style="dim", no_wrap=True)
    table.add_row("node", "graph truth, authoring, runtime/evaluator join", "gddp node list")
    table.add_row("jobs", "runtime queue, results, and audited state changes", "gddp jobs list")
    table.add_row("evaluations", "evaluator receipts, verdicts, and timing", "gddp evaluations")
    table.add_row("verify", "node evaluation", "gddp verify node")
    table.add_row("project", "project graph creation and validation", "gddp project -h")
    table.add_row("obsidian", "graph export", "gddp obsidian export")
    console.print(table)
    console.print(Text("Run `gddp` in a terminal for the menu; use `gddp <group> -h` for commands.", style="dim"))


def interactive_menu():
    """Keep graph control in config while delegating the jobs section to runtime."""
    actions = {
        "n": ("nodes", "review and update graph truth"),
        "j": ("jobs", "review and update runtime jobs"),
        "e": ("evaluations", "evaluator receipts, verdicts, and timing"),
        "d": ("dispatch", "dispatch ready nodes through the event pipeline"),
        "f": ("frontier", "derived operating frontier (read-only)"),
        "s": ("status", "summarize graph completion"),
        "v": ("validate", "validate graph definitions"),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("gddp", style="bold").append("  ·  graph control plane", style="dim"))
        try:
            choice = _menu_choice(actions, default="n")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if choice == "q":
            break
        try:
            if choice == "n":
                outcome = interactive_nodes()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "j":
                outcome = interactive_jobs()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "e":
                outcome = interactive_evaluations()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "d":
                _clear_screen()
                outcome = interactive_dispatch()
                if outcome is _MENU_QUIT:
                    break
                if outcome is _MENU_BACK:
                    continue
                _pause()
            elif choice == "f":
                outcome = interactive_frontier()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "s":
                outcome = interactive_status()
                if outcome is _MENU_QUIT:
                    break
            elif choice == "v":
                outcome = interactive_validate()
                if outcome is _MENU_QUIT:
                    break
        except SystemExit:
            # Existing command handlers use SystemExit; one menu action should
            # return to the control-plane menu instead of closing the CLI.
            pass
            if choice == "v":
                _pause()
        except KeyboardInterrupt:
            break
    _clear_screen()
    console.print(Text("bye.", style="dim"))


# ---------------------------------------------------------------------------
# watch / steer — live observability + operator steering over the pi_rpc spool
# ---------------------------------------------------------------------------
# Read-only over filesystem truth: attempt dirs hold packet.json, pid,
# worktree_path, events.jsonl, result.json. watch never writes; steer appends
# one line to steer.jsonl, which the steer-aware supervisor drains.

def _spool_root(runtime_root: Path) -> Path:
    configured = os.environ.get("GDDP_PI_RPC_SPOOL_DIR") or os.environ.get(
        "GDDP_LOCAL_SUBPROCESS_SPOOL_DIR"
    )
    root = (
        Path(configured).expanduser()
        if configured
        else runtime_root / "jobs" / "local-subprocess-spool"
    )
    return root.resolve()


def _attempt_info(attempt_dir: Path) -> dict | None:
    packet_path = attempt_dir / "packet.json"
    if not packet_path.is_file():
        return None
    try:
        packet = json.loads(packet_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    pid = None
    try:
        pid = int((attempt_dir / "pid").read_text().strip())
    except (OSError, ValueError):
        pass
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            pass
    done = (attempt_dir / "result.json").is_file() or (
        attempt_dir / "exit.json"
    ).is_file()
    worktree = None
    try:
        worktree = (attempt_dir / "worktree_path").read_text().strip() or None
    except OSError:
        pass
    try:
        last_write = (attempt_dir / "events.jsonl").stat().st_mtime
    except OSError:
        last_write = attempt_dir.stat().st_mtime
    state = "running" if alive and not done else ("done" if done else "dead")
    return {
        "dir": attempt_dir,
        "name": attempt_dir.name,
        "job_id": str(packet.get("job_id") or ""),
        "node_id": str(packet.get("node_id") or ""),
        "pid": pid,
        "state": state,
        "worktree": worktree,
        "last_write": last_write,
        "created": attempt_dir.stat().st_ctime,
    }


def _scan_attempts(spool: Path) -> list[dict]:
    if not spool.is_dir():
        return []
    found = []
    for child in sorted(spool.iterdir()):
        if child.is_dir():
            info = _attempt_info(child)
            if info:
                found.append(info)
    order = {"running": 0, "done": 1, "dead": 2}
    found.sort(key=lambda a: (order[a["state"]], -a["created"]))
    return found


def _git(worktree: str, *git_args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", worktree, *git_args],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _diff_summary(worktree: str | None) -> tuple[str, int]:
    """(compact 'Nf +X/-Y', untracked file count) for the attempt worktree."""
    if not worktree or not Path(worktree).is_dir():
        return "-", 0
    shortstat = _git(worktree, "diff", "--shortstat", "HEAD")
    files = re.search(r"(\d+) file", shortstat)
    ins = re.search(r"(\d+) insertion", shortstat)
    dele = re.search(r"(\d+) deletion", shortstat)
    compact = (
        f"{files.group(1) if files else 0}f "
        f"+{ins.group(1) if ins else 0}/-{dele.group(1) if dele else 0}"
    )
    untracked = len(
        _git(worktree, "ls-files", "--others", "--exclude-standard").split()
    )
    return compact, untracked


def _age(ts: float, now: float) -> str:
    seconds = max(0, int(now - ts))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _event_brief(evt: dict) -> str:
    et = evt.get("type") or (evt.get("event") or {}).get("type") or "?"
    detail = ""
    for key in ("name", "command", "path", "tool"):
        value = evt.get(key) or (evt.get("event") or {}).get(key)
        if isinstance(value, str) and value:
            detail = value
            break
    return f"{et} {detail}".strip()[:110]


def _recent_events(attempt_dir: Path, count: int = 8) -> list[str]:
    events = attempt_dir / "events.jsonl"
    try:
        lines = events.read_text(errors="replace").splitlines()
    except OSError:
        return []
    briefs = []
    for line in lines[-200:]:
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        briefs.append(_event_brief(evt))
    return briefs[-count:]


def _find_attempt(attempts: list[dict], target: str) -> dict | None:
    for info in attempts:
        if target in (info["job_id"], info["node_id"], info["name"]):
            return info
    matches = [a for a in attempts if a["name"].startswith(target)]
    return matches[0] if len(matches) == 1 else None


def _render_fleet(attempts: list[dict], now: float) -> None:
    print(f"gddp watch — {len(attempts)} attempt(s)  ({time.strftime('%H:%M:%S')})")
    print(f"{'NODE':38} {'STATE':8} {'AGE':>7} {'DIFF':>28} {'QUIET':>6}")
    for info in attempts:
        shortstat, untracked = _diff_summary(info["worktree"])
        diff = shortstat
        if untracked:
            diff = f"{diff} +{untracked}new"
        quiet = _age(info["last_write"], now)
        flag = " !" if info["state"] == "running" and now - info["last_write"] > 180 else ""
        node = (info["node_id"] or info["name"])[:38]
        print(
            f"{node:38} {info['state']:8} {_age(info['created'], now):>7} "
            f"{diff:>28} {quiet:>5}{flag}"
        )


def _render_single(info: dict, now: float) -> None:
    print(
        f"gddp watch {info['node_id'] or info['name']} — {info['state']}  "
        f"age {_age(info['created'], now)}  pid {info['pid']}  "
        f"({time.strftime('%H:%M:%S')})"
    )
    print(f"  worktree: {info['worktree'] or '-'}")
    print(f"  job: {info['job_id'] or '-'}")
    if (info["dir"] / "result.json").is_file():
        print("  ** turn complete — verdict pending; review via: gddp review / gddp node browse")
    print("\n-- diff vs HEAD " + "-" * 50)
    if info["worktree"] and Path(info["worktree"]).is_dir():
        stat = _git(info["worktree"], "diff", "--stat", "HEAD").strip()
        lines = stat.splitlines()
        print("\n".join(lines[-25:]) if lines else "  (clean)")
        untracked = _git(
            info["worktree"], "ls-files", "--others", "--exclude-standard"
        ).split()
        for path in untracked[:10]:
            print(f"  [new] {path}")
    else:
        print("  (no worktree recorded yet)")
    print("\n-- recent events " + "-" * 49)
    events = _recent_events(info["dir"])
    print("\n".join(f"  {e}" for e in events) if events else print("  (none)"))


def cmd_watch(args) -> int:
    runtime_root = resolve_runtime_root()
    spool = _spool_root(runtime_root)
    if not spool.is_dir():
        print(f"no spool at {spool}; nothing has run yet", file=sys.stderr)
        return 1
    tty = sys.stdout.isatty()
    while True:
        attempts = _scan_attempts(spool)
        if args.target:
            info = _find_attempt(attempts, args.target)
            if info is None:
                print(f"no attempt matching {args.target!r}", file=sys.stderr)
                return 1
        if tty and not args.once:
            sys.stdout.write("\033[2J\033[H")
        now = time.time()
        if args.target:
            _render_single(info, now)
        else:
            _render_fleet(attempts, now)
        if args.once or not tty:
            return 0
        time.sleep(args.interval)


def cmd_steer(args) -> int:
    runtime_root = resolve_runtime_root()
    attempts = _scan_attempts(_spool_root(runtime_root))
    info = _find_attempt(attempts, args.target)
    if info is None:
        print(f"no attempt matching {args.target!r}", file=sys.stderr)
        return 1
    if info["state"] != "running":
        print(
            f"{info['name']} is {info['state']}; steer only delivers to a running attempt",
            file=sys.stderr,
        )
        return 1
    message = " ".join(args.message).strip()
    if not message:
        print("empty steer message", file=sys.stderr)
        return 1
    line = json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "message": message}
    )
    with (info["dir"] / "steer.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(f"steer queued for {info['node_id'] or info['name']}: {message}")
    print("delivered on the supervisor's next read cycle (needs the steer-aware runtime)")
    return 0


def cmd_overview(_args):
    if sys.stdin.isatty() and sys.stdout.isatty():
        return interactive_menu()
    static_overview()
    return 0


def cmd_receipt(args) -> int:
    """Delegate mission worker receipt writes to runtime's receipt CLI."""
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    script = runtime_root / "scripts" / "gddp_node_receipt.py"
    if not script.is_file():
        print(f"ERROR: receipt backend not found at {script}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(script),
        "--node-id",
        args.node_id,
        "--base",
        args.base,
        "--result",
        args.result,
    ]
    env = os.environ.copy()
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    return subprocess.run(command, env=env, check=False).returncode


def cmd_verify_node(args):
    """Delegate node verification to the runtime evaluator — the single judge.

    Default runs the deterministic lane (offline, fast — the verb's original
    contract). --live runs the full two-lane evaluation (deterministic +
    semantic + integrity), the same judge the pipeline uses.
    """
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    node_yaml = ROOT / "graphs" / args.project / "nodes" / f"{args.node}.yaml"
    project_yaml = ROOT / "graphs" / args.project / "project.yaml"
    for path, label in ((node_yaml, "node yaml"), (project_yaml, "project yaml")):
        if not path.is_file():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            sys.exit(2)

    with open(project_yaml) as f:
        proj = yaml.safe_load(f) or {}
    repo_name = str(proj.get("repo", "")).split("/")[-1]
    repo = None
    candidates = []
    if args.repo_path:
        candidates.append(Path(args.repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for c in candidates:
        if c.is_dir():
            repo = c
            break
    if repo is None:
        print(f"ERROR: could not resolve repo checkout for '{proj.get('repo', '')}' "
              "(pass --repo-path)", file=sys.stderr)
        sys.exit(2)

    receipt_dir = ROOT / "verification"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    live = bool(getattr(args, "live", False))
    manual_job_id = "manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cmd = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "verification" / "cli.py"),
        "--node-yaml", str(node_yaml),
        "--project-yaml", str(project_yaml),
        "--repo", str(repo),
        "--config-root", str(ROOT),
        "--receipt-dir", str(receipt_dir),
        "--job-id", manual_job_id,
        "--attempt", "0",
        *(["--base", args.base] if getattr(args, "base", None) else []),
        "--semantic-mode", "live" if live else "offline",
        # --live must select the Pi harness explicitly: auto resolves to the
        # removed built-in runner and the evaluator refuses to start.
        *(["--semantic-harness", "pi"] if live else []),
        "--integrity", "on" if live else "off",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
    env["GDDP_RUNTIME_ROOT"] = str(runtime_root)
    sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


def cmd_obsidian_export(args):
    obsidian_export = _import_module("obsidian_export")
    argv = ["--project", args.project]
    if args.vault:
        argv += ["--vault", str(args.vault)]
    if args.dry_run:
        argv.append("--dry-run")
    sys.exit(obsidian_export.main(argv))


def cmd_project_new(args):
    if args.from_outline:
        outline = _import_module("outline_to_nodes")
        sys.exit(outline.main(
            outline_path=args.from_outline,
            project_id=args.project_id,
            repo=args.repo,
            project_name=args.project_name,
            dry_run=args.dry_run,
            force=args.force,
        ))
    elif args.from_graphify:
        graphify = _import_module("graphify_to_nodes")
        sys.argv = [
            "graphify_to_nodes",
            "--input", str(args.from_graphify),
            "--project-id", args.project_id,
            "--repo", args.repo or "",
        ]
        if args.project_name:
            sys.argv.extend(["--project-name", args.project_name])
        if args.dry_run:
            sys.argv.append("--dry-run")
        if args.force:
            sys.argv.append("--force")
        sys.exit(graphify.main())
    else:
        rapid = _import_module("rapid_add")
        rapid.ensure_project_shell(ROOT, args.project_id, args.repo, args.project_name)
        print(f"Created empty project: graphs/{args.project_id}/")
        print(f"Next: gddp node rapid --project {args.project_id} --repo {args.repo}")


def cmd_project_validate(args):
    validate_project(args.project)


def _list_status_projects() -> list[str]:
    graphs = ROOT / "graphs"
    if not graphs.exists():
        return []
    return sorted(
        p.name for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )


def _load_project_doc(project_id: str) -> dict:
    with open(ROOT / "graphs" / project_id / "project.yaml") as f:
        return yaml.safe_load(f) or {}


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
    projects = _list_status_projects()
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
        proj = _load_project_doc(pid)
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
    node_cli = _import_module("node_cli")
    proj = _load_project_doc(project_id)
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
        line.append_text(_node_row_description(phase, "", verdict))
        if title:
            line.append(f"  {title}", style="dim")
        console.print(line)

    console.print()
    scan = Text("  operator scan  ")
    scan.append_text(_status_counts_text(phase_counts))
    console.print(scan)
    if verdict_counts:
        ev_scan = Text("  evaluator       ")
        ev_scan.append_text(_status_counts_text(verdict_counts))
        console.print(ev_scan)


def interactive_status():
    """Status menu: all projects summary or one project with node phases."""
    actions = {
        "a": ("all", "every project completion summary"),
        "o": ("one", "pick one project — counts + node phases"),
        "b": ("main menu", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("status", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            show_status()
            _pause()
            continue
        projects = _list_status_projects()
        if not projects:
            console.print(Text("No graphs found", style="yellow"))
            _pause()
            continue
        project = _pick_list(
            "status · projects",
            [(pid, "") for pid in projects],
            preview_cmd=_project_preview_cmd(),
            back_label="status",
        )
        if project is _MENU_QUIT:
            return _MENU_QUIT
        if project is _MENU_BACK:
            continue
        _clear_screen()
        show_status(project)
        _pause()


def interactive_validate():
    """Validate menu: all graphs or one project."""
    actions = {
        "a": ("all", "validate every project"),
        "o": ("one", "pick one project"),
        "b": ("main menu", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(Text("validate", style="bold"))
        choice = _menu_choice(actions, default="a")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "a":
            _clear_screen()
            validate_project(None)
            _pause()
            continue
        projects = _list_status_projects()
        if not projects:
            console.print(Text("No graphs found", style="yellow"))
            _pause()
            continue
        project = _pick_list(
            "validate · projects",
            [(pid, "") for pid in projects],
            preview_cmd=_project_preview_cmd(),
            back_label="validate",
        )
        if project is _MENU_QUIT:
            return _MENU_QUIT
        if project is _MENU_BACK:
            continue
        _clear_screen()
        validate_project(project)
        _pause()


def validate_project(project_id: str | None):
    graphs = ROOT / "graphs"
    if not graphs.exists():
        console.print(Text("No graphs/ directory found", style="yellow"))
        return

    projects = _list_status_projects()
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Positional dispatch: gddp <graph|node> [executor] [--yes]. Anything that
    # is not a known subcommand is an exact graph or node target.
    if argv and argv[0] not in _CLI_COMMANDS and not argv[0].startswith("-"):
        return cmd_dispatch(argv)
    parser = argparse.ArgumentParser(
        description="gddp — graph truth and runtime evidence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=cmd_overview)
    sub = parser.add_subparsers(dest="command")

    node_p = sub.add_parser("node", help="Node operations")
    node_sub = node_p.add_subparsers(dest="subcommand")

    node_browse = node_sub.add_parser(
        "browse", help="Interactive node review and graph-status menu")
    node_browse.add_argument(
        "--project", default=None, help="Open this project directly")
    node_browse.set_defaults(func=cmd_node_browse)

    node_new = node_sub.add_parser("new", help="Interactive TUI node scaffold (full editor)")
    node_new.set_defaults(func=cmd_node_new)

    node_rapid = node_sub.add_parser("rapid", help="Minimal-keystroke rapid node adder")
    node_rapid.add_argument("--project", required=True, help="Project ID")
    node_rapid.add_argument("--repo", default="")
    node_rapid.add_argument("--project-name", default=None)
    node_rapid.add_argument("--llm-draft", action="store_true",
                            help="Use LLM to draft why/acceptance/constraints")
    node_rapid.add_argument("--dry-run", action="store_true")
    node_rapid.set_defaults(func=cmd_node_rapid)

    node_batch = node_sub.add_parser("batch", help="Walk through REPLACE_ME nodes in a project")
    node_batch.add_argument("--project", required=True, help="Project ID")
    node_batch.set_defaults(func=cmd_node_batch)

    node_import = node_sub.add_parser("import", help="Import node YAML from file or stdin")
    node_import.add_argument("--file", type=Path, default=None, help="YAML file to import")
    node_import.add_argument("--stdin", action="store_true", help="Read YAML from stdin")
    node_import.add_argument("--project", required=True, help="Project ID")
    node_import.add_argument("--auto-approve", action="store_true")
    node_import.add_argument("--dry-run", action="store_true")
    node_import.add_argument(
        "--update", action="store_true",
        help="Replace an existing node; preserve its status",
    )
    node_import.set_defaults(func=cmd_node_import)

    node_val = node_sub.add_parser("validate", help="Validate nodes")
    node_val.add_argument("--project", default=None, help="Only check this project")
    node_val.add_argument("--json", action="store_true", help="Machine-readable output")
    node_val.add_argument("--strict", action="store_true", help="Warnings count as errors")
    node_val.add_argument("--quiet", action="store_true", help="Only summary line")
    node_val.add_argument("--root", type=Path, default=None)
    node_val.set_defaults(func=cmd_node_validate)

    node_list = node_sub.add_parser(
        "list", help="List nodes (ID | GRAPH | RUNTIME | VERDICT)")
    node_list.add_argument("--project", default=None, help="Project ID (omit for all)")
    node_list.add_argument("--status", default=None, help="Filter by graph status")
    node_list.add_argument(
        "--active", action="store_true",
        help="Only graph status pending or ready",
    )
    node_list.set_defaults(func=cmd_node_list)

    node_show = node_sub.add_parser(
        "show", help="Show one node + evaluator summary")
    node_show.add_argument("--project", required=True, help="Project ID")
    node_show.add_argument("node_id", help="Node ID")
    node_show.add_argument(
        "--trace", action="store_true",
        help="Expand tool traces and result/job history",
    )
    node_show.add_argument(
        "--view",
        choices=("all", "summary", "evaluation", "contract"),
        default="all",
        help="Limit output to one operator view",
    )
    node_show.set_defaults(func=cmd_node_show)

    node_status = node_sub.add_parser(
        "status", help="Status summary (all projects, or one with --project)"
    )
    node_status.add_argument(
        "--project", default=None, help="One project — counts + node phases"
    )
    node_status.set_defaults(func=cmd_node_status)

    evals_p = sub.add_parser(
        "evaluations",
        help="List evaluator receipts with verdict and timing",
    )
    evals_p.set_defaults(func=cmd_evaluations)

    jobs_p = sub.add_parser("jobs", help="Runtime jobs and evaluator evidence")
    jobs_p.set_defaults(func=cmd_jobs)

    watch_p = sub.add_parser(
        "watch", help="Live view of running attempts (fleet, or one node's diff/events)"
    )
    watch_p.add_argument("target", nargs="?", default=None,
                         help="node id, job id, or attempt-dir prefix; omit for fleet view")
    watch_p.add_argument("--interval", type=float, default=2.0,
                         help="refresh seconds (default 2)")
    watch_p.add_argument("--once", action="store_true", help="render once and exit")
    watch_p.set_defaults(func=cmd_watch)

    steer_p = sub.add_parser(
        "steer", help="Send an operator message into a running attempt's session"
    )
    steer_p.add_argument("target", help="node id, job id, or attempt-dir prefix")
    steer_p.add_argument("message", nargs="+", help="message text")
    steer_p.set_defaults(func=cmd_steer)
    jobs_sub = jobs_p.add_subparsers(dest="jobs_command")

    jobs_list = jobs_sub.add_parser("list", help="List jobs and queue states")
    jobs_list.add_argument("--state", default=None, help="Filter by queue state")
    jobs_list.set_defaults(func=cmd_jobs)

    jobs_show = jobs_sub.add_parser("show", help="Show one job by job ID or node ID")
    jobs_show.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_show.add_argument(
        "--full", action="store_true", help="Include criterion-level reasoning"
    )
    jobs_show.set_defaults(func=cmd_jobs)

    jobs_results = jobs_sub.add_parser("results", help="Summarize evaluator output")
    jobs_results.add_argument("--all", action="store_true", help="List every result row")
    jobs_results.set_defaults(func=cmd_jobs)

    jobs_set = jobs_sub.add_parser("set", help="Change runtime job state")
    jobs_set.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_set.add_argument("state", help="New runtime job state")
    jobs_set.add_argument(
        "--reason",
        required=True,
        help="Why; stored in the runtime audit row",
    )
    jobs_set.add_argument("--yes", action="store_true", help="Skip confirmation")
    jobs_set.set_defaults(func=cmd_jobs)

    receipt_p = sub.add_parser(
        "receipt",
        help="Append a mission worker node receipt (requires GDDP_RECEIPTS_PATH)",
    )
    receipt_p.add_argument("--node-id", required=True, help="Graph/feature node id")
    receipt_p.add_argument("--base", required=True, help="Starting commit SHA")
    receipt_p.add_argument("--result", required=True, help="Result commit SHA")
    receipt_p.set_defaults(func=cmd_receipt)

    verify_p = sub.add_parser("verify", help="Node evaluation harness")
    verify_sub = verify_p.add_subparsers(dest="subcommand")

    verify_node = verify_sub.add_parser(
        "node", help="Run the runtime evaluator on a node; emit a receipt")
    verify_node.add_argument("--project", required=True, help="Project ID")
    verify_node.add_argument("--node", required=True, help="Node ID")
    verify_node.add_argument("--repo-path", default=None,
                             help="Path to the source repo checkout "
                                  "(overrides auto-resolve)")
    verify_node.add_argument("--live", action="store_true",
                             help="Full two-lane evaluation (deterministic + semantic + integrity); default is the fast deterministic lane")
    verify_node.add_argument("--base", default=None,
                             help="Base commit the subject was built on; enables "
                                  "subject-diff evidence (pipeline runs get this "
                                  "from the session row automatically)")
    verify_node.set_defaults(func=cmd_verify_node)

    review_p = sub.add_parser(
        "review",
        help="Human-gate review surface: latest verdict, subject diff, merge state",
    )
    review_p.add_argument("--project", required=True, help="Project ID")
    review_p.add_argument("--node", required=True, help="Node ID")
    review_p.add_argument("--repo-path", default=None,
                          help="Path to the source repo checkout (overrides auto-resolve)")
    review_p.add_argument("--full", action="store_true",
                          help="Full patch instead of --stat")
    review_p.set_defaults(func=cmd_review)

    obs_p = sub.add_parser("obsidian", help="Obsidian vault export")
    obs_sub = obs_p.add_subparsers(dest="subcommand")

    obs_export = obs_sub.add_parser(
        "export", help="Export one graph to an Obsidian vault folder")
    obs_export.add_argument("--project", required=True,
                            help="Graph to export (graphs/<project>/)")
    obs_export.add_argument("--vault", type=Path, default=None,
                            help="Destination vault (default: ~/Obsidian/gdd-<project>)")
    obs_export.add_argument("--dry-run", action="store_true")
    obs_export.set_defaults(func=cmd_obsidian_export)

    proj_p = sub.add_parser("project", help="Project operations")
    proj_sub = proj_p.add_subparsers(dest="subcommand")

    proj_new = proj_sub.add_parser("new", help="Create project skeleton")
    proj_new.add_argument("--project-id", required=True, help="kebab-case project id")
    proj_new.add_argument("--project-name", default=None, help="Display name")
    proj_new.add_argument("--repo", default="")
    source = proj_new.add_mutually_exclusive_group(required=False)
    source.add_argument("--from-outline", type=Path, default=None, help="Markdown outline file")
    source.add_argument("--from-graphify", type=Path, default=None, help="graphify-out/graph.json file")
    proj_new.add_argument("--dry-run", action="store_true")
    proj_new.add_argument("--force", action="store_true")
    proj_new.set_defaults(func=cmd_project_new)

    proj_val = proj_sub.add_parser("validate", help="Validate project.yaml files")
    proj_val.add_argument("--project", default=None, help="Project ID (omit for all)")
    proj_val.set_defaults(func=cmd_project_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
