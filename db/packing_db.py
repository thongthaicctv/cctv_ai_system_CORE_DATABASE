# db/packing_db.py
# -*- coding: utf-8 -*-

import os
import sqlite3
from datetime import datetime

from core.resource_paths import ensure_app_file


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class PackingDB:
    """
    Database lưu nghiệp vụ:
    - Đóng hàng sỉ / đại lý
    - Mã đơn nhỏ trong đơn lớn
    - Giao hàng / đối chiếu thùng
    - Video record đóng/giao
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or ensure_app_file("db", "packing.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.connect() as conn:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS packing_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    master_order_code TEXT NOT NULL,
                    packing_scanner_id TEXT NOT NULL,
                    employee_code TEXT,
                    employee_name TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_items INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'packing',
                    note TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS packing_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    master_order_code TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    scan_time TEXT NOT NULL,
                    scan_index INTEGER,
                    FOREIGN KEY(session_id) REFERENCES packing_sessions(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS handover_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_order_code TEXT,
                    packing_order_code TEXT,
                    packing_session_id INTEGER,
                    packing_scanner_id TEXT,
                    delivery_scanner_id TEXT,
                    result TEXT,
                    error_message TEXT,
                    first_scan_time TEXT,
                    second_scan_time TEXT,
                    created_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS record_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,
                    session_id INTEGER,
                    order_code TEXT NOT NULL,
                    scanner_id TEXT,
                    camera_id TEXT,
                    file_path TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_sec INTEGER,
                    file_size_mb REAL,
                    result TEXT,
                    created_at TEXT
                )
            """)


            self.ensure_column("handover_sessions", "delivery_employee_code", "TEXT")
            self.ensure_column("handover_sessions", "delivery_employee_name", "TEXT")

            self.ensure_column("packing_items", "is_deleted", "INTEGER DEFAULT 0")
            self.ensure_column("packing_items", "deleted_time", "TEXT")
            self.ensure_column("packing_items", "deleted_reason", "TEXT")

            conn.commit()



    # =========================================================
    # PACKING - ĐÓNG HÀNG
    # =========================================================

    def get_active_packing_session(self, scanner_id):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM packing_sessions
                WHERE packing_scanner_id = ?
                  AND status = 'packing'
                ORDER BY id DESC
                LIMIT 1
            """, (scanner_id,))
            return cur.fetchone()

    def create_packing_session(
        self,
        master_order_code,
        scanner_id,
        employee_code=None,
        employee_name=None,
        note=None
    ):
        start_time = now_str()

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO packing_sessions (
                    master_order_code,
                    packing_scanner_id,
                    employee_code,
                    employee_name,
                    start_time,
                    status,
                    note
                )
                VALUES (?, ?, ?, ?, ?, 'packing', ?)
            """, (
                master_order_code,
                scanner_id,
                employee_code,
                employee_name,
                start_time,
                note
            ))

            session_id = cur.lastrowid
            conn.commit()
            return session_id

    def add_packing_item(self, session_id, master_order_code, item_code):
        scan_time = now_str()

        with self.connect() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM packing_items
                WHERE session_id = ?
                AND IFNULL(is_deleted, 0) = 0
            """, (session_id,))
            row = cur.fetchone()
            scan_index = int(row["cnt"]) + 1

            cur.execute("""
                INSERT INTO packing_items (
                    session_id,
                    master_order_code,
                    item_code,
                    scan_time,
                    scan_index
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                master_order_code,
                item_code,
                scan_time,
                scan_index
            ))

            cur.execute("""
                UPDATE packing_sessions
                SET total_items = total_items + 1
                WHERE id = ?
            """, (session_id,))

            conn.commit()
            return scan_index

    def finish_packing_session(self, session_id):
        end_time = now_str()

        with self.connect() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM packing_items
                WHERE session_id = ?
                AND IFNULL(is_deleted, 0) = 0
            """, (session_id,))
            total_items = int(cur.fetchone()["cnt"])

            cur.execute("""
                UPDATE packing_sessions
                SET end_time = ?,
                    total_items = ?,
                    status = 'done'
                WHERE id = ?
            """, (
                end_time,
                total_items,
                session_id
            ))

            conn.commit()
            return total_items

    def find_done_packing_order(self, master_order_code):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM packing_sessions
                WHERE master_order_code = ?
                  AND status = 'done'
                ORDER BY end_time DESC
                LIMIT 1
            """, (master_order_code,))
            return cur.fetchone()


    def find_success_handover(self, order_code):
        """
        Kiểm tra đơn hàng đã từng giao thành công chưa.
        Dùng để chặn giao trùng / giao nhầm đơn đã giao.
        """
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM handover_sessions
                WHERE delivery_order_code = ?
                AND result = 'success'
                ORDER BY created_at DESC
                LIMIT 1
            """, (order_code,))
            return cur.fetchone()
        
    
    def create_handover_failed_already_delivered(self, delivery_order_code, scanner_id):
        created_at = now_str()

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO handover_sessions (
                    delivery_order_code,
                    packing_order_code,
                    packing_session_id,
                    packing_scanner_id,
                    delivery_scanner_id,
                    result,
                    error_message,
                    first_scan_time,
                    created_at
                )
                VALUES (?, NULL, NULL, NULL, ?, 'failed_already_delivered', ?, ?, ?)
            """, (
                delivery_order_code,
                scanner_id,
                "Đơn hàng đã được giao thành công trước đó",
                created_at,
                created_at
            ))

            conn.commit()
            return cur.lastrowid
        
        
    # =========================================================
    # HANDOVER - GIAO HÀNG
    # =========================================================

    def create_handover_failed_not_packed(self, delivery_order_code, scanner_id):
        created_at = now_str()

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO handover_sessions (
                    delivery_order_code,
                    packing_order_code,
                    packing_session_id,
                    packing_scanner_id,
                    delivery_scanner_id,
                    result,
                    error_message,
                    first_scan_time,
                    created_at
                )
                VALUES (?, NULL, NULL, NULL, ?, 'failed_not_packed', ?, ?, ?)
            """, (
                delivery_order_code,
                scanner_id,
                "Đơn hàng chưa được đóng",
                created_at,
                created_at
            ))

            conn.commit()
            return cur.lastrowid

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
        created_at = now_str()

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO handover_sessions (
                    delivery_order_code,
                    packing_order_code,
                    packing_session_id,
                    packing_scanner_id,
                    delivery_scanner_id,
                    result,
                    error_message,
                    first_scan_time,
                    second_scan_time,
                    delivery_employee_code,
                    delivery_employee_name,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                delivery_order_code,
                packing_order_code,
                packing_session_id,
                packing_scanner_id,
                delivery_scanner_id,
                result,
                error_message,
                first_scan_time,
                second_scan_time,
                delivery_employee_code,
                delivery_employee_name,     
                created_at
            ))

            conn.commit()
            return cur.lastrowid

    # =========================================================
    # RECORD FILES
    # =========================================================

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
        result=None
    ):
        created_at = now_str()

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO record_files (
                    session_type,
                    session_id,
                    order_code,
                    scanner_id,
                    camera_id,
                    file_path,
                    start_time,
                    end_time,
                    duration_sec,
                    file_size_mb,
                    result,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_type,
                session_id,
                order_code,
                scanner_id,
                camera_id,
                file_path,
                start_time,
                end_time,
                duration_sec,
                file_size_mb,
                result,
                created_at
            ))

            conn.commit()
            return cur.lastrowid
        
    def ensure_column(self, table_name, column_name, column_def):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = [row["name"] for row in cur.fetchall()]

            if column_name not in cols:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
                conn.commit()
    
    def update_packing_employee(self, session_id, employee_code=None, employee_name=None):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE packing_sessions
                SET employee_code = ?,
                    employee_name = ?
                WHERE id = ?
            """, (
                employee_code or "",
                employee_name or "",
                session_id
            ))
            conn.commit()
    
    def delete_last_packing_item(self, session_id, item_code=None, reason="Xóa thao tác quét nhầm"):
        """
        Xóa mềm mã kiện nhỏ vừa quét nhầm.
        Nếu item_code có giá trị: xóa lần quét gần nhất của mã đó.
        Nếu item_code rỗng: xóa lần quét gần nhất bất kỳ.
        """
        deleted_time = now_str()

        with self.connect() as conn:
            cur = conn.cursor()

            params = [session_id]
            where_item = ""

            if item_code:
                where_item = "AND item_code = ?"
                params.append(item_code)

            cur.execute(f"""
                SELECT *
                FROM packing_items
                WHERE session_id = ?
                AND IFNULL(is_deleted, 0) = 0
                {where_item}
                ORDER BY scan_index DESC, id DESC
                LIMIT 1
            """, params)

            row = cur.fetchone()

            if not row:
                return None

            item_id = row["id"]

            cur.execute("""
                UPDATE packing_items
                SET is_deleted = 1,
                    deleted_time = ?,
                    deleted_reason = ?
                WHERE id = ?
            """, (
                deleted_time,
                reason,
                item_id
            ))

            cur.execute("""
                UPDATE packing_sessions
                SET total_items = (
                    SELECT COUNT(*)
                    FROM packing_items
                    WHERE session_id = ?
                    AND IFNULL(is_deleted, 0) = 0
                )
                WHERE id = ?
            """, (
                session_id,
                session_id
            ))

            conn.commit()

            return {
                "id": item_id,
                "session_id": session_id,
                "item_code": row["item_code"],
                "scan_index": row["scan_index"],
                "deleted_time": deleted_time,
            }
