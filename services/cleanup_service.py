import os
import json
import shutil
from datetime import datetime, timedelta

from system_logger import log


VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov")


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
    Chỉ chạy 1 lần khi khởi động app.
    Xoá đồng bộ:
    - index/YYYY-MM-DD.json cũ
    - video trong index cũ
    - thư mục video YYYY-MM-DD cũ nếu còn sót
    """

    _log("=" * 70)
    _log("[CLEANUP START] Dọn dẹp video + index theo ngày")
    _log(f"[CLEANUP CONFIG] enabled={enabled} | keep_days={keep_days} | storage={storage_path}")

    if not enabled:
        _log("[CLEANUP SKIP] Chưa bật checkbox xoá dữ liệu cũ")
        _log("=" * 70)
        return

    if keep_days <= 0:
        _log("[CLEANUP SKIP] keep_days không hợp lệ")
        _log("=" * 70)
        return

    today = datetime.now().date()

    # Giữ đúng số ngày:
    # keep_days = 3 => giữ hôm nay + 2 ngày trước
    cutoff_date = today - timedelta(days=keep_days - 1)

    _log(f"[CLEANUP LIMIT] Giữ từ ngày {cutoff_date} trở về sau")
    _log(f"[CLEANUP LIMIT] Xoá trước ngày {cutoff_date}")

    index_dir = os.path.join(storage_path, "index")

    deleted_videos = 0
    deleted_indexes = 0
    deleted_folders = 0
    missing_videos = 0
    failed = 0
    freed_bytes = 0

    # ==================================================
    # 1. XOÁ THEO INDEX/YYYY-MM-DD.JSON
    # ==================================================
    if os.path.exists(index_dir):
        for file_name in sorted(os.listdir(index_dir)):
            if not file_name.endswith(".json"):
                continue

            date_str = file_name.replace(".json", "")
            index_date = _is_date_name(date_str)

            if not index_date:
                continue

            if index_date >= cutoff_date:
                continue

            index_path = os.path.join(index_dir, file_name)

            _log("-" * 70)
            _log(f"[CLEANUP INDEX] Xử lý index cũ: {file_name}")

            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                _log(f"[CLEANUP ERROR] Không đọc được index: {index_path} | {e}")
                failed += 1
                continue

            for v in data.get("videos", []):
                rel_path = (
                    v.get("file_path")
                    or v.get("video_path")
                    or v.get("path")
                    or v.get("filename")
                    or ""
                )

                if not rel_path:
                    continue

                video_path = rel_path.replace("\\", "/")

                if not os.path.isabs(video_path):
                    video_path = os.path.join(storage_path, video_path)

                video_path = os.path.normpath(video_path)

                if not video_path.lower().endswith(VIDEO_EXTS):
                    continue

                if not os.path.exists(video_path):
                    missing_videos += 1
                    _log(f"[CLEANUP MISSING] Không thấy video: {video_path}")
                    continue

                try:
                    size = os.path.getsize(video_path)
                    os.remove(video_path)

                    deleted_videos += 1
                    freed_bytes += size

                    _log(
                        f"[CLEANUP VIDEO] Đã xoá | "
                        f"{os.path.basename(video_path)} | "
                        f"{round(size / 1024 / 1024, 2)} MB"
                    )

                except Exception as e:
                    failed += 1
                    _log(f"[CLEANUP ERROR] Xoá video lỗi: {video_path} | {e}")

            try:
                os.remove(index_path)
                deleted_indexes += 1
                _log(f"[CLEANUP INDEX] Đã xoá index: {index_path}")
            except Exception as e:
                failed += 1
                _log(f"[CLEANUP ERROR] Xoá index lỗi: {index_path} | {e}")

    # ==================================================
    # 2. XOÁ THƯ MỤC NGÀY CŨ NẾU CÒN SÓT
    # ==================================================
    for name in sorted(os.listdir(storage_path)):
        full_path = os.path.join(storage_path, name)

        if not os.path.isdir(full_path):
            continue

        if name == "index":
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
                f"[CLEANUP FOLDER] Đã xoá thư mục ngày cũ | "
                f"{name} | {round(size_before / 1024 / 1024, 2)} MB"
            )

        except Exception as e:
            failed += 1
            _log(f"[CLEANUP ERROR] Xoá thư mục lỗi: {full_path} | {e}")

    _remove_empty_dirs(storage_path)

    _log("-" * 70)
    _log(
        f"[CLEANUP DONE] "
        f"Video xoá={deleted_videos} | "
        f"Index xoá={deleted_indexes} | "
        f"Folder xoá={deleted_folders} | "
        f"Video thiếu={missing_videos} | "
        f"Lỗi={failed} | "
        f"Giải phóng={round(freed_bytes / 1024 / 1024, 2)} MB"
    )
    _log("=" * 70)


def _folder_size(folder: str) -> int:
    total = 0

    for root, dirs, files in os.walk(folder):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except Exception:
                pass

    return total


def _remove_empty_dirs(storage_path: str):
    for root, dirs, files in os.walk(storage_path, topdown=False):
        if root == storage_path:
            continue

        try:
            if not os.listdir(root):
                os.rmdir(root)
                _log(f"[CLEANUP EMPTY] Đã xoá thư mục rỗng: {root}")
        except Exception:
            pass