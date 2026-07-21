#!/usr/bin/env python3
"""Stage-1 node operator helpers for gddp.py.

Read graph truth from project.yaml + nodes/<id>.yaml.
Optionally join latest runtime evidence (jobs/results) read-only.
set_status dual-writes graph status only — never mutates runtime DB.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

VALID_STATUSES = frozenset({"pending", "ready", "complete", "deferred"})
ACTIVE_STATUSES = frozenset({"pending", "ready"})


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def resolve_runtime_root(explicit: Path | str | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("GDDP_RUNTIME_ROOT") or os.environ.get("OPCLAW_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return None


def resolve_queue_db(config_root: Path, runtime_root: Path | str | None = None) -> Path | None:
    root = resolve_runtime_root(runtime_root)
    if root is None:
        sibling = (config_root.parent / "gddp-runtime").resolve()
        if sibling.is_dir():
            root = sibling
    if root is None:
        return None
    db = root / "db" / "queue.db"
    return db if db.is_file() else None


# ---------------------------------------------------------------------------
# Graph reads
# ---------------------------------------------------------------------------

def list_projects(config_root: Path) -> list[str]:
    graphs = config_root / "graphs"
    if not graphs.is_dir():
        return []
    return sorted(
        p.name
        for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").is_file()
    )


def load_project(config_root: Path, project_id: str) -> dict[str, Any]:
    path = config_root / "graphs" / project_id / "project.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"project not found: {project_id} ({path})")
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"project.yaml is not a mapping: {path}")
    return doc


def load_node_yaml(config_root: Path, project_id: str, node_id: str) -> dict[str, Any]:
    path = config_root / "graphs" / project_id / "nodes" / f"{node_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"node yaml not found: {project_id}/{node_id} ({path})")
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"node yaml is not a mapping: {path}")
    return doc


def project_node_entry(project: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for entry in project.get("nodes") or []:
        if isinstance(entry, dict) and entry.get("id") == node_id:
            return entry
    return None


def iter_index_nodes(
    config_root: Path,
    project_id: str | None = None,
    *,
    status: str | None = None,
    active: bool = False,
) -> list[tuple[str, dict[str, Any]]]:
    """Return (project_id, index_entry) rows from project.yaml nodes lists."""
    projects = [project_id] if project_id else list_projects(config_root)
    if project_id and project_id not in list_projects(config_root):
        raise FileNotFoundError(f"project not found: {project_id}")

    rows: list[tuple[str, dict[str, Any]]] = []
    for pid in projects:
        proj = load_project(config_root, pid)
        for entry in proj.get("nodes") or []:
            if not isinstance(entry, dict):
                continue
            st = entry.get("status", "unknown")
            if active and st not in ACTIVE_STATUSES:
                continue
            if status is not None and st != status:
                continue
            rows.append((pid, entry))
    return rows


# ---------------------------------------------------------------------------
# Runtime evidence (read-only)
# ---------------------------------------------------------------------------

@dataclass
class RuntimeEvidence:
    job_id: str | None = None
    queue_state: str | None = None
    job_status: str | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    executor: str | None = None
    created_at: str | None = None
    result_received_at: str | None = None
    result_outcome: str | None = None
    result_status: str | None = None
    acceptance_check: dict[str, Any] | None = None

    @property
    def eval_verdict(self) -> str | None:
        if not self.acceptance_check:
            return None
        v = self.acceptance_check.get("verdict")
        return str(v) if v is not None else None


def _parse_check(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def load_live_receipt(
    config_root: Path, project_id: str, node_id: str
) -> dict[str, Any] | None:
    """Fallback evaluator receipt: verification-runtime-live/<project>/<node>.json."""
    path = config_root / "verification-runtime-live" / project_id / f"{node_id}.json"
    if not path.is_file():
        # also accept any newer receipt that embeds node_id in name
        folder = config_root / "verification-runtime-live" / project_id
        if not folder.is_dir():
            return None
        candidates = sorted(folder.glob(f"*{node_id}*.json"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return None
        path = candidates[-1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # normalize: some receipts nest under "summary" / top-level is the check itself
    if "verdict" in data or "criteria_verdict" in data or "integrity" in data:
        if "receipt_path" not in data:
            data = {**data, "receipt_path": str(path)}
        return data
    for key in ("acceptance_check", "summary", "result"):
        inner = data.get(key)
        if isinstance(inner, dict) and (
            "verdict" in inner or "criteria_verdict" in inner or "integrity" in inner
        ):
            if "receipt_path" not in inner:
                inner = {**inner, "receipt_path": str(path)}
            return inner
    return None


def fetch_runtime_evidence(
    db_path: Path | None,
    project_id: str,
    node_id: str,
    *,
    config_root: Path | None = None,
) -> RuntimeEvidence | None:
    """Latest job + latest result for (project_id, node_id).

    DB absent / no job / parse failure is not an error — returns None or
    partial evidence. If DB has no acceptance_check, falls back to
    verification-runtime-live receipt when config_root is provided.
    """
    ev: RuntimeEvidence | None = None
    if db_path is not None and db_path.is_file():
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            con = None
        if con is not None:
            try:
                con.row_factory = sqlite3.Row
                job = con.execute(
                    "SELECT job_id, queue_state, status, attempt, max_attempts, "
                    "executor, created_at "
                    "FROM jobs WHERE project_id = ? AND node_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (project_id, node_id),
                ).fetchone()
                if job is None:
                    job = con.execute(
                        "SELECT job_id, queue_state, status, attempt, max_attempts, "
                        "executor, created_at "
                        "FROM jobs WHERE node_id = ? ORDER BY created_at DESC LIMIT 1",
                        (node_id,),
                    ).fetchone()
                if job is not None:
                    result = con.execute(
                        "SELECT received_at, outcome, status, acceptance_check "
                        "FROM results WHERE job_id = ? ORDER BY received_at DESC LIMIT 1",
                        (job["job_id"],),
                    ).fetchone()
                    check = _parse_check(result["acceptance_check"] if result else None)
                    ev = RuntimeEvidence(
                        job_id=job["job_id"],
                        queue_state=job["queue_state"],
                        job_status=job["status"],
                        attempt=job["attempt"],
                        max_attempts=job["max_attempts"],
                        executor=job["executor"],
                        created_at=job["created_at"],
                        result_received_at=result["received_at"] if result else None,
                        result_outcome=result["outcome"] if result else None,
                        result_status=result["status"] if result else None,
                        acceptance_check=check,
                    )
            except sqlite3.Error:
                ev = None
            finally:
                con.close()

    if config_root is not None:
        if ev is None or not ev.acceptance_check:
            receipt = load_live_receipt(config_root, project_id, node_id)
            if receipt is not None:
                if ev is None:
                    ev = RuntimeEvidence(acceptance_check=receipt)
                else:
                    ev.acceptance_check = receipt
    return ev


def fetch_result_history(
    db_path: Path | None,
    project_id: str,
    node_id: str,
) -> list[dict[str, Any]]:
    if db_path is None or not db_path.is_file():
        return []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        con.row_factory = sqlite3.Row
        jobs = con.execute(
            "SELECT job_id FROM jobs WHERE project_id = ? AND node_id = ? "
            "ORDER BY created_at DESC",
            (project_id, node_id),
        ).fetchall()
        if not jobs:
            jobs = con.execute(
                "SELECT job_id FROM jobs WHERE node_id = ? ORDER BY created_at DESC",
                (node_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for j in jobs:
            rows = con.execute(
                "SELECT result_id, job_id, received_at, outcome, status, acceptance_check "
                "FROM results WHERE job_id = ? ORDER BY received_at ASC",
                (j["job_id"],),
            ).fetchall()
            for r in rows:
                out.append(
                    {
                        "result_id": r["result_id"],
                        "job_id": r["job_id"],
                        "received_at": r["received_at"],
                        "outcome": r["outcome"],
                        "status": r["status"],
                        "acceptance_check": _parse_check(r["acceptance_check"]),
                    }
                )
        return out
    except sqlite3.Error:
        return []
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_list_line(
    node_id: str,
    graph_status: str,
    runtime_state: str | None,
    eval_verdict: str | None,
    *,
    ntype: str = "",
    title: str = "",
) -> str:
    """ID | GRAPH | RUNTIME | VERDICT — signals never collapsed."""
    rid = runtime_state if runtime_state else "-"
    verd = eval_verdict if eval_verdict else "-"
    # fixed-ish columns after exact ID (ID unpadded so copy is clean at line start)
    base = f"{node_id}  {graph_status:<10}  {rid:<16}  {verd}"
    tail = f"{ntype}  {title}".strip()
    return f"{base}  {tail}" if tail else base


def format_evaluator_compact(check: dict[str, Any] | None) -> list[str]:
    if not check:
        return ["  no evaluation evidence"]
    lines: list[str] = []
    integrity = check.get("integrity") or {}
    if not isinstance(integrity, dict):
        integrity = {}
    lane = check.get("lane_status") or {}
    if not isinstance(lane, dict):
        lane = {}
    harness = check.get("harness_error") or {}
    if not isinstance(harness, dict):
        harness = {}

    lines.append(f"  overall_verdict: {check.get('verdict', '-')}")
    lines.append(
        f"  criteria: verdict={check.get('criteria_verdict', '-')}  "
        f"confidence={check.get('criteria_confidence', '-')}  "
        f"lane={lane.get('criteria', '-')}"
    )
    lines.append(
        f"  integrity: verdict={integrity.get('verdict', '-')}  "
        f"confidence={integrity.get('confidence', '-')}  "
        f"lane={lane.get('integrity', '-')}"
    )
    if harness.get("criteria") or harness.get("integrity"):
        lines.append(
            f"  harness_errors: criteria={harness.get('criteria') or '-'}  "
            f"integrity={harness.get('integrity') or '-'}"
        )
    commit_sha = check.get("evaluated_commit_sha")
    merge_sha = check.get("merge_commit_sha")
    tree_sha = check.get("evaluated_tree_sha")
    if commit_sha or merge_sha or tree_sha:
        if commit_sha and merge_sha:
            match = "match" if commit_sha == merge_sha else "mismatch"
        else:
            match = "n/a"
        lines.append(
            f"  provenance: commit={commit_sha or '-'}  merge={merge_sha or '-'}  "
            f"tree={tree_sha or '-'}  ({match})"
        )
    for f in check.get("criteria_findings") or []:
        if isinstance(f, dict):
            lines.append(
                f"  criterion_finding: {f.get('criterion_id', '?')} -> {f.get('judgment', '?')}"
            )
    for f in integrity.get("findings") or []:
        if isinstance(f, dict):
            lines.append(
                f"  integrity_finding: [{f.get('severity', '?')}] {f.get('summary', '')}"
            )
    cov = check.get("context_coverage")
    if isinstance(cov, dict):
        crit = cov.get("criteria")
        if isinstance(crit, dict):
            crit = crit.get("rating", crit)
        integ = cov.get("integrity")
        if isinstance(integ, dict):
            integ = integ.get("rating", integ)
        lines.append(
            f"  context_coverage: criteria={crit or '-'}  integrity={integ or '-'}  "
            f"overall={cov.get('overall', '-')}"
        )
    if check.get("receipt_path"):
        lines.append(f"  receipt_path: {check['receipt_path']}")
    return lines


# ---------------------------------------------------------------------------
# set-status dual write
# ---------------------------------------------------------------------------

_TOP_STATUS_RE = re.compile(r"^status:\s*.*$", re.MULTILINE)


def _replace_top_level_status(text: str, new_status: str) -> str:
    if not _TOP_STATUS_RE.search(text):
        raise ValueError("no top-level status: field found in node yaml")
    # Only first top-level occurrence (node files have single top-level status)
    return _TOP_STATUS_RE.sub(f"status: {new_status}", text, count=1)


def _replace_project_index_status(text: str, node_id: str, new_status: str) -> str:
    """Surgically update status under the matching - id: node_id block."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_block = False
    replaced = False
    i = 0
    while i < len(lines):
        line = lines[i]
        # start of a list entry with id
        m_id = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", line)
        if m_id:
            in_block = m_id.group(2) == node_id
            out.append(line)
            i += 1
            continue
        # next top-level key ends any node entry context that used "  - id:"
        if in_block and re.match(r"^[A-Za-z_]", line):
            in_block = False
        if in_block and re.match(r"^(\s+)status:\s*.*$", line):
            indent = re.match(r"^(\s+)", line).group(1)  # type: ignore[union-attr]
            nl = "\n" if line.endswith("\n") else ""
            # preserve original newline style
            if line.endswith("\r\n"):
                nl = "\r\n"
            elif line.endswith("\n"):
                nl = "\n"
            else:
                nl = ""
            out.append(f"{indent}status: {new_status}{nl}")
            replaced = True
            in_block = False
            i += 1
            continue
        # also handle inline "- id: x" followed later; if a new "- id:" starts, leave
        if in_block and re.match(r"^\s*-\s+id:\s*", line):
            in_block = re.match(r"^\s*-\s+id:\s*(\S+)", line).group(1) == node_id  # type: ignore
        out.append(line)
        i += 1
    if not replaced:
        raise ValueError(f"node id {node_id!r} not found with a status field in project.yaml")
    return "".join(out)


