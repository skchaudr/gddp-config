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
    jobs live         Live running executors (alias for watch)
    jobs results      Summarize evaluator output
    jobs set          Change runtime job state with an audit reason

    evaluations       List evaluator receipts (verdict + timing)

    timeline <project> [node]  What happened, in order, in words; flags disagreements
    watch [target]    Live running fleet (default); drill-in by node/job id
    runs              fzf picker over attempts (agent-runs style; Enter → watch)
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
import io
import json
import os
import platform
import socket
import re
import shlex
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
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
_MENU_REFRESH = object()
_RUNTIME_JOB_COMMANDS = frozenset({"list", "show", "results", "set", "retry", "adopt"})
_CLI_COMMANDS = frozenset(
    {
        "node",
        "jobs",
        "evaluations",
        "verify",
        "eval",
        "review",
        "receipt",
        "obsidian",
        "deliver",
        "project",
        "watch",
        "runs",
        "steer",
        "timeline",
    }
)
_ABSTRACT_EXECUTION_MODES = frozenset({"agent", "human"})

# --------------------------------------------------------------------------- #
# Runtime settings (executor + evaluator configuration)
# --------------------------------------------------------------------------- #
# Human-editable config lives in runtime/settings.env (KEY=value lines). gddp
# loads it at startup into os.environ so every subprocess it spawns inherits
# executor and evaluator configuration. The interactive `config` menu edits
# this file; `gddp eval` and the dispatch/evaluate menu paths read it.

SETTINGS_FILE = ROOT / "runtime" / "settings.env"

SETTINGS_FIELDS: dict[str, tuple[str, str]] = {
    "GDDP_EXECUTOR_OVERRIDE": (
        "executor",
        "force a concrete executor for all dispatch (empty = per-project default; pi_rpc, local_subprocess, jules, droid, factory_mission)",
    ),
    "GDDP_PI_RPC_MODEL": (
        "pi_rpc model",
        "model id for the pi_rpc executor (e.g. xai/grok-4.5)",
    ),
    "GDDP_PI_RPC_TOOLS": (
        "pi_rpc tools",
        "comma-separated tool allowlist for the pi_rpc executor",
    ),
    "GDDP_PI_RPC_TURN_TIMEOUT_S": (
        "pi_rpc turn timeout",
        "seconds before a single executor turn is considered hung",
    ),
    "GDDP_VERIFY_SEMANTIC_ARGS": (
        "evaluator lanes",
        "semantic lane args: --semantic-provider <p> --semantic-pi-model <m> --semantic-thinking <level>",
    ),
    "GDDP_EVAL_MODEL_CHEAP": (
        "eval cheap model",
        "model id for the cheap evaluator preset (default: deepseek-v4-flash)",
    ),
    "GDDP_EVAL_MODEL_EXPENSIVE": (
        "eval expensive model",
        "model id for the expensive evaluator preset (empty until set)",
    ),
    "GDDP_EVAL_THINKING_DEFAULT": (
        "eval thinking default",
        "default semantic thinking level (e.g. medium)",
    ),
    "GDDP_EVAL_LANES_DEFAULT": (
        "eval lanes default",
        "default lanes: live or deterministic",
    ),
    "GDDP_INTEGRITY_MODE": (
        "integrity lane",
        "on/off — intent/integrity evaluation always runs when on",
    ),
    "GDDP_DEEPSEEK_KEY_CMD": (
        "evaluator key cmd",
        "shell command that prints the DeepSeek API key (default: pass show api/deepseek)",
    ),
}

DEFAULT_SEMANTIC_ARGS = (
    "--semantic-mode live --semantic-harness pi --semantic-provider deepseek "
    "--semantic-pi-model deepseek-v4-flash --semantic-thinking medium"
)


def _load_runtime_settings() -> None:
    """Load runtime/settings.env into os.environ (setdefault semantics).

    Subprocesses spawned later inherit these values. Explicit shell env always
    wins over the settings file, so an operator can override on the command
    line without editing the file."""
    if not SETTINGS_FILE.is_file():
        return
    try:
        for line in SETTINGS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            os.environ.setdefault(key, value)
    except OSError as exc:
        print(f"warning: could not read {SETTINGS_FILE}: {exc}", file=sys.stderr)


