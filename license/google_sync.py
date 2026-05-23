import csv
import requests

from io import StringIO
from datetime import datetime

from .cache_manager import CacheManager


# =========================
# GOOGLE SHEET CSV URL
# =========================
GOOGLE_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/1PgrEJ4yJPE-hXBCa_snroalCTE-ySJEhxbiQ1CHe6c8/export?format=csv&gid=0"
)


# =========================
# FETCH LICENSE
# =========================
def fetch_license_from_google(device_id):

    try:

        res = requests.get(
            GOOGLE_SHEET_CSV_URL,
            timeout=10
        )

        if res.status_code != 200:
            return None, "GOOGLE_SYNC_HTTP_ERROR"

        csv_text = res.text

        reader = csv.DictReader(
            StringIO(csv_text)
        )

        for row in reader:

            sheet_device_id = (
                row.get("DEVICE_ID", "")
                .strip()
            )

            if sheet_device_id == device_id:

                return {
                    "device_id": sheet_device_id,

                    "max_camera": int(
                        row.get(
                            "MAX_CAMERA",
                            0
                        )
                    ),

                    "expire_date": (
                        row.get(
                            "EXPIRE_DATE",
                            ""
                        )
                        .strip()
                    ),

                    "status": (
                        row.get(
                            "STATUS",
                            "active"
                        )
                        .strip()
                        .lower()
                    ),

                    "last_sync": str(
                        datetime.now()
                    ),

                    "offline_days": 30,

                }, "GOOGLE_SYNC_OK"

        return None, "DEVICE_ID_NOT_FOUND"
    
    

    except Exception as e:

        return (
            None,
            f"GOOGLE_SYNC_FAIL: {e}"
        )


# =========================
# UPDATE CACHE
# =========================
def update_cache_from_google(
    device_id,
    hardware_hash
):

    data, msg = fetch_license_from_google(
        device_id
    )

    if not data:
        return False, msg

    # =========================
    # ONLINE FOUND DEVICE
    # DELETE OLD CACHE
    # =========================
    CacheManager.delete()

    data["hardware_hash"] = hardware_hash

    data["last_run_time"] = str(
        datetime.now()
    )

    # =========================
    # CREATE NEW CACHE
    # =========================
    CacheManager.save(data)

    if data.get("status") != "active":
        return False, "LICENSE_DISABLED_BY_GOOGLE"

    return True, "ATG_LICENSE_UPDATED_FROM_GOOGLE"