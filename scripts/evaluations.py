"""Evaluator receipt list for the gddp control plane.

This module is evidence-only. It never writes graph or node status.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def load_evaluation_rows(
    *,
    db_path: Path | None = None,
    receipt_root: Path | None = None,
) -> list[dict]:
    """Newest-first evaluator rows from the results table and receipt files."""
    rows: list[dict] = []
    seen_receipts: set[str] = set()
    if db_path is not None and db_path.is_file():
        rows.extend(_rows_from_db(db_path, seen_receipts))
    if receipt_root is not None and receipt_root.is_dir():
        rows.extend(_rows_from_receipts(receipt_root, seen_receipts))
    rows.sort(key=lambda row: str(row.get("sort_at") or ""), reverse=True)
    return rows


def format_evaluation_row(row: dict) -> str:
    when = _short_when(row.get("sort_at"))
    verdict = str(row.get("verdict") or "-")
    wall = _clock(row.get("wall_s"))
    project = str(row.get("project_id") or "-")
    node = str(row.get("node_id") or "-")
    criteria = _lane_chip(row.get("criteria_status"), row.get("criteria_elapsed_s"))
    integrity = _lane_chip(row.get("integrity_status"), row.get("integrity_elapsed_s"))
    return (
        f"{when}  {verdict:<22}  wall={wall:<8}  "
        f"c={criteria}  i={integrity}  {project}/{node}"
    )


def print_evaluation_detail(row: dict) -> None:
    print(f"project:    {row.get('project_id') or '-'}")
    print(f"node:       {row.get('node_id') or '-'}")
    print(f"verdict:    {row.get('verdict') or '-'}")
    print(f"job_id:     {row.get('job_id') or '-'}")
    print(f"source:     {row.get('source') or '-'}")
    print(f"when:       {row.get('sort_at') or '-'}")
    print(
        "timing:     "
        f"wall={_clock(row.get('wall_s'))}  "
        f"criteria={_lane_chip(row.get('criteria_status'), row.get('criteria_elapsed_s'))}  "
        f"integrity={_lane_chip(row.get('integrity_status'), row.get('integrity_elapsed_s'))}"
    )
    if row.get("receipt_path"):
        print(f"receipt:    {row['receipt_path']}")
    check = row.get("check") or {}
    why = (
        ((check.get("integrity") or {}).get("reasoning"))
        or check.get("decision_reasoning")
        or check.get("required_next_action")
    )
    if why:
        print("why:")
        for line in str(why).splitlines():
            print(f"  {line}")


def _rows_from_db(db_path: Path, seen_receipts: set[str]) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        fetched = con.execute(
            """
            SELECT r.job_id, r.received_at, r.acceptance_check,
                   j.node_id, j.project_id
            FROM results r
            JOIN jobs j ON j.job_id = r.job_id
            ORDER BY r.received_at DESC
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()

    rows = []
    for raw in fetched:
        check = _parse_check(raw["acceptance_check"])
        receipt_path = check.get("receipt_path")
        if receipt_path:
            seen_receipts.add(str(Path(str(receipt_path)).resolve()) if Path(str(receipt_path)).exists() else str(receipt_path))
        rows.append(_row_from_check(
            check,
            source="result",
            job_id=raw["job_id"],
            project_id=raw["project_id"],
            node_id=raw["node_id"],
            fallback_when=raw["received_at"],
            receipt_path=receipt_path,
        ))
    return rows


def _rows_from_receipts(receipt_root: Path, seen_receipts: set[str]) -> list[dict]:
    rows = []
    for path in sorted(receipt_root.rglob("*.json")):
        resolved = str(path.resolve())
        if resolved in seen_receipts or str(path) in seen_receipts:
            continue
        try:
            check = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(check, dict) or "verdict" not in check:
            continue
        seen_receipts.add(resolved)
        rows.append(_row_from_check(
            check,
            source="receipt",
            job_id=check.get("job_id"),
            project_id=check.get("project_id"),
            node_id=check.get("node_id"),
            fallback_when=check.get("generated_at"),
            receipt_path=str(path),
        ))
    return rows


def _row_from_check(
    check: dict,
    *,
    source: str,
    job_id,
    project_id,
    node_id,
    fallback_when,
    receipt_path,
) -> dict:
    timing = check.get("evaluation_timing") if isinstance(check.get("evaluation_timing"), dict) else {}
    lanes = check.get("lane_status") if isinstance(check.get("lane_status"), dict) else {}
    criteria = timing.get("criteria") if isinstance(timing.get("criteria"), dict) else {}
    integrity = timing.get("integrity") if isinstance(timing.get("integrity"), dict) else {}
    sort_at = (
        timing.get("finished_at")
        or check.get("generated_at")
        or fallback_when
        or ""
    )
    return {
        "key": str(job_id or receipt_path or f"{project_id}/{node_id}"),
        "source": source,
        "job_id": job_id,
        "project_id": project_id,
        "node_id": node_id,
        "verdict": check.get("verdict") or "-",
        "sort_at": sort_at,
        "wall_s": timing.get("wall_s"),
        "criteria_status": criteria.get("status") or lanes.get("criteria") or "n/a",
        "criteria_elapsed_s": criteria.get("elapsed_s"),
        "integrity_status": integrity.get("status") or lanes.get("integrity") or "n/a",
        "integrity_elapsed_s": integrity.get("elapsed_s"),
        "receipt_path": receipt_path,
        "check": check,
    }


def _parse_check(raw) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _short_when(value) -> str:
    text = str(value or "-")
    return text[:19].replace("T", " ")


def _clock(value) -> str:
    if value is None or value == "":
        return "-"
    return f"{value}s"


def _lane_chip(status, elapsed) -> str:
    label = str(status or "n/a")
    if elapsed is None or elapsed == "":
        return label
    return f"{label}/{elapsed}s"
