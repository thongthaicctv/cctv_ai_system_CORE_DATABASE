from datetime import datetime

from core.logger import write_license_log

from .hardware import get_hardware_hash, get_device_id
from .cache_manager import CacheManager
from .anti_rollback import AntiRollback

from .google_sync import update_cache_from_google
from datetime import datetime, timedelta
class LicenseManager:

    def __init__(self):

        self.device_id = get_device_id()
        self.hardware_hash = get_hardware_hash()

        self.data = None

    def load(self):


        data = CacheManager.load()

        if not data:
            data = CacheManager.create_default(
                self.device_id,
                self.hardware_hash
            )

        self.data = data

        return data
    
        

    def verify_hardware(self):

        if not self.data:
            return False

        return self.data.get("hardware_hash") == self.hardware_hash

    def verify_expire(self):

        expire_text = str(
            self.data.get("expire_date", "")
        ).strip()

        if not expire_text:
            return False

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]

        expire_date = None

        for fmt in formats:
            try:
                expire_date = datetime.strptime(
                    expire_text,
                    fmt
                )
                break
            except:
                pass

        if not expire_date:
            print("EXPIRE DATE INVALID:", expire_text)
            return False

        return datetime.now() <= expire_date

    def verify_offline_days(self):

        last_sync = datetime.fromisoformat(self.data["last_sync"])

        days = (datetime.now() - last_sync).days

        return days <= 30
    

  


    def check_offline_days(self):

        last_sync = self.data.get("last_sync")

        offline_days = int(
            self.data.get("offline_days", 30)
        )

        if not last_sync:
            return False, "Không tìm thấy thời gian đồng bộ license."

        try:
            last_sync_time = datetime.fromisoformat(
                str(last_sync)
            )
        except:
            return False, "Dữ liệu thời gian license không hợp lệ."

        now = datetime.now()

        if now - last_sync_time > timedelta(days=offline_days):
            return False, (
                f"License đã offline quá {offline_days} ngày.\n"
                f"Vui lòng kết nối Internet để đồng bộ lại license."
            )

        remain_days = (
            offline_days - (now - last_sync_time).days
        )

        return True, (
            f"OFFLINE_OK | "
            f"Còn {remain_days} ngày cần kết nối Internet"
        )

    def verify_time_rollback(self):

        return not AntiRollback.is_time_invalid(
            self.data["last_run_time"]
        )

    def update_last_run(self):

        self.data["last_run_time"] = str(datetime.now())

        CacheManager.save(self.data)

    def check(self):

        self.load()

        # =========================
        # GOOGLE SYNC
        # =========================
        ok_sync, sync_msg = update_cache_from_google(
            self.device_id,
            self.hardware_hash
        )

        print(sync_msg)

        if sync_msg == "DEVICE_ID_NOT_FOUND":

            return False, (
                "DEVICE_ID chưa được kích hoạt trên hệ thống ATG.\n"
                "Vui lòng gửi Device ID cho quản trị viên Điện thoại 0904143113."
            )

        # nếu sync thành công thì reload cache mới
        if ok_sync:
            self.load()

        # =========================
        # STATUS
        # =========================
        if self.data.get(
            "status",
            ""
        ).strip().lower() != "active":

            msg = (
                "LICENSE BLOCKED | "
                "License đã bị khóa trên hệ thống ATG."
            )

            print(msg)
            write_license_log(msg)

            return False, msg

        # =========================
        # OFFLINE DAYS
        # =========================
        ok_offline, msg_offline = (
            self.check_offline_days()
        )

        print(msg_offline)
        write_license_log(msg_offline)

        if not ok_offline:
            return False, msg_offline
        
        if not self.verify_expire():
            return False, "License đã hết hạn. Vui lòng liên hệ quản trị viên 0904143113 để gia hạn license."

        # =========================
        # HARDWARE
        # =========================
        if not self.verify_hardware():
            return False, (
                "LICENSE HARDWARE INVALID"
            )

        return True, "LICENSE OK"
    



