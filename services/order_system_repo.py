# services/order_system_repo.py
# -*- coding: utf-8 -*-
"""
Repository MySQL dùng song song với PackingDB SQLite cũ.
Mục tiêu: app hiện tại vẫn chạy, nhưng ghi thêm dữ liệu chuẩn vào MySQL LAN.
"""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from services.mysql_client import MySQLClient, get_machine_name


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class OrderSystemRepo:
    def __init__(self, db: Optional[MySQLClient] = None, app_name: str = "ATG_PACKING_RECORDER"):
        self.db = db or MySQLClient()
        self.app_name = app_name
        self.instance_id = f"{app_name}-{get_machine_name()}-{uuid.uuid4().hex[:8]}"

    # -----------------------------------------------------
    # WEB INDEX
    # -----------------------------------------------------
    def _queue_web_index_update_cur(self, cur, order_code: str, action_type: str = "REFRESH_ORDER", payload: Optional[Dict[str, Any]] = None) -> None:
        cur.execute(
            """
            INSERT INTO web_index_queue (order_code, action_type, payload)
            VALUES (%s, %s, %s)
            """,
            (order_code, action_type, json.dumps(payload or {}, ensure_ascii=False)),
        )

    def _packing_video_columns_cur(self, cur) -> set[str]:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'packing_videos'
            """
        )
        return {row["COLUMN_NAME"] for row in cur.fetchall()}

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

    def _has_packing_small_packages_cur(self, cur) -> bool:
        return self._table_exists_cur(cur, "packing_small_packages")

    def _refresh_web_index_order_cur(self, cur, order_code: str) -> None:
        cur.execute(
            """
            INSERT INTO web_index_orders (
                order_code, order_id, order_type, platform, shop_name,
                customer_name, customer_phone, total_boxes, total_items,
                packed_boxes, packed_children, video_count, last_video_path,
                order_status, packing_status, conveyor_status, shipping_status,
                carrier_code, carrier_name, tracking_code, raw_last_status,
                last_packed_at, last_conveyor_check_at, last_shipping_event_at,
                last_handover_at, last_sync_at
            )
            SELECT
                o.order_code,
                o.id,
                o.order_type,
                o.platform,
                o.shop_name,
                o.customer_name,
                o.customer_phone,
                o.total_boxes,
                COALESCE((
                    SELECT SUM(ps.total_items)
                    FROM packing_sessions ps
                    WHERE ps.order_id = o.id
                ), 0),
                COALESCE((
                    SELECT COUNT(*)
                    FROM packing_boxes pb
                    WHERE pb.order_id = o.id
                      AND pb.status <> 'DELETED'
                ), 0),
                COALESCE((
                    SELECT COUNT(*)
                    FROM wholesale_box_items wi
                    WHERE wi.master_order_code = o.order_code
                      AND wi.is_deleted = 0
                ), 0),
                COALESCE((
                    SELECT COUNT(*)
                    FROM packing_videos pv
                    WHERE pv.order_id = o.id
                ), 0),
                (
                    SELECT pv.file_path
                    FROM packing_videos pv
                    WHERE pv.order_id = o.id
                    ORDER BY pv.created_at DESC, pv.id DESC
                    LIMIT 1
                ),
                o.order_status,
                o.packing_status,
                o.conveyor_status,
                o.shipping_status,
                s.carrier_code,
                s.carrier_name,
                s.tracking_code,
                s.raw_last_status,
                (
                    SELECT MAX(ps.end_time)
                    FROM packing_sessions ps
                    WHERE ps.order_id = o.id
                ),
                (
                    SELECT MAX(cc.checked_at)
                    FROM conveyor_checks cc
                    WHERE cc.order_id = o.id
                ),
                (
                    SELECT MAX(se.event_time)
                    FROM shipment_events se
                    WHERE se.order_code = o.order_code
                ),
                (
                    SELECT MAX(dc.confirmed_at)
                    FROM delivery_confirmations dc
                    WHERE dc.order_id = o.id
                ),
                NOW()
            FROM orders o
            LEFT JOIN shipments s ON s.id = (
                SELECT s2.id
                FROM shipments s2
                WHERE s2.order_id = o.id
                ORDER BY s2.updated_at DESC, s2.id DESC
                LIMIT 1
            )
            WHERE o.order_code = %s
            ON DUPLICATE KEY UPDATE
                order_id=VALUES(order_id),
                order_type=VALUES(order_type),
                platform=VALUES(platform),
                shop_name=VALUES(shop_name),
                customer_name=VALUES(customer_name),
                customer_phone=VALUES(customer_phone),
                total_boxes=VALUES(total_boxes),
                total_items=VALUES(total_items),
                packed_boxes=VALUES(packed_boxes),
                packed_children=VALUES(packed_children),
                video_count=VALUES(video_count),
                last_video_path=VALUES(last_video_path),
                order_status=VALUES(order_status),
                packing_status=VALUES(packing_status),
                conveyor_status=VALUES(conveyor_status),
                shipping_status=VALUES(shipping_status),
                carrier_code=VALUES(carrier_code),
                carrier_name=VALUES(carrier_name),
                tracking_code=VALUES(tracking_code),
                raw_last_status=VALUES(raw_last_status),
                last_packed_at=VALUES(last_packed_at),
                last_conveyor_check_at=VALUES(last_conveyor_check_at),
                last_shipping_event_at=VALUES(last_shipping_event_at),
                last_handover_at=VALUES(last_handover_at),
                last_sync_at=VALUES(last_sync_at)
            """,
            (order_code,),
        )
        self._queue_web_index_update_cur(cur, order_code)

    def refresh_web_index_order(self, order_code: str) -> None:
        with self.db.cursor() as cur:
            self._refresh_web_index_order_cur(cur, order_code)

    # -----------------------------------------------------
    # ORDER
    # -----------------------------------------------------
    def ensure_order(
        self,
        order_code: str,
        order_type: str = "ECOM",
        total_boxes: int = 1,
        note: str = "",
    ) -> int:
        order_code = (order_code or "").strip()
        if not order_code:
            raise ValueError("order_code rỗng")

        with self.db.cursor() as cur:
            cur.execute("SELECT id FROM orders WHERE order_code=%s LIMIT 1", (order_code,))
            row = cur.fetchone()
            if row:
                return int(row["id"])

            cur.execute(
                """
                INSERT INTO orders (
                    order_code, order_type, total_boxes,
                    order_status, packing_status, conveyor_status, shipping_status, note
                ) VALUES (%s, %s, %s, 'NEW', 'WAITING', 'WAITING', 'WAITING', %s)
                """,
                (order_code, order_type, int(total_boxes or 1), note),
            )
            order_id = int(cur.lastrowid)
            self._refresh_web_index_order_cur(cur, order_code)
            return order_id

    def update_order_status(
        self,
        order_code: str,
        order_status: Optional[str] = None,
        packing_status: Optional[str] = None,
        conveyor_status: Optional[str] = None,
        shipping_status: Optional[str] = None,
    ) -> None:
        fields = []
        params = []
        if order_status:
            fields.append("order_status=%s")
            params.append(order_status)
        if packing_status:
            fields.append("packing_status=%s")
            params.append(packing_status)
        if conveyor_status:
            fields.append("conveyor_status=%s")
            params.append(conveyor_status)
        if shipping_status:
            fields.append("shipping_status=%s")
            params.append(shipping_status)
        if not fields:
            return
        params.append(order_code)
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE orders SET {', '.join(fields)} WHERE order_code=%s", params)
            self._refresh_web_index_order_cur(cur, order_code)

    def upsert_order_from_external_api(
        self,
        order_code: str,
        tracking_code: str = "",
        carrier_code: str = "",
        carrier_name: str = "",
        shipping_status: str = "",
        raw_last_status: str = "",
        platform: str = "",
        shop_name: str = "",
        customer_name: str = "",
        customer_phone: str = "",
        customer_address: str = "",
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        order_id = self.ensure_order(order_code, order_type="ECOM")
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE orders
                SET platform=COALESCE(NULLIF(%s,''), platform),
                    shop_name=COALESCE(NULLIF(%s,''), shop_name),
                    customer_name=COALESCE(NULLIF(%s,''), customer_name),
                    customer_phone=COALESCE(NULLIF(%s,''), customer_phone),
                    customer_address=COALESCE(NULLIF(%s,''), customer_address),
                    shipping_status=COALESCE(NULLIF(%s,''), shipping_status),
                    order_status=IF(NULLIF(%s,'') IS NULL, order_status, %s)
                WHERE id=%s
                """,
                (
                    platform,
                    shop_name,
                    customer_name,
                    customer_phone,
                    customer_address,
                    shipping_status,
                    shipping_status,
                    shipping_status,
                    order_id,
                ),
            )
            if tracking_code:
                cur.execute(
                    """
                    INSERT INTO shipments (
                        order_id, order_code, carrier_code, carrier_name,
                        tracking_code, shipping_status, raw_last_status, last_api_sync
                    ) VALUES (%s, %s, %s, %s, %s, COALESCE(NULLIF(%s,''), 'CREATED'), %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        carrier_code=VALUES(carrier_code),
                        carrier_name=VALUES(carrier_name),
                        shipping_status=VALUES(shipping_status),
                        raw_last_status=VALUES(raw_last_status),
                        last_api_sync=NOW()
                    """,
                    (
                        order_id,
                        order_code,
                        carrier_code or None,
                        carrier_name or None,
                        tracking_code,
                        shipping_status,
                        raw_last_status or None,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO api_sync_logs (
                        provider, api_name, order_code, tracking_code,
                        response_body, is_success
                    ) VALUES (%s, 'SHIPMENT_UPSERT', %s, %s, %s, 1)
                    """,
                    (
                        carrier_code or carrier_name or "EXTERNAL",
                        order_code,
                        tracking_code,
                        json.dumps(raw_data or {}, ensure_ascii=False),
                    ),
                )
            self._refresh_web_index_order_cur(cur, order_code)
        return order_id

    # -----------------------------------------------------
    # PACKING
    # -----------------------------------------------------
    def create_packing_session(
        self,
        order_code: str,
        scanner_id: str,
        employee_code: str = "",
        employee_name: str = "",
        legacy_session_id: Optional[int] = None,
        order_type: str = "WHOLESALE",
    ) -> int:
        order_id = self.ensure_order(order_code, order_type=order_type)
        with self.db.cursor() as cur:
            if legacy_session_id:
                cur.execute(
                    "SELECT id FROM packing_sessions WHERE legacy_session_id=%s LIMIT 1",
                    (legacy_session_id,),
                )
                row = cur.fetchone()
                if row:
                    return int(row["id"])

            cur.execute(
                """
                INSERT INTO packing_sessions (
                    order_id, order_code, legacy_session_id, packing_type,
                    employee_code, employee_name, scanner_id, start_time, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'PACKING')
                """,
                (order_id, order_code, legacy_session_id, order_type, employee_code, employee_name, scanner_id),
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
            self._refresh_web_index_order_cur(cur, order_code)
            return session_id

    def record_ecom_packing(
        self,
        order_code: str,
        scanner_id: str,
        employee_code: str = "",
        employee_name: str = "",
        video_path: str = "",
        camera_id: str = "",
        camera_name: str = "",
        result: str = "done",
    ) -> int:
        session_id = self.create_packing_session(
            order_code=order_code,
            scanner_id=scanner_id,
            employee_code=employee_code,
            employee_name=employee_name,
            order_type="ECOM",
        )
        self.finish_packing_session(
            order_code=order_code,
            packing_session_id=session_id,
            total_items=0,
            employee_code=employee_code,
            employee_name=employee_name,
        )
        if video_path:
            self.add_packing_video(
                order_code=order_code,
                file_path=video_path,
                session_type="ecom_packing",
                packing_session_id=session_id,
                scanner_id=scanner_id,
                camera_id=camera_id,
                camera_name=camera_name,
                result=result,
                video_type="ECOM",
                item_report_enabled=False,
                item_count=0,
            )
        return session_id

    def add_packing_box(
        self,
        order_code: str,
        box_code: str,
        packing_session_id: Optional[int] = None,
        box_index: int = 1,
        total_boxes: int = 1,
    ) -> int:
        order_id = self.ensure_order(order_code, order_type="WHOLESALE", total_boxes=total_boxes)
        with self.db.cursor() as cur:
            cur.execute("SELECT id FROM packing_boxes WHERE box_code=%s LIMIT 1", (box_code,))
            row = cur.fetchone()
            if row:
                return int(row["id"])
            cur.execute(
                """
                INSERT INTO packing_boxes (
                    order_id, order_code, packing_session_id, box_code,
                    box_index, total_boxes, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'PACKED')
                """,
                (order_id, order_code, packing_session_id, box_code, box_index, total_boxes),
            )
            box_id = int(cur.lastrowid)
            self._refresh_web_index_order_cur(cur, order_code)
            return box_id

    def finish_packing_session(
        self,
        order_code: str,
        packing_session_id: Optional[int] = None,
        total_items: int = 0,
        employee_code: str = "",
        employee_name: str = "",
    ) -> None:
        with self.db.cursor() as cur:
            if packing_session_id:
                cur.execute(
                    """
                    UPDATE packing_sessions
                    SET end_time=NOW(), status='COMPLETED', total_items=%s,
                        employee_code=COALESCE(NULLIF(%s,''), employee_code),
                        employee_name=COALESCE(NULLIF(%s,''), employee_name)
                    WHERE id=%s
                    """,
                    (int(total_items or 0), employee_code, employee_name, packing_session_id),
                )
            cur.execute(
                """
                UPDATE orders
                SET order_status='PACKED', packing_status='COMPLETED'
                WHERE order_code=%s
                """,
                (order_code,),
            )
            self._refresh_web_index_order_cur(cur, order_code)

    def add_packing_video(
        self,
        order_code: str,
        file_path: str,
        session_type: str = "packing",
        packing_session_id: Optional[int] = None,
        box_code: str = "",
        scanner_id: str = "",
        camera_id: str = "",
        camera_name: str = "",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        duration_seconds: float = 0,
        file_size: int = 0,
        result: str = "done",
        video_type: str = "ECOM",
        item_report_enabled: bool = False,
        item_count: int = 0,
    ) -> int:
        order_id = self.ensure_order(order_code)
        video_type = (video_type or "ECOM").upper()
        file_name = os.path.basename(file_path or "")
        with self.db.cursor() as cur:
            columns = self._packing_video_columns_cur(cur)
            has_video_type_columns = {
                "video_type",
                "item_report_enabled",
                "item_count",
            }.issubset(columns)

            if has_video_type_columns:
                cur.execute(
                    """
                    INSERT INTO packing_videos (
                        order_id, order_code, packing_session_id, box_code,
                        session_type, video_type, item_report_enabled, item_count,
                        scanner_id, camera_id, camera_name,
                        file_path, file_name, file_size, duration_seconds,
                        start_time, end_time, result
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id, order_code, packing_session_id, box_code or None,
                        session_type, video_type, 1 if item_report_enabled else 0, int(item_count or 0),
                        scanner_id, camera_id, camera_name,
                        file_path, file_name, int(file_size or 0), float(duration_seconds or 0),
                        start_time, end_time, result,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO packing_videos (
                        order_id, order_code, packing_session_id, box_code,
                        session_type, scanner_id, camera_id, camera_name,
                        file_path, file_name, file_size, duration_seconds,
                        start_time, end_time, result
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id, order_code, packing_session_id, box_code or None,
                        session_type, scanner_id, camera_id, camera_name,
                        file_path, file_name, int(file_size or 0), float(duration_seconds or 0),
                        start_time, end_time, result,
                    ),
                )
            video_id = int(cur.lastrowid)
            self._refresh_web_index_order_cur(cur, order_code)
            return video_id

    # -----------------------------------------------------
    # CONVEYOR / WHOLESALE CHECKS
    # -----------------------------------------------------
    def check_conveyor_order(
        self,
        scan_code: str,
        conveyor_id: str = "",
        station_id: str = "",
        scanner_id: str = "",
        employee_code: str = "",
        employee_name: str = "",
        video_path: str = "",
        image_path: str = "",
    ) -> Dict[str, Any]:
        scan_code = (scan_code or "").strip()
        if not scan_code:
            raise ValueError("scan_code rong")

        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, order_code, packing_status, conveyor_status, shipping_status
                FROM orders
                WHERE order_code=%s
                LIMIT 1
                """,
                (scan_code,),
            )
            order = cur.fetchone()
            if not order:
                result = "NOT_FOUND"
                message = "Don hang khong co trong database"
                order_id = None
                order_code = scan_code
            elif order["shipping_status"] == "DELIVERED":
                result = "ALREADY_DELIVERED"
                message = "Don hang da giao truoc do"
                order_id = order["id"]
                order_code = order["order_code"]
            elif order["packing_status"] not in ("COMPLETED", "PACKED"):
                result = "NOT_PACKED"
                message = "Don hang chua dong xong"
                order_id = order["id"]
                order_code = order["order_code"]
            else:
                result = "OK"
                message = "Don hang hop le"
                order_id = order["id"]
                order_code = order["order_code"]

            cur.execute(
                """
                INSERT INTO conveyor_checks (
                    order_id, order_code, conveyor_id, station_id, scan_code,
                    scan_type, result, message, employee_code, employee_name,
                    image_path, video_path
                ) VALUES (%s, %s, %s, %s, %s, 'ORDER_CODE', %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    order_code,
                    conveyor_id or scanner_id,
                    station_id,
                    scan_code,
                    result,
                    message,
                    employee_code,
                    employee_name,
                    image_path,
                    video_path,
                ),
            )
            if order_id:
                cur.execute(
                    "UPDATE orders SET conveyor_status=%s WHERE id=%s",
                    ("CHECKED_OK" if result == "OK" else result, order_id),
                )
                self._refresh_web_index_order_cur(cur, order_code)
            return {"ok": result == "OK", "result": result, "message": message, "order_code": order_code}

    def add_wholesale_child_item(
        self,
        master_order_code: str,
        child_order_code: str,
        packing_session_id: Optional[int] = None,
        box_code: str = "",
        scanner_id: str = "",
        employee_code: str = "",
        employee_name: str = "",
        legacy_item_id: Optional[int] = None,
        scanned_at: Optional[str] = None,
    ) -> int:
        master_order_id = self.ensure_order(master_order_code, order_type="WHOLESALE")
        child_order_id = self.ensure_order(child_order_code, order_type="WHOLESALE_CHILD")
        with self.db.cursor() as cur:
            has_small_packages = self._has_packing_small_packages_cur(cur)
            if has_small_packages and legacy_item_id:
                cur.execute(
                    """
                    SELECT id
                    FROM packing_small_packages
                    WHERE order_code=%s
                      AND packing_session_id <=> %s
                      AND legacy_item_id=%s
                    LIMIT 1
                    """,
                    (master_order_code, packing_session_id, legacy_item_id),
                )
                existing_sync = cur.fetchone()
                if existing_sync:
                    return int(existing_sync["id"])

            index_table = "packing_small_packages" if has_small_packages else "wholesale_box_items"
            order_column = "order_code" if has_small_packages else "master_order_code"
            cur.execute(
                f"""
                SELECT COALESCE(MAX(scan_index), 0) + 1 AS next_index
                FROM {index_table}
                WHERE {order_column}=%s
                  AND is_deleted=0
                """,
                (master_order_code,),
            )
            scan_index = int(cur.fetchone()["next_index"])

            item_id = 0
            if has_small_packages:
                cur.execute(
                    """
                    INSERT INTO packing_small_packages (
                        order_id, order_code, packing_session_id, legacy_item_id,
                        small_package_code, scan_index, scanner_id,
                        employee_code, employee_name, scanned_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                    """,
                    (
                        master_order_id,
                        master_order_code,
                        packing_session_id,
                        legacy_item_id,
                        child_order_code,
                        scan_index,
                        scanner_id,
                        employee_code,
                        employee_name,
                        scanned_at,
                    ),
                )
                item_id = int(cur.lastrowid)

            cur.execute(
                """
                INSERT INTO wholesale_box_items (
                    master_order_id, master_order_code, child_order_id, child_order_code,
                    packing_session_id, box_code, scan_index, scanner_id,
                    employee_code, employee_name, scanned_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                """,
                (
                    master_order_id,
                    master_order_code,
                    child_order_id,
                    child_order_code,
                    packing_session_id,
                    box_code or child_order_code,
                    scan_index,
                    scanner_id,
                    employee_code,
                    employee_name,
                    scanned_at,
                ),
            )
            if not item_id:
                item_id = int(cur.lastrowid)
            cur.execute(
                """
                UPDATE orders
                SET order_status='PACKED', packing_status='COMPLETED'
                WHERE id IN (%s, %s)
                """,
                (master_order_id, child_order_id),
            )
            self._refresh_web_index_order_cur(cur, master_order_code)
            self._refresh_web_index_order_cur(cur, child_order_code)
            return item_id

    def soft_delete_wholesale_child_item(
        self,
        master_order_code: str,
        child_order_code: str = "",
        packing_session_id: Optional[int] = None,
        reason: str = "Xoa ma kien nho quet nham",
    ) -> Optional[int]:
        with self.db.cursor() as cur:
            has_small_packages = self._has_packing_small_packages_cur(cur)
            if has_small_packages:
                filters = [
                    "order_code=%s",
                    "IFNULL(is_deleted, 0)=0",
                ]
                params: list[Any] = [master_order_code]
                if child_order_code:
                    filters.append("small_package_code=%s")
                    params.append(child_order_code)
                if packing_session_id:
                    filters.append("packing_session_id=%s")
                    params.append(packing_session_id)

                cur.execute(
                    f"""
                    SELECT id, small_package_code
                    FROM packing_small_packages
                    WHERE {" AND ".join(filters)}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    params,
                )
                row = cur.fetchone()
                if not row:
                    return None

                cur.execute(
                    """
                    UPDATE packing_small_packages
                    SET is_deleted=1,
                        deleted_at=NOW(),
                        deleted_reason=%s
                    WHERE id=%s
                    """,
                    (reason, row["id"]),
                )
                deleted_code = row["small_package_code"]
                deleted_id = int(row["id"])
            else:
                filters = [
                    "master_order_code=%s",
                    "IFNULL(is_deleted, 0)=0",
                ]
                params = [master_order_code]
                if child_order_code:
                    filters.append("child_order_code=%s")
                    params.append(child_order_code)
                if packing_session_id:
                    filters.append("packing_session_id=%s")
                    params.append(packing_session_id)

                cur.execute(
                    f"""
                    SELECT id, child_order_code AS small_package_code
                    FROM wholesale_box_items
                    WHERE {" AND ".join(filters)}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    params,
                )
                row = cur.fetchone()
                if not row:
                    return None
                deleted_code = row["small_package_code"]
                deleted_id = int(row["id"])

            cur.execute(
                """
                UPDATE wholesale_box_items
                SET is_deleted=1,
                    deleted_at=NOW(),
                    deleted_reason=%s
                WHERE master_order_code=%s
                  AND child_order_code=%s
                  AND IFNULL(is_deleted, 0)=0
                ORDER BY id DESC
                LIMIT 1
                """,
                (reason, master_order_code, deleted_code),
            )
            self._refresh_web_index_order_cur(cur, master_order_code)
            return deleted_id

    def check_wholesale_handover(
        self,
        master_order_code: str,
        scanned_code: str,
        delivery_scanner_id: str = "",
        employee_code: str = "",
        employee_name: str = "",
        video_path: str = "",
        image_path: str = "",
    ) -> Dict[str, Any]:
        master_order_id = self.ensure_order(master_order_code, order_type="WHOLESALE")
        with self.db.cursor() as cur:
            if self._has_packing_small_packages_cur(cur):
                cur.execute(
                    """
                    SELECT
                        small_package_code AS child_order_code,
                        packing_session_id
                    FROM packing_small_packages
                    WHERE order_code=%s
                      AND IFNULL(is_deleted, 0)=0
                      AND small_package_code=%s
                    LIMIT 1
                    """,
                    (master_order_code, scanned_code),
                )
            else:
                cur.execute(
                    """
                    SELECT child_order_code, packing_session_id
                    FROM wholesale_box_items
                    WHERE master_order_code=%s
                      AND is_deleted=0
                      AND (child_order_code=%s OR box_code=%s)
                    LIMIT 1
                    """,
                    (master_order_code, scanned_code, scanned_code),
                )
            row = cur.fetchone()
            result = "OK" if row else "WRONG_BOX"
            message = "Kien dung trong don si" if row else "Kien khong thuoc don si"
            cur.execute(
                """
                INSERT INTO wholesale_handover_checks (
                    master_order_id, master_order_code, scanned_code,
                    matched_child_order_code, packing_session_id, delivery_scanner_id,
                    employee_code, employee_name, result, message, video_path, image_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    master_order_id,
                    master_order_code,
                    scanned_code,
                    row["child_order_code"] if row else None,
                    row["packing_session_id"] if row else None,
                    delivery_scanner_id,
                    employee_code,
                    employee_name,
                    result,
                    message,
                    video_path,
                    image_path,
                ),
            )
            if result == "OK":
                cur.execute(
                    """
                    UPDATE orders
                    SET shipping_status='HANDOVER_CHECKED'
                    WHERE order_code IN (%s, %s)
                    """,
                    (master_order_code, row["child_order_code"]),
                )
                self._refresh_web_index_order_cur(cur, row["child_order_code"])
            self._refresh_web_index_order_cur(cur, master_order_code)
            return {
                "ok": result == "OK",
                "result": result,
                "message": message,
                "master_order_code": master_order_code,
                "matched_child_order_code": row["child_order_code"] if row else "",
            }

    # -----------------------------------------------------
    # HANDOVER / INTERNAL DELIVERY
    # -----------------------------------------------------
    def ensure_internal_shipment(self, order_code: str, tracking_code: Optional[str] = None) -> int:
        order_id = self.ensure_order(order_code, order_type="WHOLESALE")
        tracking_code = tracking_code or f"PG-{order_code}"
        with self.db.cursor() as cur:
            cur.execute("SELECT id FROM shipments WHERE tracking_code=%s LIMIT 1", (tracking_code,))
            row = cur.fetchone()
            if row:
                return int(row["id"])
            cur.execute(
                """
                INSERT INTO shipments (
                    order_id, order_code, carrier_code, carrier_name,
                    tracking_code, shipping_status
                ) VALUES (%s, %s, 'INTERNAL', 'Giao hàng nội bộ', %s, 'CREATED')
                """,
                (order_id, order_code, tracking_code),
            )
            shipment_id = int(cur.lastrowid)
            self._refresh_web_index_order_cur(cur, order_code)
            return shipment_id

    def save_handover_result(
        self,
        order_code: str,
        result: str,
        packing_order_code: str = "",
        scanner_id: str = "",
        employee_code: str = "",
        employee_name: str = "",
        error_message: str = "",
    ) -> None:
        shipment_id = self.ensure_internal_shipment(order_code)
        status = "DELIVERED" if result == "success" else "FAILED_DELIVERY"
        with self.db.cursor() as cur:
            cur.execute("SELECT tracking_code FROM shipments WHERE id=%s", (shipment_id,))
            tracking_code = cur.fetchone()["tracking_code"]

            cur.execute(
                """
                UPDATE shipments
                SET shipping_status=%s, delivered_time=IF(%s='DELIVERED', NOW(), delivered_time)
                WHERE id=%s
                """,
                (status, status, shipment_id),
            )
            cur.execute(
                """
                UPDATE orders
                SET order_status=%s, shipping_status=%s
                WHERE order_code=%s
                """,
                (status, status, order_code),
            )
            cur.execute(
                """
                INSERT INTO shipment_events (
                    shipment_id, order_code, tracking_code, carrier_code,
                    event_time, event_status, event_description, raw_data
                ) VALUES (%s, %s, %s, 'INTERNAL', NOW(), %s, %s, %s)
                """,
                (
                    shipment_id,
                    order_code,
                    tracking_code,
                    status,
                    error_message or result,
                    json.dumps(
                        {
                            "scanner_id": scanner_id,
                            "result": result,
                            "packing_order_code": packing_order_code,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            cur.execute(
                """
                INSERT INTO delivery_confirmations (
                    shipment_id, order_id, order_code, tracking_code,
                    delivered_by_code, delivered_by_name, delivery_result, note
                )
                SELECT %s, id, order_code, %s, %s, %s, %s, %s
                FROM orders WHERE order_code=%s
                """,
                (shipment_id, tracking_code, employee_code, employee_name, status, error_message, order_code),
            )
            self._refresh_web_index_order_cur(cur, order_code)

    # -----------------------------------------------------
    # APP LOG / HEARTBEAT
    # -----------------------------------------------------
    def log_event(self, event_type: str, message: str, level: str = "INFO", order_code: str = "", detail: str = "") -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_events (app_name, event_type, level, order_code, message, detail)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (self.app_name, event_type, level, order_code, message, detail),
            )

    def heartbeat(self, status: str = "ONLINE") -> None:
        machine = get_machine_name()
        ip = socket.gethostbyname(socket.gethostname())
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_instances (app_name, instance_id, machine_name, ip_address, status, last_heartbeat)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    status=VALUES(status),
                    machine_name=VALUES(machine_name),
                    ip_address=VALUES(ip_address),
                    last_heartbeat=NOW()
                """,
                (self.app_name, self.instance_id, machine, ip, status),
            )
