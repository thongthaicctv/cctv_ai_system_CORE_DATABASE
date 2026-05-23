# services/scan_command_router.py
# -*- coding: utf-8 -*-

from services.packing_service import PackingService


class ScanCommandRouter:
    """
    Nhận chuỗi scan đầy đủ từ máy đọc mã vạch.

    Ví dụ phần mềm nhận:
    - s01dong:ABC1234
    - s01aaa
    - s01bbb
    - s01stop
    - s08giao:ABC1234
    - s08dong:ABC1234

    Router sẽ tách:
    - scanner_id = s01 / s08
    - code = dong:ABC1234 / aaa / stop / giao:ABC1234
    """

    def __init__(
        self,
        scanner_prefixes,
        packing_service: PackingService,
        log_callback=None
    ):
        self.scanner_prefixes = sorted(scanner_prefixes, key=len, reverse=True)
        self.packing_service = packing_service
        self.log_callback = log_callback

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def parse_scanner_code(self, text):
        text = (text or "").strip()

        for prefix in self.scanner_prefixes:
            if text.startswith(prefix):
                code = text[len(prefix):].strip()
                return prefix, code

        return None, text

    def handle_scan(self, text):
        """
        Điểm vào chính.

        Quy tắc:
        1. giao:ABC1234
           => check database
           => nếu done thì record giao theo mapping scanner
        2. dong:ABC1234
           => nếu scanner đang pending giao thì xác nhận giao
           => nếu không pending thì bắt đầu đóng hàng + record đóng hàng
        3. stop
           => kết thúc đóng hàng + stop record
        4. mã thường aaa/bbb/cccc
           => chỉ lưu database packing_items
        """
        scanner_id, code = self.parse_scanner_code(text)

        if not scanner_id:
            self.log(f"[SCAN ERROR] Không nhận được prefix scanner từ mã: {text}")
            return {
                "ok": False,
                "reason": "scanner_prefix_not_found",
                "raw": text
            }

        if not code:
            self.log(f"[SCAN ERROR] Mã rỗng sau prefix scanner: {text}")
            return {
                "ok": False,
                "reason": "empty_code",
                "scanner_id": scanner_id,
                "raw": text
            }

        code_lower = code.lower()

        self.log(f"[SCAN] scanner={scanner_id}, code={code}")

        # =====================================================
        # GIAO HÀNG
        # =====================================================
        if code_lower.startswith("giao:"):
            order_code = code.split(":", 1)[1].strip()

            if not order_code:
                return {
                    "ok": False,
                    "reason": "empty_delivery_order_code",
                    "scanner_id": scanner_id
                }

            return self.packing_service.start_handover(
                scanner_id=scanner_id,
                delivery_order_code=order_code
            )

        # =====================================================
        # DONG:
        # Có 2 nghĩa:
        # 1. Nếu scanner đang pending giao => xác nhận mã thùng
        # 2. Nếu không pending giao => bắt đầu đóng hàng
        # =====================================================
        if code_lower.startswith("dong:"):
            order_code = code.split(":", 1)[1].strip()

            if not order_code:
                return {
                    "ok": False,
                    "reason": "empty_packing_order_code",
                    "scanner_id": scanner_id
                }

            confirm_result = self.packing_service.confirm_handover_box(
                scanner_id=scanner_id,
                packing_order_code=order_code
            )

            if confirm_result is not None:
                return confirm_result

            return self.packing_service.start_packing(
                scanner_id=scanner_id,
                master_order_code=order_code
            )

        # =====================================================
        # STOP
        # =====================================================
        if code_lower == "stop":
            return self.packing_service.stop_packing(scanner_id=scanner_id)

        # =====================================================
        # MÃ NHỎ: aaa/bbb/cccc
        # Chỉ lưu database, không record mới
        # =====================================================
        return self.packing_service.add_packing_item(
            scanner_id=scanner_id,
            item_code=code
        )