def _atomic_replace(path: Path, new_text: str) -> None:
    """Write via temp file in same dir + os.replace (POSIX atomic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def set_graph_status(
    config_root: Path,
    project_id: str,
    node_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Dual-write status to node yaml + project.yaml index.

    Preserves original file bytes except the target status values.
    Uses temp files + os.replace; restores both originals on any failure.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {new_status!r}; valid: {', '.join(sorted(VALID_STATUSES))}"
        )

    project_path = config_root / "graphs" / project_id / "project.yaml"
    node_path = config_root / "graphs" / project_id / "nodes" / f"{node_id}.yaml"
    if not project_path.is_file():
        raise FileNotFoundError(f"project not found: {project_id}")
    if not node_path.is_file():
        raise FileNotFoundError(f"node yaml not found: {project_id}/{node_id}")

    project_orig = project_path.read_text(encoding="utf-8")
    node_orig = node_path.read_text(encoding="utf-8")

    proj = yaml.safe_load(project_orig) or {}
    entry = project_node_entry(proj, node_id)
    if entry is None:
        raise FileNotFoundError(f"node {node_id!r} not listed in project.yaml")
    node_doc = yaml.safe_load(node_orig) or {}
    if node_doc.get("node_id") not in (None, node_id):
        raise ValueError(
            f"node_id mismatch: file has {node_doc.get('node_id')!r}, arg {node_id!r}"
        )
    old_index = entry.get("status")
    old_node = node_doc.get("status")

    if old_index == new_status and old_node == new_status:
        return {
            "project_id": project_id,
            "node_id": node_id,
            "old_index_status": old_index,
            "old_node_status": old_node,
            "new_status": new_status,
            "project_path": str(project_path),
            "node_path": str(node_path),
            "noop": True,
        }

    new_project = _replace_project_index_status(project_orig, node_id, new_status)
    new_node = _replace_top_level_status(node_orig, new_status)

    # pre-validate candidates in memory
    pre_proj = yaml.safe_load(new_project) or {}
    pre_entry = project_node_entry(pre_proj, node_id)
    pre_node = yaml.safe_load(new_node) or {}
    if not pre_entry or pre_entry.get("status") != new_status:
        raise RuntimeError("pre-validate failed: project.yaml candidate status")
    if pre_node.get("status") != new_status:
        raise RuntimeError("pre-validate failed: node yaml candidate status")

    node_replaced = False
    project_replaced = False
    try:
        _atomic_replace(node_path, new_node)
        node_replaced = True
        _atomic_replace(project_path, new_project)
        project_replaced = True

        v_proj = yaml.safe_load(project_path.read_text(encoding="utf-8")) or {}
        v_entry = project_node_entry(v_proj, node_id)
        v_node = yaml.safe_load(node_path.read_text(encoding="utf-8")) or {}
        if not v_entry or v_entry.get("status") != new_status:
            raise RuntimeError("post-write validation failed: project.yaml status mismatch")
        if v_node.get("status") != new_status:
            raise RuntimeError("post-write validation failed: node yaml status mismatch")
    except Exception:
        if project_replaced:
            _atomic_replace(project_path, project_orig)
        if node_replaced:
            _atomic_replace(node_path, node_orig)
        raise

    return {
        "project_id": project_id,
        "node_id": node_id,
        "old_index_status": old_index,
        "old_node_status": old_node,
        "new_status": new_status,
        "project_path": str(project_path),
        "node_path": str(node_path),
        "noop": False,
    }


# ---------------------------------------------------------------------------
# CLI command bodies (print + exit codes)
# ---------------------------------------------------------------------------

def cmd_list(
    config_root: Path,
    *,
    project_id: str | None,
    status: str | None,
    active: bool,
    runtime_root: Path | str | None,
) -> int:
    try:
        rows = iter_index_nodes(
            config_root, project_id, status=status, active=active
        )
    except FileNotFoundError as e:
        print(e)
        return 2

    db = resolve_queue_db(config_root, runtime_root)
    if not rows:
        if active:
            print("No active nodes.")
        else:
            print("No nodes." + (f" (status={status})" if status else ""))
        return 0

    # Group by project for multi-project listing
    current_pid = None
    for pid, entry in rows:
        if pid != current_pid:
            current_pid = pid
            print(f"{pid}")
            print(f"{'ID':<40}  {'GRAPH':<10}  {'RUNTIME':<16}  VERDICT")
        nid = entry.get("id", "?")
        gstatus = str(entry.get("status", "?"))
        ev = fetch_runtime_evidence(db, pid, nid, config_root=config_root)
        runtime_state = ev.queue_state if ev else None
        verdict = ev.eval_verdict if ev else None
        print(
            format_list_line(
                nid,
                gstatus,
                runtime_state,
                verdict,
                ntype=str(entry.get("type") or ""),
                title=str(entry.get("title") or ""),
            )
        )
    return 0


def cmd_show(
    config_root: Path,
    *,
    project_id: str,
    node_id: str,
    runtime_root: Path | str | None,
    trace: bool,
) -> int:
    try:
        proj = load_project(config_root, project_id)
        node = load_node_yaml(config_root, project_id, node_id)
    except FileNotFoundError as e:
        print(e)
        return 2
    except ValueError as e:
        print(e)
        return 2

    entry = project_node_entry(proj, node_id)
    index_status = entry.get("status") if entry else None
    node_status = node.get("status")
    graph_status = index_status if index_status is not None else node_status

    print("## Graph")
    print(f"  node_id: {node.get('node_id', node_id)}")
    print(f"  title: {node.get('title', entry.get('title') if entry else '')}")
    print(f"  type: {node.get('type', entry.get('type') if entry else '')}")
    print(f"  graph_status: {graph_status}")
    if index_status is not None and node_status is not None and index_status != node_status:
        print(
            f"  WARN: status desync  project.yaml={index_status}  "
            f"node.yaml={node_status}"
        )
    print(f"  priority: {node.get('priority', '-')}")
    print(f"  depends_on: {node.get('depends_on') or []}")
    print(f"  unlocks: {node.get('unlocks') or []}")
    why = (node.get("why") or "").strip()
    if why:
        # intent / why — first paragraph only unless trace
        first = why.split("\n\n", 1)[0]
        if not trace and len(first) > 400:
            first = first[:400] + "…"
        print("  why:")
        for line in first.splitlines() or [first]:
            print(f"    {line}")
    criteria = node.get("acceptance_criteria") or []
    print("  acceptance_criteria:")
    if not criteria:
        print("    (none)")
    for c in criteria:
        if isinstance(c, dict):
            print(f"    - {c.get('id', '?')}: {c.get('criterion', c)}")
        else:
            print(f"    - {c}")
    constraints = node.get("constraints") or []
    print("  constraints:")
    if not constraints:
        print("    (none)")
    for c in constraints:
        print(f"    - {c}")

    db = resolve_queue_db(config_root, runtime_root)
    ev = fetch_runtime_evidence(db, project_id, node_id, config_root=config_root)

    print("## Runtime")
    if not ev or not ev.job_id:
        print("  runtime_state: -")
        print("  no evaluation evidence" if not (ev and ev.acceptance_check) else "  (receipt only; no job row)")
    else:
        print(f"  job_id: {ev.job_id}")
        print(f"  runtime_state: {ev.queue_state or '-'}")
        print(f"  job_status: {ev.job_status or '-'}")
        print(f"  attempt: {ev.attempt}/{ev.max_attempts}")
        print(f"  executor: {ev.executor or '-'}")
        print(f"  created_at: {ev.created_at or '-'}")

    print("## Evaluator")
    if not ev or not ev.acceptance_check:
        print("  no evaluation evidence")
    else:
        for line in format_evaluator_compact(ev.acceptance_check):
            print(line)

    if trace:
        print("## Evaluator trace / history")
        history = fetch_result_history(db, project_id, node_id)
        if not history:
            # still surface live receipt if that was the only source
            if ev and ev.acceptance_check:
                print("  --- live receipt / latest check")
                print(json.dumps(ev.acceptance_check, indent=2, sort_keys=True))
            else:
                print("  no evaluation evidence")
        else:
            for i, row in enumerate(history, 1):
                print(
                    f"  --- result {i}  {row.get('received_at')}  "
                    f"job={row.get('job_id')}  outcome={row.get('outcome')}/"
                    f"{row.get('status')}"
                )
                check = row.get("acceptance_check")
                if check:
                    print(json.dumps(check, indent=2, sort_keys=True))
                else:
                    print("  (empty acceptance_check)")
    return 0


def cmd_set_status(
    config_root: Path,
    *,
    project_id: str,
    node_id: str,
    new_status: str,
    yes: bool,
    reason: str | None,
) -> int:
    try:
        proj = load_project(config_root, project_id)
        node = load_node_yaml(config_root, project_id, node_id)
    except FileNotFoundError as e:
        print(e)
        return 2

    entry = project_node_entry(proj, node_id)
    if entry is None:
        print(f"node {node_id!r} not listed in project.yaml for {project_id}")
        return 2

    old_index = entry.get("status")
    old_node = node.get("status")
    print(f"{project_id}/{node_id}")
    print(f"  project.yaml status: {old_index}  ->  {new_status}")
    print(f"  node.yaml status:    {old_node}  ->  {new_status}")
    if reason:
        print(f"  reason: {reason}")

    if old_index == new_status and old_node == new_status:
        print("Already at target status — nothing to do.")
        return 0

    if not yes:
        try:
            ans = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans != "y":
            print("Aborted.")
            return 1

    try:
        result = set_graph_status(config_root, project_id, node_id, new_status)
    except ValueError as e:
        print(e)
        return 1
    except Exception as e:
        print(f"Failed (rolled back if partial): {e}")
        return 2

    print(
        f"Done: {result['node_id']} -> {result['new_status']}\n"
        f"  {result['node_path']}\n"
        f"  {result['project_path']}"
    )
    return 0
