import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.resource_paths import resource_path
from license.cache_manager import CacheManager
from license.google_sync import fetch_license_from_google
from license.hardware import (
    get_baseboard_id,
    get_bios_id,
    get_cpu_id,
    get_device_id,
    get_hardware_hash,
    get_hardware_string,
)
from license.paths import CACHE_FILE, LICENSE_DIR


def collect_device_info(check_google=False):
    device_id = get_device_id()
    hardware_hash = get_hardware_hash()
    cache_data = CacheManager.load()

    info = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device_id": device_id,
        "hardware_hash": hardware_hash,
        "hardware_string": get_hardware_string(),
        "cpu_id": get_cpu_id(),
        "bios_serial": get_bios_id(),
        "baseboard_serial": get_baseboard_id(),
        "license_dir": str(LICENSE_DIR),
        "cache_file": str(CACHE_FILE),
        "cache_exists": CACHE_FILE.exists(),
        "cache_valid": bool(cache_data),
        "cache": {},
        "google": {},
    }

    if cache_data:
        cache_hardware = str(cache_data.get("hardware_hash", ""))
        cache_device = str(cache_data.get("device_id", ""))
        info["cache"] = {
            "license_id": cache_data.get("license_id", ""),
            "customer": cache_data.get("customer", ""),
            "device_id": cache_device,
            "device_matches": cache_device == device_id,
            "hardware_hash": cache_hardware,
            "hardware_matches": cache_hardware == hardware_hash,
            "max_camera": cache_data.get("max_camera", ""),
            "expire_date": cache_data.get("expire_date", ""),
            "offline_days": cache_data.get("offline_days", ""),
            "status": cache_data.get("status", ""),
            "features": cache_data.get("features", ""),
            "last_sync": cache_data.get("last_sync", ""),
            "last_run_time": cache_data.get("last_run_time", ""),
            "sheet_note": cache_data.get("_sheet_note", ""),
        }

    if check_google:
        google_data, msg = fetch_license_from_google(device_id)
        google_info = {"message": msg, "found": bool(google_data)}
        if google_data:
            payload = google_data.get("payload", {})
            google_info.update(
                {
                    "device_id": payload.get("device_id", ""),
                    "device_matches": payload.get("device_id", "") == device_id,
                    "hardware_hash": payload.get("hardware_hash", ""),
                    "hardware_matches": payload.get("hardware_hash", "") == hardware_hash,
                    "max_camera": payload.get("max_camera", ""),
                    "expire_date": payload.get("expire_date", ""),
                    "status": payload.get("status", ""),
                    "customer": payload.get("customer", ""),
                    "sheet_note": google_data.get("sheet_note", ""),
                }
            )
        info["google"] = google_info

    return info


class DeviceIdCheckWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATG Device ID Check Tool")
        self.resize(820, 620)
        self.setMinimumSize(720, 520)
        icon = QIcon(resource_path("icon.ico"))
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.google_checked = False
        self._build()
        self.refresh()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(16, 14, 16, 14)
        main.setSpacing(10)

        title = QLabel("ATG Device ID / Hardware Hash Check")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#ffffff;")
        main.addWidget(title)

        note = QLabel(
            "Tool doc thong tin may truc tiep. Khong can khoi dong phan mem record."
        )
        note.setStyleSheet("color:#facc15;font-size:12px;")
        main.addWidget(note)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        main.addLayout(grid)

        self.device_id = QLabel()
        self.hardware_hash = QLabel()
        self.cache_status = QLabel()
        self.google_status = QLabel()

        for value in (
            self.device_id,
            self.hardware_hash,
            self.cache_status,
            self.google_status,
        ):
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setStyleSheet(
                "background:#111;color:#00ffaa;border:1px solid #333;"
                "border-radius:6px;padding:8px;font-weight:700;"
            )

        grid.addWidget(QLabel("DEVICE_ID"), 0, 0)
        grid.addWidget(self.device_id, 0, 1)
        grid.addWidget(QLabel("HARDWARE_HASH"), 1, 0)
        grid.addWidget(self.hardware_hash, 1, 1)
        grid.addWidget(QLabel("CACHE"), 2, 0)
        grid.addWidget(self.cache_status, 2, 1)
        grid.addWidget(QLabel("GOOGLE"), 3, 0)
        grid.addWidget(self.google_status, 3, 1)

        self.detail_box = QPlainTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setStyleSheet(
            "QPlainTextEdit{background:#151515;color:#e5e7eb;"
            "border:1px solid #333;border-radius:6px;padding:8px;"
            "font-family:Consolas;font-size:11px;}"
        )
        main.addWidget(self.detail_box, 1)

        buttons = QHBoxLayout()
        main.addLayout(buttons)

        btn_refresh = QPushButton("Lam moi")
        btn_google = QPushButton("Kiem tra Google")
        btn_copy_machine = QPushButton("Copy thong tin may")
        btn_copy_all = QPushButton("Copy tat ca")
        btn_delete_cache = QPushButton("Xoa cache license")

        btn_refresh.clicked.connect(self.refresh)
        btn_google.clicked.connect(self.check_google)
        btn_copy_machine.clicked.connect(self.copy_machine)
        btn_copy_all.clicked.connect(self.copy_all)
        btn_delete_cache.clicked.connect(self.delete_cache)

        for btn in (
            btn_refresh,
            btn_google,
            btn_copy_machine,
            btn_copy_all,
            btn_delete_cache,
        ):
            buttons.addWidget(btn)

        self.setStyleSheet(
            """
            QMainWindow{background:#0f0f0f;}
            QLabel{color:#ffffff;font-size:13px;}
            QPushButton{
                background:#0f62fe;color:white;border:none;border-radius:8px;
                padding:10px;font-size:13px;font-weight:bold;
            }
            QPushButton:hover{background:#0353e9;}
            """
        )

    def refresh(self):
        self.google_checked = False
        self._set_info(collect_device_info(check_google=False))

    def check_google(self):
        self.google_checked = True
        self._set_info(collect_device_info(check_google=True))

    def _set_info(self, info):
        self.info = info
        self.device_id.setText(info.get("device_id", ""))
        self.hardware_hash.setText(info.get("hardware_hash", ""))

        cache = info.get("cache") or {}
        if not info.get("cache_exists"):
            cache_text = "Khong co cache"
        elif not info.get("cache_valid"):
            cache_text = "Co cache nhung token khong hop le"
        else:
            cache_text = (
                f"{cache.get('status', '')} | "
                f"device_match={cache.get('device_matches')} | "
                f"hardware_match={cache.get('hardware_matches')} | "
                f"exp={cache.get('expire_date', '')} | "
                f"{cache.get('max_camera', '')} cam"
            )
        self.cache_status.setText(cache_text)

        google = info.get("google") or {}
        if not self.google_checked:
            google_text = "Chua kiem tra"
        elif not google.get("found"):
            google_text = google.get("message", "Khong tim thay")
        else:
            google_text = (
                f"{google.get('message', '')} | "
                f"hardware_match={google.get('hardware_matches')} | "
                f"status={google.get('status', '')} | "
                f"exp={google.get('expire_date', '')}"
            )
        self.google_status.setText(google_text)

        self.detail_box.setPlainText(
            json.dumps(info, ensure_ascii=False, indent=2)
        )

    def copy_machine(self):
        text = (
            f"DEVICE_ID={self.info.get('device_id', '')}\n"
            f"HARDWARE_HASH={self.info.get('hardware_hash', '')}\n"
            f"HARDWARE_STRING={self.info.get('hardware_string', '')}"
        )
        QApplication.clipboard().setText(text)

    def copy_all(self):
        QApplication.clipboard().setText(self.detail_box.toPlainText())

    def delete_cache(self):
        if not CACHE_FILE.exists():
            QMessageBox.information(self, "Cache", "Khong co cache license de xoa.")
            self.refresh()
            return

        confirm = QMessageBox.question(
            self,
            "Xoa cache license",
            (
                "Xoa cache license tren may nay?\n\n"
                "Sau khi xoa, phan mem record se phai load lai license online."
            ),
        )
        if confirm != QMessageBox.Yes:
            return

        if CacheManager.delete():
            QMessageBox.information(self, "Cache", "Da xoa cache license.")
        else:
            QMessageBox.warning(self, "Cache", "Khong xoa duoc cache license.")
        self.refresh()


def main():
    if "--print" in sys.argv:
        print(json.dumps(collect_device_info("--google" in sys.argv), ensure_ascii=False, indent=2))
        return

    app = QApplication(sys.argv)
    window = DeviceIdCheckWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
