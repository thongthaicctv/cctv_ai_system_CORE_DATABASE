import sys
import os
import ctypes
import tempfile
import msvcrt

from license.license_dialog import LicenseDialog, LicenseNoticeDialog

from core.config_manager import load_config
from core.resource_paths import resource_path
# =========================
# EXE RUNTIME PATH
# =========================
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# =========================
# OPENCV RTSP TCP
# =========================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QIcon

from core.gpu_acceleration import configure_opencv_acceleration, prepare_gpu_runtime
from license.license_manager import LicenseManager
from services.cleanup_service import cleanup_index_and_video_sync
from system_logger import log

# =========================
# SINGLE INSTANCE LOCK
# =========================

_lock_file = None
_native_icon_handles = []


def apply_native_taskbar_icon(window):
    """Force Windows to use the bundled icon for the title bar and taskbar."""
    if sys.platform != "win32":
        return

    icon_file = resource_path("icon_taskbar.ico")
    if not os.path.isfile(icon_file):
        return

    user32 = ctypes.windll.user32
    image_icon = 1
    lr_loadfromfile = 0x0010
    wm_seticon = 0x0080
    icon_small = 0
    icon_big = 1

    hwnd = int(window.winId())
    small_icon = user32.LoadImageW(
        None, icon_file, image_icon, 16, 16, lr_loadfromfile
    )
    big_icon = user32.LoadImageW(
        None, icon_file, image_icon, 32, 32, lr_loadfromfile
    )

    if small_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_small, small_icon)
        _native_icon_handles.append(small_icon)
    if big_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_big, big_icon)
        _native_icon_handles.append(big_icon)

def ensure_single_instance():
    global _lock_file

    lock_path = os.path.join(
        tempfile.gettempdir(),
        "ATG_AI_SYSTEM_RECORD.lock"
    )

    _lock_file = open(lock_path, "w")

    try:
        msvcrt.locking(
            _lock_file.fileno(),
            msvcrt.LK_NBLCK,
            1
        )
        return True

    except OSError:
        return False


def main():

    # =========================
    # SINGLE INSTANCE CHECK
    # =========================
    if not ensure_single_instance():
        print("ATG AI SYSTEM đang chạy.")
        return

    prepare_gpu_runtime()

    from ui.main_window import MainWindow

    accel_info = configure_opencv_acceleration()
    print(accel_info["message"])

    app = QApplication(sys.argv)
    app.gpu_runtime_info = accel_info
    app_icon = QIcon(resource_path("icon_taskbar.ico"))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    cfg = load_config(force=True)
    storage_path = cfg.get("storage_path", "recordings")

    print("STORAGE =", storage_path)
    print("WEB INDEX URL =", cfg.get("web_index_url", "http://127.0.0.1:8088/"))

    try:
        cleanup_index_and_video_sync(
            storage_path,
            cfg.get("keep_index_days", 240),
            bool(cfg.get("cleanup_enabled", False)),
        )
    except Exception as exc:
        log(f"[CLEANUP ERROR] Khong the don video cu: {exc}")
   

    # =========================
    # LICENSE CHECK
    # =========================

    license_manager = LicenseManager()

    while True:
        ok, msg = license_manager.check()
        print(msg)

        if ok:
            break

        dlg = LicenseDialog(
            license_manager.device_id,
            msg
        )

        if dlg.exec() != QDialog.Accepted:
            sys.exit()
    # ========================= 
    # GLOBAL LICENSE MANAGER 
    # ========================= 
    app.license_manager = license_manager

    if license_manager.startup_notice:
        LicenseNoticeDialog(license_manager.startup_notice).exec()

    # =========================
    # MAIN WINDOW
    # =========================

    window = MainWindow()

    QTimer.singleShot(
        1000,
        lambda: log(f"[GPU] {accel_info['message']}")
    )
    
    app.record_engine = window.record

    window.show()
    apply_native_taskbar_icon(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