def _write_runtime_settings(settings: dict[str, str]) -> None:
    """Persist executor/evaluator settings to runtime/settings.env."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# gddp runtime settings — edited via `gddp config` (front-page c)",
        "# Loaded into the environment for every executor/evaluator subprocess.",
    ]
    for key in SETTINGS_FIELDS:
        value = settings.get(key, "").strip()
        if value:
            lines.append(f"{key}={value}")
    SETTINGS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key, value in settings.items():
        if value.strip():
            os.environ[key] = value.strip()
        else:
            os.environ.pop(key, None)


# --------------------------------------------------------------------------- #
# Positional dispatch: gddp <graph|node> [executor]
# --------------------------------------------------------------------------- #

























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


def _frontier_pick_items(projects: list[str]) -> list[tuple[str, str | Text]]:
    """Ready / in-flight / blocked / correction nodes across ``projects``."""
    frontier = _import_module("frontier")
    items: list[tuple[str, str | Text]] = []
    try:
        con = frontier.connect_readonly(resolve_runtime_root() / "db" / "queue.db")
    except frontier.FrontierUnavailable:
        con = None
    try:
        for pid in projects:
            graph = frontier.load_graph(ROOT, pid)
            runtime: dict = {}
            if con is not None:
                try:
                    runtime = frontier.load_runtime(con, pid)
                except sqlite3.Error:
                    runtime = {}
            derived = frontier.derive(graph, runtime)
            prefix = f"{pid}/" if len(projects) > 1 else ""
            for node_id, executor in derived["ready"]:
                key = f"{pid}\t{node_id}"
                label = f"{prefix}{node_id} · ready"
                if executor:
                    label += f" [{executor}]"
                items.append((key, label))
            for node_id, motion in derived["in_flight"]:
                key = f"{pid}\t{node_id}"
                items.append((
                    key,
                    f"{prefix}{node_id} · in flight · {motion['phase']}",
                ))
            for node_id, _motion in derived["correction"]:
                key = f"{pid}\t{node_id}"
                items.append((key, f"{prefix}{node_id} · awaiting correction"))
            for node_id, status, _unsat in derived["blocked"]:
                key = f"{pid}\t{node_id}"
                items.append((key, f"{prefix}{node_id} · blocked · {status}"))
    finally:
        if con is not None:
            con.close()
    return items


def _frontier_after_show(projects: list[str], *, back_label: str = "more") -> str:
    """Refresh/back menu or pick a frontier node for review."""
    actions = {
        "p": ("pick node", "ready · in flight · blocked"),
        "r": ("refresh", "recompute frontier"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        choice = _menu_choice(actions, default="r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "r":
            _clear_screen()
            _show_frontier(projects)
            continue
        items = _frontier_pick_items(projects)
        if not items:
            console.print(Text("No frontier nodes to open.", style="yellow"))
            continue
        picked = _pick_list(
            "frontier · nodes",
            items,
            back_label=back_label,
        )
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        pid, node_id = str(picked).split("\t", 1)
        node_cli = _import_module("node_cli")
        try:
            siblings = [nid for nid, _, _ in node_cli.iter_nodes(ROOT, pid)]
        except Exception:
            siblings = [node_id]
        outcome = _node_review_menu(pid, node_id, siblings)
        if outcome is _MENU_QUIT:
            return _MENU_QUIT
        _clear_screen()
        _show_frontier(projects)


_GRAPH_ARCHIVE_AFTER = timedelta(days=7)
_ARCHIVE_SENTINEL = "__archive__"


def _parse_activity_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _job_last_activity_by_project() -> dict[str, datetime]:
    """project_id -> latest jobs.created_at from runtime queue DB (best effort)."""
    out: dict[str, datetime] = {}
    try:
        db_path = resolve_runtime_root() / "db" / "queue.db"
    except RuntimeError:
        return out
    if not db_path.is_file():
        return out
    try:
        con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT project_id, MAX(created_at) AS last_at "
                "FROM jobs WHERE project_id IS NOT NULL AND project_id != '' "
                "GROUP BY project_id"
            ).fetchall()
        except sqlite3.Error:
            return out
        finally:
            con.close()
    except sqlite3.Error:
        return out
    for row in rows:
        when = _parse_activity_ts(row["last_at"])
        if when is not None:
            out[str(row["project_id"])] = when
    return out


def _graph_file_activity(project_id: str) -> datetime:
    """Latest mtime under graphs/<id>/ (project.yaml + node YAMLs)."""
    root = ROOT / "graphs" / project_id
    latest = 0.0
    if not root.is_dir():
        return datetime.fromtimestamp(0, tz=timezone.utc)
    for path in root.rglob("*"):
        if path.is_file():
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    if latest <= 0:
        try:
            latest = root.stat().st_mtime
        except OSError:
            return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromtimestamp(latest, tz=timezone.utc)


def _graph_activity_at(
    project_id: str,
    job_times: dict[str, datetime] | None = None,
) -> datetime:
    """Most recent signal: last job or graph file edit."""
    job_times = job_times if job_times is not None else _job_last_activity_by_project()
    candidates = [_graph_file_activity(project_id)]
    if project_id in job_times:
        candidates.append(job_times[project_id])
    return max(candidates)


def _format_activity_age(when: datetime, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    secs = int((now - when).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = secs // 86400
    return "1d ago" if days == 1 else f"{days}d ago"


def partition_graphs_by_activity(
    project_ids: list[str] | None = None,
    *,
    now: datetime | None = None,
    archive_after: timedelta = _GRAPH_ARCHIVE_AFTER,
    job_times: dict[str, datetime] | None = None,
) -> tuple[list[tuple[str, datetime]], list[tuple[str, datetime]]]:
    """Split graphs into active vs archive (> archive_after idle), newest first."""
    now = now or datetime.now(timezone.utc)
    ids = project_ids if project_ids is not None else _graph_projects(ROOT)
    job_times = job_times if job_times is not None else _job_last_activity_by_project()
    active: list[tuple[str, datetime]] = []
    archive: list[tuple[str, datetime]] = []
    for pid in ids:
        when = _graph_activity_at(pid, job_times)
        if now - when <= archive_after:
            active.append((pid, when))
        else:
            archive.append((pid, when))
    active.sort(key=lambda item: item[1], reverse=True)
    archive.sort(key=lambda item: item[1], reverse=True)
    return active, archive


def _graph_pick_items(
    rows: list[tuple[str, datetime]],
    *,
    now: datetime | None = None,
) -> list[tuple[str, str | Text]]:
    """(project_id, '3d ago · N nodes') for paged menus."""
    now = now or datetime.now(timezone.utc)
    node_cli = _import_module("node_cli")
    items: list[tuple[str, str | Text]] = []
    for pid, when in rows:
        age = _format_activity_age(when, now=now)
        try:
            count = len(node_cli.iter_nodes(ROOT, pid))
            detail = f"{age} · {count} node{'s' if count != 1 else ''}"
        except Exception:
            detail = age
        desc = Text()
        desc.append(age, style="bold cyan" if (now - when) <= timedelta(days=2) else "dim")
        if " · " in detail:
            desc.append(detail[len(age):], style="dim")
        items.append((pid, desc))
    return items


def _pick_graph(
    heading: str,
    *,
    back_label: str = "main menu",
    include_archive: bool = True,
) -> str | object:
    """Activity-sorted graph picker; ``r`` reloads graph and runtime state."""
    archive_mode = False
    while True:
        active, archive = partition_graphs_by_activity()
        now = datetime.now(timezone.utc)
        rows = archive if archive_mode else active
        items = _graph_pick_items(rows, now=now)
        if not archive_mode and include_archive and archive:
            items.append((
                _ARCHIVE_SENTINEL,
                Text(
                    f"archive · {len(archive)} inactive (>7d)",
                    style="dim",
                ),
            ))
        if not items:
            if archive_mode:
                console.print(Text("Archive empty.", style="dim"))
                archive_mode = False
                continue
            _clear_screen()
            console.print(Text("No graphs found.", style="yellow"))
            _pause()
            return _MENU_BACK
        picked = _pick_list(
            f"{heading} · archive" if archive_mode else heading,
            items,
            preview_cmd=_project_preview_cmd(),
            back_label="active graphs" if archive_mode else back_label,
            refreshable=True,
        )
        if picked is _MENU_REFRESH:
            continue
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            if archive_mode:
                archive_mode = False
                continue
            return _MENU_BACK
        if picked == _ARCHIVE_SENTINEL:
            archive_mode = True
            continue
        return picked


def interactive_frontier(project: str | None = None):
    """Derived frontier view; recomputes from live graph + runtime on open."""
    if project:
        _clear_screen()
        _show_frontier([project])
        return _frontier_after_show([project], back_label="more")
    frontier = _import_module("frontier")
    projects = frontier.project_ids(ROOT)
    if not projects:
        console.print(Text("no graphs found", style="yellow"))
        return _MENU_BACK
    actions = {
        "a": ("all", "frontier for every project"),
        "o": ("one", "pick one project"),
        "b": ("back", ""),
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
            outcome = _frontier_after_show(projects, back_label="frontier")
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue
        picked = _pick_graph("frontier · graphs", back_label="frontier")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            continue
        _clear_screen()
        _show_frontier([str(picked)])
        outcome = _frontier_after_show([str(picked)], back_label="frontier")
        if outcome is _MENU_QUIT:
            return _MENU_QUIT


def _dispatch_for_project(project: str, *, back_label: str = "graphs"):
    """Dispatchability table + target pick for one graph."""
    try:
        con = _connect_events_db(resolve_runtime_root() / "db" / "queue.db")
    except cli_dispatch.DispatchError as exc:
        console.print(f"[bold red]ERROR:[/] {exc}")
        _pause()
        return _MENU_BACK
    try:
        try:
            plan = cli_dispatch.build_dispatch_plan(
                ROOT, project, None, project_hint=project
            )
            movable, excluded = _classify_dispatch_items(con, ROOT, plan)
        except cli_dispatch.DispatchError as exc:
            console.print(f"[bold red]ERROR:[/] {exc}")
            _pause()
            return _MENU_BACK

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
            _pause()
            return _MENU_BACK

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
            back_label=back_label,
        )
        if target is _MENU_QUIT:
            return _MENU_QUIT
        if target is _MENU_BACK:
            return _MENU_BACK
        # Executor already shown on each row; override is shell-only
        # (`gddp <node> <executor>`). Empty Prompt.ask "():" was noise that
        # trained people to hit Enter into the next default-no confirm.
        _dispatch_flow(
            con,
            ROOT,
            target,
            None,
            project_hint=project,
        )
        return _MENU_BACK
    finally:
        con.close()


def interactive_dispatch(project: str | None = None):
    """Pick a graph (activity-sorted) and dispatch ready targets."""
    if project:
        return _dispatch_for_project(project, back_label="graph")
    while True:
        picked = _pick_graph("dispatch · graphs", back_label="main menu")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            return _MENU_BACK
        outcome = _dispatch_for_project(str(picked), back_label="graphs")
        if outcome is _MENU_QUIT:
            return _MENU_QUIT
        # After a dispatch attempt, return to main (same as before).
        return outcome


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


def _ellipsize(text: str, width: int) -> str:
    """Truncate to width with a single ellipsis; empty when width is gone."""
    body = str(text or "")
    if width <= 0:
        return ""
    if len(body) <= width:
        return body
    if width == 1:
        return "…"
    return body[: width - 1] + "…"


def _is_running_state(runtime: str) -> bool:
    token = str(runtime or "").strip().lower().replace(" ", "_")
    return token == "running"


def _runtime_label(queue_state: str = "-", job_status: str = "-") -> str:
    """Prefer live queue state; fall back to job status. Never invent graph truth."""
    queue = str(queue_state or "").strip()
    if queue and queue != "-":
        return queue
    job = str(job_status or "").strip()
    if job and job != "-":
        return job
    return "-"


def _is_node_list_desc(description: object) -> bool:
    return isinstance(description, dict) and {
        "graph", "runtime", "title",
    }.issubset(description.keys())


def _runtime_column(runtime: str, width: int) -> Text:
    """Fixed-width runtime cell; running uses a mark + reverse, not color alone."""
    running = _is_running_state(runtime)
    mark = "▶" if running else " "
    label = str(runtime or "-").replace("_", " ")
    body = mark + _ellipsize(label, max(0, width - 1))
    cell = Text(f"{body:<{width}}")
    if running:
        cell.stylize("bold magenta reverse")
    else:
        cell.stylize(_graph_status_style(runtime))
    return cell


def _node_column_budget(room: int) -> tuple[int, int, int, int]:
    """GRAPH / RUNTIME / EVAL / TITLE widths for a given remainder."""
    room = max(0, int(room))
    # mark + "awaiting review" needs 16 so the live phase stays readable.
    if room < 30:
        rt_w = min(16, room) if room >= 6 else room
        title_w = max(0, room - rt_w - (2 if room - rt_w >= 2 else 0))
        return 0, rt_w, 0, title_w
    if room < 52:
        g_w, rt_w, c_w = 12, 16, 4
        used = g_w + 2 + rt_w + 2 + c_w
        if used > room:
            c_w = 0
            used = g_w + 2 + rt_w
        title_w = max(0, room - used - (2 if room > used else 0))
        return g_w, rt_w, c_w, title_w
    g_w, rt_w, c_w = 16, 16, 4
    title_w = max(0, room - g_w - 2 - rt_w - 2 - c_w - 2)
    return g_w, rt_w, c_w, title_w


def _format_node_columns(
    *,
    graph: str,
    runtime: str,
    verdict: str | None,
    title: str,
    room: int,
) -> Text:
    """Aligned GRAPH / RUNTIME / VERDICT / TITLE; collapse by priority when narrow."""
    chip = _verdict_chip(verdict)
    g_w, rt_w, c_w, title_w = _node_column_budget(room)
    out = Text()
    if rt_w <= 0 and g_w <= 0:
        mark = "▶" if _is_running_state(runtime) else "-"
        return Text(_ellipsize(mark, max(0, int(room))))
    if g_w:
        out.append(_ellipsize(graph, g_w).ljust(g_w), style=_graph_status_style(graph))
        out.append("  ")
    out.append_text(_runtime_column(runtime, rt_w))
    if c_w:
        out.append("  ")
        if chip:
            out.append(f"{chip:<{c_w}}", style=_graph_status_style(chip))
        else:
            out.append(f"{'-':<{c_w}}", style="dim")
    if title_w:
        out.append("  ")
        out.append(_ellipsize(title, title_w), style="dim")
    return out


def _node_column_header(room: int) -> Text:
    """Same widths as ``_format_node_columns`` so headers stay under the cells."""
    g_w, rt_w, c_w, title_w = _node_column_budget(room)
    bits: list[str] = []
    if g_w:
        bits.append(f"{'GRAPH':<{g_w}}")
    if rt_w:
        bits.append(f"{'RUNTIME':<{rt_w}}")
    if c_w:
        bits.append(f"{'EVAL':<{c_w}}")
    if title_w:
        bits.append("TITLE")
    return Text("  ".join(bits), style="dim")


def _node_list_desc(
    graph: str,
    runtime: str,
    title: str = "",
    verdict: str | None = None,
) -> dict[str, str]:
    """Structured picker row: graph truth, runtime, evaluator chip, title."""
    return {
        "graph": str(graph or "-"),
        "runtime": str(runtime or "-"),
        "verdict": "" if verdict is None else str(verdict),
        "title": str(title or ""),
    }


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


class _TtyCapture(io.StringIO):
    """Capture stdout while claiming to be a TTY so color guards keep ANSI."""

    def isatty(self) -> bool:
        return True


_ANSI_SGR = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Drop SGR color codes — the editor file is plain text."""
    return _ANSI_SGR.sub("", text)


def _char_cells(ch: str) -> int:
    """Terminal cells one character occupies (wcwidth approximation)."""
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1


def _wrap_ansi_line(line: str, width: int) -> list[str]:
    """Hard-wrap one line, keeping ANSI codes so pager redraw stays aligned."""
    if width <= 0:
        return [line]
    wrapped: list[str] = []
    chunk: list[str] = []
    used = 0
    pos = 0
    while pos < len(line):
        match = _ANSI_SGR.match(line, pos)
        if match is not None:
            chunk.append(match.group(0))
            pos = match.end()
            continue
        ch = line[pos]
        pos += 1
        if ch == "\t":
            ch = " " * (8 - used % 8)
        chunk.append(ch)
        used += len(ch) if len(ch) > 1 else _char_cells(ch)
        if used >= width:
            wrapped.append("".join(chunk))
            chunk, used = [], 0
    if chunk or not wrapped:
        wrapped.append("".join(chunk))
    return wrapped


def _editor_command() -> list[str]:
    """Reading editor for long verdicts: GDDP_EDITOR > $VISUAL > $EDITOR > nvim."""
    for key in ("GDDP_EDITOR", "VISUAL", "EDITOR"):
        value = os.environ.get(key, "").strip()
        if value:
            return shlex.split(value)
    for name in ("nvim", "vim", "vi"):
        found = shutil.which(name)
        if found:
            return [found]
    return []


