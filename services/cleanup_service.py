import os
import shutil
from datetime import datetime, timedelta

from system_logger import log


def _log(msg: str):
    print(msg)
    log(msg)


def _is_date_name(name: str):
    try:
        return datetime.strptime(name, "%Y-%m-%d").date()
    except Exception:
        return None


def cleanup_index_and_video_sync(storage_path: str, keep_days: int, enabled: bool):
    """
    Keep the old function name for compatibility.

    The record app no longer manages webindex files. Cleanup is now limited to
    video folders named YYYY-MM-DD inside storage_path.
    """
    _log("=" * 70)
    _log("[CLEANUP START] Don video cu theo ngay")
    _log(
        f"[CLEANUP CONFIG] enabled={enabled} | "
        f"keep_days={keep_days} | storage={storage_path}"
    )

    if not enabled:
        _log("[CLEANUP SKIP] Chua bat xoa video cu")
        _log("=" * 70)
        return _empty_stats()

    try:
        keep_days = int(keep_days)
    except Exception:
        keep_days = 0

    if keep_days <= 0:
        _log("[CLEANUP SKIP] So ngay giu lai khong hop le")
        _log("=" * 70)
        return _empty_stats()

    storage_path = os.path.abspath(storage_path or "videos")
    if not os.path.isdir(storage_path):
        _log(f"[CLEANUP SKIP] Khong thay thu muc video: {storage_path}")
        _log("=" * 70)
        return _empty_stats()

    today = datetime.now().date()
    cutoff_date = today - timedelta(days=keep_days - 1)

    _log(f"[CLEANUP LIMIT] Giu tu ngay {cutoff_date} tro ve sau")
    _log(f"[CLEANUP LIMIT] Xoa thu muc video truoc ngay {cutoff_date}")

    deleted_folders = 0
    failed = 0
    freed_bytes = 0

    for name in sorted(os.listdir(storage_path)):
        full_path = os.path.join(storage_path, name)
        if not os.path.isdir(full_path) or os.path.islink(full_path):
            continue

        folder_date = _is_date_name(name)
        if not folder_date:
            continue

        if folder_date >= cutoff_date:
            continue

        try:
            size_before = _folder_size(full_path)
            shutil.rmtree(full_path)
            deleted_folders += 1
            freed_bytes += size_before
            _log(
                f"[CLEANUP FOLDER] Da xoa {name} | "
                f"{round(size_before / 1024 / 1024, 2)} MB"
            )
        except Exception as exc:
            failed += 1
            _log(f"[CLEANUP ERROR] Xoa thu muc loi: {full_path} | {exc}")

    stats = {
        "deleted_folders": deleted_folders,
        "failed": failed,
        "freed_bytes": freed_bytes,
    }

    _log("-" * 70)
    _log(
        f"[CLEANUP DONE] Folder xoa={deleted_folders} | "
        f"Loi={failed} | "
        f"Giai phong={round(freed_bytes / 1024 / 1024, 2)} MB"
    )
    _log("=" * 70)
    return stats


def _empty_stats():
    return {
        "deleted_folders": 0,
        "failed": 0,
        "freed_bytes": 0,
    }


def _folder_size(folder: str) -> int:
    total = 0
    for root, dirs, files in os.walk(folder):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                total += os.path.getsize(file_path)
            except Exception:
                pass
    return total
