import copy
import json
import os

from utils.url_helper import camera_rtsp_url, camera_source_key

CONFIG_FILE = "config.json"
_CONFIG_CACHE = None
_CONFIG_MTIME = None
DEFAULT_QR_CONFIG = {
    "scan_interval": 0.02,
    "full_scan_every_frames": 3,
    "slow_scan_every_frames": 15,
    "max_width": 960,
    "heavy_scan_max_width": 1280,
    "drop_stale_frames": 1,
}
LEGACY_TURBO_QR_CONFIG = {
    "scan_interval": 0.003,
    "full_scan_every_frames": 1,
    "slow_scan_every_frames": 4,
    "max_width": 1600,
}
LEGACY_FAST_QR_CONFIG = {
    "scan_interval": 0.01,
    "full_scan_every_frames": 2,
    "slow_scan_every_frames": 8,
    "max_width": 1280,
}
LEGACY_SLOW_QR_CONFIG = {
    "scan_interval": 0.18,
    "full_scan_every_frames": 10,
    "slow_scan_every_frames": 15,
    "max_width": 960,
}


def _same_numeric_value(left, right):
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return str(left).strip() == str(right).strip()


def _matches_qr_config(qr_config, expected):
    return all(
        _same_numeric_value(qr_config.get(key), expected_value)
        for key, expected_value in expected.items()
    )


def _normalize_qr_config(raw_qr_config):
    qr_config = dict(DEFAULT_QR_CONFIG)
    if isinstance(raw_qr_config, dict):
        qr_config.update(
            {
                key: raw_qr_config[key]
                for key in DEFAULT_QR_CONFIG
                if key in raw_qr_config
            }
        )

    if _matches_qr_config(qr_config, LEGACY_TURBO_QR_CONFIG):
        return dict(DEFAULT_QR_CONFIG)

    if _matches_qr_config(qr_config, LEGACY_FAST_QR_CONFIG):
        return dict(DEFAULT_QR_CONFIG)

    if _matches_qr_config(qr_config, LEGACY_SLOW_QR_CONFIG):
        return dict(DEFAULT_QR_CONFIG)

    return qr_config


def _default_config():
    return {
        

        "storage_path": "videos",

        "record_auto_stop_seconds": 600,

        "record_mapping": {},

        "qr": dict(DEFAULT_QR_CONFIG),

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
        
        
        "web_index_url": "http://127.0.0.1:8088/",


    }

def _normalize_config(data):
    merged = _default_config()
    merged.update(data or {})
    merged["qr"] = _normalize_qr_config(merged.get("qr"))

    web_index_url = str(merged.get("web_index_url") or "").strip()
    if not web_index_url:
        web_index_url = "http://127.0.0.1:8088/"
    merged["web_index_url"] = web_index_url
    for legacy_key in ("http_enabled", "http_port", "ddns_domain", "http_user", "http_pass"):
        merged.pop(legacy_key, None)

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
