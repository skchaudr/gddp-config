#!/usr/bin/env python3
"""Stage 1 node CLI helpers: list, show, set-status.

Graph status (YAML), runtime queue state, and evaluator verdict stay distinct.
Runtime DB is read-only. Human status *reasons* append to runtime
node_status_history/ (not node YAML).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Install deps:  pip install pyyaml rich", file=sys.stderr)
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent

GRAPH_STATUSES = ("pending", "ready", "complete", "deferred")
ACTIVE_STATUSES = frozenset({"pending", "ready"})
_NODE_STATUS_RE = re.compile(r"^(status:\s*)(\S+)\s*$", re.MULTILINE)

# Narrow layout threshold for `node list` (binding Stage-1 UX fix).
LIST_WIDE_MIN_COLUMNS = 120


def config_root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else ROOT


def runtime_root() -> Path:
    env = os.environ.get("GDDP_RUNTIME_ROOT")
    return Path(env) if env else (ROOT / ".." / "gddp-runtime").resolve()


def runtime_db_path() -> Path:
    return runtime_root() / "db" / "queue.db"


def _load_status_history_mod():
    """Load gddp-runtime scripts/node_status_history.py if present."""
    path = runtime_root() / "scripts" / "node_status_history.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("node_status_history", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def project_dir(root: Path, project_id: str) -> Path:
    return root / "graphs" / project_id


def node_path(root: Path, project_id: str, node_id: str) -> Path:
    return project_dir(root, project_id) / "nodes" / f"{node_id}.yaml"


def project_yaml_path(root: Path, project_id: str) -> Path:
    return project_dir(root, project_id) / "project.yaml"


def list_project_ids(root: Path) -> list[str]:
    graphs = root / "graphs"
    if not graphs.exists():
        return []
    return sorted(
        p.name
        for p in graphs.iterdir()
        if p.is_dir() and p.name != "_template" and (p / "project.yaml").exists()
    )


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml_text(text: str) -> Any:
    return yaml.safe_load(text)


def load_node_doc(root: Path, project_id: str, node_id: str) -> dict:
    path = node_path(root, project_id, node_id)
    if not path.exists():
        raise FileNotFoundError(f"node file not found: {path}")
    doc = load_yaml(path)
    if not isinstance(doc, dict):
        raise ValueError(f"node YAML is not a mapping: {path}")
    return doc


def load_project_doc(root: Path, project_id: str) -> dict:
    path = project_yaml_path(root, project_id)
    if not path.exists():
        raise FileNotFoundError(f"project not found: {project_id}")
    doc = load_yaml(path)
    if not isinstance(doc, dict):
        raise ValueError(f"project YAML is not a mapping: {path}")
    return doc


def project_index_entry(proj: dict, node_id: str) -> dict | None:
    for entry in proj.get("nodes") or []:
        if isinstance(entry, dict) and entry.get("id") == node_id:
            return entry
    return None


def iter_nodes(root: Path, project_id: str) -> list[tuple[str, dict, dict | None]]:
    """(node_id, node_doc, index_entry). Prefer node YAML; fall back to index."""
    proj = load_project_doc(root, project_id)
    nodes_dir = project_dir(root, project_id) / "nodes"
    out: list[tuple[str, dict, dict | None]] = []
    seen: set[str] = set()

    for entry in proj.get("nodes") or []:
        if not isinstance(entry, dict):
            continue
        nid = entry.get("id")
        if not isinstance(nid, str) or not nid:
            continue
        seen.add(nid)
        path = nodes_dir / f"{nid}.yaml"
        if path.exists():
            try:
                doc = load_yaml(path) or {}
            except Exception:
                doc = {
                    "node_id": nid,
                    "title": entry.get("title", ""),
                    "status": entry.get("status"),
                    "type": entry.get("type", ""),
                }
        else:
            doc = {
                "node_id": nid,
                "title": entry.get("title", ""),
                "status": entry.get("status", "?"),
                "type": entry.get("type", ""),
            }
        if not isinstance(doc, dict):
            doc = {"node_id": nid, "status": entry.get("status", "?")}
        out.append((nid, doc, entry))

    if nodes_dir.exists():
        for path in sorted(nodes_dir.glob("*.yaml")):
            if path.stem in seen:
                continue
            try:
                doc = load_yaml(path) or {}
            except Exception:
                continue
            if isinstance(doc, dict):
                out.append((doc.get("node_id") or path.stem, doc, None))
    return out


# ── surgical status rewrite ────────────────────────────────────────────────


def replace_node_status(text: str, new_status: str) -> tuple[str, str | None]:
    match = _NODE_STATUS_RE.search(text)
    if not match:
        raise ValueError("top-level status: field not found in node YAML")
    old = match.group(2)
    # $ stops before trailing newline; keep it from text[end:]
    new_text = text[: match.start()] + f"{match.group(1)}{new_status}" + text[match.end() :]
    return new_text, old


def replace_project_index_status(
    text: str, node_id: str, new_status: str
) -> tuple[str, str | None]:
    """Replace status under one nodes[] entry only. Stops at any dedent/top-level."""
    lines = text.splitlines(keepends=True)
    id_re = re.compile(rf"^(\s*)-\s+id:\s*{re.escape(node_id)}\s*$")
    status_re = re.compile(r"^(\s*)status:\s*(\S+)\s*$")
    entry_start = None
    entry_indent = ""
    for i, line in enumerate(lines):
        m = id_re.match(line.rstrip("\n"))
        if m:
            entry_start = i
            entry_indent = m.group(1)
            break
    if entry_start is None:
        raise ValueError(f"project.yaml has no nodes entry id={node_id!r}")

    entry_lead = len(entry_indent)
    status_line = None
    old_status = None
    for j in range(entry_start + 1, len(lines)):
        raw = lines[j]
        stripped = raw.rstrip("\n")
        if not stripped.strip():
            continue
        leading = len(stripped) - len(stripped.lstrip(" "))
        # Next sibling list item at same indent, or any dedent/top-level boundary
        if leading <= entry_lead:
            break
        sm = status_re.match(stripped)
        if sm:
            status_line = j
            old_status = sm.group(2)
            nl = "\n" if raw.endswith("\n") else ""
            lines[j] = f"{sm.group(1)}status: {new_status}{nl}"
            break

    if status_line is None:
        raise ValueError(f"status field not found under nodes entry id={node_id!r}")
    return "".join(lines), old_status


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _restore_pair(
    node_file: Path, project_file: Path, node_orig: bytes, project_orig: bytes
) -> None:
    errors: list[str] = []
    for path, orig, label in (
        (node_file, node_orig, "node"),
        (project_file, project_orig, "project"),
    ):
        try:
            _atomic_write(path, orig.decode("utf-8"))
        except Exception as e:
            try:
                path.write_bytes(orig)
            except Exception as e2:
                errors.append(f"{label} restore failed: {e}; fallback: {e2}")
    if errors:
        raise RuntimeError("; ".join(errors))


# ── validation ─────────────────────────────────────────────────────────────


def _finding_key(f: Any) -> tuple:
    return (
        getattr(f, "path", ""),
        getattr(f, "rule", ""),
        getattr(f, "message", ""),
        getattr(f, "severity", ""),
    )


def baseline_error_keys(root: Path, project_id: str) -> set[tuple]:
    sys.path.insert(0, str(SCRIPTS_DIR))
    import validate  # noqa: WPS433

    findings = validate.run(root, project_id)
    return {_finding_key(f) for f in findings if f.severity == "error"}


def verify_ids_before_write(root: Path, project_id: str, node_id: str) -> list[str]:
    problems: list[str] = []
    npath = node_path(root, project_id, node_id)
    ppath = project_yaml_path(root, project_id)
    if not ppath.exists():
        return [f"project '{project_id}' not found"]
    if not npath.exists():
        return [f"node file not found: graphs/{project_id}/nodes/{node_id}.yaml"]
    if npath.stem != node_id:
        problems.append(f"filename stem {npath.stem!r} != node_id {node_id!r}")
    try:
        node_doc = load_yaml(npath)
        proj_doc = load_yaml(ppath)
    except Exception as e:
        return [f"YAML parse error: {e}"]
    if not isinstance(node_doc, dict):
        return ["node YAML is not a mapping"]
    if not isinstance(proj_doc, dict):
        return ["project YAML is not a mapping"]
    if node_doc.get("node_id") != node_id:
        problems.append(
            f"node_id in file is {node_doc.get('node_id')!r}, expected {node_id!r}"
        )
    if proj_doc.get("project_id") not in (None, project_id):
        problems.append(
            f"project_id in project.yaml is {proj_doc.get('project_id')!r}, "
            f"expected {project_id!r}"
        )
    entry = project_index_entry(proj_doc, node_id)
    if entry is None:
        problems.append(f"project.yaml nodes index has no id={node_id!r}")
    return problems


def verify_candidates(
    node_text: str,
    project_text: str,
    project_id: str,
    node_id: str,
    expected_status: str,
) -> list[str]:
    """Parse candidate strings and check ids/status before any disk write."""
    problems: list[str] = []
    try:
        node_doc = load_yaml_text(node_text)
    except Exception as e:
        return [f"candidate node YAML parse failed: {e}"]
    try:
        proj_doc = load_yaml_text(project_text)
    except Exception as e:
        return [f"candidate project YAML parse failed: {e}"]
    if not isinstance(node_doc, dict):
        return ["candidate node YAML is not a mapping"]
    if not isinstance(proj_doc, dict):
        return ["candidate project YAML is not a mapping"]
    if node_doc.get("node_id") != node_id:
        problems.append(
            f"candidate node_id is {node_doc.get('node_id')!r}, expected {node_id!r}"
        )
    if node_doc.get("status") != expected_status:
        problems.append(
            f"candidate node status is {node_doc.get('status')!r}, "
            f"expected {expected_status!r}"
        )
    if proj_doc.get("project_id") not in (None, project_id):
        problems.append(
            f"candidate project_id is {proj_doc.get('project_id')!r}, "
            f"expected {project_id!r}"
        )
    entry = project_index_entry(proj_doc, node_id)
    if entry is None:
        problems.append(f"candidate project index missing id={node_id!r}")
    elif entry.get("status") != expected_status:
        problems.append(
            f"candidate index status is {entry.get('status')!r}, "
            f"expected {expected_status!r}"
        )
    return problems


def validate_status_change_docs(
    root: Path,
    project_id: str,
    node_id: str,
    expected_status: str,
    baseline: set[tuple],
) -> list[str]:
    """Post-write checks. Inherited validate errors do not block."""
    problems: list[str] = []
    npath = node_path(root, project_id, node_id)
    ppath = project_yaml_path(root, project_id)
    try:
        node_doc = load_yaml(npath)
        proj_doc = load_yaml(ppath)
    except Exception as e:
        return [f"YAML parse failed after write: {e}"]
    if not isinstance(node_doc, dict) or not isinstance(proj_doc, dict):
        return ["YAML is not a mapping after write"]
    if node_doc.get("node_id") != node_id:
        problems.append(
            f"node_id mismatch: file has {node_doc.get('node_id')!r}, expected {node_id!r}"
        )
    if node_doc.get("status") != expected_status:
        problems.append(
            f"node status after write is {node_doc.get('status')!r}, "
            f"expected {expected_status!r}"
        )
    if proj_doc.get("project_id") not in (None, project_id):
        problems.append(
            f"project_id mismatch: {proj_doc.get('project_id')!r} != {project_id!r}"
        )
    entry = project_index_entry(proj_doc, node_id)
    if entry is None:
        problems.append(f"project index missing node {node_id!r} after write")
    elif entry.get("status") != expected_status:
        problems.append(
            f"project index status after write is {entry.get('status')!r}, "
            f"expected {expected_status!r}"
        )
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import validate  # noqa: WPS433

        findings = validate.run(root, project_id)
        for f in findings:
            if f.severity == "error" and _finding_key(f) not in baseline:
                problems.append(
                    f"new validate error: {f.path} — {f.rule} — {f.message}"
                )
    except Exception as e:
        problems.append(f"validate.py failed to run after write: {e}")
    return problems


# ── runtime DB + receipts (read-only) ──────────────────────────────────────


@dataclass
class RuntimeEvidence:
    queue_state: str = "-"
    job_status: str = "-"
    job_id: str | None = None
    verdict: str = "-"
    acceptance_check: dict = field(default_factory=dict)
    receipt: dict | None = None
    receipt_path: str | None = None
    results_history: list[dict] = field(default_factory=list)
    jobs_history: list[dict] = field(default_factory=list)

    @property
    def has_evaluation(self) -> bool:
        """Evaluator evidence only — independent of runtime job existence."""
        if self.verdict and self.verdict != "-":
            return True
        if self.receipt:
            return True
        if self.acceptance_check:
            return True
        return False


def _connect_ro(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


def _table_cols(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _parse_json_obj(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        val = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return val if isinstance(val, dict) else {}


def load_receipt_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_receipt(
    root: Path, project_id: str, node_id: str, acceptance_check: dict
) -> tuple[dict | None, str | None]:
    rp = acceptance_check.get("receipt_path")
    if isinstance(rp, str) and rp.strip():
        p = Path(rp)
        receipt = load_receipt_file(p)
        if receipt is not None:
            return receipt, str(p)
    fallback = root / "verification-runtime-live" / project_id / f"{node_id}.json"
    receipt = load_receipt_file(fallback)
    if receipt is not None:
        return receipt, str(fallback)
    return None, None


def fetch_runtime_evidence(
    root: Path,
    project_id: str,
    node_id: str,
    db_path: Path | None = None,
) -> RuntimeEvidence:
    ev = RuntimeEvidence()
    db = db_path if db_path is not None else runtime_db_path()
    con = _connect_ro(db)
    acceptance: dict = {}

    if con is not None:
        try:
            job_cols = _table_cols(con, "jobs")
            res_cols = _table_cols(con, "results")
            need = {"job_id", "project_id", "node_id", "queue_state", "status", "created_at"}
            if need.issubset(job_cols):
                jobs = con.execute(
                    "SELECT * FROM jobs WHERE project_id = ? AND node_id = ? "
                    "ORDER BY created_at DESC",
                    (project_id, node_id),
                ).fetchall()
                ev.jobs_history = [dict(j) for j in jobs]
                if jobs:
                    latest = jobs[0]
                    ev.queue_state = latest["queue_state"] or "-"
                    ev.job_status = latest["status"] or "-"
                    ev.job_id = latest["job_id"]
                if jobs and {"job_id", "acceptance_check"}.issubset(res_cols):
                    job_ids = [j["job_id"] for j in jobs]
                    ph = ",".join("?" * len(job_ids))
                    order = "received_at" if "received_at" in res_cols else "result_id"
                    rows = con.execute(
                        f"SELECT * FROM results WHERE job_id IN ({ph}) "
                        f"ORDER BY {order} DESC",
                        job_ids,
                    ).fetchall()
                    for r in rows:
                        d = dict(r)
                        d["_acceptance"] = _parse_json_obj(d.get("acceptance_check"))
                        ev.results_history.append(d)
                    if rows:
                        acceptance = ev.results_history[0]["_acceptance"]
                        ev.acceptance_check = acceptance
                        v = acceptance.get("verdict")
                        if isinstance(v, str) and v:
                            ev.verdict = v
        except sqlite3.Error:
            pass
        finally:
            con.close()

    receipt, receipt_path = resolve_receipt(root, project_id, node_id, acceptance)
    if receipt is not None:
        ev.receipt = receipt
        if ev.verdict == "-":
            v = receipt.get("verdict")
            if isinstance(v, str) and v:
                ev.verdict = v
    if receipt_path:
        ev.receipt_path = receipt_path
    elif isinstance(acceptance.get("receipt_path"), str):
        ev.receipt_path = acceptance["receipt_path"]
    return ev


# ── evaluator field normalization ──────────────────────────────────────────


def _as_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else {}


def _pick(acceptance: dict, receipt: dict | None, key: str) -> Any:
    if key in acceptance and acceptance[key] is not None:
        return acceptance[key]
    if receipt and key in receipt:
        return receipt.get(key)
    return None


def _lane_fields(receipt: dict | None, acceptance: dict) -> tuple[dict, dict]:
    """Normalize summary (top-level dicts) and full (nested lane_status) shapes."""
    lane: dict[str, Any] = {}
    harness: dict[str, Any] = {}
    for src in (acceptance, receipt or {}):
        if isinstance(src.get("lane_status"), dict) and not lane:
            lane = dict(src["lane_status"])
        if isinstance(src.get("harness_error"), dict) and not harness:
            harness = dict(src["harness_error"])
    if receipt:
        sem = _as_dict(receipt.get("semantic"))
        integ = _as_dict(receipt.get("integrity"))
        if "criteria" not in lane and sem.get("lane_status") is not None:
            lane["criteria"] = sem["lane_status"]
        if "integrity" not in lane and integ.get("lane_status") is not None:
            lane["integrity"] = integ["lane_status"]
        if "criteria" not in harness and sem.get("harness_error") is not None:
            harness["criteria"] = sem["harness_error"]
        if "integrity" not in harness and integ.get("harness_error") is not None:
            harness["integrity"] = integ["harness_error"]
    return lane, harness


def _coverage_line(receipt: dict | None, acceptance: dict) -> str | None:
    cov = _pick(acceptance, receipt, "context_coverage")
    if not isinstance(cov, dict):
        return None

    def rating(side: str) -> Any:
        raw = cov.get(side, "n/a")
        return raw.get("rating", "n/a") if isinstance(raw, dict) else raw

    return (
        f"criteria={rating('criteria')}  integrity={rating('integrity')}  "
        f"overall={cov.get('overall', 'n/a')}"
    )


def _provenance_line(receipt: dict | None, acceptance: dict) -> str | None:
    commit_sha = _pick(acceptance, receipt, "evaluated_commit_sha")
    tree_sha = _pick(acceptance, receipt, "evaluated_tree_sha")
    merge_sha = _pick(acceptance, receipt, "merge_commit_sha")
    if not (commit_sha or tree_sha or merge_sha):
        return None
    if commit_sha:
        if merge_sha and commit_sha == merge_sha:
            match = "  (match)"
        elif merge_sha:
            match = "  (mismatch)"
        else:
            match = ""
        return f"commit={commit_sha}  merge={merge_sha or 'n/a'}{match}"
    return (
        f"tree={tree_sha or 'n/a'}  merge={merge_sha or 'n/a'}  "
        "(different SHA types; not compared)"
    )


def _findings_lines(receipt: dict | None, acceptance: dict) -> list[str]:
    lines: list[str] = []
    acc_i = _as_dict(acceptance.get("integrity"))
    rec_i = _as_dict((receipt or {}).get("integrity"))
    for f in rec_i.get("findings") or acc_i.get("findings") or []:
        if isinstance(f, dict):
            lines.append(f"[{f.get('severity')}] {f.get('summary')}")
    for o in rec_i.get("graph_observations") or acc_i.get("graph_observations") or []:
        if isinstance(o, dict):
            lines.append(f"graph-obs [{o.get('severity')}] {o.get('summary')}")
    for f in acceptance.get("criteria_findings") or []:
        if isinstance(f, dict):
            lines.append(f"criterion {f.get('criterion_id')}: {f.get('judgment')}")
    for j in _as_dict((receipt or {}).get("semantic")).get("judgments") or []:
        if isinstance(j, dict):
            lines.append(
                f"criterion {j.get('criterion_id')}: {j.get('judgment')} "
                f"@ {j.get('confidence')}"
            )
    return lines


# ── list formatting (width-aware) ───────────────────────────────────────────


def terminal_width(fallback: int = 80) -> int:
    """Respect COLUMNS; else shutil.get_terminal_size.

    COLUMNS=0 / empty / non-int is ignored (some shells export COLUMNS=0 when
    not a TTY).
    """
    env = os.environ.get("COLUMNS")
    if env is not None and str(env).strip():
        try:
            n = int(env)
            if n > 0:
                return max(20, n)
        except ValueError:
            pass
    try:
        n = int(shutil.get_terminal_size(fallback=(fallback, 24)).columns)
        if n > 0:
            return max(20, n)
    except OSError:
        pass
    return fallback


def _ellipsize(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def _soft_wrap(text: str, width: int, *, cont_indent: str = "  ") -> list[str]:
    """Wrap on spaces when possible; never emit a line longer than width.

    First line uses text as-is (including any leading indent already in text).
    Subsequent lines are prefixed with cont_indent.
    """
    if width < 1:
        return []
    if not text:
        return [""]
    if len(cont_indent) >= width:
        cont_indent = ""
    out: list[str] = []
    rest = text
    first = True
    while rest:
        budget = width if first else width - len(cont_indent)
        if budget < 1:
            budget = 1
        if len(rest) <= budget:
            out.append(rest if first else cont_indent + rest)
            break
        window = rest[:budget]
        br = window.rfind(" ")
        min_br = max(4, budget // 5)
        if br >= min_br:
            chunk = rest[:br].rstrip()
            rest = rest[br:].lstrip()
        else:
            chunk = rest[:budget]
            rest = rest[budget:]
        out.append(chunk if first else cont_indent + chunk)
        first = False
    return [line if len(line) <= width else line[:width] for line in out]


def _graph_status_reason(project_id: str, node_id: str, graph_status: str) -> str:
    """Latest history reason matching current graph status, or '-' if none/unavailable."""
    hist_mod = _load_status_history_mod()
    if hist_mod is None:
        return "-"
    try:
        last = hist_mod.latest_reason(
            project_id,
            node_id,
            runtime_root=runtime_root(),
            kind="graph",
            matching_to_status=str(graph_status),
        )
    except ValueError:
        return "!err"
    if not last:
        return "-"
    reason = str(last.get("reason") or "").strip()
    return reason if reason else "-"


def format_list_lines(
    rows: list[tuple[str, str, str, str, str, str, str]],
    width: int,
) -> list[str]:
    """Render list rows for a terminal width.

    rows: (node_id, graph, runtime, verdict, type, title, reason)

    <120: compact multi-line records — exact node_id alone on line 1;
          line 2+ carry GRAPH/RUNTIME/VERDICT, then REASON, then TYPE/TITLE.
    >=120: table-like scan; ID intact; REASON + TITLE are truncated fields;
           no emitted line exceeds width.
    """
    if not rows:
        return []
    width = max(20, int(width))

    if width < LIST_WIDE_MIN_COLUMNS:
        lines: list[str] = []
        for nid, g, rt, v, ntype, title, reason in rows:
            # Line 1: exact full node_id — never truncated (IDs short by canon).
            lines.append(nid)
            meta = f"  GRAPH {g}  RUNTIME {rt}  VERDICT {v}"
            lines.extend(_soft_wrap(meta, width, cont_indent="  "))
            reason_line = f"  REASON {reason if reason else '-'}"
            lines.extend(_soft_wrap(reason_line, width, cont_indent="  "))
            rest_bits = [b for b in (ntype, title) if b]
            if rest_bits:
                cont = "  " + "  ".join(rest_bits)
                lines.extend(_soft_wrap(cont, width, cont_indent="  "))
        # Clamp non-id lines only (id lines must stay exact).
        clamped: list[str] = []
        id_set = {r[0] for r in rows}
        for ln in lines:
            if ln in id_set:
                clamped.append(ln)
            else:
                clamped.append(ln if len(ln) <= width else ln[:width])
        return clamped

    # Wide: table with fixed signal columns; REASON and TITLE share remainder.
    id_w = max(len("ID"), max(len(r[0]) for r in rows))
    g_w = max(len("GRAPH"), max(len(r[1]) for r in rows))
    rt_w = max(len("RUNTIME"), max(len(r[2]) for r in rows))
    v_w = max(len("VERDICT"), max(len(r[3]) for r in rows))
    t_w = max(len("TYPE"), max(len(r[4]) for r in rows))
    # separators = 2 spaces × 6 between seven columns
    fixed = id_w + 2 + g_w + 2 + rt_w + 2 + v_w + 2 + t_w + 2
    if fixed + 12 >= width:
        # Pathological narrow-"wide": fall back to compact layout.
        return format_list_lines(rows, min(width, LIST_WIDE_MIN_COLUMNS - 1))
    flex = width - fixed
    # Prefer showing reason; give it ~40% of flex, rest to title (min 8 each).
    reason_w = max(8, min(36, flex * 2 // 5))
    title_w = max(8, flex - reason_w - 2)
    # If still too tight, rebalance.
    if reason_w + 2 + title_w > flex:
        reason_w = max(8, flex // 2 - 1)
        title_w = max(8, flex - reason_w - 2)

    header = (
        f"{'ID':<{id_w}}  {'GRAPH':<{g_w}}  {'RUNTIME':<{rt_w}}  "
        f"{'VERDICT':<{v_w}}  {'TYPE':<{t_w}}  "
        f"{'REASON':<{reason_w}}  TITLE"
    )
    if len(header) > width:
        header = header[:width]

    out = [header]
    for nid, g, rt, v, ntype, title, reason in rows:
        line = (
            f"{nid:<{id_w}}  {g:<{g_w}}  {rt:<{rt_w}}  "
            f"{v:<{v_w}}  {ntype:<{t_w}}  "
            f"{_ellipsize(reason or '-', reason_w):<{reason_w}}  "
            f"{_ellipsize(title, title_w)}"
        )
        if len(line) > width:
            line = line[:width]
        out.append(line)
    return out


# ── commands ───────────────────────────────────────────────────────────────


def cmd_list(
    project: str | None = None,
    status: str | None = None,
    active: bool = False,
    root: Path | None = None,
    db_path: Path | None = None,
    width: int | None = None,
) -> int:
    root = config_root(root)
    if status is not None and status not in GRAPH_STATUSES:
        print(
            f"Invalid --status '{status}'. Valid: {', '.join(GRAPH_STATUSES)}"
        )
        return 2

    projects = list_project_ids(root)
    if project:
        if project not in projects:
            print(f"Project '{project}' not found. Available: {', '.join(projects)}")
            return 1
        projects = [project]
    if not projects:
        print("No projects found")
        return 0

    # per-project rows: (nid, graph, runtime, verdict, type, title, reason)
    by_project: list[tuple[str, list[tuple[str, str, str, str, str, str, str]]]] = []
    total = 0
    for pid in projects:
        try:
            nodes = iter_nodes(root, pid)
        except Exception as e:
            print(f"# {pid}: {e}", file=sys.stderr)
            by_project.append((pid, []))
            continue
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for nid, doc, entry in nodes:
            # Preserve the original list command's project index as its graph-status
            # source; `node show` exposes any mismatch with the full node document.
            graph_status = (entry or {}).get("status") or doc.get("status") or "?"
            if status and graph_status != status:
                continue
            if active and graph_status not in ACTIVE_STATUSES:
                continue
            ev = fetch_runtime_evidence(root, pid, nid, db_path=db_path)
            ntype = str(doc.get("type") or (entry or {}).get("type") or "")
            title = str(doc.get("title") or (entry or {}).get("title") or "")
            reason = _graph_status_reason(pid, nid, str(graph_status))
            rows.append((
                nid,
                str(graph_status),
                ev.queue_state if ev.queue_state != "-" else "-",
                ev.verdict if ev.verdict != "-" else "-",
                ntype,
                title,
                reason,
            ))
        by_project.append((pid, rows))
        total += len(rows)

    if total == 0:
        print("No nodes matched the given filters.")
        return 0

    term_w = terminal_width() if width is None else max(20, int(width))

    for pid, rows in by_project:
        print(f"\n# {pid}")
        if not rows:
            print("  (no matching nodes)")
            continue
        for line in format_list_lines(rows, term_w):
            print(line)
    return 0


def _fmt_list(items: Any) -> list[str]:
    if not items:
        return ["(none)"]
    if not isinstance(items, list):
        return [str(items)]
    out = []
    for it in items:
        if isinstance(it, dict):
            cid = it.get("id", "")
            crit = it.get("criterion", it)
            out.append(f"- {cid}: {crit}" if cid else f"- {crit}")
        else:
            out.append(f"- {it}")
    return out


def cmd_show(
    project: str,
    node_id: str,
    trace: bool = False,
    root: Path | None = None,
    db_path: Path | None = None,
) -> int:
    root = config_root(root)
    try:
        proj = load_project_doc(root, project)
    except FileNotFoundError:
        print(f"Project '{project}' not found")
        return 1

    if not node_path(root, project, node_id).exists():
        print(f"Node '{node_id}' not found in project '{project}'")
        return 1

    try:
        doc = load_node_doc(root, project, node_id)
    except Exception as e:
        print(f"Failed to load node: {e}")
        return 1

    entry = project_index_entry(proj, node_id)
    graph_status = doc.get("status", "?")
    index_status = entry.get("status") if entry else None

    print(f"node_id:           {doc.get('node_id', node_id)}")
    print(f"title:             {doc.get('title', '')}")
    print(f"type:              {doc.get('type', '')}")
    print(f"priority:          {doc.get('priority', '')}")
    print(f"graph status:      {graph_status}", end="")
    if entry is None:
        print("  (missing from project.yaml index)")
        print("WARNING: project.yaml has no nodes entry for this node_id")
    elif index_status != graph_status:
        print(f"  (index: {index_status})")
        print("WARNING: DESYNC — node YAML status != project.yaml index status")
    else:
        print()

    hist_mod = _load_status_history_mod()
    if hist_mod is not None:
        try:
            last = hist_mod.latest_reason(
                project,
                node_id,
                runtime_root=runtime_root(),
                kind="graph",
                matching_to_status=str(graph_status),
            )
            stale = None
            if last is None:
                # Any latest graph record that does not match current status.
                any_last = hist_mod.latest_reason(
                    project,
                    node_id,
                    runtime_root=runtime_root(),
                    kind="graph",
                )
                if any_last is not None:
                    stale = any_last
            if last:
                print(f"status reason:     {last.get('reason', '')}")
                print(
                    f"  (from {last.get('from_status', '?')} -> "
                    f"{last.get('to_status', '?')} @ {last.get('ts', '?')})"
                )
            elif stale is not None:
                print(
                    "status reason:     (none matching current graph status "
                    f"'{graph_status}')"
                )
                print(
                    f"  WARNING: stale history ends at "
                    f"{stale.get('from_status', '?')} -> "
                    f"{stale.get('to_status', '?')}: {stale.get('reason', '')}"
                )
            else:
                print("status reason:     (none recorded in node_status_history)")
        except ValueError as e:
            print(f"status reason:     ERROR reading history: {e}")
    else:
        print("status reason:     (runtime history module unavailable)")

    print("\nintent (why):")
    for line in str(doc.get("why") or "").rstrip().splitlines() or [""]:
        print(f"  {line}")

    print("\ndepends_on:")
    for line in _fmt_list(doc.get("depends_on")):
        print(f"  {line}")
    print("unlocks:")
    for line in _fmt_list(doc.get("unlocks")):
        print(f"  {line}")

    print("\nacceptance_criteria:")
    for line in _fmt_list(doc.get("acceptance_criteria")):
        print(f"  {line}")
    print("constraints:")
    for line in _fmt_list(doc.get("constraints")):
        print(f"  {line}")
    print("required_artifacts:")
    for line in _fmt_list(doc.get("required_artifacts")):
        print(f"  {line}")
    print("allowed_execution_modes:")
    for line in _fmt_list(doc.get("allowed_execution_modes")):
        print(f"  {line}")

    ev = fetch_runtime_evidence(root, project, node_id, db_path=db_path)
    print("\n--- layers (distinct) ---")
    print(f"graph status:      {graph_status}")
    runtime_extra = (
        f"  (job status: {ev.job_status})"
        if ev.job_status not in ("-", None)
        else ""
    )
    print(f"runtime state:     {ev.queue_state}{runtime_extra}")
    if ev.job_id:
        print(f"runtime job_id:    {ev.job_id}")
    print(f"evaluator verdict: {ev.verdict}")

    print("\n--- evaluator summary ---")
    if not ev.has_evaluation:
        print("no evaluation evidence")
    else:
        acc = ev.acceptance_check
        receipt = ev.receipt
        lane, harness = _lane_fields(receipt, acc)
        c_verdict = _pick(acc, receipt, "criteria_verdict")
        c_conf = _pick(acc, receipt, "criteria_confidence")
        if c_conf is None:
            c_conf = _pick(acc, receipt, "confidence")
        integ = _as_dict(acc.get("integrity")) or _as_dict((receipt or {}).get("integrity"))
        print(
            f"criteria:  verdict={c_verdict or '-'}  "
            f"confidence={c_conf if c_conf is not None else '-'}  "
            f"lane={lane.get('criteria') or '-'}"
        )
        print(
            f"integrity: verdict={integ.get('verdict') or '-'}  "
            f"confidence={integ.get('confidence') if integ.get('confidence') is not None else '-'}  "
            f"lane={lane.get('integrity') or '-'}"
        )
        for side in ("criteria", "integrity"):
            if harness.get(side):
                print(f"harness error ({side}): {harness[side]}")
        print(f"provenance: {_provenance_line(receipt, acc) or '-'}")
        print(f"context coverage: {_coverage_line(receipt, acc) or '-'}")
        findings = _findings_lines(receipt, acc)
        if findings:
            print("findings / graph observations:")
            for fl in findings:
                print(f"  - {fl}")
        else:
            print("findings / graph observations: (none)")
        print(f"receipt path: {ev.receipt_path or '-'}")

    if trace:
        print("\n--- trace ---")
        if ev.jobs_history:
            print("jobs (newest first):")
            for j in ev.jobs_history:
                print(
                    f"  {j.get('job_id')}  queue_state={j.get('queue_state')}  "
                    f"status={j.get('status')}  created={j.get('created_at')}"
                )
        else:
            print("jobs: (none)")
        if ev.results_history:
            print("results (newest first):")
            for r in ev.results_history:
                acc = r.get("_acceptance") or {}
                print(
                    f"  job={r.get('job_id')}  received={r.get('received_at')}  "
                    f"outcome={r.get('outcome')}/{r.get('status')}  "
                    f"verdict={acc.get('verdict', '-')}"
                )
        else:
            print("results: (none)")
        sem = _as_dict((ev.receipt or {}).get("semantic"))
        integ = _as_dict((ev.receipt or {}).get("integrity"))
        st = sem.get("tool_trace") or sem.get("budget_trace")
        print("semantic trace:")
        print(json.dumps(st, indent=2, default=str) if st else "  (none)")
        it = integ.get("tool_trace")
        print("integrity tool_trace:")
        print(json.dumps(it, indent=2, default=str) if it else "  (none)")
    return 0


def cmd_set_status(
    project: str,
    node_id: str,
    status: str,
    yes: bool = False,
    reason: str | None = None,
    root: Path | None = None,
) -> int:
    root = config_root(root)

    if status not in GRAPH_STATUSES:
        print(
            f"Invalid graph status '{status}'. Valid: {', '.join(GRAPH_STATUSES)}"
        )
        return 2

    reason_text = (reason or "").strip()
    if not reason_text:
        print(
            "ERROR: --reason is required. Status without reason misleads agents "
            "(e.g. deferred ≠ work was bad)."
        )
        return 2

    problems = verify_ids_before_write(root, project, node_id)
    if problems:
        for p in problems:
            print(f"ERROR: {p}")
        return 1

    npath = node_path(root, project, node_id)
    ppath = project_yaml_path(root, project)
    node_bytes = npath.read_bytes()
    project_bytes = ppath.read_bytes()
    try:
        node_text = node_bytes.decode("utf-8")
        project_text = project_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"ERROR: UTF-8 decode failed: {e}")
        return 1

    try:
        new_node_text, old_node_status = replace_node_status(node_text, status)
        new_project_text, old_proj_status = replace_project_index_status(
            project_text, node_id, status
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    cand_problems = verify_candidates(
        new_node_text, new_project_text, project, node_id, status
    )
    if cand_problems:
        for p in cand_problems:
            print(f"ERROR: {p}")
        print("No files written.")
        return 1

    print(f"node:    graphs/{project}/nodes/{node_id}.yaml  {old_node_status} -> {status}")
    print(f"project: graphs/{project}/project.yaml          {old_proj_status} -> {status}")
    print(f"reason:  {reason_text}")

    if old_node_status == status and old_proj_status == status:
        print("No-op: already at target status — files not rewritten.")
        return 0

    if old_node_status != old_proj_status:
        print(
            f"NOTE: node YAML ({old_node_status}) and project index ({old_proj_status}) "
            "were desynced; both will be set to the new status."
        )

    if not yes:
        try:
            ans = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans != "y":
            print("Aborted.")
            return 1

    # Reason ledger first, then graph. Never advance graph truth without a
    # durable reason. Crash after history / before YAML leaves an orphan record
    # that `node show` ignores unless to_status matches current graph status.
    hist_mod = _load_status_history_mod()
    if hist_mod is None:
        print(
            "ERROR: runtime node_status_history module missing under "
            f"{runtime_root()} — no files written."
        )
        return 1

    try:
        baseline = baseline_error_keys(root, project)
    except Exception as e:
        print(f"ERROR: validate.py baseline failed before write: {e}")
        print("No files written.")
        return 1

    try:
        hist_path = hist_mod.append_status_change(
            project_id=project,
            node_id=node_id,
            from_status=old_node_status,
            to_status=status,
            reason=reason_text,
            kind="graph",
            source="gddp node set-status",
            runtime_root=runtime_root(),
        )
    except Exception as e:
        print(f"ERROR: history append failed ({e}) — no files written.")
        return 1

    try:
        _atomic_write(npath, new_node_text)
        _atomic_write(ppath, new_project_text)
    except Exception as e:
        try:
            _restore_pair(npath, ppath, node_bytes, project_bytes)
            print(
                f"ERROR: graph write failed ({e}); rolled back YAML. "
                f"History entry left at {hist_path} (orphaned; show ignores "
                "until to_status matches graph)."
            )
        except Exception as e2:
            print(
                f"ERROR: graph write failed ({e}); rollback also failed: {e2}. "
                f"History entry at {hist_path}."
            )
        return 1

    post = validate_status_change_docs(root, project, node_id, status, baseline)
    if post:
        try:
            _restore_pair(npath, ppath, node_bytes, project_bytes)
            print("ERROR: post-write validation failed; rolled back both files:")
            for p in post:
                print(f"  - {p}")
            print(
                f"History entry left at {hist_path} (orphaned; show ignores "
                "until to_status matches graph)."
            )
        except Exception as e2:
            print("ERROR: post-write validation failed and rollback failed:")
            for p in post:
                print(f"  - {p}")
            print(f"  rollback: {e2}")
            print(f"  history: {hist_path}")
        return 1

    print(f"Done: {node_id} graph status -> {status}")
    print(f"history: {hist_path}")
    return 0
