import re
import time

import cv2
from PySide6.QtWidgets import QApplication

from core.config_manager import load_config
from core.logger import write_license_log
from services.audio_service import employee_ok, order_ok, stop_ok, play_event_sound
from services.packing_service import PackingService
from system_logger import log as system_log

try:
    from services.order_system_repo import OrderSystemRepo
except Exception:
    OrderSystemRepo = None


from services.qr_decoder import decode_qr_texts, decode_qr_texts_fast, parse_qr_command
from utils.url_helper import camera_rtsp_url, open_rtsp_capture


DEFAULT_SCAN_INTERVAL = 0.01
DEFAULT_DUPLICATE_SECONDS = 5
RECONNECT_DELAY_SECONDS = 2
MAX_RECONNECT_DELAY_SECONDS = 30
RTSP_OPEN_TIMEOUT_MSEC = 5000
RTSP_READ_TIMEOUT_MSEC = 5000
FULL_SCAN_EVERY_FRAMES = 2
SLOW_SCAN_EVERY_FRAMES = 8
SCAN_MAX_WIDTH = 1280
DEFAULT_RECORD_SCANNER_ID = "s01"


class QRWorker:
    def __init__(self, cam, state):
        self.cam = cam
        self.state = state
        self.running = True

        self.last_seen = {}
        self.cap = None
        self.fail_count = 0
        self.frame_index = 0

        self.packing_service = PackingService(
            start_record_callback=self._packing_start_record,
            stop_record_callback=self._packing_stop_record,
            sound_callback=self._packing_sound,
            log_callback=self._packing_log,
        )

        # Lưu tạm các camera đã được bật record theo nghiệp vụ đóng/giao
        # key = f"{session_type}:{session_id}:{scanner_id}"
        self.packing_record_targets = {}
        # Lưu trạng thái thao tác dạng QR lệnh cố định:
        # s01DONG -> chờ quét thùng lớn
        # s08GIAO -> chờ quét mã đơn, sau đó chờ quét thùng giao
        self.packing_action_state = {}
        self.mysql_repo = None
        if OrderSystemRepo:
            try:
                self.mysql_repo = OrderSystemRepo(app_name="ATG_QR_WORKER")
                self.mysql_repo.heartbeat()
            except Exception as exc:
                self.mysql_repo = None
                self._packing_log(f"[MYSQL WARNING] Khong ket noi duoc database LAN: {exc}")


    def run(self):
        cam_id = self.cam["id"]
        rtsp = camera_rtsp_url(self.cam, prefer="sub")

        if not rtsp:
            self.state.set_error(cam_id, "Missing RTSP URL")
            return

        print(f"[{cam_id}] QR stream: {rtsp}")

        while self.running:
            if not self._ensure_capture(rtsp, cam_id):
                self._sleep_after_failure()
                continue

            try:
                ok, frame = self.cap.read()
            except Exception as exc:
                self.state.set_error(cam_id, f"Read RTSP failed: {exc}")
                self._release_capture()
                self._sleep_after_failure()
                continue

            if not ok or frame is None:
                self.state.set_error(cam_id, "Lost RTSP frame")
                self._release_capture()
                self._sleep_after_failure()
                continue

            self.fail_count = 0
            self.state.clear_error(cam_id)
            self.frame_index += 1

            if self.frame_index % 100 == 0:
                self._clean_seen_cache()

            self._scan_frame(cam_id, frame)
            time.sleep(float(self.cam.get("qr_scan_interval", DEFAULT_SCAN_INTERVAL)))

        self._release_capture()

    def _ensure_capture(self, rtsp, cam_id):
        if self.cap is not None and self.cap.isOpened():
            return True

        self._release_capture()
        self.cap = open_rtsp_capture(
            rtsp,
            open_timeout_msec=self.cam.get("rtsp_open_timeout_msec", RTSP_OPEN_TIMEOUT_MSEC),
            read_timeout_msec=self.cam.get("rtsp_read_timeout_msec", RTSP_READ_TIMEOUT_MSEC),
        )

        if self.cap.isOpened():
            return True

        self.state.set_error(cam_id, "Cannot open RTSP stream for QR")
        self._release_capture()
        return False

    def _sleep_after_failure(self):
        delay = min(
            MAX_RECONNECT_DELAY_SECONDS,
            RECONNECT_DELAY_SECONDS * (2 ** min(self.fail_count, 4)),
        )
        self.fail_count += 1
        time.sleep(delay)

    def _release_capture(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _scan_frame(self, cam_id, frame):
        frame = self._prepare_frame(frame)

        for region in self._fast_scan_regions(frame):
            if self._process_texts(cam_id, decode_qr_texts_fast(region)):
                return

        if self.frame_index % self._slow_scan_every_frames() != 0:
            return

        for region in self._slow_scan_regions(frame):
            if self._process_texts(cam_id, decode_qr_texts(region)):
                return

    def _process_texts(self, cam_id, texts):
        for text in texts:
            if not self._should_accept(text):
                return True

            print(f"[{cam_id}] SCAN: {text}")
            self.state.set_scan(cam_id, text)
            self._handle_command(cam_id, text)
            return True

        return False

    def _fast_scan_regions(self, frame):
        yield self._center_roi(frame)
        if self.frame_index % self._full_scan_every_frames() == 0:
            yield frame

    def _slow_scan_regions(self, frame):
        yield self._center_roi(frame)
        yield frame

    def _center_roi(self, frame):
        h, w = frame.shape[:2]
        x1 = int(w * 0.15)
        x2 = int(w * 0.85)
        y1 = int(h * 0.15)
        y2 = int(h * 0.85)
        return frame[y1:y2, x1:x2]

    def _prepare_frame(self, frame):
        max_width = int(self.cam.get("qr_max_width", SCAN_MAX_WIDTH))
        if frame is None or max_width <= 0:
            return frame

        h, w = frame.shape[:2]
        if w <= max_width:
            return frame

        scale = max_width / float(w)
        return cv2.resize(
            frame,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )

    def _full_scan_every_frames(self):
        return max(1, int(self.cam.get("qr_full_scan_every_frames", FULL_SCAN_EVERY_FRAMES)))

    def _slow_scan_every_frames(self):
        return max(1, int(self.cam.get("qr_slow_scan_every_frames", SLOW_SCAN_EVERY_FRAMES)))

    def _should_accept(self, text):
        now = time.time()
        duplicate_seconds = float(self.cam.get("qr_duplicate_seconds", DEFAULT_DUPLICATE_SECONDS))
        last_time = self.last_seen.get(text)
        if last_time and now - last_time < duplicate_seconds:
            return False

        self.last_seen[text] = now
        return True

    def _parse_manual_cmd(self, text):
        text = str(text or "").strip()
        if len(text) < 3:
            return None

        match = re.match(r"^([cCsS])(\d{1,2})(.*)$", text)
        if not match:
            return None

        prefix = f"{match.group(1).lower()}{match.group(2).zfill(2)}"
        body = match.group(3).strip()
        return prefix, body

    def _find_camera_by_sub(self, prefix):
        """
        c12 / s12 đều hiểu là ID camera thật = 12.
        Không dùng số thứ tự dòng trong bảng camera.
        """
        data = load_config()
        cameras = list(data.get("cameras", []))

        prefix = str(prefix or "").lower().strip()

        if not prefix:
            return None

        if prefix[0] not in ("c", "s"):
            return None

        raw_id = prefix[1:].strip()
        cam_id_from_cmd = raw_id.lstrip("0") or raw_id

        for cam in cameras:
            real_id = str(cam.get("id", "")).strip()
            real_id_normalized = real_id.lstrip("0") or real_id

            if real_id_normalized == cam_id_from_cmd:
                return real_id

        return None

    def _scanner_id_for_scan_camera(self, scan_cam_id):
        scan_cam_id = str(scan_cam_id or "").strip()
        if not scan_cam_id:
            return ""

        try:
            return f"s{int(scan_cam_id):02d}"
        except ValueError:
            return f"s{scan_cam_id}"

    def _default_record_scan_camera_id(self):
        return self._find_camera_by_sub(DEFAULT_RECORD_SCANNER_ID) or "1"

    def _default_record_targets(self):
        return self._target_camera_ids(self._default_record_scan_camera_id())

    def _safe_active_packing_session(self, scanner_id, context=""):
        try:
            return self.packing_service.db.get_active_packing_session(scanner_id)
        except Exception as exc:
            self._packing_log(
                f"[MYSQL WARNING] get_active_packing_session failed"
                f"{' in ' + context if context else ''}, continue record flow: {exc}"
            )
            return None

    def _wait_next_handover_order(self, scanner_id):
        self.packing_action_state[scanner_id] = {
            "mode": "handover_wait_delivery_order"
        }

    def _has_active_handover_flow(self, scanner_id):
        return (
            scanner_id in self.packing_service.pending_handover
            or scanner_id in self.packing_service.active_handover_record
        )

    def _handle_raw_business_scan(self, scan_cam_id, text):
        """
        Xử lý mã quét không có prefix sau các lệnh nghiệp vụ cố định.

        Ví dụ:
        - s01DONG, sau đó quét MADON thô => bắt đầu đóng và start record.
        - Đang đóng đơn sỉ, quét mã kiện nhỏ thô => chỉ lưu DB.
        - s08GIAO, sau đó quét MADON thô => bắt đầu giao nếu đơn đã đóng.
        """
        body = str(text or "").strip()
        if not body:
            return False

        scanner_id = self._scanner_id_for_scan_camera(scan_cam_id)
        if not scanner_id:
            return False

        body_lower = body.lower()
        state_action = self.packing_action_state.get(scanner_id)

        if body_lower.startswith("stop"):
            employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)
            active_packing = self._safe_active_packing_session(
                scanner_id,
                context="raw_stop",
            )
            if active_packing:
                self.packing_service.stop_packing(
                    scanner_id=scanner_id,
                    employee_code=employee_id,
                    employee_name=employee_name,
                )
                self.packing_action_state.pop(scanner_id, None)
                return True

            if self._has_active_handover_flow(scanner_id):
                self.packing_service.finish_handover(
                    scanner_id=scanner_id,
                    delivery_employee_code=employee_id,
                    delivery_employee_name=employee_name,
                )
                self.packing_action_state.pop(scanner_id, None)
                return True

            if state_action:
                self.packing_action_state.pop(scanner_id, None)
                stop_ok()
                return True

            return False

        if state_action and state_action.get("mode") == "packing_wait_master_order":
            employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

            self._packing_log(
                f"[ĐÓNG HÀNG XÁC NHẬN THÙNG LỚN] "
                f"scanner={scanner_id}, "
                f"mã_thùng_lớn={body}, "
                f"employee={employee_id or ''} {employee_name or ''}"
            )

            self.packing_service.start_packing(
                scanner_id=scanner_id,
                master_order_code=body,
                employee_code=employee_id,
                employee_name=employee_name,
            )

            self._packing_log(
                f"[ĐÓNG HÀNG - MỜI QUÉT KIỆN NHỎ] "
                f"scanner={scanner_id}, "
                f"mã_đơn={body}, "
                f"trạng_thái=đang_đóng_hàng"
            )

            self._packing_sound("prompt_scan_packing_items")
            self.packing_action_state.pop(scanner_id, None)
            return True

        if state_action and state_action.get("mode") == "handover_wait_delivery_order":
            employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

            result = self.packing_service.start_handover(
                scanner_id=scanner_id,
                delivery_order_code=body,
                delivery_employee_code=employee_id,
                delivery_employee_name=employee_name,
            )

            if result and result.get("ok"):
                self.packing_action_state[scanner_id] = {
                    "mode": "handover_wait_box_code",
                    "delivery_order_code": body,
                }
                self._packing_log(
                    f"[GIAO HÀNG - MỜI QUÉT KIỆN ĐỂ XÁC NHẬN] "
                    f"scanner_giao={scanner_id}, "
                    f"mã_giao={body}, "
                    f"trạng_thái=chờ_quét_mã_kiện"
                )
                self._packing_sound("prompt_scan_delivery_box")
            else:
                self._wait_next_handover_order(scanner_id)

            return True

        if state_action and state_action.get("mode") == "handover_wait_box_code":
            self.packing_service.confirm_handover_box(
                scanner_id=scanner_id,
                packing_order_code=body,
            )
            self._wait_next_handover_order(scanner_id)
            return True

        if scanner_id in self.packing_service.pending_handover:
            self.packing_service.confirm_handover_box(
                scanner_id=scanner_id,
                packing_order_code=body,
            )
            if scanner_id in self.packing_service.active_handover_record:
                self._wait_next_handover_order(scanner_id)
            return True

        active_packing = self._safe_active_packing_session(
            scanner_id,
            context="raw_scan",
        )
        if active_packing:
            self.packing_service.add_packing_item(
                scanner_id=scanner_id,
                item_code=body,
            )
            return True

        return False

    def _get_record_engine(self):
        app = QApplication.instance()
        if app is None:
            return None
        return getattr(app, "record_engine", None)

    def _record_worker_for_target(self, target_id):
        record_engine = self._get_record_engine()
        if not record_engine:
            print("LICENSE RECORD BLOCK: ENGINE NOT FOUND")
            return None

        worker = record_engine.workers.get(str(target_id))
        if worker is not None:
            return worker

        msg = f"LICENSE RECORD BLOCK: {target_id}"
        print(msg)
        write_license_log(msg)
        return None

    def _start_order_targets(self, target_ids, order_code):
        any_started = False

        for target_id in target_ids:
            worker = self._record_worker_for_target(target_id)
            if worker is None:
                continue

            state = self.state.get(target_id)
            if self._record_requested(state) and state.get("order_code") == order_code:
                continue
            if self._record_requested(state) and state.get("order_code"):
                scanner_id = self._scanner_id_for_scan_camera(target_id)
                self._save_mysql_ecom_video_before_stop(scanner_id, target_id, state)

            self.state.start_record(target_id, order_code=order_code)
            any_started = True

        return any_started

    def _packing_log(self, msg):
        print(msg)
        try:
            system_log(msg)
        except Exception:
            pass

    def _packing_sound(self, sound_name):
        """
        Phát âm thanh thật theo nghiệp vụ đóng/giao.
        Nếu chưa có file wav thì fallback về âm thanh cũ.
        """
        try:
            if play_event_sound(sound_name):
                return
        except Exception as exc:
            print("[PACKING SOUND ERROR]", sound_name, exc)

        # Fallback nhóm thông báo / thành công
        if sound_name in (
            "packing_start",
            "prompt_scan_packing_order",
            "prompt_scan_packing_items",
            "prompt_scan_delivery_order",
            "prompt_scan_delivery_box",
            "ready_for_packing",
            "invite_scan_order",
            "invite_scan_box",
            "box_confirm_ok",
            "ready_for_handover",
            "handover_success",
        ):
            order_ok()
            return

        # Fallback quét kiện nhỏ
        if sound_name in (
            "item_scan_ok",
        ):
            employee_ok()
            return

        # Fallback nhóm lỗi / stop
        if sound_name in (
            "packing_stop",
            "handover_error",
            "order_not_packed",
            "order_already_delivered",
            "error_session_running",
            "error_no_session",
            "packing_delete_ok",
        ):
            stop_ok()
            return

        print("[PACKING SOUND]", sound_name)

    def _packing_start_record(self, scanner_id, order_code, session_type, session_id):
        """
        Scanner nào quét thì record theo mapping scanner đó.

        Tên file video phân biệt:
        - DONG_abc1234
        - GIAO_abc1234
        """

        scan_cam_id = self._find_camera_by_sub(scanner_id)

        if not scan_cam_id:
            print("[PACKING RECORD START ERROR] Scanner not found:", scanner_id)
            return

        target_ids = self._target_camera_ids(scan_cam_id)

        record_key = f"{session_type}:{session_id}:{scanner_id}"
        self.packing_record_targets[record_key] = list(target_ids)

        if session_type == "packing":
            record_order_code = f"DONG_{order_code}"
        elif session_type == "handover":
            record_order_code = f"GIAO_{order_code}"
        else:
            record_order_code = order_code

        print(
            "[PACKING RECORD START]",
            "scanner=", scanner_id,
            "scan_cam_id=", scan_cam_id,
            "targets=", target_ids,
            "order=", order_code,
            "record_order_code=", record_order_code,
            "type=", session_type,
            "session_id=", session_id,
        )

        for target_id in target_ids:
            worker = self._record_worker_for_target(target_id)
            if worker is None:
                continue

            state = self.state.get(target_id)

            if self._record_requested(state) and state.get("order_code") == record_order_code:
                continue

            self.state.start_record(target_id, order_code=record_order_code)


    def _get_last_video_info_from_state(self, camera_id):
        """
        Lấy đường dẫn video hiện tại/gần nhất.
        Ưu tiên lấy trực tiếp từ RecordWorker.current_file,
        sau đó fallback về state.set_video().
        """
        camera_id = str(camera_id)

        file_path = ""
        duration_sec = None
        file_size_mb = None
        start_time = None
        end_time = None

        # 1. Ưu tiên lấy từ RecordWorker.current_file
        try:
            worker = self._record_worker_for_target(camera_id)
            if worker is not None:
                file_path = getattr(worker, "current_file", "") or ""
                started_mono = getattr(worker, "record_started_mono", 0.0) or 0.0
                if started_mono:
                    import time
                    duration_sec = int(max(0, time.monotonic() - started_mono))
        except Exception as exc:
            print("[VIDEO WORKER INFO ERROR]", camera_id, exc)

        # 2. Fallback lấy từ state
        try:
            state = self.state.get(camera_id) or {}
        except Exception:
            state = {}

        if not file_path:
            file_path = (
                state.get("video")
                or state.get("video_path")
                or state.get("current_video")
                or state.get("current_video_path")
                or state.get("last_file")
                or state.get("last_file_path")
                or state.get("last_video")
                or state.get("last_video_path")
                or state.get("file_path")
                or state.get("current_file")
                or ""
            )

        if not duration_sec:
            duration_sec = (
                state.get("duration_sec")
                or state.get("last_duration_sec")
                or state.get("video_duration_sec")
                or None
            )

        if file_path:
            try:
                import os
                if os.path.exists(file_path):
                    file_size_mb = round(os.path.getsize(file_path) / 1024 / 1024, 2)
            except Exception:
                file_size_mb = None

        start_time = (
            state.get("start_time")
            or state.get("record_start_time")
            or None
        )

        end_time = (
            state.get("end_time")
            or state.get("record_end_time")
            or None
        )

        return {
            "file_path": file_path,
            "duration_sec": duration_sec,
            "file_size_mb": file_size_mb,
            "start_time": start_time,
            "end_time": end_time,
        }
            
    def _employee_info_for_scanner(self, scan_cam_id):
        """
        Lấy nhân viên đang gán cho scanner/camera mapping.
        Ưu tiên target camera theo mapping.
        """
        employee_id = ""
        employee_name = ""

        try:
            target_ids = self._target_camera_ids(scan_cam_id)
        except Exception:
            target_ids = [scan_cam_id]

        # Ưu tiên lấy từ các camera target
        for target_id in target_ids:
            try:
                st = self.state.get(target_id) or {}
            except Exception:
                st = {}

            employee_id = st.get("employee_id", "") or st.get("employee_code", "")
            employee_name = st.get("employee_name", "")

            if employee_id or employee_name:
                return employee_id, employee_name

        # Fallback lấy từ chính camera scan
        try:
            st = self.state.get(scan_cam_id) or {}
        except Exception:
            st = {}

        employee_id = st.get("employee_id", "") or st.get("employee_code", "")
        employee_name = st.get("employee_name", "")

        return employee_id, employee_name

    def _packing_item_count(self, session_id):
        if hasattr(self.packing_service.db, "count_packing_items"):
            try:
                return self.packing_service.db.count_packing_items(session_id)
            except Exception:
                return 0
        try:
            with self.packing_service.db.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM packing_items
                    WHERE session_id = ?
                      AND IFNULL(is_deleted, 0) = 0
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
                return int(row["cnt"] or 0)
        except Exception:
            return 0

    def _sync_mysql_small_packages(self, order_code, scanner_id, sqlite_session_id, mysql_session_id):
        if getattr(self.packing_service.db, "is_mysql", False):
            return
        if not self.mysql_repo or not sqlite_session_id or not mysql_session_id:
            return

        try:
            with self.packing_service.db.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        pi.id,
                        pi.item_code,
                        pi.scan_time,
                        pi.scan_index,
                        ps.employee_code,
                        ps.employee_name
                    FROM packing_items pi
                    LEFT JOIN packing_sessions ps ON ps.id = pi.session_id
                    WHERE pi.session_id = ?
                      AND IFNULL(pi.is_deleted, 0) = 0
                    ORDER BY pi.scan_index ASC, pi.id ASC
                    """,
                    (sqlite_session_id,),
                )
                rows = cur.fetchall()

            for row in rows:
                self.mysql_repo.add_wholesale_child_item(
                    master_order_code=order_code,
                    child_order_code=row["item_code"],
                    packing_session_id=mysql_session_id,
                    scanner_id=scanner_id,
                    employee_code=row["employee_code"] or "",
                    employee_name=row["employee_name"] or "",
                    legacy_item_id=row["id"],
                    scanned_at=row["scan_time"],
                )
        except Exception as exc:
            self._packing_log(
                f"[MYSQL SMALL PACKAGE SYNC ERROR] order={order_code}, session={sqlite_session_id}, error={exc}"
            )

    def _save_mysql_packing_video(
        self,
        order_code,
        scanner_id,
        session_type,
        session_id,
        target_id,
        video_info,
        result=None,
    ):
        if session_type == "handover":
            return
        if not self.mysql_repo or not order_code or not video_info.get("file_path"):
            return

        try:
            if session_type == "packing":
                video_type = "WHOLESALE"
                item_count = self._packing_item_count(session_id)
                item_report_enabled = True
                mysql_session_id = self.mysql_repo.create_packing_session(
                    order_code=order_code,
                    scanner_id=scanner_id,
                    legacy_session_id=session_id,
                    order_type="WHOLESALE",
                )
                self._sync_mysql_small_packages(
                    order_code=order_code,
                    scanner_id=scanner_id,
                    sqlite_session_id=session_id,
                    mysql_session_id=mysql_session_id,
                )
                self.mysql_repo.finish_packing_session(
                    order_code=order_code,
                    packing_session_id=mysql_session_id,
                    total_items=item_count,
                )
            else:
                video_type = "ECOM"
                item_count = 0
                item_report_enabled = False
                mysql_session_id = None

            file_size = 0
            if video_info.get("file_size_mb") is not None:
                file_size = int(float(video_info.get("file_size_mb") or 0) * 1024 * 1024)

            self.mysql_repo.add_packing_video(
                order_code=order_code,
                file_path=video_info.get("file_path"),
                session_type=session_type,
                packing_session_id=mysql_session_id,
                scanner_id=scanner_id,
                camera_id=str(target_id),
                camera_name=str(target_id),
                start_time=video_info.get("start_time"),
                end_time=video_info.get("end_time"),
                duration_seconds=float(video_info.get("duration_sec") or 0),
                file_size=file_size,
                result=result or "done",
                video_type=video_type,
                item_report_enabled=item_report_enabled,
                item_count=item_count,
            )
            self._packing_log(
                f"[MYSQL VIDEO] type={video_type}, order={order_code}, "
                f"camera={target_id}, items={item_count}, file={video_info.get('file_path')}"
            )
        except Exception as exc:
            self._packing_log(
                f"[MYSQL VIDEO ERROR] order={order_code}, camera={target_id}, error={exc}"
            )

    def _save_mysql_ecom_video_before_stop(self, scanner_id, target_id, state):
        order_code = (state or {}).get("order_code", "")
        if not order_code:
            return

        video_info = self._get_last_video_info_from_state(target_id)
        self._save_mysql_packing_video(
            order_code=order_code,
            scanner_id=scanner_id,
            session_type="ecom_packing",
            session_id=None,
            target_id=target_id,
            video_info=video_info,
            result="done",
        )
        
    def _packing_stop_record(self, scanner_id, order_code, session_type, session_id, result=None):
        """
        Dừng record theo mapping scanner đó.
        Đồng thời lưu thông tin video vào bảng record_files.
        """

        scan_cam_id = self._find_camera_by_sub(scanner_id)

        if not scan_cam_id:
            print("[PACKING RECORD STOP ERROR] Scanner not found:", scanner_id)
            return

        record_key = f"{session_type}:{session_id}:{scanner_id}"

        target_ids = self.packing_record_targets.get(record_key)

        if not target_ids:
            target_ids = self._target_camera_ids(scan_cam_id)

        if session_type == "packing":
            record_order_code = f"DONG_{order_code}"
        elif session_type == "handover":
            record_order_code = f"GIAO_{order_code}"
        else:
            record_order_code = order_code

        print(
            "[PACKING RECORD STOP]",
            "scanner=", scanner_id,
            "scan_cam_id=", scan_cam_id,
            "targets=", target_ids,
            "order=", order_code,
            "record_order_code=", record_order_code,
            "type=", session_type,
            "session_id=", session_id,
            "result=", result,
        )

        for target_id in target_ids:
            video_info = self._get_last_video_info_from_state(target_id)

            self.state.stop_record(target_id, clear_employee=False)

            try:
                self.packing_service.db.add_record_file(
                    session_type=session_type,
                    session_id=session_id,
                    order_code=order_code,
                    scanner_id=scanner_id,
                    camera_id=str(target_id),
                    file_path=video_info.get("file_path"),
                    start_time=video_info.get("start_time"),
                    end_time=video_info.get("end_time"),
                    duration_sec=video_info.get("duration_sec"),
                    file_size_mb=video_info.get("file_size_mb"),
                    result=result,
                )

                self._packing_log(
                    f"[VIDEO DB] "
                    f"type={session_type}, "
                    f"order={order_code}, "
                    f"record_order_code={record_order_code}, "
                    f"scanner={scanner_id}, "
                    f"camera={target_id}, "
                    f"result={result}, "
                    f"file={video_info.get('file_path')}"
                )
                if not getattr(self.packing_service.db, "is_mysql", False):
                    self._save_mysql_packing_video(
                        order_code=order_code,
                        scanner_id=scanner_id,
                        session_type=session_type,
                        session_id=session_id,
                        target_id=target_id,
                        video_info=video_info,
                        result=result,
                    )

            except Exception as exc:
                self._packing_log(
                    f"[VIDEO DB ERROR] "
                    f"type={session_type}, "
                    f"order={order_code}, "
                    f"scanner={scanner_id}, "
                    f"camera={target_id}, "
                    f"error={exc}"
                )

        self.packing_record_targets.pop(record_key, None)
            


    def _handle_command(self, scan_cam_id, text):
        cmd = self._parse_manual_cmd(text)
        if cmd:
            prefix, body = cmd

            scanner_id = prefix.lower().strip()
            body = str(body or "").strip()
            body_lower = body.lower()

            scan_cam_id = self._find_camera_by_sub(scanner_id)
            if not scan_cam_id:
                print("CMD CAMERA NOT FOUND", scanner_id)
                return
            
            # =========================================================
            # CHẾ ĐỘ QR LỆNH CỐ ĐỊNH: DONG / GIAO
            # Dùng khi chưa in được mã dạng dong:ABC / giao:ABC
            # =========================================================

            # 0.1. QR DONG: bật chế độ chờ quét mã thùng lớn
            # Ví dụ: s01DONG
            if body_lower == "dong":
                self.packing_action_state[scanner_id] = {
                    "mode": "packing_wait_master_order"
                }

                self._packing_log(
                    f"[ĐÓNG HÀNG - MỜI QUÉT ĐƠN ĐỂ ĐÓNG] "
                    f"scanner={scanner_id}, "
                    f"trạng_thái=chờ_quét_mã_đơn_đóng"
                )

                self._packing_sound("prompt_scan_packing_order")
                return


            # 0.2. QR GIAO: bật chế độ chờ quét mã đơn giao
            # Ví dụ: s08GIAO
            if body_lower == "giao":
                self.packing_action_state[scanner_id] = {
                    "mode": "handover_wait_delivery_order"
                }

                self._packing_log(
                    f"[GIAO HÀNG - MỜI QUÉT ĐƠN ĐỂ XÁC NHẬN GIAO] "
                    f"scanner_giao={scanner_id}, "
                    f"trạng_thái=chờ_quét_mã_đơn"
                )

                self._packing_sound("prompt_scan_delivery_order")
                return


            # 0.3. Nếu đang ở chế độ chờ mã thùng lớn sau QR DONG
            state_action = self.packing_action_state.get(scanner_id)

            # STOP is a control command and must win over handover state.
            # Example: s03stop must finish the s03 session, not deliver order "stop".
            if body_lower.startswith("stop"):
                active_packing = self._safe_active_packing_session(
                    scanner_id,
                    context="prefixed_stop",
                )

                if active_packing:
                    employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                    self.packing_service.stop_packing(
                        scanner_id=scanner_id,
                        employee_code=employee_id,
                        employee_name=employee_name,
                    )
                    self.packing_action_state.pop(scanner_id, None)
                    return

                if self._has_active_handover_flow(scanner_id):
                    employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                    self.packing_service.finish_handover(
                        scanner_id=scanner_id,
                        delivery_employee_code=employee_id,
                        delivery_employee_name=employee_name,
                    )
                    self.packing_action_state.pop(scanner_id, None)
                    return

                if state_action:
                    self.packing_action_state.pop(scanner_id, None)
                    stop_ok()
                    print("CMD STOP MODE", scanner_id)
                    return

                target_ids = self._target_camera_ids(scan_cam_id)

                for target_id in target_ids:
                    st = self.state.get(target_id)
                    self._save_mysql_ecom_video_before_stop(scanner_id, target_id, st)
                    self.state.stop_record(target_id, clear_employee=False)

                stop_ok()
                print("CMD STOP", target_ids)
                return

            if state_action and state_action.get("mode") == "packing_wait_master_order":
                master_order_code = body.strip()

                if not master_order_code:
                    self._packing_log(
                        f"[ĐÓNG HÀNG LỖI] scanner={scanner_id}, lý_do=Mã thùng lớn rỗng"
                    )
                    self._packing_sound("handover_error")
                    return

                employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                self._packing_log(
                    f"[ĐÓNG HÀNG XÁC NHẬN THÙNG LỚN] "
                    f"scanner={scanner_id}, "
                    f"mã_thùng_lớn={master_order_code}, "
                    f"employee={employee_id or ''} {employee_name or ''}"
                )

                self.packing_service.start_packing(
                    scanner_id=scanner_id,
                    master_order_code=master_order_code,
                    employee_code=employee_id,
                    employee_name=employee_name,
                )

                self._packing_log(
                    f"[ĐÓNG HÀNG - MỜI QUÉT KIỆN NHỎ] "
                    f"scanner={scanner_id}, "
                    f"mã_đơn={master_order_code}, "
                    f"trạng_thái=đang_đóng_hàng"
                )

                self._packing_sound("prompt_scan_packing_items")

                self.packing_action_state.pop(scanner_id, None)
                return


            # 0.4. Nếu đang ở chế độ chờ mã đơn giao sau QR GIAO
            if state_action and state_action.get("mode") == "handover_wait_delivery_order":
                delivery_order_code = body.strip()

                if not delivery_order_code:
                    self._packing_log(
                        f"[GIAO HÀNG LỖI] scanner_giao={scanner_id}, lý_do=Mã đơn giao rỗng"
                    )
                    self._packing_sound("handover_error")
                    return

                employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                result = self.packing_service.start_handover(
                    scanner_id=scanner_id,
                    delivery_order_code=delivery_order_code,
                    delivery_employee_code=employee_id,
                    delivery_employee_name=employee_name,
                )

                if result and result.get("ok"):
                    self.packing_action_state[scanner_id] = {
                        "mode": "handover_wait_box_code",
                        "delivery_order_code": delivery_order_code,
                    }

                    self._packing_log(
                        f"[GIAO HÀNG - MỜI QUÉT KIỆN ĐỂ XÁC NHẬN] "
                        f"scanner_giao={scanner_id}, "
                        f"mã_giao={delivery_order_code}, "
                        f"trạng_thái=chờ_quét_mã_kiện"
                    )

                    self._packing_sound("prompt_scan_delivery_box")
                else:
                    # Đơn lỗi vẫn giữ chế độ giao để người dùng quét đơn tiếp theo.
                    self._wait_next_handover_order(scanner_id)

                return


            # 0.5. Nếu đang chờ quét mã thùng giao
            if state_action and state_action.get("mode") == "handover_wait_box_code":
                packing_order_code = body.strip()

                if not packing_order_code:
                    self._packing_log(
                        f"[GIAO HÀNG LỖI] scanner_giao={scanner_id}, lý_do=Mã thùng rỗng"
                    )
                    self._packing_sound("handover_error")
                    return

                self.packing_service.confirm_handover_box(
                    scanner_id=scanner_id,
                    packing_order_code=packing_order_code
                )

                # Sau khi xác nhận đúng/sai xong thì quay lại chờ quét đơn tiếp theo.
                # Chỉ sXXstop mới kết thúc phiên giao và dừng record.
                self._wait_next_handover_order(scanner_id)
                return

            # =========================================================
            # NGHIỆP VỤ MỚI: ĐÓNG HÀNG / GIAO HÀNG
            # Dùng chung scanner prefix s01, s02, s08...
            # =========================================================

            # 1. Giao hàng:
            # s08giao:ABC1234
            # => check database xem đơn đã đóng xong chưa
            # => nếu done thì start record theo mapping s08
            if body_lower.startswith("giao:"):
                order_code = body.split(":", 1)[1].strip()

                if not order_code:
                    print("[HANDOVER ERROR] Empty giao order code")
                    return

                employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                self.packing_service.start_handover(
                    scanner_id=scanner_id,
                    delivery_order_code=order_code,
                    delivery_employee_code=employee_id,
                    delivery_employee_name=employee_name,
                )
                return

            # 2. dong: có 2 nghĩa:
            # - Nếu scanner đang chờ giao hàng => xác nhận mã thùng
            # - Nếu không chờ giao hàng => bắt đầu đóng hàng
            #
            # s01dong:ABC1234 => bắt đầu đóng hàng + record theo mapping s01
            # s08dong:ABC1234 sau s08giao:ABC1234 => xác nhận giao
            if body_lower.startswith("dong:"):
                order_code = body.split(":", 1)[1].strip()

                if not order_code:
                    print("[PACKING ERROR] Empty dong order code")
                    return

                confirm_result = self.packing_service.confirm_handover_box(
                    scanner_id=scanner_id,
                    packing_order_code=order_code
                )

                if confirm_result is not None:
                    if scanner_id in self.packing_service.active_handover_record:
                        self._wait_next_handover_order(scanner_id)
                    return

                employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                self.packing_service.start_packing(
                    scanner_id=scanner_id,
                    master_order_code=order_code,
                    employee_code=employee_id,
                    employee_name=employee_name,
                )
                return

            # 3. stop:
            # Nếu scanner đang có phiên đóng hàng thì stop phiên đóng hàng.
            # Nếu không có phiên đóng hàng thì chạy logic stop record cũ.
            if body_lower.startswith("stop"):
                # 1. Nếu scanner đang có phiên đóng hàng thì stop đóng hàng
                active_packing = self._safe_active_packing_session(
                    scanner_id,
                    context="prefixed_stop",
                )

                if active_packing:
                    employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                    self.packing_service.stop_packing(
                        scanner_id=scanner_id,
                        employee_code=employee_id,
                        employee_name=employee_name,
                    )
                    return
                # 2. Nếu scanner đang có phiên giao hàng thì stop toàn bộ phiên giao
                if self._has_active_handover_flow(scanner_id):
                    employee_id, employee_name = self._employee_info_for_scanner(scan_cam_id)

                    self.packing_service.finish_handover(
                        scanner_id=scanner_id,
                        delivery_employee_code=employee_id,
                        delivery_employee_name=employee_name,
                    )
                    self.packing_action_state.pop(scanner_id, None)
                    return

                # 3. Nếu không thuộc nghiệp vụ đóng/giao thì chạy stop record cũ
                target_ids = self._target_camera_ids(scan_cam_id)

                for target_id in target_ids:
                    st = self.state.get(target_id)
                    self._save_mysql_ecom_video_before_stop(scanner_id, target_id, st)
                    self.state.stop_record(target_id, clear_employee=False)

                stop_ok()
                print("CMD STOP", target_ids)
                return



            # 4. EMP vẫn giữ logic cũ
            if body_lower.startswith("emp:"):
                target_ids = self._target_camera_ids(scan_cam_id)

                emp = body.split(":", 1)[1].strip()
                for target_id in target_ids:
                    self.state.assign_employee(target_id, employee_id=emp, employee_name="")

                employee_ok()
                print("CMD EMP", target_ids, emp)
                return
            
            # 5. XÓA MÃ KIỆN NHỎ QUÉT NHẦM
            # s01xoa        => xóa mã vừa quét gần nhất
            # s01xoa:ABC999 => xóa lần quét gần nhất của mã ABC999
            if body_lower == "xoa" or body_lower.startswith("xoa:"):
                item_code = ""

                if ":" in body:
                    item_code = body.split(":", 1)[1].strip()

                self.packing_service.delete_packing_item(
                    scanner_id=scanner_id,
                    item_code=item_code or None
                )
                return

            # 5. Mã nhỏ aaa/bbb/cccc:
            # Nếu scanner đang có phiên đóng hàng thì chỉ lưu database,
            # KHÔNG start record mới.
            active_packing = self._safe_active_packing_session(
                scanner_id,
                context="prefixed_scan",
            )

            if active_packing:
                self.packing_service.add_packing_item(
                    scanner_id=scanner_id,
                    item_code=body
                )
                return

            # 6. Không thuộc nghiệp vụ đóng/giao thì giữ logic order cũ
            target_ids = self._target_camera_ids(scan_cam_id)

            order_code = body.strip()
            if not order_code:
                return

            if self._start_order_targets(target_ids, order_code):
                order_ok()
                print("CMD RECORD", target_ids, order_code)

            return

        if self._handle_raw_business_scan(scan_cam_id, text):
            return

        command = parse_qr_command(text)
        action = command["action"]
        if action == "stop":
            scanner_id = DEFAULT_RECORD_SCANNER_ID
            if self._has_active_handover_flow(scanner_id):
                self.packing_service.finish_handover(scanner_id=scanner_id)
                self.packing_action_state.pop(scanner_id, None)
                stop_ok()
                print("CMD DEFAULT HANDOVER STOP", DEFAULT_RECORD_SCANNER_ID)
                return

            target_ids = self._default_record_targets()
            for target_id in target_ids:
                st = self.state.get(target_id)
                self._save_mysql_ecom_video_before_stop(scanner_id, target_id, st)
                self.state.stop_record(target_id, clear_employee=False)
            stop_ok()
            print("CMD DEFAULT STOP", DEFAULT_RECORD_SCANNER_ID, target_ids)
            return

        if action == "employee":
            target_ids = self._target_camera_ids(scan_cam_id)
            for target_id in target_ids:
                self.state.assign_employee(
                    target_id,
                    employee_id=command.get("employee_id", ""),
                    employee_name=command.get("employee_name", ""),
                    shift_code=command.get("shift_code", ""),
                )
            employee_ok()
            return

        if action != "order":
            return

        order_code = command.get("order_code", "")
        if not order_code:
            return

        target_ids = self._default_record_targets()
        if self._start_order_targets(target_ids, order_code):
            order_ok()
            print("CMD DEFAULT RECORD", DEFAULT_RECORD_SCANNER_ID, target_ids, order_code)

    def _target_camera_ids(self, scan_cam_id):
        data = load_config()
        mapping = data.get("record_mapping", {})
        targets = mapping.get(str(scan_cam_id), [])
        return targets or [str(scan_cam_id)]

    def stop(self):
        self.running = False

    def _record_requested(self, state):
        return bool((state or {}).get("record_requested", (state or {}).get("recording", False)))

    def _clean_seen_cache(self):
        now = time.time()
        self.last_seen = {key: value for key, value in self.last_seen.items() if now - value < 10}
