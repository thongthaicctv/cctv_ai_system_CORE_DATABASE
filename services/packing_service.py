# services/packing_service.py
# -*- coding: utf-8 -*-

from datetime import datetime

from db.packing_mysql_db import MySQLPackingDB


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class PackingService:
    """
    Service xử lý nghiệp vụ đóng hàng và giao hàng.

    Quy tắc:
    - dong:ABC1234 bắt đầu đóng hàng nếu scanner không có pending giao hàng
    - mã aaa/bbb/cccc chỉ lưu database, không kích hoạt record
    - stop kết thúc đóng hàng và dừng record
    - giao:ABC1234 check database:
        + chưa đóng xong => phát âm thanh cảnh báo
        + đã đóng xong => phát âm thanh sẵn sàng + bắt đầu record giao hàng
    - sau giao:ABC1234, quét dong:ABC1234 để đối chiếu thùng
    """

    def __init__(
        self,
        db_path=None,
        start_record_callback=None,
        stop_record_callback=None,
        sound_callback=None,
        log_callback=None,
    ):
        self.db = MySQLPackingDB()
        self._memory_session_seq = 0
        self._memory_sessions = {}

        # Callback nối với hệ thống record hiện tại
        self.start_record_callback = start_record_callback
        self.stop_record_callback = stop_record_callback

        # Callback phát âm thanh
        self.sound_callback = sound_callback

        # Callback ghi log ra UI hoặc console
        self.log_callback = log_callback

        # Trạng thái giao hàng đang chờ quét mã thùng
        # key = scanner_id
        self.pending_handover = {}

        # Record giao hàng đang chạy theo scanner
        # key = scanner_id
        self.active_handover_record = {}

    # =========================================================
    # LOG / SOUND
    # =========================================================

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def _next_memory_session_id(self):
        self._memory_session_seq += 1
        return -self._memory_session_seq

    def play_sound(self, sound_name):
        """
        sound_name:
        - packing_start
        - item_scan_ok
        - packing_stop
        - order_not_packed
        - ready_for_handover
        - handover_success
        - handover_error
        - error_session_running
        - error_no_session
        """
        if self.sound_callback:
            self.sound_callback(sound_name)
        else:
            print("[SOUND]", sound_name)

    # =========================================================
    # RECORD CALLBACK
    # =========================================================

    def start_record(self, scanner_id, order_code, session_type, session_id):
        """
        Scanner nào quét thì record theo mapping của scanner đó.
        session_type = packing / handover
        """
        if self.start_record_callback:
            self.start_record_callback(
                scanner_id=scanner_id,
                order_code=order_code,
                session_type=session_type,
                session_id=session_id
            )
        else:
            self.log(
                f"[RECORD START MOCK] scanner={scanner_id}, "
                f"order={order_code}, type={session_type}, session={session_id}"
            )

    def stop_record(self, scanner_id, order_code, session_type, session_id, result=None):
        if self.stop_record_callback:
            self.stop_record_callback(
                scanner_id=scanner_id,
                order_code=order_code,
                session_type=session_type,
                session_id=session_id,
                result=result
            )
        else:
            self.log(
                f"[RECORD STOP MOCK] scanner={scanner_id}, "
                f"order={order_code}, type={session_type}, "
                f"session={session_id}, result={result}"
            )

    # =========================================================
    # PACKING
    # =========================================================

    def start_packing(
        self,
        scanner_id,
        master_order_code,
        employee_code=None,
        employee_name=None,
    ):
        """
        s01dong:ABC1234
        => bắt đầu đóng đơn lớn
        => start record theo mapping scanner s01

        Lưu ý:
        - Nếu đơn đã giao thành công rồi thì không cho đóng lại.
        - Nếu scanner đang có đơn đóng chưa stop thì không cho mở đơn mới.
        """

        # 0. Chặn đóng lại đơn đã giao thành công
        try:
            success_handover = self.db.find_success_handover(master_order_code)
        except Exception as exc:
            success_handover = None
            self.log(f"[MYSQL WARNING] find_success_handover failed, continue record: {exc}")

        if success_handover:
            self.log(
                f"[ĐÓNG HÀNG LỖI - ĐƠN ĐÃ GIAO] "
                f"scanner={scanner_id}, "
                f"mã_đơn={master_order_code}, "
                f"handover_id_cũ={success_handover['id']}, "
                f"kết_quả=blocked_already_delivered, "
                f"lý_do=Đơn hàng đã được giao thành công trước đó"
            )

            self.play_sound("order_already_delivered")

            return {
                "ok": False,
                "action": "packing_start",
                "reason": "order_already_delivered",
                "message": "Đơn hàng đã được giao thành công trước đó, không cho đóng lại"
            }

        # 1. Chặn scanner đang có phiên đóng chưa stop
        try:
            active = self.db.get_active_packing_session(scanner_id)
        except Exception as exc:
            active = self._memory_sessions.get(scanner_id)
            self.log(f"[MYSQL WARNING] get_active_packing_session failed, use memory state: {exc}")

        if active:
            current_order = active["master_order_code"]

            self.log(
                f"[PACKING WARNING] Scanner {scanner_id} đang đóng đơn "
                f"{current_order}, chưa stop."
            )

            self.play_sound("error_session_running")

            return {
                "ok": False,
                "action": "packing_start",
                "reason": "session_running",
                "message": f"Scanner {scanner_id} đang đóng đơn {current_order}"
            }

        # 2. Tạo phiên đóng hàng mới
        try:
            session_id = self.db.create_packing_session(
                master_order_code=master_order_code,
                scanner_id=scanner_id,
                employee_code=employee_code,
                employee_name=employee_name,
            )
        except Exception as exc:
            session_id = self._next_memory_session_id()
            self._memory_sessions[scanner_id] = {
                "id": session_id,
                "master_order_code": master_order_code,
                "packing_scanner_id": scanner_id,
                "employee_code": employee_code or "",
                "employee_name": employee_name or "",
                "total_items": 0,
            }
            self.log(f"[MYSQL ERROR] create_packing_session failed, record still starts: {exc}")

        self.log(
            f"[PACKING START] scanner={scanner_id}, "
            f"order={master_order_code}, "
            f"employee={employee_code or ''} {employee_name or ''}, "
            f"session_id={session_id}"
        )

        self.play_sound("packing_start")

        # 3. Bắt đầu ghi hình đóng hàng theo mapping scanner
        self.start_record(
            scanner_id=scanner_id,
            order_code=master_order_code,
            session_type="packing",
            session_id=session_id
        )

        return {
            "ok": True,
            "action": "packing_start",
            "session_id": session_id,
            "master_order_code": master_order_code
        }
    

    def add_packing_item(self, scanner_id, item_code):
        """
        s01aaa / s01bbb / s01cccc
        => chỉ lưu database
        => không start record mới
        """
        try:
            active = self.db.get_active_packing_session(scanner_id)
        except Exception as exc:
            active = self._memory_sessions.get(scanner_id)
            self.log(f"[MYSQL WARNING] get_active_packing_session failed, use memory state: {exc}")

        if not active:
            self.log(
                f"[PACKING ITEM ERROR] Scanner {scanner_id} quét mã {item_code} "
                f"nhưng chưa có đơn lớn đang đóng."
            )
            self.play_sound("error_no_session")
            return {
                "ok": False,
                "action": "packing_item",
                "reason": "no_active_session",
                "message": "Chưa có đơn lớn đang đóng"
            }

        session_id = active["id"]
        master_order_code = active["master_order_code"]

        try:
            scan_index = self.db.add_packing_item(
                session_id=session_id,
                master_order_code=master_order_code,
                item_code=item_code
            )
        except Exception as exc:
            if active is self._memory_sessions.get(scanner_id):
                active["total_items"] = int(active.get("total_items") or 0) + 1
                scan_index = active["total_items"]
            else:
                scan_index = 0
            self.log(f"[MYSQL ERROR] add_packing_item failed, continue record: {exc}")

        self.log(
            f"[PACKING ITEM] scanner={scanner_id}, "
            f"order={master_order_code}, item={item_code}, index={scan_index}"
        )

        self.play_sound("item_scan_ok")

        return {
            "ok": True,
            "action": "packing_item",
            "session_id": session_id,
            "master_order_code": master_order_code,
            "item_code": item_code,
            "scan_index": scan_index
        }

    def delete_packing_item(self, scanner_id, item_code=None):
        """
        s01xoa        => xóa mã kiện nhỏ vừa quét gần nhất
        s01xoa:ABC999 => xóa lần quét gần nhất của mã ABC999
        """
        try:
            active = self.db.get_active_packing_session(scanner_id)
        except Exception as exc:
            active = self._memory_sessions.get(scanner_id)
            self.log(f"[MYSQL WARNING] get_active_packing_session failed, use memory state: {exc}")

        if not active:
            self.log(
                f"[PACKING DELETE ERROR] Scanner {scanner_id} chưa có đơn lớn đang đóng."
            )
            self.play_sound("error_no_session")
            return {
                "ok": False,
                "action": "packing_delete_item",
                "reason": "no_active_session",
                "message": "Chưa có đơn lớn đang đóng"
            }

        session_id = active["id"]
        master_order_code = active["master_order_code"]

        try:
            deleted = self.db.delete_last_packing_item(
                session_id=session_id,
                item_code=item_code
            )
        except Exception as exc:
            deleted = None
            self.log(f"[MYSQL ERROR] delete_last_packing_item failed: {exc}")

        if not deleted:
            self.log(
                f"[PACKING DELETE ERROR] scanner={scanner_id}, "
                f"order={master_order_code}, "
                f"item={item_code or 'LAST'}, "
                f"reason=Không tìm thấy mã cần xóa"
            )
            self.play_sound("handover_error")
            return {
                "ok": False,
                "action": "packing_delete_item",
                "reason": "item_not_found",
                "message": "Không tìm thấy mã kiện cần xóa"
            }

        self.log(
            f"[PACKING DELETE ITEM] "
            f"scanner={scanner_id}, "
            f"order={master_order_code}, "
            f"deleted_item={deleted['item_code']}, "
            f"scan_index={deleted['scan_index']}, "
            f"session_id={session_id}"
        )

        self.play_sound("packing_delete_ok")

        return {
            "ok": True,
            "action": "packing_delete_item",
            "session_id": session_id,
            "master_order_code": master_order_code,
            "deleted_item": deleted["item_code"],
            "scan_index": deleted["scan_index"],
        }

    def stop_packing(self, scanner_id, employee_code=None, employee_name=None):
        """
        s01stop
        => kết thúc đóng hàng
        => nếu có thông tin nhân viên thì lưu bổ sung vào packing_sessions
        => stop record theo mapping s01

        An toàn:
        - Nếu packing_db.py chưa có update_packing_employee thì vẫn chạy tiếp.
        - Không làm hỏng logic stop cũ.
        """
        try:
            active = self.db.get_active_packing_session(scanner_id)
        except Exception as exc:
            active = self._memory_sessions.get(scanner_id)
            self.log(f"[MYSQL WARNING] get_active_packing_session failed, use memory state: {exc}")

        if not active:
            self.log(f"[PACKING STOP ERROR] Scanner {scanner_id} không có đơn đang đóng.")
            self.play_sound("error_no_session")
            return {
                "ok": False,
                "action": "packing_stop",
                "reason": "no_active_session",
                "message": "Không có đơn đang đóng"
            }

        session_id = active["id"]
        master_order_code = active["master_order_code"]

        try:
            total_items = self.db.finish_packing_session(session_id)
        except Exception as exc:
            total_items = int(active.get("total_items") or 0)
            self.log(f"[MYSQL ERROR] finish_packing_session failed, stop record still runs: {exc}")
        self._memory_sessions.pop(scanner_id, None)

        # Lưu nhân viên đóng nếu DB đã hỗ trợ
        try:
            if hasattr(self.db, "update_packing_employee"):
                self.db.update_packing_employee(
                    session_id=session_id,
                    employee_code=employee_code,
                    employee_name=employee_name,
                )
        except Exception as exc:
            self.log(
                f"[PACKING EMPLOYEE SAVE WARNING] "
                f"session_id={session_id}, "
                f"employee={employee_code or ''} {employee_name or ''}, "
                f"error={exc}"
            )

        self.log(
            f"[PACKING STOP] scanner={scanner_id}, "
            f"order={master_order_code}, "
            f"employee={employee_code or ''} {employee_name or ''}, "
            f"session_id={session_id}, total_items={total_items}"
        )

        self.play_sound("packing_stop")

        self.stop_record(
            scanner_id=scanner_id,
            order_code=master_order_code,
            session_type="packing",
            session_id=session_id,
            result="done"
        )

        return {
            "ok": True,
            "action": "packing_stop",
            "session_id": session_id,
            "master_order_code": master_order_code,
            "total_items": total_items,
            "employee_code": employee_code or "",
            "employee_name": employee_name or "",
        }

    # =========================================================
    # HANDOVER
    # =========================================================

    def start_handover(
        self,
        scanner_id,
        delivery_order_code,
        delivery_employee_code=None,
        delivery_employee_name=None,
    ):
        """
        s08giao:ABC1234

        Check database:
        - Nếu đã giao thành công rồi => báo đơn đã giao, không record
        - Nếu chưa có packing_sessions status=done => báo chưa đóng
        - Nếu đã done => phát sẵn sàng + start record giao theo mapping s08
        """

        # 0. Chặn giao lại đơn đã giao thành công
        try:
            success_handover = self.db.find_success_handover(delivery_order_code)
        except Exception as exc:
            success_handover = None
            self.log(f"[MYSQL WARNING] find_success_handover failed, continue handover record: {exc}")

        if success_handover:
            self.log(
                f"[GIAO HÀNG LỖI - ĐƠN ĐÃ GIAO] "
                f"scanner_giao={scanner_id}, "
                f"mã_giao={delivery_order_code}, "
                f"handover_id_cũ={success_handover['id']}, "
                f"kết_quả=failed_already_delivered, "
                f"lý_do=Đơn hàng đã được giao thành công trước đó"
            )

            try:
                self.db.create_handover_failed_already_delivered(
                    delivery_order_code=delivery_order_code,
                    scanner_id=scanner_id
                )
            except Exception as exc:
                self.log(f"[MYSQL ERROR] create_handover_failed_already_delivered failed: {exc}")

            self.play_sound("order_already_delivered")

            return {
                "ok": False,
                "action": "handover_start",
                "reason": "order_already_delivered",
                "message": "Đơn hàng đã được giao thành công trước đó"
            }

        # 1. Check đơn đã đóng xong chưa
        try:
            done_packing = self.db.find_done_packing_order(delivery_order_code)
        except Exception as exc:
            done_packing = {
                "id": self._next_memory_session_id(),
                "master_order_code": delivery_order_code,
                "packing_scanner_id": "MYSQL_UNKNOWN",
            }
            self.log(f"[MYSQL ERROR] find_done_packing_order failed, handover record still starts: {exc}")

        if not done_packing:
            self.log(
                f"[GIAO HÀNG LỖI - CHƯA ĐÓNG] "
                f"scanner_giao={scanner_id}, "
                f"mã_giao={delivery_order_code}, "
                f"kết_quả=failed_not_packed, "
                f"lý_do=Đơn hàng chưa được đóng xong"
            )

            try:
                self.db.create_handover_failed_not_packed(
                    delivery_order_code=delivery_order_code,
                    scanner_id=scanner_id
                )
            except Exception as exc:
                self.log(f"[MYSQL ERROR] create_handover_failed_not_packed failed: {exc}")

            self.play_sound("order_not_packed")

            return {
                "ok": False,
                "action": "handover_start",
                "reason": "order_not_packed",
                "message": "Đơn hàng chưa được đóng"
            }

        packing_session_id = done_packing["id"]
        packing_scanner_id = done_packing["packing_scanner_id"]

        first_scan_time = now_str()

        self.pending_handover[scanner_id] = {
            "delivery_order_code": delivery_order_code,
            "packing_order_code": "",
            "packing_session_id": packing_session_id,
            "packing_scanner_id": packing_scanner_id,
            "delivery_employee_code": delivery_employee_code or "",
            "delivery_employee_name": delivery_employee_name or "",
            "first_scan_time": first_scan_time,
            "second_scan_time": "",
        }

        self.log(
            f"[GIAO HÀNG SẴN SÀNG] "
            f"scanner_giao={scanner_id}, "
            f"nv_giao={delivery_employee_code or ''} {delivery_employee_name or ''}, "
            f"mã_giao={delivery_order_code}, "
            f"packing_session_id={packing_session_id}, "
            f"scanner_đóng={packing_scanner_id}, "
            f"kết_quả=ready"
        )

        self.play_sound("ready_for_handover")

        # Chỉ start record giao hàng lần đầu tiên.
        # Các đơn giao tiếp theo dùng chung video cho đến khi s08stop.
        if scanner_id not in self.active_handover_record:
            self.active_handover_record[scanner_id] = {
                "first_delivery_order_code": delivery_order_code,
                "first_packing_session_id": packing_session_id,
                "start_time": first_scan_time,
            }

            self.start_record(
                scanner_id=scanner_id,
                order_code=delivery_order_code,
                session_type="handover",
                session_id=packing_session_id
            )

            self.log(
                f"[GIAO HÀNG RECORD START] "
                f"scanner_giao={scanner_id}, "
                f"mã_đầu_tiên={delivery_order_code}, "
                f"packing_session_id={packing_session_id}"
            )
        else:
            self.log(
                f"[GIAO HÀNG TIẾP TỤC] "
                f"scanner_giao={scanner_id}, "
                f"mã_giao={delivery_order_code}, "
                f"record=đang_chạy"
            )

        return {
            "ok": True,
            "action": "handover_ready",
            "delivery_order_code": delivery_order_code,
            "packing_session_id": packing_session_id,
            "packing_scanner_id": packing_scanner_id
        }



    def confirm_handover_box(self, scanner_id, packing_order_code):
        """
        Sau khi quét giao:ABC1234,
        quét dong:ABC1234 để xác nhận thùng.

        Logic mới:
        - Nếu đúng: lưu DB success ngay
        - Nếu sai: lưu DB failed_wrong_box ngay
        - Không stop record
        - Xóa pending để scanner có thể quét giao: đơn tiếp theo
        """
        pending = self.pending_handover.get(scanner_id)

        if not pending:
            # Không có pending giao, dong: sẽ được hiểu là bắt đầu đóng hàng ở qr_worker.
            return None

        delivery_order_code = pending["delivery_order_code"]
        packing_session_id = pending["packing_session_id"]
        packing_scanner_id = pending["packing_scanner_id"]
        first_scan_time = pending["first_scan_time"]
        second_scan_time = now_str()

        delivery_employee_code = pending.get("delivery_employee_code", "")
        delivery_employee_name = pending.get("delivery_employee_name", "")

        if delivery_order_code == packing_order_code:
            result = "success"
            error_message = None
            sound = "handover_success"

            self.log(
                f"[GIAO HÀNG THÀNH CÔNG] "
                f"scanner_giao={scanner_id}, "
                f"nv_giao={delivery_employee_code or ''} {delivery_employee_name or ''}, "
                f"mã_giao={delivery_order_code}, "
                f"mã_thùng={packing_order_code}, "
                f"packing_session_id={packing_session_id}, "
                f"scanner_đóng={packing_scanner_id}, "
                f"kết_quả=success, "
                f"record=tiếp_tục_chạy"
            )

        else:
            result = "failed_wrong_box"
            error_message = "Sai thùng hàng"
            sound = "handover_error"

            self.log(
                f"[GIAO HÀNG LỖI - SAI THÙNG] "
                f"scanner_giao={scanner_id}, "
                f"nv_giao={delivery_employee_code or ''} {delivery_employee_name or ''}, "
                f"mã_giao={delivery_order_code}, "
                f"mã_thùng={packing_order_code}, "
                f"packing_session_id={packing_session_id}, "
                f"scanner_đóng={packing_scanner_id}, "
                f"kết_quả=failed_wrong_box, "
                f"lý_do=Sai thùng hàng, "
                f"record=tiếp_tục_chạy"
            )

        try:
            handover_id = self.db.create_handover_result(
                delivery_order_code=delivery_order_code,
                packing_order_code=packing_order_code,
                packing_session_id=packing_session_id,
                packing_scanner_id=packing_scanner_id,
                delivery_scanner_id=scanner_id,
                result=result,
                error_message=error_message,
                first_scan_time=first_scan_time,
                second_scan_time=second_scan_time,
                delivery_employee_code=delivery_employee_code,
                delivery_employee_name=delivery_employee_name,
            )
        except Exception as exc:
            handover_id = None
            self.log(f"[MYSQL ERROR] create_handover_result failed, record continues: {exc}")
        except TypeError:
            # DB cũ chưa hỗ trợ delivery_employee_code/name
            handover_id = self.db.create_handover_result(
                delivery_order_code=delivery_order_code,
                packing_order_code=packing_order_code,
                packing_session_id=packing_session_id,
                packing_scanner_id=packing_scanner_id,
                delivery_scanner_id=scanner_id,
                result=result,
                error_message=error_message,
                first_scan_time=first_scan_time,
                second_scan_time=second_scan_time
            )

        self.log(
            f"[GIAO HÀNG ĐÃ LƯU DB] "
            f"handover_id={handover_id}, "
            f"scanner_giao={scanner_id}, "
            f"mã_giao={delivery_order_code}, "
            f"mã_thùng={packing_order_code}, "
            f"kết_quả={result}, "
            f"record=tiếp_tục_chạy"
        )

        self.play_sound(sound)

        # Quan trọng:
        # Xóa pending hiện tại để cho phép quét giao đơn tiếp theo.
        # KHÔNG stop record tại đây.
        self.pending_handover.pop(scanner_id, None)

        return {
            "ok": result == "success",
            "action": "handover_confirm_saved",
            "handover_id": handover_id,
            "delivery_order_code": delivery_order_code,
            "packing_order_code": packing_order_code,
            "result": result,
            "error_message": error_message,
            "recording_continue": True,
        }

    def finish_handover(self, scanner_id, delivery_employee_code=None, delivery_employee_name=None):
        """
        s08stop

        Logic mới:
        - Kết thúc toàn bộ phiên giao hàng của scanner
        - Nếu còn pending giao chưa quét dong: thì lưu failed_missing_box_code
        - Stop record giao hàng
        """
        active_record = self.active_handover_record.get(scanner_id)
        pending = self.pending_handover.get(scanner_id)

        # Nếu không có phiên giao đang chạy và cũng không có pending
        if not active_record and not pending:
            return None

        # Nếu còn pending chưa xác nhận mã thùng thì lưu lỗi thiếu mã thùng
        if pending:
            delivery_order_code = pending.get("delivery_order_code", "")
            packing_session_id = pending.get("packing_session_id")
            packing_scanner_id = pending.get("packing_scanner_id")
            first_scan_time = pending.get("first_scan_time")
            second_scan_time = now_str()

            result = "failed_missing_box_code"
            error_message = "Chưa quét mã thùng dong:"

            self.log(
                f"[GIAO HÀNG LỖI - CHƯA QUÉT MÃ THÙNG] "
                f"scanner_giao={scanner_id}, "
                f"mã_giao={delivery_order_code}, "
                f"kết_quả={result}, "
                f"lý_do={error_message}"
            )

            try:
                self.db.create_handover_result(
                    delivery_order_code=delivery_order_code,
                    packing_order_code="",
                    packing_session_id=packing_session_id,
                    packing_scanner_id=packing_scanner_id,
                    delivery_scanner_id=scanner_id,
                    result=result,
                    error_message=error_message,
                    first_scan_time=first_scan_time,
                    second_scan_time=second_scan_time,
                    delivery_employee_code=delivery_employee_code,
                    delivery_employee_name=delivery_employee_name,
                )
            except TypeError:
                self.db.create_handover_result(
                    delivery_order_code=delivery_order_code,
                    packing_order_code="",
                    packing_session_id=packing_session_id,
                    packing_scanner_id=packing_scanner_id,
                    delivery_scanner_id=scanner_id,
                    result=result,
                    error_message=error_message,
                    first_scan_time=first_scan_time,
                    second_scan_time=second_scan_time
                )

            self.play_sound("handover_error")
            self.pending_handover.pop(scanner_id, None)

        # Stop record giao hàng nếu đang chạy
        if active_record:
            first_order = active_record.get("first_delivery_order_code", "")
            first_session_id = active_record.get("first_packing_session_id")

            self.log(
                f"[GIAO HÀNG KẾT THÚC PHIÊN] "
                f"scanner_giao={scanner_id}, "
                f"mã_đầu_tiên={first_order}, "
                f"session_id={first_session_id}, "
                f"hành_động=stop_record"
            )

            self.stop_record(
                scanner_id=scanner_id,
                order_code=first_order,
                session_type="handover",
                session_id=first_session_id,
                result="done"
            )

            self.active_handover_record.pop(scanner_id, None)

        return {
            "ok": True,
            "action": "handover_finish_batch",
            "scanner_id": scanner_id,
        }
