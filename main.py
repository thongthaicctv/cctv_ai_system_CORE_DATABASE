import sys
import os
import ctypes
import tempfile
import msvcrt

from license.license_dialog import LicenseDialog

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
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from core.gpu_acceleration import configure_opencv_acceleration, prepare_gpu_runtime
from license.license_manager import LicenseManager
from system_logger import log

# =========================
# SINGLE INSTANCE LOCK
# =========================

_lock_file = None

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

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ATGSolution.ProVideoAISystem.1.0"
        )
    except Exception:
        pass

    from ui.main_window import MainWindow

    accel_info = configure_opencv_acceleration()
    print(accel_info["message"])

    app = QApplication(sys.argv)
    app.gpu_runtime_info = accel_info
    app_icon = QIcon(resource_path("icon.ico"))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    cfg = load_config(force=True)
    storage_path = cfg.get("storage_path", "recordings")

    print("STORAGE =", storage_path)
    print("WEB INDEX URL =", cfg.get("web_index_url", "http://127.0.0.1:8088/"))


   

    # =========================
    # LICENSE CHECK
    # =========================

    license_manager = LicenseManager()

    ok, msg = license_manager.check()

    print(msg)

    if not ok:

        dlg = LicenseDialog(
            license_manager.device_id,
            msg
        )

        dlg.exec()

        sys.exit()
    # ========================= 
    # GLOBAL LICENSE MANAGER 
    # ========================= 
    app.license_manager = license_manager


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

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
