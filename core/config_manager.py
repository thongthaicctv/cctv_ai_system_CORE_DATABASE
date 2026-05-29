import copy
import json
import os

from utils.url_helper import camera_rtsp_url, camera_source_key

CONFIG_FILE = "config.json"
_CONFIG_CACHE = None
_CONFIG_MTIME = None


def _default_config():
    return {
        

        "storage_path": "videos",

        "record_auto_stop_seconds": 600,

        "record_mapping": {},

        "cleanup_enabled": False,
        "keep_index_days": 240,

        "cameras": [],

        "db": {
            "type": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "atg_order_system",
            "user": "atg_app",
            "password": "atg_password",
            "charset": "utf8mb4",
            "connect_timeout": 2,
            "read_timeout": 3,
            "write_timeout": 3,
        },
        
        
        "http_enabled": False,
        "http_port": 18080,
        "ddns_domain": "",
        "http_user": "admin",
        "http_pass": "123456",


    }

def _normalize_config(data):
    merged = _default_config()
    merged.update(data or {})

    cameras = merged.get("cameras", [])
    camera_ids = [str(cam.get("id", "")).strip() for cam in cameras if cam.get("id")]
    valid_ids = set(camera_ids)

    raw_mapping = merged.get("record_mapping", {}) or {}
    normalized = {}

    for cam_id in camera_ids:
        if cam_id in raw_mapping:
            targets = [
                str(target)
                for target in raw_mapping.get(cam_id, [])
                if str(target) in valid_ids
            ]
            normalized[cam_id] = targets
        else:
            normalized[cam_id] = [cam_id]

    merged["record_mapping"] = normalized
    return merged


def load_config(force=False):
    global _CONFIG_CACHE, _CONFIG_MTIME

    if not os.path.exists(CONFIG_FILE):
        default_data = _default_config()
        _CONFIG_CACHE = default_data
        _CONFIG_MTIME = None
        return copy.deepcopy(default_data)

    try:
        current_mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        return copy.deepcopy(_default_config())

    if force or _CONFIG_CACHE is None or _CONFIG_MTIME != current_mtime:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _CONFIG_CACHE = _normalize_config(json.load(f))
        _CONFIG_MTIME = current_mtime

    return copy.deepcopy(_CONFIG_CACHE)


def save_config(data):
    global _CONFIG_CACHE, _CONFIG_MTIME

    normalized = _normalize_config(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=4, ensure_ascii=False)

    _CONFIG_CACHE = normalized
    try:
        _CONFIG_MTIME = os.path.getmtime(CONFIG_FILE)
    except OSError:
        _CONFIG_MTIME = None


def find_duplicate_camera_sources(data):
    cameras = list((data or {}).get("cameras", []))
    groups = {}

    for cam in cameras:
        cam_id = str(cam.get("id", "")).strip()
        if not cam_id or not cam.get("enabled", True):
            continue

        main_url, sub_url = camera_source_key(cam)
        key = (main_url, sub_url)

        if not main_url and not sub_url:
            continue

        groups.setdefault(key, []).append(
            {
                "id": cam_id,
                "name": str(cam.get("name", cam_id)).strip() or cam_id,
                "main_url": main_url,
                "sub_url": sub_url,
            }
        )

    return [items for items in groups.values() if len(items) > 1]
