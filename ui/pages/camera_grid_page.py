import os
import shutil
import subprocess

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)



from core.config_manager import load_config
from log_panel import LogPanel
from system_logger import log



from ui.widgets.camera_card import CameraCard
from utils.url_helper import camera_rtsp_url


class CameraGridPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.cards = {}
        self.cameras = []
        self._camera_signature = ()
        

        self.title = QLabel("TRẠNG THÁI CAMERA")
        self.title.setFont(QFont("Segoe UI", 24, QFont.Bold))

        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addLayout(self.grid)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText(
            "Lệnh thủ công: S+ID_CAM+emp:xxx=mã nhân viên xxx | S+ID_CAM+abc123= dơn hàng abc123| S+ID_CAM+stop= kết thúc ca"
        )
        self.cmd_input.setFixedHeight(38)
        self.cmd_input.setStyleSheet(
            """
            QLineEdit{
                background:#0b0f14;
                color:#00ff99;
                border:2px solid #00aa66;
                border-radius:8px;
                padding-left:12px;
                font-size:14px;
                font-weight:bold;
                selection-background-color:#00aa66;
            }
            QLineEdit:focus{
                border:2px solid #00ff99;
                background:#101820;
            }
            """
        )
        self.cmd_input.returnPressed.connect(self.send_cmd)
        layout.addWidget(self.cmd_input)

        self.log_panel = LogPanel()
        self.log_panel.setFixedHeight(120)
        layout.addWidget(self.log_panel)

        self.refresh_from_config()

    def clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _build_signature(self, cameras):
        return tuple(
            (
                str(cam.get("id", "")),
                cam.get("name", ""),
                cam.get("ip", ""),
                bool(cam.get("enabled", True)),
            )
            for cam in cameras
        )

    def sync_cameras(self, cameras):
        signature = self._build_signature(cameras)
        if signature == self._camera_signature:
            return

        self._camera_signature = signature
        self.cameras = list(cameras)
        self.cards = {}
        self.clear_grid()

        for index, cam in enumerate(self.cameras):
            card = CameraCard(cam.get("name", f"CAM-{cam.get('id', '')}"))
            card.btn_preview.clicked.connect(self.make_preview_handler(cam))
            card.btn_stop.clicked.connect(
                lambda _, cid=cam.get("id"): self.manual_stop(cid)
            )
            self.cards[str(cam.get("id"))] = card
            self.grid.addWidget(card, index // 4, index % 4)

    def update_runtime(self, runtime=None):
        runtime = runtime or {}
        for cam in self.cameras:
            cam_id = str(cam.get("id"))
            card = self.cards.get(cam_id)
            if not card:
                continue
            card.apply_state(cam, runtime.get(cam_id, {}))

    def refresh_from_config(self, runtime=None):
        self.sync_cameras(load_config().get("cameras", []))
        self.update_runtime(runtime)

    def reload_data(self, runtime=None):
        self.refresh_from_config(runtime)
    

    def is_camera_licensed(self, cam_id):

        app = QApplication.instance()
        record_engine = getattr(app, "record_engine", None)

        if not record_engine:
            return False

        return str(cam_id) in record_engine.workers


    def make_preview_handler(self, cam):

        def handler():

            cam_id = str(cam.get("id"))

            if not self.is_camera_licensed(cam_id):

                QMessageBox.warning(
                    self,
                    "Giới hạn License",
                    (
                        f"Camera ID {cam_id} không nằm trong license hiện tại.\n\n"
                        f"Vui lòng mở rộng license để preview camera này."
                    )
                )

                return

            rtsp = camera_rtsp_url(cam, prefer="sub") or camera_rtsp_url(cam, prefer="main")

            log(f"VLC Preview {cam.get('name', cam_id)}")

            self.open_preview(
                cam.get("name", f"CAM-{cam_id}"),
                rtsp
            )

        return handler


    
    def is_camera_licensed(self, cam_id):

        app = QApplication.instance()

        record_engine = getattr(app, "record_engine", None)

        if not record_engine:
            return False

        return str(cam_id) in record_engine.workers



    def _find_vlc(self):
        """
        Tìm VLC Player trong các đường dẫn phổ biến.
        """
        candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            "vlc",
        ]

        for p in candidates:
            if p == "vlc":
                found = shutil.which("vlc")
                if found:
                    return found
            elif os.path.exists(p):
                return p

        return ""


    def open_preview(self, name, rtsp):
        """
        Preview bằng VLC external.
        Không dùng OpenCV, không decode frame trong app.
        """
        if not rtsp:
            QMessageBox.warning(
                self,
                "Thiếu RTSP",
                f"Camera {name} chưa có luồng RTSP để Preview."
            )
            return

        vlc_exe = self._find_vlc()

        if not vlc_exe:
            QMessageBox.warning(
                self,
                "Không tìm thấy VLC",
                (
                    "Không tìm thấy VLC Player trên máy.\n\n"
                    "Vui lòng cài VLC hoặc kiểm tra đường dẫn:\n"
                    "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
                )
            )
            return

        try:
            subprocess.Popen(
                [
                    vlc_exe,
                    "--rtsp-tcp",
                    "--network-caching=300",
                    "--no-video-title-show",
                    rtsp,
                ],
                shell=False
            )

            log(f"VLC PREVIEW {name}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi mở VLC",
                str(e)
            )

            
        
        def make_preview_handler(self, cam):

            def handler():

                cam_id = str(cam.get("id"))

                # =========================
                # LICENSE CHECK
                # =========================
                if not self.is_camera_licensed(cam_id):

                    QMessageBox.warning(
                        self,
                        "Giới hạn License",
                        (
                            f"Camera ID {cam_id} "
                            f"không nằm trong license hiện tại.\n\n"
                            f"Vui lòng mở rộng license "
                            f"để preview camera này."
                        )
                    )

                    return

                rtsp = camera_rtsp_url(
                    cam,
                    prefer="main"
                )

                log(f"Preview {cam['name']}")

                self.open_preview(
                    cam["name"],
                    rtsp
                )

            return handler

    def manual_stop(self, cam_id):
        log(f"Manual stop CAM-{cam_id}")
        self.state.stop_record(cam_id, clear_employee=False)

    def send_cmd(self):
        text = self.cmd_input.text().strip()
        if not text:
            return

        try:
            from services.qr_engine import manual_qr_command

            manual_qr_command(text)
            log(f"CMD {text}")
        except Exception as exc:
            log(f"CMD ERROR {exc}")

        self.cmd_input.clear()
