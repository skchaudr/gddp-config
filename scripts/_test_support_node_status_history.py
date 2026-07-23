"""Append-only node status reason history under runtime node_status_history/.

Graph node YAML stays status-only. Reasons live here so agents read *why*
before inventing a story from the status enum alone.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_default_root = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(
    os.environ.get("GDDP_RUNTIME_ROOT")
    or os.environ.get("OPCLAW_ROOT")
    or _default_root
)
HISTORY_DIRNAME = "node_status_history"

# Canonical record fields — never overwritten by `extra`.
_CANONICAL_KEYS = frozenset({
    "ts",
    "project_id",
    "node_id",
    "from_status",
    "to_status",
    "reason",
    "kind",
    "source",
})
_REQUIRED_KEYS = _CANONICAL_KEYS


def history_root(runtime_root: Path | str | None = None) -> Path:
    root = Path(runtime_root) if runtime_root is not None else RUNTIME_ROOT
    return Path(root).expanduser().resolve() / HISTORY_DIRNAME


def history_path(
    project_id: str,
    node_id: str,
    *,
    runtime_root: Path | str | None = None,
) -> Path:
    return history_root(runtime_root) / project_id / f"{node_id}.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_record(obj: Any, *, line_no: int | None = None) -> dict[str, Any]:
    where = f" line {line_no}" if line_no is not None else ""
    if not isinstance(obj, dict):
        raise ValueError(f"history record{where} is not a JSON object")
    missing = sorted(_REQUIRED_KEYS - set(obj))
    if missing:
        raise ValueError(
            f"history record{where} missing required keys: {', '.join(missing)}"
        )
    reason = str(obj.get("reason") or "").strip()
    if not reason:
        raise ValueError(f"history record{where} has empty reason")
    kind = obj.get("kind")
    if kind not in ("graph", "queue"):
        raise ValueError(f"history record{where} has invalid kind: {kind!r}")
    return obj


def append_status_change(
    *,
    project_id: str,
    node_id: str,
    from_status: str,
    to_status: str,
    reason: str,
    kind: str = "graph",
    source: str = "gddp",
    runtime_root: Path | str | None = None,
    ts: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append one transition with exclusive lock + fsync. Returns file path."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("reason is required and must be non-empty")
    if kind not in ("graph", "queue"):
        raise ValueError(f"kind must be 'graph' or 'queue', got {kind!r}")
    if not project_id or not node_id:
        raise ValueError("project_id and node_id are required")

    record: dict[str, Any] = {
        "ts": ts or now_iso(),
        "project_id": project_id,
        "node_id": node_id,
        "from_status": from_status,
        "to_status": to_status,
        "reason": reason,
        "kind": kind,
        "source": source,
    }
    if extra:
        for key, value in extra.items():
            if key in _CANONICAL_KEYS:
                continue  # never let extra rewrite semantic fields
            record[key] = value

    _validate_record(record)

    path = history_path(project_id, node_id, runtime_root=runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"

    # Exclusive lock across open-append-fsync so concurrent writers serialize.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    # Best-effort directory fsync so the directory entry is durable.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
    return path


def load_history(
    project_id: str,
    node_id: str,
    *,
    runtime_root: Path | str | None = None,
    strict: bool = True,
) -> list[dict[str, Any]]:
    """Load history records.

    strict=True (default): raise on malformed lines — silent skip is forbidden
    for an integrity ledger. strict=False: return only valid records and ignore
    bad lines (debug only).
    """
    path = history_path(project_id, node_id, runtime_root=runtime_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            out.append(_validate_record(obj, line_no=i))
        except (json.JSONDecodeError, ValueError) as exc:
            if strict:
                raise ValueError(f"{path}: {exc}") from exc
            continue
    return out


def latest_reason(
    project_id: str,
    node_id: str,
    *,
    runtime_root: Path | str | None = None,
    kind: str | None = None,
    matching_to_status: str | None = None,
    strict: bool = True,
) -> dict[str, Any] | None:
    """Return the last history record, optionally filtered by kind and to_status.

    When matching_to_status is set, only a record whose to_status equals that
    value is returned — prevents attaching a stale reason to current graph truth.
    """
    rows = load_history(
        project_id, node_id, runtime_root=runtime_root, strict=strict
    )
    if kind is not None:
        rows = [r for r in rows if r.get("kind") == kind]
    if matching_to_status is not None:
        rows = [r for r in rows if r.get("to_status") == matching_to_status]
    return rows[-1] if rows else None
