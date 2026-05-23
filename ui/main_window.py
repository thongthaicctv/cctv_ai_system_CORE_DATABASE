# FILE: ui/main_window.py
# RESTORE UI PRO VERSION
# giữ module mới + giao diện cũ

import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import webbrowser

from PySide6.QtGui import QIcon, QPixmap

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QFrame, QStackedWidget
)

from core.config_manager import find_duplicate_camera_sources, load_config, save_config
from core.logger import write_log
from core.ping_service import ping_host
from core.resource_paths import resource_path

from ui.camera_config import CameraConfigPage
from ui.pages.camera_grid_page import CameraGridPage
from core.runtime_state import RuntimeState
from services.qr_engine import QREngine
from services.record_engine import RecordEngine

from ui.pages.dashboard_page import DashboardPage

from ui.pages.storage_page import StoragePage

from services.runtime_cleanup import RuntimeCleanup

from system_logger import log

from ui.pages.log_page import LogPage

from hr.hr_page import HRPage, VideoPage


class NetworkCheckWorker(QThread):
    results_ready = Signal(list)

    def __init__(self, cameras):
        super().__init__()
        self.cameras = list(cameras)

    def run(self):
        def worker(cam):
            online, latency = ping_host(cam["ip"])
            return cam["id"], cam["name"], online, latency

        results = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            for item in ex.map(worker, self.cameras):
                results.append(item)

        self.results_ready.emit(results)




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Pro Video AI System  - ATG Solution Version 3.2 visitor: www.annguyen.pro - https://camerathainguyen.com - ĐT: 0208 656 5555")
        self.resize(1366, 768)
        self.setMinimumSize(1280, 700)
        app_icon = QIcon(resource_path("icon.ico"))
        self.setWindowIcon(app_icon)

        self.setStyleSheet("""
            QMainWindow{
                background:#111111;
            }

            QLabel{
                color:#eeeeee;
            }

            QPushButton{
                background:#1b1b1b;
                color:#dddddd;
                border:none;
                padding:12px;
                border-radius:8px;
                text-align:left;
                font-size:14px;
            }

            QPushButton:hover{
                background:#2b2b2b;
            }

            QPushButton:checked{
                background:#0f62fe;
                color:white;
            }

            QCheckBox{
                color:white;
                padding:8px;
                font-size:13px;
            }
        """)

        root = QWidget()
        self.setCentralWidget(root)

        

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==================================================
        # LOAD CONFIG
        # ==================================================
        data = load_config()
        self._log_duplicate_camera_sources(data)


        # ==================================================
        # SIDEBAR
        # ==================================================
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame{
                background:#161616;
                border-right:1px solid #222;
            }
        """)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(8)

        logo = QLabel("Pro Video AI System  - ATG Solution Version 3.2 visitor: www.annguyen.pro - https://camerathainguyen.com - ĐT: 0208 656 5555")
        logo.setFont(QFont("Segoe UI", 15, QFont.Bold))

        side.addWidget(logo)
        side.addSpacing(10)

        self.btn_camera = QPushButton("🎥 Trạng thái Camera ghi hình")
        self.btn_dashboard = QPushButton("🏠 Tổng quan")
        self.btn_config = QPushButton("⚙️ Cấu hình Camera")
        self.btn_search = QPushButton("🔍 Quản lý nhân sự")
        self.btn_storage = QPushButton("💾 Cài đặt ghi và lưu video")
        self.btn_video = QPushButton("🎬 Tra cứu video")
        self.btn_log = QPushButton("📜 Nhật ký")

        self.buttons = [
            self.btn_camera,
            self.btn_dashboard,
            self.btn_config,
            self.btn_search,
            self.btn_storage,
            self.btn_video,
            self.btn_log
        ]

        for b in self.buttons:
            b.setCheckable(True)
            b.setMinimumHeight(46)
            side.addWidget(b)

        self.btn_youtube = QPushButton("▶️ Hướng dẫn sử dụng")
        self.btn_youtube.setMinimumHeight(46)
        self.btn_youtube.clicked.connect(self.open_youtube_playlist)

        side.addSpacing(8)
        side.addWidget(self.btn_youtube)

        side.addStretch()

        # =========================
        # CONTACT / LOGO INFO
        # =========================
        contact_box = QFrame()
        contact_box.setFixedHeight(240)
        contact_box.setStyleSheet("""
        QFrame{
            background:#101010;
            border:1px solid #2a2a2a;
            border-radius:10px;
        }
        QLabel{
            color:#dddddd;
            border:none;
        }
        """)

        contact_layout = QVBoxLayout(contact_box)
        contact_layout.setContentsMargins(10, 10, 10, 10)
        contact_layout.setSpacing(3)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)

        pix = QPixmap(resource_path("logo_app.png"))

        logo.setPixmap(
            pix.scaled(
                200,
                200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        company = QLabel("www.annguyen.pro ")
        company.setAlignment(Qt.AlignCenter)
        company.setStyleSheet("""
        font-size:12px;
        font-weight:bold;
        color:#ffffff;
        background:transparent;
        """)

        phone = QLabel("☎ 090 414 3113")
        phone.setAlignment(Qt.AlignCenter)
        phone.setStyleSheet("font-size:18px;color:#22c55e;background:transparent;")

        zalo = QLabel("Zalo: 090 414 3113")
        zalo.setAlignment(Qt.AlignCenter)
        zalo.setStyleSheet("font-size:18px;color:#93c5fd;background:transparent;")

        contact_layout.addWidget(logo)
        contact_layout.addWidget(company)
        contact_layout.addWidget(phone)
        contact_layout.addWidget(zalo)

        side.addWidget(contact_box)

        # ==================================================
        # PAGES
        # ==================================================
        self.stack = QStackedWidget()

        self.state = RuntimeState()

        self.page_camera = CameraGridPage(self.state)
        self.page_camera.sync_cameras(data["cameras"])

        self.page_config = CameraConfigPage()

        # Dashboard chưa load ngay
        self.page_dashboard = None

        self.stack.addWidget(self.page_camera)                 # 0
        self.stack.addWidget(QWidget())                       # 1 placeholder
        self.stack.addWidget(self.page_config)                # 2


        self.page_hr = HRPage()
        self.stack.addWidget(self.page_hr)                       # 3

        self.page_storage = StoragePage()
        self.page_storage.settings_saved.connect(self.apply_storage_settings)
        self.stack.addWidget(self.page_storage)                  # 4

        self.page_video = VideoPage()
        self.stack.addWidget(self.page_video)                    # 5

        self.page_log = LogPage()
        self.stack.addWidget(self.page_log)                      # 6

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        # ==================================================
        # BUTTON EVENT
        # ==================================================
        self.btn_camera.clicked.connect(lambda: self.switch_page(0))
        self.btn_dashboard.clicked.connect(self.open_dashboard)
        self.btn_config.clicked.connect(lambda: self.switch_page(2))
        self.btn_search.clicked.connect(lambda: self.switch_page(3))
        self.btn_storage.clicked.connect(lambda: self.switch_page(4))
        self.btn_video.clicked.connect(lambda: self.switch_page(5))
        self.btn_log.clicked.connect(lambda: self.switch_page(6))

        self.btn_camera.setChecked(True)
        self.stack.setCurrentIndex(0)

        # ==================================================
        # CAMERA STATUS
        # ==================================================
        #self.state = RuntimeState()

        self.qr = QREngine(self.state)
        self.qr.start_all(
            data["cameras"],
            data.get("record_mapping", {}),
        )

        self.record = RecordEngine(
            self.state,
            data.get("storage_path", "records"),
            data.get("record_auto_stop_seconds", 300),
        )
        self.record.start_all(data["cameras"])

        for cam in data["cameras"]:
            self.state.add_camera(cam["id"])

        self.network_worker = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_check)
        self.timer.start(8000)
        QTimer.singleShot(0, self.auto_check)

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.refresh_camera_cards)
        self.ui_timer.start(1000)

        #Xoá bộ nhớ đệm cache
        self.runtime_cleaner = RuntimeCleanup(interval=180, full_collect_every=10)
        self.runtime_cleaner.start()

        
    # ==================================================
    # SWITCH PAGE
    # ==================================================
    def switch_page(self, index):
        for b in self.buttons:
            b.setChecked(False)

        sender = self.sender()
        if sender:
            sender.setChecked(True)

        self.stack.setCurrentIndex(index)

        if index == 0:
            self.refresh_camera_cards()

    def refresh_camera_cards(self):
        if self.stack.currentIndex() == 0:
            self.page_camera.refresh_from_config(self.state.all())

    # ==================================================
    # AUTO CHECK CAMERA
    # ==================================================
    def auto_check(self):
        if self.network_worker and self.network_worker.isRunning():
            return

        cams = load_config()["cameras"]

        self.network_worker = NetworkCheckWorker(cams)
        self.network_worker.results_ready.connect(self.apply_network_results)
        self.network_worker.finished.connect(self.network_check_finished)
        self.network_worker.start()

    def apply_network_results(self, results):
        for cam_id, name, online, latency in results:
            old = self.state.get(cam_id)["online"]

            self.state.update_network(
                cam_id,
                online,
                latency
            )

            if old != online:
                log(f"{name} {'ONLINE' if online else 'OFFLINE'}")

        self.refresh_camera_cards()

    def network_check_finished(self):
        self.network_worker = None

    def show_alert(self, title, message):
        log(f"[{title}] {message}")



    def apply_storage_settings(self, data):
        self._log_duplicate_camera_sources(data)
        self.qr.start_all(
            data.get("cameras", []),
            data.get("record_mapping", {}),
        )
        self.record.update_settings(
            data.get("storage_path", "records"),
            data.get("record_auto_stop_seconds", 300),
        )

    def _log_duplicate_camera_sources(self, data):
        duplicate_groups = find_duplicate_camera_sources(data)
        for group in duplicate_groups:
            camera_labels = ", ".join(
                f"{item['name']}({item['id']})"
                for item in group
            )
            log(f"DUPLICATE RTSP SOURCE: {camera_labels}")

    def open_dashboard(self):
        # bỏ check hết nút cũ
        for b in self.buttons:
            b.setChecked(False)

        self.btn_dashboard.setChecked(True)

        # chỉ tạo lần đầu
        if self.page_dashboard is None:
            self.page_dashboard = DashboardPage()

            # thay placeholder index 1
            old = self.stack.widget(1)
            self.stack.removeWidget(old)
            old.deleteLater()

            self.stack.insertWidget(1, self.page_dashboard)

        self.stack.setCurrentIndex(1)

    def open_youtube_playlist(self):
        webbrowser.open(
            "https://www.youtube.com/playlist?list=PLwJIqstNBJGnfHiQblP5g1YJKcwlMp8HV"
        )

    def closeEvent(self, event):
        try:
            self.timer.stop()
            self.ui_timer.stop()
        except Exception:
            pass

        try:
            self.qr.stop_all()
        except Exception:
            pass

        try:
            self.record.stop_all()
        except Exception:
            pass

        try:
            self.runtime_cleaner.stop()
        except Exception:
            pass

        super().closeEvent(event)

# ==================================================
# RUN APP
# ==================================================
def run_app():
    app = QApplication(sys.argv)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
