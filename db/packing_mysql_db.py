# -*- coding: utf-8 -*-
"""MySQL-only storage for packing and handover workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from services.mysql_client import MySQLClient


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MySQLPackingDB:
    is_mysql = True

    def __init__(self, db: Optional[MySQLClient] = None):
        self.db = db or MySQLClient()

    def _table_exists_cur(self, cur, table_name: str) -> bool:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
        return bool(row and row.get("cnt"))

    def _ensure_order_cur(self, cur, order_code: str, order_type: str = "WHOLESALE") -> int:
        cur.execute("SELECT id FROM orders WHERE order_code=%s LIMIT 1", (order_code,))
        row = cur.fetchone()
        if row:
            return int(row["id"])
        cur.execute(
            """
            INSERT INTO orders (
                order_code, order_type, order_status, packing_status,
                conveyor_status, shipping_status
            ) VALUES (%s, %s, 'NEW', 'WAITING', 'WAITING', 'WAITING')
            """,
            (order_code, order_type),
        )
        return int(cur.lastrowid)

    def get_active_packing_session(self, scanner_id):
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    order_code AS master_order_code,
                    scanner_id AS packing_scanner_id,
                    employee_code,
                    employee_name,
                    start_time,
                    end_time,
                    total_items,
                    status,
                    note
                FROM packing_sessions
                WHERE scanner_id=%s
                  AND status IN ('PACKING', 'packing')
                ORDER BY id DESC
                LIMIT 1
                """,
                (scanner_id,),
            )
            return cur.fetchone()

    def create_packing_session(
        self,
        master_order_code,
        scanner_id,
        employee_code=None,
        employee_name=None,
        note=None,
    ):
        with self.db.cursor() as cur:
            order_id = self._ensure_order_cur(cur, master_order_code, "WHOLESALE")
            cur.execute(
                """
                INSERT INTO packing_sessions (
                    order_id, order_code, packing_type,
                    employee_code, employee_name, scanner_id,
                    start_time, status, note
                ) VALUES (%s, %s, 'WHOLESALE', %s, %s, %s, NOW(), 'PACKING', %s)
                """,
                (order_id, master_order_code, employee_code, employee_name, scanner_id, note),
            )
            session_id = int(cur.lastrowid)
            cur.execute(
                """
                UPDATE orders
                SET order_status='PACKING', packing_status='PACKING'
                WHERE id=%s
                """,
                (order_id,),
            )
            return session_id

    def add_packing_item(self, session_id, master_order_code, item_code):
        with self.db.cursor() as cur:
            has_small_packages = self._table_exists_cur(cur, "packing_small_packages")
            table_name = "packing_small_packages" if has_small_packages else "wholesale_box_items"
            order_column = "order_code" if has_small_packages else "master_order_code"
            cur.execute(
                f"""
                SELECT COALESCE(MAX(scan_index), 0) + 1 AS next_index
                FROM {table_name}
                WHERE {order_column}=%s
                  AND packing_session_id=%s
                  AND IFNULL(is_deleted, 0)=0
                """,
                (master_order_code, session_id),
            )
            scan_index = int(cur.fetchone()["next_index"] or 1)
            cur.execute(
                """
                SELECT order_id, employee_code, employee_name, scanner_id
                FROM packing_sessions
                WHERE id=%s
                LIMIT 1
                """,
                (session_id,),
            )
            session = cur.fetchone() or {}
            order_id = int(session.get("order_id") or self._ensure_order_cur(cur, master_order_code, "WHOLESALE"))
            child_order_id = self._ensure_order_cur(cur, item_code, "WHOLESALE_CHILD")

            if has_small_packages:
                cur.execute(
                    """
                    INSERT INTO packing_small_packages (
                        order_id, order_code, packing_session_id,
                        small_package_code, scan_index, scanner_id,
                        employee_code, employee_name, scanned_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        order_id,
                        master_order_code,
                        session_id,
                        item_code,
                        scan_index,
                        session.get("scanner_id"),
                        session.get("employee_code"),
                        session.get("employee_name"),
                    ),
                )

            cur.execute(
                """
                INSERT INTO wholesale_box_items (
                    master_order_id, master_order_code, child_order_id, child_order_code,
                    packing_session_id, box_code, scan_index, scanner_id,
                    employee_code, employee_name, scanned_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    order_id,
                    master_order_code,
                    child_order_id,
                    item_code,
                    session_id,
                    item_code,
                    scan_index,
                    session.get("scanner_id"),
                    session.get("employee_code"),
                    session.get("employee_name"),
                ),
            )
            cur.execute(
                """
                UPDATE packing_sessions
                SET total_items = (
                    SELECT COUNT(*)
                    FROM wholesale_box_items
                    WHERE packing_session_id=%s
                      AND IFNULL(is_deleted, 0)=0
                )
                WHERE id=%s
                """,
                (session_id, session_id),
            )
            return scan_index

    def count_packing_items(self, session_id):
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM wholesale_box_items
                WHERE packing_session_id=%s
                  AND IFNULL(is_deleted, 0)=0
                """,
                (session_id,),
            )
            return int(cur.fetchone()["cnt"] or 0)

    def finish_packing_session(self, session_id):
        total_items = self.count_packing_items(session_id)
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE packing_sessions
                SET end_time=NOW(),
                    total_items=%s,
                    status='COMPLETED'
                WHERE id=%s
                """,
                (total_items, session_id),
            )
            cur.execute(
                """
                UPDATE orders o
                JOIN packing_sessions ps ON ps.order_id=o.id
                SET o.order_status='PACKED',
                    o.packing_status='COMPLETED'
                WHERE ps.id=%s
                """,
                (session_id,),
            )
            return total_items

    def find_done_packing_order(self, master_order_code):
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    order_code AS master_order_code,
                    scanner_id AS packing_scanner_id,
                    employee_code,
                    employee_name,
                    start_time,
                    end_time,
                    total_items,
                    status,
                    note
                FROM packing_sessions
                WHERE order_code=%s
                  AND status IN ('COMPLETED', 'PACKED', 'done')
                ORDER BY end_time DESC, id DESC
                LIMIT 1
                """,
                (master_order_code,),
            )
            return cur.fetchone()

    def find_success_handover(self, order_code):
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM wholesale_handover_checks
                WHERE master_order_code=%s
                  AND result IN ('OK', 'success')
                ORDER BY checked_at DESC, id DESC
                LIMIT 1
                """,
                (order_code,),
            )
            return cur.fetchone()

    def create_handover_failed_already_delivered(self, delivery_order_code, scanner_id):
        return self._create_handover_event(
            delivery_order_code=delivery_order_code,
            packing_order_code=None,
            packing_session_id=None,
            packing_scanner_id=None,
            delivery_scanner_id=scanner_id,
            result="failed_already_delivered",
            error_message="Don hang da duoc giao thanh cong truoc do",
        )

    def create_handover_failed_not_packed(self, delivery_order_code, scanner_id):
        return self._create_handover_event(
            delivery_order_code=delivery_order_code,
            packing_order_code=None,
            packing_session_id=None,
            packing_scanner_id=None,
            delivery_scanner_id=scanner_id,
            result="failed_not_packed",
            error_message="Don hang chua duoc dong",
        )

    def create_handover_result(
        self,
        delivery_order_code,
        packing_order_code,
        packing_session_id,
        packing_scanner_id,
        delivery_scanner_id,
        result,
        error_message=None,
        first_scan_time=None,
        second_scan_time=None,
        delivery_employee_code=None,
        delivery_employee_name=None,
    ):
        return self._create_handover_event(
            delivery_order_code=delivery_order_code,
            packing_order_code=packing_order_code,
            packing_session_id=packing_session_id,
            packing_scanner_id=packing_scanner_id,
            delivery_scanner_id=delivery_scanner_id,
            result=result,
            error_message=error_message,
            delivery_employee_code=delivery_employee_code,
            delivery_employee_name=delivery_employee_name,
        )

    def _create_handover_event(
        self,
        delivery_order_code,
        packing_order_code,
        packing_session_id,
        packing_scanner_id,
        delivery_scanner_id,
        result,
        error_message=None,
        delivery_employee_code=None,
        delivery_employee_name=None,
    ):
        with self.db.cursor() as cur:
            master_order_id = self._ensure_order_cur(cur, delivery_order_code, "WHOLESALE")
            matched_code = packing_order_code if packing_order_code == delivery_order_code else None
            mysql_result = "OK" if result == "success" else result
            cur.execute(
                """
                INSERT INTO wholesale_handover_checks (
                    master_order_id, master_order_code, scanned_code,
                    matched_child_order_code, packing_session_id,
                    delivery_scanner_id, employee_code, employee_name,
                    result, message, checked_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    master_order_id,
                    delivery_order_code,
                    packing_order_code or delivery_order_code,
                    matched_code,
                    packing_session_id,
                    delivery_scanner_id,
                    delivery_employee_code,
                    delivery_employee_name,
                    mysql_result,
                    error_message,
                ),
            )
            handover_id = int(cur.lastrowid)
            if mysql_result == "OK":
                cur.execute(
                    """
                    UPDATE orders
                    SET shipping_status='HANDOVER_CHECKED'
                    WHERE order_code=%s
                    """,
                    (delivery_order_code,),
                )
            return handover_id

    def add_record_file(
        self,
        session_type,
        session_id,
        order_code,
        scanner_id,
        camera_id=None,
        file_path=None,
        start_time=None,
        end_time=None,
        duration_sec=None,
        file_size_mb=None,
        result=None,
    ):
        with self.db.cursor() as cur:
            order_id = self._ensure_order_cur(cur, order_code, "WHOLESALE" if session_type == "packing" else "ECOM")
            file_size = int(float(file_size_mb or 0) * 1024 * 1024)
            cur.execute(
                """
                INSERT INTO packing_videos (
                    order_id, order_code, packing_session_id, session_type,
                    video_type, item_report_enabled, item_count,
                    scanner_id, camera_id, camera_name,
                    file_path, file_name, file_size, duration_seconds,
                    start_time, end_time, result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    order_code,
                    session_id,
                    session_type,
                    "WHOLESALE" if session_type == "packing" else "ECOM",
                    1 if session_type == "packing" else 0,
                    self.count_packing_items(session_id) if session_type == "packing" and session_id else 0,
                    scanner_id,
                    camera_id,
                    camera_id,
                    file_path,
                    (file_path or "").replace("\\", "/").split("/")[-1],
                    file_size,
                    float(duration_sec or 0),
                    start_time,
                    end_time,
                    result,
                ),
            )
            return int(cur.lastrowid)

    def update_packing_employee(self, session_id, employee_code=None, employee_name=None):
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE packing_sessions
                SET employee_code=%s,
                    employee_name=%s
                WHERE id=%s
                """,
                (employee_code or "", employee_name or "", session_id),
            )

    def delete_last_packing_item(self, session_id, item_code=None, reason="Xoa thao tac quet nham"):
        with self.db.cursor() as cur:
            params = [session_id]
            where_item = ""
            if item_code:
                where_item = "AND child_order_code=%s"
                params.append(item_code)

            cur.execute(
                f"""
                SELECT id, child_order_code, scan_index, master_order_code
                FROM wholesale_box_items
                WHERE packing_session_id=%s
                  AND IFNULL(is_deleted, 0)=0
                  {where_item}
                ORDER BY scan_index DESC, id DESC
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                """
                UPDATE wholesale_box_items
                SET is_deleted=1,
                    deleted_at=NOW(),
                    deleted_reason=%s
                WHERE id=%s
                """,
                (reason, row["id"]),
            )
            if self._table_exists_cur(cur, "packing_small_packages"):
                cur.execute(
                    """
                    UPDATE packing_small_packages
                    SET is_deleted=1,
                        deleted_at=NOW(),
                        deleted_reason=%s
                    WHERE packing_session_id=%s
                      AND small_package_code=%s
                      AND IFNULL(is_deleted, 0)=0
                    ORDER BY scan_index DESC, id DESC
                    LIMIT 1
                    """,
                    (reason, session_id, row["child_order_code"]),
                )
            cur.execute(
                """
                UPDATE packing_sessions
                SET total_items = (
                    SELECT COUNT(*)
                    FROM wholesale_box_items
                    WHERE packing_session_id=%s
                      AND IFNULL(is_deleted, 0)=0
                )
                WHERE id=%s
                """,
                (session_id, session_id),
            )
            return {
                "id": row["id"],
                "session_id": session_id,
                "item_code": row["child_order_code"],
                "scan_index": row["scan_index"],
                "deleted_time": now_str(),
            }
