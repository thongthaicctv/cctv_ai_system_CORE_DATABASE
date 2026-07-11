from datetime import datetime, timedelta

from core.logger import write_license_log

from .anti_rollback import AntiRollback
from .cache_manager import CacheManager
from .google_sync import update_cache_from_google
from .hardware import get_device_id, get_hardware_hash


class LicenseManager:
    def __init__(self):
        self.device_id = get_device_id()
        self.hardware_hash = get_hardware_hash()
        self.data = None
        self.startup_notice = None

    def load(self):
        self.data = CacheManager.load()
        return self.data

    def verify_hardware(self):
        if not self.data:
            return False
        return self.data.get("hardware_hash") == self.hardware_hash

    def _parse_expire_date(self):
        expire_text = str((self.data or {}).get("expire_date", "")).strip()
        if not expire_text:
            return None

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                parsed = datetime.strptime(expire_text, fmt)
                return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            except Exception:
                pass
        return None

    def verify_expire(self):
        expire_date = self._parse_expire_date()
        if not expire_date:
            print("EXPIRE DATE INVALID:", (self.data or {}).get("expire_date", ""))
            return False
        return datetime.now() <= expire_date

    def check_offline_days(self):
        last_sync = (self.data or {}).get("last_sync")
        offline_days = int((self.data or {}).get("offline_days", 30) or 30)

        if not last_sync:
            return False, "Khong tim thay thoi gian dong bo license."

        try:
            last_sync_time = datetime.fromisoformat(str(last_sync))
        except Exception:
            return False, "Du lieu thoi gian license khong hop le."

        now = datetime.now()
        if now - last_sync_time > timedelta(days=offline_days):
            return False, (
                f"License da offline qua {offline_days} ngay.\n"
                "Vui long ket noi Internet de dong bo lai license."
            )

        remain_days = offline_days - (now - last_sync_time).days
        return True, f"OFFLINE_OK | Con {remain_days} ngay can ket noi Internet"

    def verify_time_rollback(self):
        last_run_time = (self.data or {}).get("last_run_time")
        if not last_run_time:
            return True
        return not AntiRollback.is_time_invalid(last_run_time)

    def update_last_run(self):
        CacheManager.update_runtime(last_run_time=str(datetime.now()))
        self.load()

    def expire_date_display(self):
        expire_date = self._parse_expire_date()
        if not expire_date:
            return "N/A"
        return expire_date.strftime("%d/%m/%Y")

    def _sheet_notice_from_data(self):
        note = str((self.data or {}).get("_sheet_note", "")).strip()
        if not note:
            return None

        if note.lower() in {"none", "null", "false", "0", "no", "khong", "không"}:
            return None

        return note

    def check(self):
        self.load()
        had_valid_cache = bool(self.data)
        self.startup_notice = None

        ok_sync, sync_msg = update_cache_from_google(
            self.device_id,
            self.hardware_hash,
        )
        print(sync_msg)

        if ok_sync:
            self.load()
            self.startup_notice = self._sheet_notice_from_data()
        elif sync_msg in (
            "LICENSE_HARDWARE_INVALID_GOOGLE",
            "LICENSE_TOKEN_DEVICE_MISMATCH",
        ):
            return False, sync_msg
        elif sync_msg.startswith("LICENSE_TOKEN_INVALID"):
            return False, sync_msg
        elif sync_msg == "DEVICE_ID_NOT_FOUND":
            return False, (
                "DEVICE_ID chua duoc kich hoat tren he thong ATG.\n"
                "Vui long gui Device ID cho quan tri vien 0904143113."
            )

        if not self.data:
            return False, (
                "Chua co license online hop le.\n"
                "Vui long tao lien he voi quan tri vien 0904143113 de duoc ho tro."
            )

        if str(self.data.get("status", "")).strip().lower() != "active":
            msg = "LICENSE BLOCKED | License da bi khoa tren he thong ATG. Vui long lien he quan tri vien 0904143113 de duoc ho tro."
            print(msg)
            write_license_log(msg)
            return False, msg

        ok_offline, msg_offline = self.check_offline_days()
        print(msg_offline)
        write_license_log(msg_offline)
        if not ok_offline:
            return False, msg_offline

        if not self.verify_time_rollback():
            return False, "LICENSE TIME ROLLBACK INVALID"

        if not self.verify_expire():
            return False, "License da het han. Vui long lien he quan tri vien 0904143113 de gia han license."

        if not self.verify_hardware():
            return False, "LICENSE HARDWARE INVALID"

        self.update_last_run()
        return True, "LICENSE OK"
