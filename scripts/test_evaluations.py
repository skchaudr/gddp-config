from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from evaluations import format_evaluation_row, load_evaluation_rows, print_evaluation_detail


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "queue.db"
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE jobs (
            job_id TEXT, node_id TEXT, project_id TEXT
        );
        CREATE TABLE results (
            job_id TEXT, received_at TEXT, acceptance_check TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO jobs VALUES (?,?,?)",
        ("job-1", "node-a", "proj"),
    )
    con.execute(
        "INSERT INTO results VALUES (?,?,?)",
        (
            "job-1",
            "2026-08-13T01:00:00+00:00",
            json.dumps(
                {
                    "verdict": "pass",
                    "receipt_path": str(tmp_path / "verification" / "proj" / "node-a" / "job-1.json"),
                    "lane_status": {"criteria": "completed", "integrity": "completed"},
                    "evaluation_timing": {
                        "started_at": "2026-08-13T00:58:00+00:00",
                        "finished_at": "2026-08-13T01:00:00+00:00",
                        "wall_s": 12.5,
                        "criteria": {
                            "status": "completed",
                            "elapsed_s": 8.0,
                            "tool_calls": 3,
                        },
                        "integrity": {
                            "status": "completed",
                            "elapsed_s": 4.5,
                            "tool_calls": 2,
                        },
                    },
                }
            ),
        ),
    )
    con.commit()
    con.close()
    return db_path


def test_load_merges_db_and_file_receipts_newest_first(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    receipt_root = tmp_path / "verification"
    linked = receipt_root / "proj" / "node-a" / "job-1.json"
    linked.parent.mkdir(parents=True)
    linked.write_text(json.dumps({"verdict": "pass", "project_id": "proj", "node_id": "node-a"}))
    orphan = receipt_root / "proj" / "node-b" / "manual.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        json.dumps(
            {
                "verdict": "needs-human-review",
                "project_id": "proj",
                "node_id": "node-b",
                "generated_at": "2026-08-13T02:00:00+00:00",
                "evaluation_timing": {
                    "started_at": "2026-08-13T01:50:00+00:00",
                    "finished_at": "2026-08-13T02:00:00+00:00",
                    "wall_s": 600.0,
                    "criteria": {"status": "completed", "elapsed_s": 10.0, "tool_calls": 1},
                    "integrity": {"status": "timed-out", "elapsed_s": 590.0, "tool_calls": 0},
                },
            }
        )
    )

    rows = load_evaluation_rows(db_path=db_path, receipt_root=receipt_root)
    assert [row["node_id"] for row in rows] == ["node-b", "node-a"]
    assert rows[0]["source"] == "receipt"
    assert rows[1]["source"] == "result"
    assert rows[1]["wall_s"] == 12.5


def test_format_row_includes_verdict_and_clocks() -> None:
    line = format_evaluation_row(
        {
            "sort_at": "2026-08-13T01:00:00+00:00",
            "verdict": "pass",
            "wall_s": 12.5,
            "project_id": "proj",
            "node_id": "node-a",
            "criteria_status": "completed",
            "criteria_elapsed_s": 8.0,
            "integrity_status": "timed-out",
            "integrity_elapsed_s": 4.5,
        }
    )
    assert "pass" in line
    assert "wall=12.5s" in line
    assert "c=completed/8.0s" in line
    assert "i=timed-out/4.5s" in line
    assert "proj/node-a" in line


def test_print_detail_is_evidence_only(capsys) -> None:
    print_evaluation_detail(
        {
            "project_id": "proj",
            "node_id": "node-a",
            "verdict": "pass",
            "job_id": "job-1",
            "source": "result",
            "sort_at": "2026-08-13T01:00:00+00:00",
            "wall_s": 12.5,
            "criteria_status": "completed",
            "criteria_elapsed_s": 8.0,
            "integrity_status": "completed",
            "integrity_elapsed_s": 4.5,
            "receipt_path": "/tmp/receipt.json",
            "check": {"required_next_action": "review"},
        }
    )
    out = capsys.readouterr().out
    assert "verdict:    pass" in out
    assert "timing:     wall=12.5s" in out
    assert "review" in out
