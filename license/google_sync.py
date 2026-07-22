import csv
from datetime import datetime
from io import StringIO

import requests

from .cache_manager import CacheManager
from .crypto import verify_signed_token


GOOGLE_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/11tfGgzuoMm9z1D9_8fSF_cjPzUByE5VP6bj9hRJOkag/export?format=csv&gid=0"
)


def _row_value(row, *names):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def fetch_license_from_google(device_id):
    try:
        res = requests.get(GOOGLE_SHEET_CSV_URL, timeout=10)
        if res.status_code != 200:
            return None, "GOOGLE_SYNC_HTTP_ERROR"

        reader = csv.DictReader(StringIO(res.text))
        for row in reader:
            sheet_device_id = _row_value(row, "DEVICE_ID", "device_id")
            if sheet_device_id != device_id:
                continue

            token = _row_value(row, "SIGNED_TOKEN", "LICENSE_TOKEN", "TOKEN", "signed_token")
            if not token:
                return None, "LICENSE_TOKEN_MISSING"

            try:
                payload = verify_signed_token(token)
            except Exception as exc:
                return None, f"LICENSE_TOKEN_INVALID: {exc}"

            if payload.get("device_id") != device_id:
                return None, "LICENSE_TOKEN_DEVICE_MISMATCH"

            return {
                "signed_token": token,
                "payload": payload,
                "sheet_note": _row_value(row, "NOTE", "note"),
            }, "GOOGLE_SYNC_OK"

        return None, "DEVICE_ID_NOT_FOUND"
    except Exception as exc:
        return None, f"GOOGLE_SYNC_FAIL: {exc}"


def update_cache_from_google(device_id, hardware_hash):
    data, msg = fetch_license_from_google(device_id)
    if not data:
        return False, msg

    payload = data["payload"]
    if payload.get("hardware_hash") != hardware_hash:
        return False, "LICENSE_HARDWARE_INVALID_GOOGLE"

    CacheManager.save_token(
        data["signed_token"],
        last_sync=str(datetime.now()),
        metadata={
            "sheet_note": data.get("sheet_note", ""),
        },
    )
    return True, "ATG_LICENSE_UPDATED_FROM_GOOGLE"