def _open_in_editor(text: str, title: str) -> None:
    """Open already-rendered output in the operator's editor; temp file is removed."""
    command = _editor_command()
    if not command:
        console.print(Text("no editor found — set $VISUAL or $EDITOR", style="yellow"))
        _import_module("terminal").getch()
        return
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-")[:48] or "view"
    fd, path = tempfile.mkstemp(prefix=f"gddp-{safe}-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_strip_ansi(text).rstrip("\n") + "\n")
        subprocess.run([*command, path], check=False)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _scroll_pause(text: str, title: str = "") -> str:
    """Hold rendered output on screen with scroll keys instead of one screenful.

    Evaluator verdicts run longer than a terminal; before this, every key but
    ``u`` dropped the operator back to the menu mid-read. Here: arrows,
    PgUp/PgDn, j/k, g/G scroll the view; ``o`` opens the same text in the
    operator's editor (neovim by default); ``u`` passes through so update
    flows keep working; any other key returns to the calling menu.
    Returns the exit keypress lowercased (same contract as ``_pause``).
    """
    terminal = _import_module("terminal")
    columns, rows = shutil.get_terminal_size((120, 40))
    width = max(columns, 20)
    lines: list[str] = []
    for raw in text.rstrip("\n").split("\n") or [""]:
        lines.extend(_wrap_ansi_line(raw, width) or [""])
    view_height = max(rows - 1, 3)
    scrollable = len(lines) > view_height
    editor = _editor_command()
    editor_name = Path(editor[0]).stem if editor else "editor"
    top = 0

    def paint() -> int:
        window = lines[top : top + view_height]
        if scrollable:
            position = f"lines {top + 1}–{top + len(window)}/{len(lines)} · "
        else:
            position = ""
        hint = (
            f"{position}↑↓/PgUp/PgDn scroll · o open in {editor_name}"
            " · u update · any other key returns"
        )
        sys.stdout.write("\n".join(window) + "\n")
        sys.stdout.write(f"\033[2m{hint}\033[0m\n")
        sys.stdout.flush()
        return len(window) + 1

    drawn = paint()
    with terminal.cbreak() as key_fd:
        while True:
            key = terminal.read_key(key_fd)
            if key == "\x03":
                raise KeyboardInterrupt
            if key == "":
                continue
            if key == "o":
                _open_in_editor(text, title)
                _clear_screen()
                drawn = paint()
                continue
            if not scrollable:
                return key.lower()
            moved = {
                "UP": -1, "k": -1,
                "DOWN": 1, "j": 1,
                "PAGE_UP": -view_height, "b": -view_height,
                "PAGE_DOWN": view_height, "f": view_height, " ": view_height,
                "HOME": -len(lines), "g": -len(lines),
                "END": len(lines), "G": len(lines),
            }.get(key)
            if moved is None:
                return key.lower()
            new_top = max(0, min(top + moved, len(lines) - view_height))
            if new_top != top:
                top = new_top
                terminal.clear_lines(drawn)
                drawn = paint()


def _page_view(render, title: str = "") -> str:
    """Show one rendered view, paged: scroll and ``o`` editor while it stays up.

    ``render`` either prints to stdout (captured with ANSI colors intact) or
    returns a string (subprocess output). Returns the exit keypress, matching
    ``_pause`` so existing menu flows keep their ``u``-update contracts.
    """
    if not console.is_terminal:
        result = render()
        if isinstance(result, str) and result:
            print(result)
        return _pause()
    capture = _TtyCapture()
    real_stdout = sys.stdout
    sys.stdout = capture
    try:
        result = render()
        if isinstance(result, str) and result:
            capture.write(result)
    finally:
        sys.stdout = real_stdout
    return _scroll_pause(capture.getvalue(), title)


def _plain_desc(description: str | Text | dict | None) -> str:
    """Strip Rich markup for fzf labels."""
    if _is_node_list_desc(description):
        chip = _verdict_chip(description.get("verdict"))
        bits = [b for b in (
            chip,
            str(description.get("graph") or ""),
            str(description.get("runtime") or ""),
            str(description.get("title") or ""),
        ) if b and b != "-"]
        return " · ".join(bits)
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
    items: list[tuple[str, str | Text | dict]],
) -> list[tuple[str, str]]:
    """(value, ANSI label) — status column first so rows scan as columns."""
    out: list[tuple[str, str]] = []
    for value, description in items:
        if _is_node_list_desc(description):
            graph = str(description.get("graph") or "-")
            runtime = str(description.get("runtime") or "-")
            title = str(description.get("title") or "")
            chip = _verdict_chip(description.get("verdict"))
            running = _is_running_state(runtime)
            mark = "▶" if running else " "
            bits = [
                _ansi(_ellipsize(graph, 16).ljust(16), _graph_status_style(graph), 16),
                _ansi(
                    (mark + _ellipsize(runtime.replace("_", " "), 15)).ljust(16),
                    "bold magenta" if running else _graph_status_style(runtime),
                    16,
                ),
            ]
            if chip:
                bits.append(_ansi(chip, _graph_status_style(chip), 4))
            else:
                bits.append(_ansi("-", "dim", 4))
            bits.append(str(value))
            if title:
                bits.append(title)
            out.append((value, "  ".join(bits)))
            continue
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
    items: list[tuple[str, str | Text | dict]],
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
    items: list[tuple[str, str | Text | dict]],
    *,
    preview_cmd: str | None = None,
    multi: bool = False,
    back_label: str = "back",
    fzf_header: str | None = None,
    refreshable: bool = False,
):
    """Rich paged list by default. Optional fzf via ``f``.

    multi=False → value | _MENU_BACK | _MENU_QUIT | _MENU_REFRESH
    multi=True  → value | list[str] | _MENU_BACK | _MENU_QUIT | _MENU_REFRESH
      (list when space/m has checked 2+ rows and Enter is pressed)
    """
    del fzf_header  # callers used to pass verbose fzf chrome; paged owns help now
    return _paged_menu(
        heading,
        items,
        back_label=back_label,
        fzf_preview_cmd=preview_cmd,
        fzf_multi=multi,
        refreshable=refreshable,
    )


