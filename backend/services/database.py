import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

_LOCAL_TZ = timezone(timedelta(hours=7))


def _local_timestamp():
    return datetime.now(_LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S+07:00")


SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    model_key TEXT NOT NULL,
    tx_id TEXT,
    raw_log TEXT NOT NULL,
    golden_summary TEXT,
    generated_summary TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    rouge1_f1 REAL,
    rouge2_f1 REAL,
    rougel_f1 REAL,
    meteor REAL,
    bertscore_f1 REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS executive_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key TEXT NOT NULL,
    log_count INTEGER NOT NULL,
    executive_summary TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    analysis_ids TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_logs (
    tx_id TEXT PRIMARY KEY,
    timestamp TEXT,
    timestamp_raw TEXT,
    request TEXT,
    status TEXT,
    alerts TEXT,
    raw_log TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dataset_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key TEXT NOT NULL,
    log_filename TEXT,
    golden_csv_filename TEXT,
    txid_count INTEGER NOT NULL,
    metrics_summary TEXT,
    csv_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stat_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_dir TEXT,
    source_files TEXT,
    highlights TEXT,
    conclusions TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    current_item TEXT,
    result TEXT,
    error TEXT,
    page_origin TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.create_function("CURRENT_TIMESTAMP", 0, _local_timestamp)
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA)
        cursor = conn.execute("PRAGMA table_info(executive_summaries)")
        columns = {row[1] for row in cursor.fetchall()}
        if "analysis_ids" not in columns:
            conn.execute("ALTER TABLE executive_summaries ADD COLUMN analysis_ids TEXT")
        conn.commit()
    finally:
        conn.close()


def save_analysis_rows(db_path: Path, rows: Iterable[dict]) -> list[int]:
    conn = _connect(db_path)
    saved_ids: list[int] = []
    try:
        for row in rows:
            cursor = conn.execute(
                """
                INSERT INTO analyses (
                    mode, model_key, tx_id, raw_log, golden_summary, generated_summary,
                    latency_ms, rouge1_f1, rouge2_f1, rougel_f1, meteor, bertscore_f1
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("mode"),
                    row.get("model_key"),
                    row.get("tx_id"),
                    row.get("raw_log"),
                    row.get("golden_summary"),
                    row.get("generated_summary"),
                    row.get("latency_ms"),
                    row.get("rouge1_f1"),
                    row.get("rouge2_f1"),
                    row.get("rougel_f1"),
                    row.get("meteor"),
                    row.get("bertscore_f1"),
                ),
            )
            saved_ids.append(int(cursor.lastrowid))
        conn.commit()
    finally:
        conn.close()
    return saved_ids


def get_analyses_by_ids(db_path: Path, analysis_ids: list[int]) -> list[dict]:
    if not analysis_ids:
        return []

    placeholders = ",".join(["?"] * len(analysis_ids))
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            f"SELECT * FROM analyses WHERE id IN ({placeholders}) ORDER BY id",
            analysis_ids,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_recent_analyses(db_path: Path, mode: str = "realtime", limit: int = 50) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM analyses WHERE mode = ? ORDER BY created_at DESC LIMIT ?",
            (mode, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def save_executive_summary(db_path: Path, model_key: str, log_count: int, executive_summary: str, latency_ms: float, analysis_ids: list[int] | None = None) -> int:
    conn = _connect(db_path)
    try:
        ids_json = json.dumps(analysis_ids) if analysis_ids else None
        cursor = conn.execute(
            """
            INSERT INTO executive_summaries (model_key, log_count, executive_summary, latency_ms, analysis_ids)
            VALUES (?, ?, ?, ?, ?)
            """,
            (model_key, log_count, executive_summary, latency_ms, ids_json),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_recent_executive_summaries(db_path: Path, limit: int = 20) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM executive_summaries ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_executive_summary_by_id(db_path: Path, summary_id: int) -> dict | None:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM executive_summaries WHERE id = ?",
            (summary_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_raw_logs(db_path: Path, rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = _connect(db_path)
    saved = 0
    try:
        for row in rows:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO raw_logs (tx_id, timestamp, timestamp_raw, request, status, alerts, raw_log) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row.get("tx_id"), row.get("timestamp"), row.get("timestamp_raw"),
                     row.get("request"), row.get("status"), json.dumps(row.get("alerts", [])),
                     row.get("raw_log")),
                )
                saved += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    finally:
        conn.close()
    return saved


def get_raw_logs(db_path: Path, limit: int = 500) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM raw_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["alerts"] = json.loads(d.get("alerts") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["alerts"] = []
            rows.append(d)
        return rows
    finally:
        conn.close()


def delete_analysis(db_path: Path, analysis_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_executive_summary(db_path: Path, summary_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM executive_summaries WHERE id = ?", (summary_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def save_dataset_evaluation(db_path: Path, model_key: str, log_filename: str, golden_csv_filename: str, txid_count: int, metrics_summary: dict, csv_path: str) -> int:
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO dataset_evaluations (model_key, log_filename, golden_csv_filename, txid_count, metrics_summary, csv_path) VALUES (?, ?, ?, ?, ?, ?)",
            (model_key, log_filename, golden_csv_filename, txid_count, json.dumps(metrics_summary), csv_path),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_dataset_evaluations(db_path: Path, limit: int = 50) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM dataset_evaluations ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["metrics_summary"] = json.loads(d.get("metrics_summary") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["metrics_summary"] = {}
            rows.append(d)
        return rows
    finally:
        conn.close()


def delete_dataset_evaluation(db_path: Path, eval_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM dataset_evaluations WHERE id = ?", (eval_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def save_stat_comparison(db_path: Path, source_dir: str, source_files: list, highlights: list, conclusions: list) -> int:
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO stat_comparisons (source_dir, source_files, highlights, conclusions) VALUES (?, ?, ?, ?)",
            (source_dir, json.dumps(source_files), json.dumps(highlights), json.dumps(conclusions)),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_stat_comparisons(db_path: Path, limit: int = 50) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM stat_comparisons ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            for key in ("source_files", "highlights", "conclusions"):
                try:
                    d[key] = json.loads(d.get(key) or "[]")
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
            rows.append(d)
        return rows
    finally:
        conn.close()


def delete_stat_comparison(db_path: Path, comp_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM stat_comparisons WHERE id = ?", (comp_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def create_task(db_path: Path, task_id: str, task_type: str, total: int, page_origin: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO tasks (task_id, task_type, total, page_origin) VALUES (?, ?, ?, ?)",
            (task_id, task_type, total, page_origin),
        )
        conn.commit()
    finally:
        conn.close()


def update_task(db_path: Path, task_id: str, **kwargs) -> None:
    allowed = {"status", "progress", "total", "current_item", "result", "error"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = _local_timestamp()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn = _connect(db_path)
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_task(db_path: Path, task_id: str) -> dict | None:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["result"] = json.loads(d.get("result")) if d.get("result") else None
        except (json.JSONDecodeError, TypeError):
            d["result"] = None
        return d
    finally:
        conn.close()


def get_active_tasks(db_path: Path, page_origin: str | None = None) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if page_origin:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'running') AND page_origin = ? ORDER BY created_at DESC",
                (page_origin,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'running') ORDER BY created_at DESC",
            )
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["result"] = json.loads(d.get("result")) if d.get("result") else None
            except (json.JSONDecodeError, TypeError):
                d["result"] = None
            rows.append(d)
        return rows
    finally:
        conn.close()


def get_recent_tasks(db_path: Path, limit: int = 20, page_origin: str | None = None) -> list[dict]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if page_origin:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE page_origin = ? ORDER BY created_at DESC LIMIT ?",
                (page_origin, limit),
            )
        else:
            cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["result"] = json.loads(d.get("result")) if d.get("result") else None
            except (json.JSONDecodeError, TypeError):
                d["result"] = None
            rows.append(d)
        return rows
    finally:
        conn.close()
