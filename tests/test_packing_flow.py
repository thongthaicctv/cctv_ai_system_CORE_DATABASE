# test_packing_flow.py
# -*- coding: utf-8 -*-

from services.packing_service import PackingService
from services.scan_command_router import ScanCommandRouter


def log_msg(msg):
    print(msg)


def play_sound_event(sound_name):
    print("[SOUND]", sound_name)


def start_record_by_scanner_mapping(scanner_id, order_code, session_type, session_id):
    print(
        f"[START RECORD] scanner={scanner_id}, "
        f"order={order_code}, type={session_type}, session_id={session_id}"
    )


def stop_record_by_scanner_mapping(scanner_id, order_code, session_type, session_id, result=None):
    print(
        f"[STOP RECORD] scanner={scanner_id}, "
        f"order={order_code}, type={session_type}, "
        f"session_id={session_id}, result={result}"
    )


scanner_prefixes = [
    "s01", "s02", "s03", "s04",
    "s05", "s06", "s07", "s08",
    "s09", "s10", "s11", "s12",
    "s13", "s14", "s15", "s16",
]

packing_service = PackingService(
    db_path="db/packing.db",
    start_record_callback=start_record_by_scanner_mapping,
    stop_record_callback=stop_record_by_scanner_mapping,
    sound_callback=play_sound_event,
    log_callback=log_msg,
)

router = ScanCommandRouter(
    scanner_prefixes=scanner_prefixes,
    packing_service=packing_service,
    log_callback=log_msg,
)


def scan(text):
    print("\n>>> SCAN:", text)
    result = router.handle_scan(text)
    print("RESULT:", result)


if __name__ == "__main__":
    # Đóng hàng bằng s01
    scan("s01dong:ABC1234")
    scan("s01aaa")
    scan("s01bbb")
    scan("s01cccc")
    scan("s01aaa")
    scan("s01stop")

    # Giao hàng bằng s08
    scan("s08giao:ABC1234")
    scan("s08dong:ABC1234")

    # Test sai thùng
    scan("s01dong:XYZ999")
    scan("s01sp001")
    scan("s01stop")

    scan("s08giao:XYZ999")
    scan("s08dong:ABC1234")

    # Test giao đơn chưa đóng
    scan("s08giao:CHUADONG001")