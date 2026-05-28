# -*- coding: utf-8 -*-
"""MySQL-backed video report compatibility layer.

Legacy UI code imports these functions, but storage is now MySQL only.
"""

from __future__ import annotations

import os
from datetime import datetime

from services.mysql_client import MySQLClient


def init_report_db():
    return True


def insert_video_report(entry: dict):
    db = MySQLClient()
    order_code = entry.get("order_code", "") or ""
    video_path = entry.get("file_path", "") or entry.get("video_path", "") or ""
    if not order_code or not video_path:
        return None

    with db.cursor() as cur:
        cur.execute("SELECT id FROM orders WHERE order_code=%s LIMIT 1", (order_code,))
        row = cur.fetchone()
        if row:
            order_id = int(row["id"])
        else:
            cur.execute(
                """
                INSERT INTO orders (
                    order_code, order_type, order_status, packing_status,
                    conveyor_status, shipping_status
                ) VALUES (%s, 'ECOM', 'NEW', 'WAITING', 'WAITING', 'WAITING')
                """,
                (order_code,),
            )
            order_id = int(cur.lastrowid)

        cur.execute(
            """
            SELECT id
            FROM packing_videos
            WHERE file_path=%s
            LIMIT 1
            """,
            (video_path,),
        )
        existing = cur.fetchone()
        if existing:
            return int(existing["id"])

        cur.execute(
            """
            INSERT INTO packing_videos (
                order_id, order_code, session_type, video_type,
                item_report_enabled, item_count,
                scanner_id, camera_id, camera_name,
                file_path, file_name, file_size, duration_seconds,
                start_time, end_time, employee_code, employee_name, result
            ) VALUES (%s, %s, 'ecom_packing', 'ECOM', 0, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                order_id,
                order_code,
                entry.get("scanner_id", "") or "",
                entry.get("camera_id", "") or "",
                entry.get("camera_name", "") or "",
                video_path,
                entry.get("video_name", "") or entry.get("filename", "") or os.path.basename(video_path),
                int(float(entry.get("file_size_mb", 0) or 0) * 1024 * 1024),
                float(entry.get("duration_sec", 0) or 0),
                entry.get("start_time", "") or None,
                entry.get("end_time", "") or None,
                entry.get("employee_id", "") or "",
                entry.get("employee_name", "") or "",
                entry.get("status", "completed") or "completed",
            ),
        )
        return int(cur.lastrowid)


def query_report_by_date(from_date: str, to_date: str):
    db = MySQLClient()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                pv.id,
                pv.order_code,
                pv.camera_id,
                pv.camera_name,
                pv.employee_code AS employee_id,
                COALESCE(e.employee_name, pv.employee_name) AS employee_name,
                e.department,
                '' AS position,
                pv.file_name AS video_name,
                pv.file_path AS video_path,
                DATE(pv.created_at) AS date,
                pv.start_time,
                pv.end_time,
                pv.duration_seconds AS duration_sec,
                pv.file_size / 1024 / 1024 AS file_size_mb,
                pv.result AS status,
                pv.created_at
            FROM packing_videos pv
            LEFT JOIN employees e ON e.employee_code = pv.employee_code
            WHERE DATE(pv.created_at) >= %s
              AND DATE(pv.created_at) <= %s
            ORDER BY pv.created_at ASC, pv.id ASC
            """,
            (from_date, to_date),
        )
        return list(cur.fetchall())


def query_report_by_employee(from_date: str, to_date: str):
    db = MySQLClient()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                pv.employee_code AS employee_id,
                COALESCE(e.employee_name, pv.employee_name) AS employee_name,
                e.department,
                '' AS position,
                COUNT(DISTINCT pv.order_code) AS total_orders,
                COUNT(*) AS total_videos,
                SUM(pv.duration_seconds) AS total_duration_sec,
                SUM(pv.file_size) / 1024 / 1024 AS total_size_mb
            FROM packing_videos pv
            LEFT JOIN employees e ON e.employee_code = pv.employee_code
            WHERE DATE(pv.created_at) >= %s
              AND DATE(pv.created_at) <= %s
            GROUP BY pv.employee_code, COALESCE(e.employee_name, pv.employee_name), e.department
            ORDER BY total_orders DESC
            """,
            (from_date, to_date),
        )
        return list(cur.fetchall())
