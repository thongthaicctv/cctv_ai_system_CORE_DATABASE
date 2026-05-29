import os

from services.mysql_client import MySQLClient


def _scanner_id_for_camera(camera_id):
    camera_id = str(camera_id or "").strip()
    try:
        return f"s{int(camera_id):02d}"
    except ValueError:
        return f"s{camera_id}" if camera_id else ""


def _classify_order(order_code):
    order_code = str(order_code or "").strip()
    upper_order = order_code.upper()
    if upper_order.startswith("DONG_"):
        return order_code[5:], "packing", "WHOLESALE", 1
    if upper_order.startswith("GIAO_"):
        return order_code[5:], "handover", "WHOLESALE", 0
    return order_code, "ecom_packing", "ECOM", 0


def upsert_closed_record_video(
    order_code,
    file_path,
    camera_id="",
    camera_name="",
    employee_code="",
    employee_name="",
    start_time=None,
    end_time=None,
    duration_seconds=0,
    result="done",
):
    order_code, session_type, video_type, item_report_enabled = _classify_order(order_code)
    file_path = os.path.abspath(str(file_path or ""))
    if not order_code or not file_path:
        return None

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    scanner_id = _scanner_id_for_camera(camera_id)

    db = MySQLClient()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM orders WHERE order_code=%s LIMIT 1", (order_code,))
        row = cur.fetchone()
        if row:
            order_id = int(row["id"])
        else:
            order_type = "WHOLESALE" if video_type == "WHOLESALE" else "ECOM"
            cur.execute(
                """
                INSERT INTO orders (
                    order_code, order_type, order_status, packing_status,
                    conveyor_status, shipping_status
                ) VALUES (%s, %s, 'NEW', 'WAITING', 'WAITING', 'WAITING')
                """,
                (order_code, order_type),
            )
            order_id = int(cur.lastrowid)

        cur.execute("SELECT id FROM packing_videos WHERE file_path=%s LIMIT 1", (file_path,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE packing_videos
                SET file_size=%s,
                    duration_seconds=%s,
                    end_time=COALESCE(%s, end_time),
                    result=COALESCE(%s, result)
                WHERE id=%s
                """,
                (
                    int(file_size or 0),
                    float(duration_seconds or 0),
                    end_time,
                    result,
                    int(existing["id"]),
                ),
            )
            return int(existing["id"])

        cur.execute(
            """
            INSERT INTO packing_videos (
                order_id, order_code, session_type, video_type,
                item_report_enabled, item_count,
                scanner_id, camera_id, camera_name,
                file_path, file_name, file_size, duration_seconds,
                start_time, end_time, employee_code, employee_name, result
            ) VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                order_id,
                order_code,
                session_type,
                video_type,
                item_report_enabled,
                scanner_id,
                str(camera_id or ""),
                str(camera_name or camera_id or ""),
                file_path,
                file_name,
                int(file_size or 0),
                float(duration_seconds or 0),
                start_time,
                end_time,
                str(employee_code or ""),
                str(employee_name or ""),
                result,
            ),
        )
        return int(cur.lastrowid)