_PICK_OTHER = "__other__"
_EXECUTOR_CHOICES = (
    "",
    "pi_rpc",
    "local_subprocess",
    "jules",
    "droid",
    "factory_mission",
)
_EVAL_THINKING_LEVELS = ("none", "low", "medium", "high", "xhigh")
_CANNED_REASONS = (
    "accepted",
    "retrying",
    "blocked on dependency",
    "deferred",
    "operator review",
    "fix applied",
)
def _pick_other_value(heading: str, *, current: str = "") -> str | object:
    """Type-in escape hatch after a picker row."""
    try:
        typed = Prompt.ask(
            Text(heading, style="cyan"),
            default=current,
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return _MENU_BACK
    return typed


def _pick_enum(
    heading: str,
    choices: list[tuple[str, str]],
    *,
    back_label: str = "back",
) -> str | object:
    """Single-value picker; Esc/q map to back/quit via ``_pick_list``."""
    return _pick_list(heading, choices, back_label=back_label)


def _pick_enum_or_other(
    heading: str,
    choices: list[tuple[str, str]],
    *,
    current: str = "",
    other_label: str = "type custom value…",
    back_label: str = "back",
) -> str | object:
    """Known values first; last row opens a type-in prompt."""
    items = list(choices)
    if other_label:
        items.append((_PICK_OTHER, other_label))
    picked = _pick_list(heading, items, back_label=back_label)
    if picked in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return picked
    if picked == _PICK_OTHER:
        return _pick_other_value(heading, current=current)
    return picked


def _recent_commit_shas(repo: Path | None, *, count: int = 8) -> list[str]:
    if repo is None or not repo.is_dir():
        return []
    proc = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H", f"-{count}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _collect_recent_reasons(
    *,
    project: str | None = None,
    node_id: str | None = None,
    limit: int = 8,
) -> list[str]:
    """Recent operator reasons from node status history when available."""
    if not project or not node_id:
        return []
    node_cli = _import_module("node_cli")
    hist_mod = getattr(node_cli, "_load_status_history_mod", lambda: None)()
    if hist_mod is None:
        return []
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError:
        runtime_root = None
    try:
        rows = hist_mod.load_history(
            project,
            node_id,
            runtime_root=runtime_root,
            strict=False,
        )
    except (OSError, ValueError):
        return []
    reasons: list[str] = []
    for row in reversed(rows):
        reason = str(row.get("reason") or "").strip()
        if not reason or reason in reasons:
            continue
        reasons.append(reason)
        if len(reasons) >= limit:
            break
    return reasons


def _pick_reason(
    heading: str = "reason",
    *,
    project: str | None = None,
    node_id: str | None = None,
    back_label: str = "back",
) -> str | object:
    """Recent + canned reasons; last row allows operator prose."""
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for reason in _collect_recent_reasons(project=project, node_id=node_id):
        if reason not in seen:
            seen.add(reason)
            items.append((reason, "recent"))
    for reason in _CANNED_REASONS:
        if reason not in seen:
            seen.add(reason)
            items.append((reason, "canned"))
    items.append((_PICK_OTHER, "type custom reason…"))
    picked = _pick_list(heading, items, back_label=back_label)
    if picked in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return picked
    if picked == _PICK_OTHER:
        return _pick_other_value(heading)
    return str(picked)


def _config_setting_value(key: str, current: str) -> str | object:
    """Picker for known settings; Prompt.ask for the rest."""
    if key == "GDDP_EXECUTOR_OVERRIDE":
        choices = [
            ("", "default (per-project)"),
            *[(value, value or "default") for value in _EXECUTOR_CHOICES if value],
        ]
        picked = _pick_enum_or_other(
            "executor override",
            choices,
            current=current,
            other_label="type custom executor…",
            back_label="config",
        )
    elif key == "GDDP_INTEGRITY_MODE":
        picked = _pick_enum(
            "integrity lane",
            [("on", "on"), ("off", "off")],
            back_label="config",
        )
    elif key == "GDDP_EVAL_LANES_DEFAULT":
        picked = _pick_enum(
            "eval lanes default",
            [("live", "live"), ("deterministic", "deterministic")],
            back_label="config",
        )
    elif key == "GDDP_EVAL_MODEL_CHEAP":
        preset = os.environ.get("GDDP_EVAL_MODEL_CHEAP") or cli_eval._EVAL_PRESETS["cheap"]
        choices = [("cheap", f"preset cheap → {preset}")]
        if current and current not in {preset, "cheap"}:
            choices.append((current, f"keep {current!r}"))
        picked = _pick_enum_or_other(
            "eval cheap model",
            choices,
            current=current or preset,
            other_label="type raw model id…",
            back_label="config",
        )
    elif key == "GDDP_EVAL_MODEL_EXPENSIVE":
        preset = (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip()
        choices: list[tuple[str, str]] = []
        if preset:
            choices.append(("expensive", f"preset expensive → {preset}"))
        if current and current not in {preset, "expensive"}:
            choices.append((current, f"keep {current!r}"))
        picked = _pick_enum_or_other(
            "eval expensive model",
            choices,
            current=current or preset,
            other_label="type raw model id…",
            back_label="config",
        )
    elif key == "GDDP_EVAL_THINKING_DEFAULT":
        picked = _pick_enum_or_other(
            "eval thinking default",
            [(level, level) for level in _EVAL_THINKING_LEVELS],
            current=current or "medium",
            other_label="type custom thinking level…",
            back_label="config",
        )
    else:
        try:
            picked = Prompt.ask(
                f"    [{key}] (enter = keep {current!r}, x = clear)",
                default=current,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if picked == "x":
            return ""
        return picked

    if picked in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return picked
    if key in {"GDDP_EVAL_MODEL_CHEAP", "GDDP_EVAL_MODEL_EXPENSIVE"}:
        if picked == "cheap":
            return os.environ.get("GDDP_EVAL_MODEL_CHEAP") or cli_eval._EVAL_PRESETS["cheap"]
        if picked == "expensive":
            return (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip()
    return str(picked)


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

    reason = _pick_reason(
        "shared reason",
        project=project,
        back_label="nodes",
    )
    if reason in {_MENU_BACK, _MENU_QUIT}:
        return reason
    if not str(reason).strip():
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


def _runtime_job_items(
    state_filter: str | None = None,
    project: str | None = None,
) -> list[tuple[str, str]]:
    """(job_id, scan label) from the runtime queue DB."""
    jobs_status = load_runtime_jobs_module()
    con = jobs_status.connect()
    try:
        q = (
            "SELECT job_id, node_id, queue_state, created_at, project_id FROM jobs"
        )
        clauses: list[str] = []
        params: list = []
        if state_filter:
            clauses.append("queue_state = ?")
            params.append(state_filter)
        if project:
            clauses.append("project_id = ?")
            params.append(project)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC"
        rows = con.execute(q, tuple(params)).fetchall()
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
    reason = _pick_reason("shared reason", back_label="jobs")
    if reason in {_MENU_BACK, _MENU_QUIT}:
        return reason
    if not str(reason).strip():
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


def _letter_keys(actions: dict[str, tuple[str, str | Text]]) -> tuple[str, ...]:
    """Displayed single-letter shortcuts — must stay in sync with handlers."""
    return tuple(key for key in actions if len(key) == 1 and not key.isdigit())


def _handled_letter_keys(
    actions: dict[str, tuple[str, str | Text]],
    handlers: dict[str, object] | None = None,
) -> tuple[str, ...]:
    """Letters the menu can actually act on: action keys plus navigation."""
    handled = set(_letter_keys(actions))
    if handlers:
        handled.update(
            key for key in handlers if len(key) == 1 and not key.isdigit()
        )
    # q/b are always selectable when shown; they are handled by the menu loop.
    return tuple(sorted(handled))


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


def _menu_columns() -> int:
    """Real pane width. Prefer ioctl over stale ``COLUMNS`` / Rich defaults."""
    explicit = getattr(console, "_width", None)
    if isinstance(explicit, int) and explicit > 0:
        width = getattr(console, "width", explicit)
        return width if isinstance(width, int) and width > 0 else explicit
    for fd in (1, 0):
        try:
            cols = os.get_terminal_size(fd).columns
        except OSError:
            continue
        if isinstance(cols, int) and cols > 0:
            return cols
    width = getattr(console, "width", None)
    return width if isinstance(width, int) and width > 0 else 80


def _emit_menu_lines(lines: list[Text]) -> int:
    """Print each menu row as one terminal row so in-place clear stays aligned.

    A wrap makes ``drawn`` short; the next ↑ then leaves the first row behind.
    Crop to width-1 so a full-width line cannot add an extra wrap row.
    """
    budget = max(1, _menu_columns() - 1)
    for line in lines:
        fitted = line.copy()
        fitted.truncate(budget, overflow="crop")
        console.print(fitted, overflow="crop", crop=True, no_wrap=True)
    return len(lines)


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
        drawn = _emit_menu_lines(lines)

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


def _format_list_description(description: str | Text | dict, room: int) -> Text:
    """One-line description: aligned columns for node rows; else status · title."""
    if _is_node_list_desc(description):
        return _format_node_columns(
            graph=str(description.get("graph") or "-"),
            runtime=str(description.get("runtime") or "-"),
            verdict=description.get("verdict"),
            title=str(description.get("title") or ""),
            room=room,
        )
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
    items: list[tuple[str, str | Text | dict]],
    checked: set[str],
):
    """Checked ids in list order. One id stays a scalar (opens that item)."""
    ordered = [value for value, _ in items if value in checked]
    if not ordered:
        return None
    return ordered if len(ordered) > 1 else ordered[0]


def _paged_menu_key_spec(
    *,
    page_count: int,
    fzf_ok: bool,
    refreshable: bool,
    fzf_multi: bool,
    back_label: str = "back",
) -> tuple[list[str], frozenset[str]]:
    """Help chrome and the letter keys it advertises. Displayed ⊆ handled."""
    help_bits = ["↑/↓"]
    letters: set[str] = set()
    if fzf_multi:
        help_bits.append("space")
        letters.add(" ")
    help_bits.extend(["enter", "1-9"])
    letters.update(str(i) for i in range(1, 10))
    if page_count > 1:
        help_bits.append("←/→ page")
        letters.update({"p", "n"})
    if fzf_ok:
        help_bits.append("f filter")
        letters.add("f")
    if refreshable:
        help_bits.append("r refresh")
        letters.add("r")
    help_bits.extend([f"b {back_label}", "q quit"])
    letters.update({"b", "q"})
    return help_bits, frozenset(letters)


def _paged_menu(
    heading: str,
    items: list[tuple[str, str | Text | dict]],
    *,
    page_size: int = 9,
    back_label: str = "back",
    fzf_preview_cmd: str | None = None,
    fzf_multi: bool = False,
    refreshable: bool = False,
):
    """Rich cursor list: ↑/↓, Enter, numbers; ←/→ page.

    Optional fzf step-in (does not replace this path):
      ``f`` / Ctrl-F  — fuzzy filter + preview
      (tab multi when ``fzf_multi`` is set)

    When ``fzf_multi`` is set, space / ``m`` toggles a checkbox on the
    current row. Enter with 2+ checked returns that list;
    Enter with 0–1 checked opens that one item.

    Static list content is redrawn in place (clear-to-end), not via a full
    terminal clear on every arrow key.
    """
    if not items:
        _clear_screen()
        console.print(Text("No items found.", style="yellow"))
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
        id_w = max((len(str(value)) for value, _ in visible), default=0)
        if width < 72:
            id_w = min(id_w, max(8, width // 3))
        node_list = bool(visible) and all(
            _is_node_list_desc(description) for _, description in visible
        )
        lines: list[Text] = [title]
        if node_list:
            header = Text()
            header.append("  #", style="dim")
            if fzf_multi:
                header.append("  ", style="dim")
            header.append(f"  {'ID':<{id_w}}", style="dim")
            used = 4 + 1 + (2 if fzf_multi else 0) + 2 + id_w + 2
            header.append("  ")
            header.append_text(_node_column_header(max(4, width - used)))
            lines.append(header)
        for offset, (value, description) in enumerate(visible, start=1):
            marker = "›" if offset - 1 == cursor else " "
            row = Text()
            row.append(f"{marker} {offset}", style="bold cyan")
            if fzf_multi:
                on = value in checked
                row.append(" ✓" if on else "  ", style="green" if on else "dim")
            shown_id = _ellipsize(str(value), id_w).ljust(id_w)
            row.append(f"  {shown_id}", style="bold")
            used = 4 + len(str(offset)) + (2 if fzf_multi else 0) + 2 + id_w + 2
            room = max(4, width - used)
            row.append("  ")
            row.append_text(_format_list_description(description, room))
            lines.append(row)

        # One help line — no stacked chrome. Letters here must be handled below.
        help_bits, _displayed = _paged_menu_key_spec(
            page_count=page_count,
            fzf_ok=fzf_ok,
            refreshable=refreshable,
            fzf_multi=fzf_multi,
            back_label=back_label,
        )
        lines.append(Text("  " + " · ".join(help_bits), style="dim"))

        if first_paint:
            _clear_screen()
            first_paint = False
        else:
            clear_lines(drawn)

        drawn = _emit_menu_lines(lines)

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
            # f / Ctrl-F — opt-in fzf. Cancel returns to this menu.
            if choice in {"f", "F", "\x06"} and fzf_ok:
                selected = _run_fzf(
                    heading,
                    items,
                    preview_cmd=fzf_preview_cmd,
                    multi=fzf_multi,
                )
                if selected:
                    if fzf_multi:
                        picked = _checked_values(items, set(selected))
                        if picked is not None:
                            return picked
                    return selected[0]
                first_paint = True  # fzf wrecked the screen; full redraw
                break
            if choice in {"f", "F", "\x06"} and not fzf_ok:
                console.print(
                    Text("  fzf not installed (brew install fzf)", style="yellow")
                )
                drawn += 1
                continue
            if refreshable and choice in {"r", "R"}:
                return _MENU_REFRESH
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
    reason = _pick_reason(
        "reason",
        project=project,
        node_id=node_id,
        back_label="review",
    )
    if reason in {_MENU_BACK, _MENU_QUIT}:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not str(reason).strip():
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
        "b": ("back", "leave the working tree dirty"),
        "n": ("no", "leave the working tree dirty"),
    }
    choice = _menu_choice(actions, default="p")
    if choice in {"s", "b", "n"}:
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
        "b": ("back", "leave repo and graph unchanged"),
    }
    # Cursor starts on default ``y``; letters still jump. No silent Enter-abort.
    choice = _menu_choice(actions, default="y")
    if choice in {"n", "b"}:
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
    allow_batch: bool = False,
) -> str:
    """Pick a node-review action with split arrow roles.

    ↑/↓ move the action cursor (Enter activates). ←/→ mean previous/next
    sibling when the project has more than one node. Letter keys still work
    as direct shortcuts. Escape maps to back.
    """
    terminal = _import_module("terminal")
    getch = terminal.getch
    clear_lines = getattr(terminal, "clear_lines", lambda _n: None)

    # Primary work only. contract / trace / diff live under "more".
    # Horizontal sibling nav (←/→) is separate chrome, not a peer option.
    selectables: list[tuple[str, str, str]] = [
        ("e", "evaluation", "verdict, why, criteria — current job evidence"),
        ("v", "evaluator", "evaluator hub for this node"),
        ("u", "update", "set graph status (your decision)"),
        ("x", "reject + retry", "return to ready; retry with your fix-list"),
        ("m", "more", "contract · diff · trace"),
        ("b", "back", "choose another node"),
        ("q", "quit", ""),
    ]
    if allow_batch:
        selectables.insert(
            2,
            ("s", "same status", "one status + reason for this set"),
        )
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
        drawn = _emit_menu_lines(lines)

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


def _confirm_reject_and_retry(project: str, node_id: str) -> int:
    """Record human rejection, return graph truth to ready, and retry the job."""
    node_cli = _import_module("node_cli")
    try:
        evidence = node_cli.fetch_runtime_evidence(ROOT, project, node_id)
    except Exception as exc:
        console.print(Text(f"Could not load runtime evidence: {exc}", style="red"))
        return 1
    job_id = getattr(evidence, "job_id", None)
    queue_state = getattr(evidence, "queue_state", None)
    if not job_id or queue_state != "awaiting_review":
        console.print(
            Text(
                f"Reject + retry requires an awaiting-review job; current state is "
                f"{queue_state or 'missing'}.",
                style="yellow",
            )
        )
        return 1

    _clear_screen()
    console.rule(f"{project} / {node_id} · reject + retry", style="bold yellow")
    actions = {
        "y": ("yes", "reject this result and dispatch the next attempt"),
        "n": ("no", "leave graph and runtime state unchanged"),
    }
    if _menu_choice(actions, default="n") != "y":
        console.print(Text("Unchanged.", style="dim"))
        return 1
    reason = _pick_reason(
        "fix-list / reason",
        project=project,
        node_id=node_id,
        back_label="review",
    )
    if reason in {_MENU_BACK, _MENU_QUIT}:
        reason = ""
    if not str(reason).strip():
        console.print(Text("Unchanged — a retry fix-list is required.", style="yellow"))
        return 1

    rc = node_cli.cmd_set_status(
        project=project,
        node_id=node_id,
        status="ready",
        yes=True,
        reason=str(reason),
    )
    if rc != 0:
        return rc
    _offer_publish_graph_status(project, node_id, "ready", reason)
    return run_runtime_jobs([
        "retry",
        str(job_id),
        "--reason",
        reason,
        "--yes",
    ])


def _node_review_menu(
    project: str,
    node_id: str,
    node_ids: list[str] | None = None,
    *,
    allow_batch: bool = False,
):
    """Review one node and optionally update its human-owned graph status.

    When ``node_ids`` is the project's ordered list:
      ←/→  previous / next sibling node
      ↑/↓  move action cursor; Enter opens the highlighted action
    Letter keys remain direct shortcuts.
    ``allow_batch`` adds ``s`` same-status for the current sibling set.
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
        choice = _node_review_pick_action(
            has_siblings=len(siblings) > 1,
            allow_batch=allow_batch,
        )
        if choice == "LEFT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx - 1) % len(siblings)]
            continue
        if choice == "RIGHT":
            idx = siblings.index(node_id)
            node_id = siblings[(idx + 1) % len(siblings)]
            continue
        if choice == "s" and allow_batch:
            outcome = _batch_node_status(project, siblings)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue
        if choice == "q":
            return _MENU_QUIT
        if choice == "p":
            return "projects"
        if choice == "b":
            return _MENU_BACK
        if choice == "e":
            _clear_screen()
            if _page_view(
                lambda: node_cli.cmd_show(
                    project=project,
                    node_id=node_id,
                    trace=False,
                    view="evaluation",
                ),
                title=f"evaluation-{project}-{node_id}",
            ) != "u":
                continue
        elif choice == "v":
            outcome = interactive_eval_hub(project, node_id)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
            continue
        elif choice == "x":
            _confirm_reject_and_retry(project, node_id)
            _pause()
            continue
        elif choice == "m":
            more = {
                "c": ("contract", "intent, dependencies, acceptance criteria"),
                "d": ("diff", "what the attempt changed + merge state"),
                "t": ("trace", "full evaluator and job history"),
                "b": ("back", ""),
                "q": ("quit", ""),
            }
            _clear_screen()
            console.print(Text("more", style="bold").append(
                f"  ·  {node_id}", style="dim"
            ))
            more_choice = _menu_choice(more, default="c")
            if more_choice == "q":
                return _MENU_QUIT
            if more_choice == "b":
                continue
            _clear_screen()
            if more_choice == "c":
                paged = _page_view(
                    lambda: node_cli.cmd_show(
                        project=project,
                        node_id=node_id,
                        trace=False,
                        view="contract",
                    ),
                    title=f"contract-{project}-{node_id}",
                )
            elif more_choice == "t":
                paged = _page_view(
                    lambda: node_cli.cmd_show(
                        project=project,
                        node_id=node_id,
                        trace=True,
                        view="evaluation",
                    ),
                    title=f"trace-{project}-{node_id}",
                )
            else:
                paged = _page_view(
                    lambda: _render_evaluation_and_diff(project, node_id),
                    title=f"diff-{project}-{node_id}",
                )
            if paged != "u":
                continue
        elif choice != "u":
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

    Default path is the rich paged menu. ``f`` steps into fzf (filter/preview;
    tab multi on this list). Space / ``m`` checks rows; Enter with 2+ checked
    reviews that set (``s`` still does one status for all).
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
                refreshable=True,
            )
            if project is _MENU_REFRESH:
                continue
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
                title = str(doc.get("title") or (entry or {}).get("title") or "")
                node_items.append((
                    node_id,
                    _node_list_desc(
                        graph_status,
                        _runtime_label(queue_state, job_status),
                        title,
                        verdict,
                    ),
                ))

            picked = _pick_list(
                f"nodes · {project}",
                node_items,
                preview_cmd=_node_preview_cmd(project),
                multi=True,
                back_label="projects",
                refreshable=True,
            )
            if picked is _MENU_REFRESH:
                continue
            if picked is _MENU_QUIT:
                return _MENU_QUIT
            if picked is _MENU_BACK:
                if fixed_project:
                    return _MENU_BACK
                break
            ordered_ids = [nid for nid, _ in node_items]
            if isinstance(picked, list) and len(picked) > 1:
                outcome = _node_review_menu(
                    project,
                    picked[0],
                    node_ids=picked,
                    allow_batch=True,
                )
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
    cli_status.show_status(getattr(args, "project", None))


def cmd_node_frontier(args):
    """Read-only frontier view: ready / in-flight / blocked / unlocks / drift.

    Uses the same derive() + render_text() the dispatch gate and interactive
    browse rely on, surfaced as a node subcommand so the graph's dependency
    and frontier state is reviewable non-interactively.
    """
    project = getattr(args, "project", None)
    if not project:
        raise SystemExit("error: --project required for node frontier")
    _show_frontier([project])


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


def run_runtime_jobs(argv: list[str], *, capture: bool = False) -> int | str:
    """Delegate one jobs invocation through runtime's job-only CLI boundary.

    ``capture=True`` returns the command's output as text (stderr appended on
    failure) for paged interactive views instead of an exit code.
    """
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
    if capture:
        proc = subprocess.run(
            command, env=env, check=False,
            capture_output=True, text=True,
        )
        text = proc.stdout
        if proc.returncode != 0 and proc.stderr.strip():
            text += ("\n" if text else "") + proc.stderr.strip()
        return text
    return subprocess.run(command, env=env, check=False).returncode


def run_graph_delivery(action: str, project: str, *, delete: bool = False) -> int:
    """Publish one graph's delivery commit, or list/retire its transport refs.

    Delegates to runtime's graph_delivery.py (never runs in-process —
    mutation stays behind the same subprocess boundary as jobs/verify).
    """
    try:
        runtime_root = resolve_runtime_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    command = [
        runtime_python(runtime_root),
        str(runtime_root / "scripts" / "runtime" / "graph_delivery.py"),
        action,
        project,
        "--config-root", str(ROOT),
        *(["--delete"] if delete else []),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_root)
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
    reason = _pick_reason("reason", back_label="jobs")
    if reason in {_MENU_BACK, _MENU_QUIT}:
        console.print()
        console.print(Text("Unchanged — reason required.", style="dim"))
        return 1
    if not str(reason).strip():
        console.print(Text("Unchanged — reason required.", style="yellow"))
        return 1
    try:
        jobs_status = load_runtime_jobs_module()
        return jobs_status.apply_state_change(ref=ref, state=state, reason=str(reason))
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
        "b": ("back", ""),
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

        def _show_evaluation():
            console.print(Text("evaluation", style="bold"))
            if row.get("job_id") and row.get("source") == "result":
                return run_runtime_jobs(["show", str(row["job_id"])], capture=True)
            evaluations.print_evaluation_detail(row)
            return None

        _page_view(_show_evaluation, title=f"evaluation-{row.get('job_id') or row.get('node_id') or 'detail'}")


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


def interactive_jobs(project: str | None = None):
    """Review and update runtime jobs inside the human-operated menu.

    open/update use the rich paged list; ``f`` filters via fzf, ``m`` multi-
    selects for batch queue-state changes. Empty queue falls back to typing an id.
    When ``project`` is set (graph hub), only that graph's jobs are shown.
    """
    state_filter: str | None = None
    back_name = "graph" if project else "graphs"
    actions = {
        "l": ("live", "running executors — refresh + events"),
        "r": ("refresh", "reload this job list"),
        "a": ("awaiting review", "human review queue"),
        "e": ("evaluations", "evaluator result summary"),
        "o": ("open", "pick a job (f = filter)"),
        "u": ("update", "set queue state (space checks)"),
        "b": (back_name, ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        if project and state_filter:
            heading = f"jobs · {project} · {state_filter}"
        elif project:
            heading = f"jobs · {project}"
        elif state_filter:
            heading = f"jobs · {state_filter}"
        else:
            heading = "jobs"
        console.print(Text(heading, style="bold"))
        try:
            listed = _runtime_job_items(state_filter, project=project)
        except RuntimeError as exc:
            console.print(Text(f"ERROR: {exc}", style="red"))
            listed = []
        if listed:
            for job_id, label in listed[:40]:
                state = label.split("  ", 1)[0]
                line = Text()
                line.append(f"{job_id}  ", style="dim")
                line.append(state, style=_graph_status_style(state))
                rest = label[len(state):]
                if rest:
                    line.append(rest)
                console.print(line)
            if len(listed) > 40:
                console.print(Text(f"  … {len(listed) - 40} more", style="dim"))
        else:
            console.print(Text("No jobs." + (
                f" (project={project})" if project else ""
            ), style="dim"))
        console.print()

        choice = _menu_choice(actions, default="l" if not state_filter else "r")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "l":
            interactive_watch(project)
            continue
        if choice == "r":
            state_filter = None
            continue
        if choice == "a":
            state_filter = "awaiting_review"
            continue
        if choice == "e":
            _clear_screen()

            def _show_results():
                console.print(Text("evaluator results", style="bold"))
                return run_runtime_jobs(["results"], capture=True)

            _page_view(_show_results, title="evaluator-results")
            continue

        try:
            job_items = _runtime_job_items(state_filter, project=project)
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
                continue
            _clear_screen()

            def _show_job():
                console.print(Text(f"job · {ref}", style="bold"))
                return run_runtime_jobs(["show", ref], capture=True)

            _page_view(_show_job, title=f"job-{ref}")
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
    command = getattr(args, "jobs_command", None)
    if command == "live":
        # Same surface as `gddp watch` — packaged under jobs for discoverability.
        return cmd_watch(args)
    argv = []
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
    elif command == "retry":
        argv.extend([args.ref, "--reason", args.reason])
        if args.yes:
            argv.append("--yes")
    elif command == "adopt":
        argv.extend(["--project", args.project, "--node", args.node, "--commit", args.commit])
        if args.base:
            argv.extend(["--base", args.base])
        if args.executor:
            argv.extend(["--executor", args.executor])
        if args.dry_run:
            argv.append("--dry-run")
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
    table.add_row("menu", "pick a graph → its truth → nodes · dispatch · live", "gddp")
    table.add_row("timeline", "what happened to a graph, in order, in words", "gddp timeline <project>")
    table.add_row("live", "running executors, diffs, events stream", "gddp watch / gddp jobs live")
    table.add_row("node", "graph truth, authoring, runtime/evaluator join", "gddp node list")
    table.add_row("jobs", "runtime queue, results, and audited state changes", "gddp jobs list")
    table.add_row("evaluations", "evaluator receipts, verdicts, and timing", "gddp evaluations")
    table.add_row("verify", "node evaluation", "gddp verify node")
    table.add_row("project", "project graph creation and validation", "gddp project -h")
    table.add_row("obsidian", "graph export", "gddp obsidian export")
    console.print(table)
    controls = " · ".join(
        f"{key} {name}" for key, (name, _desc) in _front_page_actions().items()
        if key in _front_page_handlers()
    )
    console.print(Text(
        f"TTY: graph picker first; Esc for the plane ({controls}). "
        "Shell: `gddp timeline <project>`, `gddp watch`, `gddp <group> -h`.",
        style="dim",
    ))


def _graph_more_menu(project: str):
    """Secondary graph tools — not on equal footing with nodes/dispatch/live."""
    actions = {
        "j": ("jobs", "runtime jobs for this graph"),
        "f": ("frontier", "ready / in flight / blocked"),
        "s": ("status", "completion + node phases"),
        "v": ("validate", "check this graph definition"),
        "t": ("timeline", "what happened on this graph"),
        "e": ("evaluations", "evaluator receipts"),
        "d": ("deliver", "publish review branch / retire transport refs"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    while True:
        _clear_screen()
        console.print(
            Text("more", style="bold")
            .append(f"  ·  {project}", style="dim")
        )
        choice = _menu_choice(actions, default="j")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        try:
            if choice == "j":
                outcome = interactive_jobs(project)
            elif choice == "f":
                outcome = interactive_frontier(project)
            elif choice == "s":
                outcome = interactive_status(project)
            elif choice == "v":
                outcome = interactive_validate(project)
            elif choice == "t":
                outcome = _interactive_timeline(project)
            elif choice == "e":
                outcome = interactive_evaluations()
            elif choice == "d":
                outcome = interactive_graph_delivery(project)
            else:
                outcome = _MENU_BACK
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
        except SystemExit:
            if choice == "v":
                _pause()
        except KeyboardInterrupt:
            return _MENU_BACK


def _graph_hub_actions() -> dict[str, tuple[str, str]]:
    return {
        "n": ("nodes", "review evidence and update graph truth"),
        "d": ("dispatch", "send ready work on this graph"),
        "w": ("live", "running executors for this graph"),
        "m": ("more", "jobs · frontier · status · validate · evaluations"),
        "b": ("graphs", ""),
        "q": ("quit", ""),
    }


def _graph_hub_handlers() -> dict[str, object]:
    return {
        "n": interactive_nodes,
        "d": interactive_dispatch,
        "w": interactive_watch,
        "m": _graph_more_menu,
    }


_HUB_RECENT_ENTRIES = 8
_HUB_MAX_WARNINGS = 6


def _print_graph_truth(project: str) -> None:
    """Opening a graph shows what is true and what is wrong before any key."""
    timeline = _import_module("timeline")
    try:
        runtime_root: Path | None = resolve_runtime_root()
    except RuntimeError:
        runtime_root = None
    try:
        tl = timeline.build(
            project, None,
            config_root=ROOT, runtime_root=runtime_root,
            repo_path=_resolve_repo_for_project(project), attempts=[],
        )
        graph = timeline.read_graph(ROOT, project)
    except (FileNotFoundError, KeyError, OSError) as exc:
        console.print(Text(f"  truth unavailable: {exc}", style="red"))
        return
    # Everything is one line, truncated to the terminal, and the whole block
    # is budgeted so the action keys stay on screen. Warnings come first.
    size = shutil.get_terminal_size((100, 40))
    one = {"overflow": "ellipsis", "no_wrap": True, "width": size.columns}
    menu_rows = len(_graph_hub_actions()) + 2          # keys + help line
    available = size.lines - menu_rows - 1             # minus trailing newline
    skeleton = len(graph["nodes"]) + 7                 # header, label, nodes, blank, wrong-label, blank, events line, blank
    warn_room = max(1, available - skeleton)
    warnings = tl.warnings[:min(_HUB_MAX_WARNINGS, warn_room)]
    hidden_warnings = len(tl.warnings) - len(warnings)
    if hidden_warnings and len(warnings) == warn_room and len(warnings) > 1:
        warnings = warnings[:-1]
        hidden_warnings += 1
    room = available - skeleton - len(warnings) - (1 if hidden_warnings else 0) - 1
    show_recent = room >= 2
    recent = tl.entries[-min(_HUB_RECENT_ENTRIES, room):] if show_recent else []
    total = len(tl.entries)

    console.print(Text("graph says now:", style="bold"))
    for nid, info in graph["nodes"].items():
        row = Text(f"  {nid:<32} ")
        row.append(f"{info['status']:<12}", style=_graph_status_style(info["status"]))
        row.append(info.get("title") or "", style="dim")
        console.print(row, **one)
    console.print()
    if warnings:
        console.print(Text(f"what is wrong ({len(tl.warnings)}):", style="bold red"))
        for w in warnings:
            console.print(Text(f"  ! {w}", style="red"), **one)
        if hidden_warnings:
            console.print(Text(f"  … {hidden_warnings} more", style="red"), **one)
    else:
        console.print(Text("what is wrong: nothing detected from this host", style="bold green"))
    console.print()
    if show_recent:
        head = "what happened" + (f" (last {len(recent)} of {total})" if total > len(recent) else "")
        console.print(Text(head + ":", style="bold"))
        for e in recent:
            line = Text(f"  {e.ts.strftime('%m-%d %H:%MZ')}  ")
            line.append(f"{e.who:<10}", style="cyan")
            line.append(e.text, style="bold red" if "OUTSIDE GDDP" in e.text else "")
            console.print(line, **one)
        if total == 0:
            console.print(Text("  (nothing recorded that this host can see)", style="dim"))
    unseen = f"{len(tl.notes)} thing(s) this host cannot see" if tl.notes else ""
    footer = f"  {total} events"
    if unseen:
        footer += f" · {unseen}"
    console.print(Text(footer, style="dim"), **one)
    console.print()


def interactive_graph_hub(project: str):
    """One graph: its truth on screen, then nodes, dispatch, live. Rest under more."""
    actions = _graph_hub_actions()
    while True:
        _clear_screen()
        console.print(
            Text("graph", style="bold")
            .append(f"  ·  {project}", style="bold cyan")
        )
        _print_graph_truth(project)
        try:
            choice = _menu_choice(actions, default="n")
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        try:
            if choice == "n":
                outcome = interactive_nodes(project)
            elif choice == "d":
                outcome = interactive_dispatch(project)
            elif choice == "w":
                outcome = interactive_watch(project)
            elif choice == "m":
                outcome = _graph_more_menu(project)
            else:
                outcome = _MENU_BACK
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
        except SystemExit:
            pass
        except KeyboardInterrupt:
            return _MENU_BACK


































def _front_page_actions() -> dict[str, tuple[str, str]]:
    """Plane page, one step back from the graph picker: everything that is
    about the whole plane rather than one graph."""
    return {
        "w": ("live", "every running executor, across all graphs"),
        "h": ("heartbeat", "arm/disarm the control plane (intake + heartbeat)"),
        "c": ("config", "executor & evaluator settings (runtime/settings.env)"),
        "b": ("graphs", ""),
        "q": ("quit", ""),
    }


def _front_page_handlers() -> dict[str, object]:
    return {
        "w": interactive_watch,
        "h": interactive_heartbeat,
        "c": interactive_config,
    }


def _eval_hub_actions() -> dict[str, tuple[str, str]]:
    return {
        "r": ("run", "run the live judge with current knobs"),
        "k": ("knobs", "per-run overrides for the next run"),
        "c": ("config", "resolved evaluator settings"),
        "i": ("instructions", "what the judge is told / offered-vs-read"),
        "h": ("runs", "receipts for this node"),
        "s": ("show", "latest run for this node"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }


def _eval_hub_handlers() -> dict[str, object]:
    return {
        "r": _run_live_eval,
        "k": _eval_knob_picker,
        "c": _render_eval_config,
        "i": _render_eval_instructions,
        "h": _render_eval_runs,
        "s": _render_eval_show,
    }


def _load_yaml_mapping(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _human_eval_path(path: str) -> str:
    text = str(path or "")
    if text.startswith("UNAVAILABLE"):
        return text
    name = Path(text).name or text
    normalized = text.replace("\\", "/")
    if "gddp-eval-wt-" in normalized:
        return f"{name}  (worktree)"
    return name


def _offered_vs_read_lines(canonical_context, context_coverage) -> list[str]:
    """Pure formatter: offered pointers + per-lane accessed/not-observed files."""
    offered: list[str] = []
    for key, val in (canonical_context or {}).items():
        if not isinstance(val, str):
            continue
        if val.startswith("UNAVAILABLE"):
            offered.append(f"{key} UNAVAILABLE")
            continue
        human = _human_eval_path(val)
        if key in {"readme", "project_brief"}:
            offered.append(human)
        else:
            offered.append(f"{key}={human}")
    lines = ["Offered: " + (" · ".join(offered) if offered else "—")]

    def _lane_line(name: str, lane) -> str:
        if lane == "not_run" or lane is None:
            return f"Read ({name}): not run"
        if not isinstance(lane, dict):
            return f"Read ({name}): —"
        accessed = [_human_eval_path(p) for p in (lane.get("accessed_paths") or [])]
        missing = [_human_eval_path(p) for p in (lane.get("not_observed_paths") or [])]
        bits = [f"{p} ✓" for p in accessed] + [f"{p} ✗" for p in missing]
        if not bits:
            return f"Read ({name}): — (none)"
        return f"Read ({name}): " + " · ".join(bits)

    cov = context_coverage or {}
    lines.append(_lane_line("criteria", cov.get("criteria")))
    lines.append(_lane_line("integrity", cov.get("integrity")))
    if cov.get("overall"):
        lines.append(f"Overall coverage: {cov.get('overall')}")
    return lines


def _offered_canonical_pointers(project: str, node_id: str, repo: Path | None) -> dict[str, str]:
    """Local reimplementation of runtime canonical pointers. Do not import runtime."""
    pointers: dict[str, str] = {}
    if repo is not None:
        repo = Path(repo)
        for name, filename in (("readme", "README.md"), ("project_brief", "PROJECT-BRIEF.md")):
            found = None
            for variant in (filename, filename.upper(), filename.lower()):
                path = repo / variant
                if path.is_file():
                    found = str(path)
                    break
            pointers[name] = found or f"UNAVAILABLE: {repo / filename} does not exist"
    else:
        pointers["readme"] = "UNAVAILABLE: no repo"
        pointers["project_brief"] = "UNAVAILABLE: no repo"

    project_yaml = ROOT / "graphs" / project / "project.yaml"
    pdata = _load_yaml_mapping(project_yaml)
    nodes = pdata.get("nodes") or []
    first_id = ""
    if nodes:
        first = nodes[0]
        first_id = first.get("id", "") if isinstance(first, dict) else str(first)
    nodes_dir = ROOT / "graphs" / project / "nodes"
    if first_id:
        path = nodes_dir / f"{first_id}.yaml"
        pointers["foundational_node"] = (
            str(path) if path.is_file() else f"UNAVAILABLE: {path} does not exist"
        )
    else:
        pointers["foundational_node"] = "UNAVAILABLE: no first node id in project.yaml"

    ndata = _load_yaml_mapping(nodes_dir / f"{node_id}.yaml")
    neighbor_ids = list(ndata.get("depends_on") or []) + list(ndata.get("unlocks") or [])
    for nid in neighbor_ids:
        path = nodes_dir / f"{nid}.yaml"
        pointers[f"neighbor:{nid}"] = (
            str(path) if path.is_file() else f"UNAVAILABLE: {path} does not exist"
        )
    return pointers


def _hydrate_eval_row(row: dict) -> dict:
    """Replace a DB summary `check` with the on-disk receipt when needed."""
    check = row.get("check") if isinstance(row.get("check"), dict) else {}
    if check.get("canonical_context"):
        return row
    receipt_path = row.get("receipt_path")
    if not receipt_path:
        return row
    node_cli = _import_module("node_cli")
    loader = getattr(node_cli, "load_receipt_file", None)
    full = loader(Path(str(receipt_path))) if callable(loader) else None
    if not isinstance(full, dict):
        return row
    return {**row, "check": full}


def _load_receipts_for_node(project: str, node_id: str) -> list[dict]:
    evaluations = _import_module("evaluations")
    db_path, receipt_root = _evaluation_sources()
    rows = evaluations.load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
    out = []
    for row in rows:
        if row.get("project_id") != project or row.get("node_id") != node_id:
            continue
        receipt_path = row.get("receipt_path")
        knobs = _load_eval_knobs_sidecar(receipt_path) if receipt_path else {}
        out.append(_hydrate_eval_row({**row, "knobs": knobs}))
    return out


def _render_eval_config() -> None:
    """Read-only resolved evaluator settings (not the settings writer)."""
    try:
        knobs = cli_eval._resolve_eval_knobs()
    except cli_eval.EvalKnobError as exc:
        console.print(Text(str(exc), style="red"))
        return
    cheap = (os.environ.get("GDDP_EVAL_MODEL_CHEAP") or cli_eval._EVAL_PRESETS["cheap"]).strip()
    expensive = (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip() or "UNSET"
    table = Table(title="evaluator config", box=box.SIMPLE, show_header=False)
    table.add_column("key", style="bold cyan")
    table.add_column("value")
    table.add_row("model", str(knobs.get("model") or "-"))
    table.add_row("preset", str(knobs.get("preset") or "-"))
    table.add_row("thinking", str(knobs.get("thinking") or "-"))
    table.add_row("integrity", str(knobs.get("integrity") or "-"))
    table.add_row("lanes", str(knobs.get("lanes") or "-"))
    table.add_row("cheap →", cheap)
    table.add_row("expensive →", expensive)
    table.add_row("key cmd", os.environ.get("GDDP_DEEPSEEK_KEY_CMD") or "-")
    table.add_row("settings", str(SETTINGS_FILE))
    console.print(table)


def _render_eval_instructions(
    project: str,
    node_id: str,
    receipt: dict | None = None,
) -> None:
    node_doc = _load_yaml_mapping(ROOT / "graphs" / project / "nodes" / f"{node_id}.yaml")
    project_doc = _load_yaml_mapping(ROOT / "graphs" / project / "project.yaml")
    blueprint = project_doc.get("blueprint") if isinstance(project_doc.get("blueprint"), dict) else {}
    console.print(Text(f"instructions · {project} / {node_id}", style="bold"))
    if receipt is None:
        console.print(Text("preflight — offered only", style="yellow"))
    console.print()
    console.print(Text("node contract", style="bold cyan"))
    why = node_doc.get("why") or "-"
    console.print(f"  why: {why}")
    criteria = node_doc.get("acceptance_criteria") or []
    if criteria:
        console.print("  acceptance:")
        for item in criteria:
            if isinstance(item, dict):
                console.print(f"    - {item.get('id')}: {item.get('criterion')}")
            else:
                console.print(f"    - {item}")
    constraints = node_doc.get("constraints") or []
    if constraints:
        console.print("  constraints:")
        for item in constraints:
            console.print(f"    - {item}")
    console.print()
    console.print(Text("project vision", style="bold cyan"))
    console.print(f"  {blueprint.get('vision') or '-'}")
    if blueprint.get("architecture_notes"):
        console.print(f"  notes: {blueprint.get('architecture_notes')}")

    if receipt:
        det = receipt.get("deterministic") if isinstance(receipt.get("deterministic"), dict) else {}
        console.print()
        console.print(Text("deterministic evidence", style="bold cyan"))
        for item in det.get("criteria") or []:
            if not isinstance(item, dict):
                continue
            console.print(
                f"  {item.get('id')}: {item.get('status')} "
                f"({item.get('method') or '-'})"
            )
            if item.get("evidence"):
                console.print(f"    evidence: {item.get('evidence')}")
        mismatches = det.get("criteria_mismatches") or []
        if mismatches:
            console.print("  mismatches:")
            for item in mismatches:
                if isinstance(item, dict):
                    cid = item.get("criterion_id") or item.get("id") or "-"
                    kind = item.get("kind") or item.get("mismatch_kind") or "-"
                    console.print(f"    - {cid}: {kind}")
                else:
                    console.print(f"    - {item}")
        if det.get("artifacts_present") is not None:
            console.print(f"  artifacts_present: {det.get('artifacts_present')}")
        subject = det.get("subject_diff") if isinstance(det.get("subject_diff"), dict) else {}
        if subject:
            console.print(
                f"  subject-diff: {subject.get('status')} "
                f"{str(subject.get('base') or '')[:8]}..{str(subject.get('tip') or '')[:8]} "
                f"files={subject.get('file_count')}"
            )
            for item in subject.get("files") or []:
                if isinstance(item, dict):
                    console.print(f"    {item.get('status') or '-'} {item.get('path') or '-'}")
                else:
                    console.print(f"    {item}")
        console.print()
        console.print(Text("canonical offered-vs-read", style="bold cyan"))
        for line in _offered_vs_read_lines(
            receipt.get("canonical_context") or {},
            receipt.get("context_coverage") or {},
        ):
            console.print(f"  {line}")
    else:
        repo = _resolve_repo_for_project(project)
        pointers = _offered_canonical_pointers(project, node_id, repo)
        console.print()
        console.print(Text("canonical offered (preflight)", style="bold cyan"))
        for key, val in pointers.items():
            console.print(f"  {key}: {_human_eval_path(val) if not str(val).startswith('UNAVAILABLE') else val}")


def _render_eval_show(row: dict) -> None:
    check = row.get("check") if isinstance(row.get("check"), dict) else {}
    knobs = row.get("knobs") if isinstance(row.get("knobs"), dict) else {}
    timing = check.get("evaluation_timing") if isinstance(check.get("evaluation_timing"), dict) else {}
    integrity = check.get("integrity") if isinstance(check.get("integrity"), dict) else {}
    console.print(Text(
        f"run · {row.get('project_id')}/{row.get('node_id')} · {row.get('job_id') or '-'}",
        style="bold",
    ))
    console.print(f"  verdict           : {row.get('verdict') or check.get('verdict') or '-'}")
    console.print(f"  criteria verdict  : {check.get('criteria_verdict') or '-'}")
    console.print(f"  confidence        : {check.get('criteria_confidence') or '-'}")
    console.print(f"  when              : {row.get('sort_at') or '-'}")
    console.print(f"  wall              : {timing.get('wall_s') if timing else row.get('wall_s')}")
    crit_timing = timing.get("criteria") if isinstance(timing.get("criteria"), dict) else {}
    integ_timing = timing.get("integrity") if isinstance(timing.get("integrity"), dict) else {}
    console.print(
        f"  tools             : c={crit_timing.get('tool_calls', 0)} "
        f"i={integ_timing.get('tool_calls', 0)}"
    )
    if crit_timing or integ_timing:
        console.print(
            f"  lanes             : criteria {crit_timing.get('status') or '-'} "
            f"· integrity {integ_timing.get('status') or '-'}"
        )
    console.print(f"  commit            : {check.get('evaluated_commit_sha') or '-'}")
    console.print(f"  base              : {check.get('expected_base_commit_sha') or knobs.get('base') or '-'}")
    console.print(
        f"  model             : {knobs.get('preset') + '/' if knobs.get('preset') else ''}"
        f"{knobs.get('model') or '-'}"
    )
    console.print(
        f"  knobs             : thinking={knobs.get('thinking') or '-'} "
        f"integrity={knobs.get('integrity') or '-'} lanes={knobs.get('lanes') or '-'}"
    )
    if integrity:
        console.print(
            f"  integrity         : {integrity.get('verdict')} "
            f"preserved={integrity.get('intent_preserved')}"
        )
        if integrity.get("reasoning"):
            console.print(f"    {integrity.get('reasoning')}")
    if check.get("required_next_action"):
        console.print(f"  next              : {check.get('required_next_action')}")
    if row.get("receipt_path"):
        console.print(f"  receipt           : {row.get('receipt_path')}")
    console.print()
    for line in _offered_vs_read_lines(
        check.get("canonical_context") or {},
        check.get("context_coverage") or {},
    ):
        console.print(f"  {line}")
    det = check.get("deterministic") if isinstance(check.get("deterministic"), dict) else {}
    criteria = det.get("criteria") or []
    if criteria:
        console.print()
        console.print(Text("deterministic criteria", style="bold cyan"))
        for item in criteria:
            if not isinstance(item, dict):
                continue
            console.print(f"  {item.get('id')}: {item.get('status')} ({item.get('method') or '-'})")


def _render_eval_runs(project: str, node_id: str):
    rows = _load_receipts_for_node(project, node_id)
    if not rows:
        console.print(Text(f"No evaluator receipts for {project}/{node_id}", style="yellow"))
        return _MENU_BACK
    items = []
    for index, row in enumerate(rows):
        when = str(row.get("sort_at") or "-")[:19].replace("T", " ")
        verdict = str(row.get("verdict") or "-")
        model = ((row.get("knobs") or {}).get("model") or "-")
        wall = row.get("wall_s")
        wall_s = f"{wall}s" if wall is not None else "-"
        check = row.get("check") if isinstance(row.get("check"), dict) else {}
        timing = check.get("evaluation_timing") if isinstance(check.get("evaluation_timing"), dict) else {}
        crit = timing.get("criteria") if isinstance(timing.get("criteria"), dict) else {}
        integ = timing.get("integrity") if isinstance(timing.get("integrity"), dict) else {}
        tools = f"c={crit.get('tool_calls', 0)} i={integ.get('tool_calls', 0)}"
        commit = str((check.get("evaluated_commit_sha") or "-"))[:8]
        items.append((str(index), f"{when}  {verdict:<8}  {model:<22}  {wall_s:<8}  {tools:<14}  {commit}"))
    picked = _pick_list(
        f"eval runs · {project}/{node_id}",
        items,
        back_label="hub",
    )
    if picked in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return picked

    def _show_run():
        _clear_screen()
        _render_eval_show(rows[int(picked)])

    _page_view(_show_run, title=f"eval-run-{project}-{node_id}")
    return _MENU_BACK


def _eval_knob_picker(current: dict, *, project: str | None = None) -> dict:
    """Per-run overrides for the next hub run. Not persisted to settings.env."""
    _clear_screen()
    console.print(Text("eval knobs · next run only", style="bold"))
    current_model = str(current.get("preset") or current.get("model") or "")
    model_choices: list[tuple[str, str]] = [
        ("cheap", "cheap preset"),
    ]
    expensive_preset = (os.environ.get("GDDP_EVAL_MODEL_EXPENSIVE") or "").strip()
    if expensive_preset:
        model_choices.append(("expensive", f"expensive preset → {expensive_preset}"))
    if current_model and current_model not in {"cheap", "expensive"}:
        model_choices.append((current_model, f"keep {current_model!r}"))
    model = _pick_enum_or_other(
        "model",
        model_choices,
        current=current_model,
        other_label="type raw model id…",
        back_label="hub",
    )
    if model in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return current

    thinking = _pick_enum_or_other(
        "thinking",
        [(level, level) for level in _EVAL_THINKING_LEVELS],
        current=str(current.get("thinking") or "medium"),
        other_label="type custom thinking level…",
        back_label="hub",
    )
    if thinking in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return current

    integrity = _pick_enum(
        "integrity",
        [("on", "on"), ("off", "off")],
        back_label="hub",
    )
    if integrity in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return current

    lanes = _pick_enum(
        "lanes",
        [("live", "live"), ("deterministic", "deterministic")],
        back_label="hub",
    )
    if lanes in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return current

    repo = _resolve_repo_for_project(project) if project else None
    base_choices: list[tuple[str, str]] = [("", "auto")]
    for sha in _recent_commit_shas(repo):
        short = sha[:12]
        base_choices.append((sha, f"recent {short}"))
    current_base = str(current.get("base") or "")
    if current_base and all(value != current_base for value, _ in base_choices):
        base_choices.append((current_base, f"keep {current_base[:12]}…"))
    base = _pick_enum_or_other(
        "base sha",
        base_choices,
        current=current_base,
        other_label="type custom sha…",
        back_label="hub",
    )
    if base in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
        return current

    try:
        return cli_eval._resolve_eval_knobs(
            model=str(model).strip() or None,
            thinking=str(thinking).strip() or None,
            integrity=str(integrity).strip() or None,
            lanes=str(lanes).strip() or None,
            base=str(base).strip() or None,
        )
    except cli_eval.EvalKnobError as exc:
        console.print(Text(str(exc), style="red"))
        _pause()
        return current


def interactive_eval_hub(project: str, node_id: str):
    """One evaluator surface: run / knobs / config / instructions / history."""
    try:
        knobs = cli_eval._resolve_eval_knobs()
    except cli_eval.EvalKnobError:
        knobs = {"model": "-", "preset": None, "thinking": "medium",
                 "integrity": "on", "lanes": "live", "base": None}
    while True:
        _clear_screen()
        rows = _load_receipts_for_node(project, node_id)
        latest = rows[0] if rows else None
        latest_verdict = (latest or {}).get("verdict") or "-"
        latest_model = ((latest or {}).get("knobs") or {}).get("model") or "-"
        latest_when = str((latest or {}).get("sort_at") or "-")[:19]
        console.print(Text(f"evaluate · {project} / {node_id}", style="bold").append(
            f"  ·  latest {latest_verdict} · {latest_model} · {latest_when}",
            style="dim",
        ))
        next_model = knobs.get("preset") or knobs.get("model") or "-"
        console.print(Text(
            f"next run: model={next_model} thinking={knobs.get('thinking')} "
            f"integrity={knobs.get('integrity')} lanes={knobs.get('lanes')}",
            style="dim",
        ))
        console.print()
        try:
            choice = _menu_choice(_eval_hub_actions(), default="r")
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "r":
            _run_live_eval(project, node_id, base=knobs.get("base"), knobs=knobs)
        elif choice == "k":
            knobs = _eval_knob_picker(knobs, project=project)
        elif choice == "c":
            def _show_config():
                _clear_screen()
                _render_eval_config()

            _page_view(_show_config, title=f"eval-config-{project}-{node_id}")
        elif choice == "i":
            receipt = (latest or {}).get("check") if latest else None

            def _show_instructions():
                _clear_screen()
                _render_eval_instructions(project, node_id, receipt=receipt)

            _page_view(_show_instructions, title=f"eval-instructions-{project}-{node_id}")
        elif choice == "h":
            outcome = _render_eval_runs(project, node_id)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT
        elif choice == "s":
            if latest:
                def _show_latest():
                    _clear_screen()
                    _render_eval_show(latest)

                _page_view(
                    _show_latest,
                    title=f"eval-show-{project}-{node_id}",
                )
            else:
                console.print(Text("No runs yet.", style="yellow"))


def interactive_evaluate():
    """Pick a graph → node → open the evaluator hub."""
    while True:
        picked = _pick_graph("evaluate · graphs", back_label="main menu")
        if picked is _MENU_QUIT:
            return _MENU_QUIT
        if picked is _MENU_BACK:
            return _MENU_BACK
        project = str(picked)
        try:
            nodes = list(_import_module("node_cli").iter_nodes(ROOT, project))
        except Exception as exc:
            console.print(Text(f"Could not load {project}: {exc}", style="red"))
            _pause()
            continue
        node_items = [(node_id, str(doc.get("title") or "")) for node_id, doc, _ in nodes]
        while True:
            node_picked = _pick_list(
                f"evaluate · nodes · {project}",
                node_items,
                preview_cmd=_node_preview_cmd(project),
                back_label="graphs",
            )
            if node_picked is _MENU_QUIT:
                return _MENU_QUIT
            if node_picked is _MENU_BACK:
                break
            node_id = node_picked[0] if isinstance(node_picked, list) else node_picked
            outcome = interactive_eval_hub(project, node_id)
            if outcome is _MENU_QUIT:
                return _MENU_QUIT


def interactive_config():
    """Editor for executor & evaluator settings (runtime/settings.env)."""
    _clear_screen()
    console.print(Text("config · executor & evaluator settings", style="bold").append(
        f"  ·  {SETTINGS_FILE}", style="dim"
    ))
    console.print()
    console.print(Text("Values shown are in effect for subprocesses. Empty = default.", style="dim"))
    console.print()
    settings: dict[str, str] = {}
    for key, (label, hint) in SETTINGS_FIELDS.items():
        current = os.environ.get(key, "")
        console.print(Text(f"  {label}", style="bold cyan"))
        console.print(Text(f"    {hint}", style="dim"))
        answer = _config_setting_value(key, current)
        if answer in {_MENU_BACK, _MENU_QUIT, _MENU_REFRESH}:
            return _MENU_BACK
        if answer == "x":
            settings[key] = ""
        elif answer != current or answer:
            settings[key] = str(answer)
        else:
            settings[key] = current
        console.print()
    _write_runtime_settings(settings)
    console.print(Text(f"  saved → {SETTINGS_FILE}", style="bold green"))
    _pause()
    return _MENU_BACK


def interactive_menu():
    """Front door is the graph picker. Pick a graph, see its truth, act.

    Cross-graph controls (heartbeat, config) sit one step back from the
    picker so the first screen is always the work, never a menu of menus.
    """
    while True:
        try:
            picked = _pick_graph("graphs", back_label="live · heartbeat · config · quit")
        except (EOFError, KeyboardInterrupt):
            break
        if picked is _MENU_QUIT:
            break
        if picked is _MENU_BACK:
            if interactive_controls() is _MENU_QUIT:
                break
            continue
        try:
            outcome = interactive_graph_hub(str(picked))
        except SystemExit:
            continue
        except KeyboardInterrupt:
            break
        if outcome is _MENU_QUIT:
            break
    _clear_screen()
    console.print(Text("bye.", style="dim"))


def interactive_controls():
    """Live fleet, heartbeat, config: the things about the plane, not one graph."""
    actions = _front_page_actions()
    handlers = _front_page_handlers()
    while True:
        _clear_screen()
        console.print(Text("gddp", style="bold").append("  ·  plane: live · heartbeat · config", style="dim"))
        try:
            choice = _menu_choice(actions, default="b")
        except (EOFError, KeyboardInterrupt):
            return _MENU_BACK
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        handler = handlers.get(choice)
        if handler is None:
            continue
        try:
            handler()
        except SystemExit:
            pass
        except KeyboardInterrupt:
            return _MENU_BACK


# ---------------------------------------------------------------------------
# watch / steer — live observability + operator steering over local attempts
# ---------------------------------------------------------------------------
# Read-only over filesystem truth: attempt dirs hold packet.json, pid,
# worktree_path, events.jsonl, result.json. watch never writes; steer appends
# one line to steer.jsonl, which the steer-aware supervisor drains.
# Discovery uses durable session records and the canonical spool root, plus a
# transitional scan of leftover jobs/cursor-cli-spool history.

























































def cmd_timeline(args) -> int:
    """What happened to a project (or one node), in order, in words. Read-only."""
    timeline = _import_module("timeline")
    try:
        runtime_root: Path | None = resolve_runtime_root()
    except RuntimeError:
        runtime_root = None
    attempts: list[dict] = []
    if runtime_root is not None:
        try:
            attempts = cli_watch._discover_attempts(runtime_root)
        except OSError:
            attempts = []
    try:
        tl = timeline.build(
            args.project,
            args.node,
            config_root=ROOT,
            runtime_root=runtime_root,
            repo_path=_resolve_repo_for_project(args.project, args.repo_path),
            attempts=attempts,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"ERROR: {exc.args[0]}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(tl.as_dict(), indent=2))
        return 0
    graph = timeline.read_graph(ROOT, args.project)
    _print_timeline_rich(tl, graph["nodes"])
    return 1 if tl.warnings else 0


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




































def cmd_obsidian_export(args):
    obsidian_export = _import_module("obsidian_export")
    argv = ["--project", args.project]
    if args.vault:
        argv += ["--vault", str(args.vault)]
    if args.dry_run:
        argv.append("--dry-run")
    sys.exit(obsidian_export.main(argv))


def cmd_deliver(args):
    """Publish a graph's delivery commit, or list/retire its transport refs.

    Scriptable counterpart to the `deliver` action in the graph hub `more`
    menu — same run_graph_delivery boundary, no in-process mutation either way.
    """
    sys.exit(run_graph_delivery(
        args.subcommand, args.project, delete=getattr(args, "delete", False)
    ))


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
    cli_status.validate_project(args.project)


























def _print_timeline_rich(tl, graph_nodes: dict) -> None:
    """Rich timeline lines from an already-built timeline object."""
    timeline = _import_module("timeline")
    for raw in timeline.render_text(tl, graph_nodes).splitlines():
        if raw.startswith("timeline:"):
            console.print(Text(raw, style="bold"))
        elif raw.startswith("what is wrong"):
            console.print(Text(raw, style="bold red" if tl.warnings else "bold green"))
        elif raw.startswith("  ! "):
            console.print(Text(raw, style="red"))
        elif raw.startswith("what this host cannot see"):
            console.print(Text(raw, style="bold yellow"))
        elif raw.startswith("  - "):
            console.print(Text(raw, style="dim"))
        elif "OUTSIDE GDDP" in raw:
            console.print(Text(raw, style="bold red"))
        else:
            console.print(raw)


def _render_timeline_text(
    project: str,
    node: str | None = None,
    *,
    repo_path: Path | str | None = None,
) -> None:
    """Rich timeline render shared by CLI and in-TUI pager."""
    timeline = _import_module("timeline")
    try:
        runtime_root: Path | None = resolve_runtime_root()
    except RuntimeError:
        runtime_root = None
    attempts: list[dict] = []
    if runtime_root is not None:
        try:
            attempts = cli_watch._discover_attempts(runtime_root)
        except OSError:
            attempts = []
    tl = timeline.build(
        project,
        node,
        config_root=ROOT,
        runtime_root=runtime_root,
        repo_path=_resolve_repo_for_project(project, repo_path),
        attempts=attempts,
    )
    graph = timeline.read_graph(ROOT, project)
    _print_timeline_rich(tl, graph["nodes"])


def _interactive_timeline(project: str) -> str:
    """In-TUI timeline pager from graph hub more menu."""
    _page_view(
        lambda: _render_timeline_text(project),
        title=f"timeline-{project}",
    )
    return _MENU_BACK


def interactive_graph_delivery(project: str):
    """Publish this graph's delivery commit, or retire its transport refs.

    Both mutate origin. Neither runs without this explicit confirmation —
    publish and cleanup are never triggered as a side effect of any other
    graph action (dispatch, node review, etc.).
    """
    actions = {
        "p": ("publish", f"push the delivery commit to review/{project}"),
        "c": ("cleanup", "list, then optionally delete, transport refs"),
        "b": ("back", ""),
        "q": ("quit", ""),
    }
    confirm = {"y": ("yes", ""), "n": ("no", "")}
    while True:
        _clear_screen()
        console.print(Text("deliver", style="bold").append(f"  ·  {project}", style="dim"))
        choice = _menu_choice(actions, default="p")
        if choice == "q":
            return _MENU_QUIT
        if choice == "b":
            return _MENU_BACK
        if choice == "p":
            console.print(
                f"Publish [bold]{project}[/bold]'s delivery commit to "
                f"[bold cyan]review/{project}[/bold cyan]?"
            )
            if _menu_choice(confirm, default="n") == "y":
                run_graph_delivery("publish", project)
            _pause()
        elif choice == "c":
            console.print(Text("dry run — nothing deleted yet:", style="dim"))
            run_graph_delivery("cleanup", project)
            console.print("Delete the ref(s) listed above?")
            if _menu_choice(confirm, default="n") == "y":
                run_graph_delivery("cleanup", project, delete=True)
            _pause()









def main(argv=None):
    _load_runtime_settings()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in _CLI_COMMANDS and not argv[0].startswith("-"):
        return cli_dispatch.cmd_dispatch(argv)
    return parse_cli_argv(argv)



# Phase 2 module imports (behavior unchanged; names re-exported below)
import graph_io
import cli_dispatch
import cli_watch
import cli_heartbeat
import cli_eval
import cli_status
from cli_parser import parse_cli_argv


# --- Phase 2 re-exports (test_gddp.py patches these on the gddp module) ---
build_dispatch_plan = cli_dispatch.build_dispatch_plan
DispatchError = cli_dispatch.DispatchError
cmd_dispatch = cli_dispatch.cmd_dispatch

insert_dispatch_events = cli_dispatch.insert_dispatch_events
_dispatch_flow = cli_dispatch._dispatch_flow
_confirm_dispatch = cli_dispatch._confirm_dispatch
_connect_events_db = cli_dispatch._connect_events_db
_classify_dispatch_items = cli_dispatch._classify_dispatch_items
_systemd_status = cli_heartbeat._systemd_status
_spool_roots = cli_watch._spool_roots
_discover_attempts = cli_watch._discover_attempts
_diff_summary = cli_watch._diff_summary
_write_eval_knobs_sidecar = cli_eval._write_eval_knobs_sidecar
_launchd_status = cli_heartbeat._launchd_status
interactive_heartbeat = cli_heartbeat.interactive_heartbeat
_recorded_attempt_dirs = cli_watch._recorded_attempt_dirs
_filter_attempts = cli_watch._filter_attempts
cmd_watch = cli_watch.cmd_watch
cmd_runs = cli_watch.cmd_runs
cmd_steer = cli_watch.cmd_steer
interactive_watch = cli_watch.interactive_watch
_run_live_eval = cli_eval._run_live_eval
_resolve_eval_knobs = cli_eval._resolve_eval_knobs
_load_eval_knobs_sidecar = cli_eval._load_eval_knobs_sidecar
EvalKnobError = cli_eval.EvalKnobError
cmd_eval = cli_eval.cmd_eval
cmd_eval_config = cli_eval.cmd_eval_config
cmd_eval_instructions = cli_eval.cmd_eval_instructions
cmd_eval_runs = cli_eval.cmd_eval_runs
cmd_eval_show = cli_eval.cmd_eval_show
cmd_verify_node = cli_eval.cmd_verify_node
show_status = cli_status.show_status
interactive_status = cli_status.interactive_status
interactive_validate = cli_status.interactive_validate
validate_project = cli_status.validate_project
_list_status_projects = cli_status._list_status_projects
_collect_validate_failures = cli_status._collect_validate_failures
_graph_projects = graph_io._graph_projects
_resolve_project_repo = graph_io._resolve_project_repo
_resolve_repo_for_project = graph_io._resolve_repo_for_project
_auto_base_commit = graph_io._auto_base_commit
_load_project_doc = graph_io._load_project_doc

if __name__ == "__main__":
    sys.exit(main())
