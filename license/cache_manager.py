import json
from datetime import datetime

from .paths import CACHE_FILE
from .crypto import encrypt_data, decrypt_data


class CacheManager:

    @staticmethod
    def save(data):
        encoded = encrypt_data(data)

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(encoded)

    @staticmethod
    def load():
        if not CACHE_FILE.exists():
            return None

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                encoded = f.read()

            return decrypt_data(encoded)

        except:
            return None

    @staticmethod
    def create_default(device_id, hardware_hash):

        data = {
            "device_id": device_id,
            "hardware_hash": hardware_hash,
            "max_camera": 4,
            "expire_date": "2026-12-31",
            "last_sync": str(datetime.now()),
            "last_run_time": str(datetime.now()),
            "offline_days": 30,
            "status": "active"
        }

        CacheManager.save(data)

        return data
    
    @staticmethod
    def delete():

        try:
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()

            return True

        except Exception as e:
            print("CACHE DELETE FAIL:", e)
            return False