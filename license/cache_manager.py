import json
from datetime import datetime

from .crypto import verify_signed_token
from .paths import CACHE_FILE


class CacheManager:
    CACHE_VERSION = 2

    @staticmethod
    def save_token(token: str, last_sync=None, last_run_time=None):
        payload = verify_signed_token(token)
        now = str(datetime.now())
        envelope = {
            "version": CacheManager.CACHE_VERSION,
            "signed_token": token.strip(),
            "last_sync": str(last_sync or now),
            "last_run_time": str(last_run_time or now),
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=2)
        data = dict(payload)
        data["_signed_token"] = token.strip()
        data["last_sync"] = envelope["last_sync"]
        data["last_run_time"] = envelope["last_run_time"]
        return data

    @staticmethod
    def install_token(token: str, expected_device_id=None, expected_hardware_hash=None):
        payload = verify_signed_token(token)
        if expected_device_id and payload.get("device_id") != expected_device_id:
            raise ValueError("License token không đúng Device ID của máy này")
        if expected_hardware_hash and payload.get("hardware_hash") != expected_hardware_hash:
            raise ValueError("License token không đúng phần cứng của máy này")
        return CacheManager.save_token(token)

    @staticmethod
    def save(data):
        token = (data or {}).get("_signed_token") or (data or {}).get("signed_token")
        if not token:
            raise RuntimeError("Cannot save unsigned license data")
        return CacheManager.save_token(
            token,
            last_sync=(data or {}).get("last_sync"),
            last_run_time=(data or {}).get("last_run_time"),
        )

    @staticmethod
    def load():
        if not CACHE_FILE.exists():
            return None

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()

            try:
                envelope = json.loads(raw)
            except Exception:
                envelope = {"signed_token": raw}

            token = envelope.get("signed_token") or envelope.get("token")
            if not token:
                return None

            payload = verify_signed_token(token)
            data = dict(payload)
            data["_signed_token"] = token
            data["last_sync"] = envelope.get("last_sync") or data.get("issued_at")
            data["last_run_time"] = envelope.get("last_run_time") or data.get("last_sync")
            return data
        except Exception:
            return None

    @staticmethod
    def update_runtime(**fields):
        data = CacheManager.load()
        if not data:
            return False

        data.update(fields)
        CacheManager.save(data)
        return True

    @staticmethod
    def create_default(device_id, hardware_hash):
        return None

    @staticmethod
    def delete():
        try:
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()
            return True
        except Exception as e:
            print("CACHE DELETE FAIL:", e)
            return False
