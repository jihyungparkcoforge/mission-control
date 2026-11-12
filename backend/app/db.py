"""SQLite persistence. One connection per operation; WAL mode for concurrent readers."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    name TEXT NOT NULL, station TEXT NOT NULL,
    wind_knots REAL NOT NULL, temp_c REAL NOT NULL, fuel_pct REAL NOT NULL,
    note TEXT NOT NULL,
    verdict TEXT NOT NULL, violations_json TEXT NOT NULL,
    status TEXT NOT NULL,
    subsystem TEXT, model_severity TEXT, final_severity TEXT, brief_by_minutes INTEGER,
    classification_error TEXT,
    classification_json TEXT, checks_json TEXT,
    injection_flag INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    briefing_json TEXT, review_rounds INTEGER NOT NULL DEFAULT 0, review_feedback TEXT,
    decided_by TEXT, decided_at REAL, decision_reason TEXT,
    run_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trace_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    run INTEGER NOT NULL,
    step TEXT NOT NULL,
    model TEXT,
    status TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd TEXT NOT NULL DEFAULT '0',
    started_at REAL NOT NULL, ended_at REAL,
    output TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS ix_trace_report ON trace_steps(report_id);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---- reports ----
    def insert_report(self, data: dict) -> int:
        cols = ", ".join(data)
        qs = ", ".join("?" for _ in data)
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO reports ({cols}) VALUES ({qs})", list(data.values()))
            return int(cur.lastrowid)

    def update_report(self, report_id: int, **fields) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE reports SET {sets} WHERE id = ?", [*fields.values(), report_id])

    def transition(self, report_id: int, from_statuses: tuple[str, ...], **fields) -> bool:
        """Atomic compare-and-set on status. Returns False if the report was not in from_statuses."""
        sets = ", ".join(f"{k} = ?" for k in fields)
        marks = ", ".join("?" for _ in from_statuses)
        with self.conn() as c:
            cur = c.execute(f"UPDATE reports SET {sets} WHERE id = ? AND status IN ({marks})",
                            [*fields.values(), report_id, *from_statuses])
            return cur.rowcount == 1

    def get_report(self, report_id: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            return dict(row) if row else None

    def list_reports(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM reports ORDER BY id DESC")]

    def recover_interrupted(self) -> int:
        with self.conn() as c:
            cur = c.execute("UPDATE reports SET status='error', error_message=? WHERE status='processing'",
                            ("Pipeline interrupted by a server restart. Re-run required.",))
            c.execute("UPDATE trace_steps SET status='error', error='interrupted by restart', ended_at=? "
                      "WHERE status='running'", (time.time(),))
            return cur.rowcount

    # ---- trace ----
    def start_step(self, report_id: int, run: int, step: str, model: str) -> int:
        with self.conn() as c:
            cur = c.execute("INSERT INTO trace_steps (report_id, run, step, model, status, started_at) "
                            "VALUES (?, ?, ?, ?, 'running', ?)", (report_id, run, step, model, time.time()))
            return int(cur.lastrowid)

    def finish_step(self, step_id: int, **fields) -> None:
        fields.setdefault("ended_at", time.time())
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE trace_steps SET {sets} WHERE id = ?", [*fields.values(), step_id])

    def add_code_step(self, report_id: int, run: int, step: str, output: dict) -> None:
        now = time.time()
        with self.conn() as c:
            c.execute("INSERT INTO trace_steps (report_id, run, step, model, status, started_at, ended_at, output) "
                      "VALUES (?, ?, ?, 'code', 'ok', ?, ?, ?)", (report_id, run, step, now, now, json.dumps(output)))

    def get_trace(self, report_id: int) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trace_steps WHERE report_id = ? ORDER BY id", (report_id,))]
