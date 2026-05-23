import os
import sqlite3
from datetime import datetime

from core.resource_paths import ensure_app_file

DB_DIR = os.path.dirname(ensure_app_file("data", "report.db"))
DB_PATH = ensure_app_file("data", "report.db")


def get_conn():
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_report_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS video_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        video_id TEXT UNIQUE,
        order_code TEXT,

        camera_id TEXT,
        camera_name TEXT,

        employee_id TEXT,
        employee_name TEXT,
        department TEXT,
        position TEXT,

        video_name TEXT,
        video_path TEXT,

        date TEXT,
        start_time TEXT,
        end_time TEXT,

        duration_sec INTEGER,
        file_size_mb REAL,

        status TEXT DEFAULT 'completed',
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def insert_video_report(entry: dict):
    """
    Ghi 1 video vào database báo cáo.
    Nếu video_id đã tồn tại thì bỏ qua.
    """

    init_report_db()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO video_report (
        video_id,
        order_code,

        camera_id,
        camera_name,

        employee_id,
        employee_name,
        department,
        position,

        video_name,
        video_path,

        date,
        start_time,
        end_time,

        duration_sec,
        file_size_mb,

        status,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry.get("id", ""),
        entry.get("order_code", ""),

        entry.get("camera_id", ""),
        entry.get("camera_name", ""),

        entry.get("employee_id", ""),
        entry.get("employee_name", ""),
        entry.get("department", ""),
        entry.get("position", ""),

        entry.get("filename", ""),
        entry.get("file_path", ""),

        entry.get("date", ""),
        entry.get("start_time", ""),
        entry.get("end_time", ""),

        int(entry.get("duration_sec", 0)),
        float(entry.get("file_size_mb", 0)),

        entry.get("status", "completed"),
        entry.get("created_at", datetime.now().isoformat())
    ))

    conn.commit()
    conn.close()


def query_report_by_date(from_date: str, to_date: str):
    init_report_db()

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM video_report
    WHERE date >= ? AND date <= ?
    ORDER BY date ASC, start_time ASC
    """, (from_date, to_date))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return rows


def query_report_by_employee(from_date: str, to_date: str):
    init_report_db()

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT
        employee_id,
        employee_name,
        department,
        position,

        COUNT(DISTINCT order_code) AS total_orders,
        COUNT(*) AS total_videos,
        SUM(duration_sec) AS total_duration_sec,
        SUM(file_size_mb) AS total_size_mb
    FROM video_report
    WHERE date >= ? AND date <= ?
    GROUP BY employee_id, employee_name, department, position
    ORDER BY total_orders DESC
    """, (from_date, to_date))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return rows
