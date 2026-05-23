import time

import cv2
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from utils.url_helper import open_rtsp_capture, safe_rtsp


class PreviewWorker(QThread):
    frame_ready = Signal(object)
    status_changed = Signal(str)

    def __init__(self, rtsp):
        super().__init__()
        self.rtsp = safe_rtsp(rtsp)
        self.running = True
        self.cap = None

    def run(self):
        if not self.rtsp:
            self.status_changed.emit("Missing RTSP URL")
            return

        while self.running:
            if not self._ensure_capture():
                time.sleep(2)
                continue

            try:
                ok, frame = self.cap.read()
            except Exception:
                ok, frame = False, None

            if not ok or frame is None:
                self.status_changed.emit("Lost frame, reconnecting...")
                self._release_capture()
                time.sleep(1)
                continue

            self.status_changed.emit("")
            self.frame_ready.emit(frame)
            time.sleep(0.03)

        self._release_capture()

    def _ensure_capture(self):
        if self.cap is not None and self.cap.isOpened():
            return True

        self._release_capture()
        self.status_changed.emit("Connecting...")
        self.cap = open_rtsp_capture(self.rtsp)

        if self.cap.isOpened():
            return True

        self.status_changed.emit("Cannot open RTSP stream")
        self._release_capture()
        return False

    def _release_capture(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def stop(self):
        self.running = False


class PreviewWindow(QWidget):

    def __init__(self, title, rtsp):
        super().__init__()

        self.setWindowTitle(title)
        self.resize(1000, 650)
        self.setStyleSheet("""
            QWidget{
                background:#050505;
            }
            QLabel{
                color:#dddddd;
                font-size:15px;
            }
        """)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)

        self.status_label = QLabel("Connecting...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(28)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.status_label)

        self.last_image = None

        self.worker = PreviewWorker(rtsp)
        self.worker.frame_ready.connect(self.show_frame)
        self.worker.status_changed.connect(self.show_status)
        self.worker.start()

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        bytes_per_line = channels * w

        self.last_image = QImage(
            rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()

        self.render_frame()

    def show_status(self, text):
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def render_frame(self):
        if self.last_image is None:
            return

        pixmap = QPixmap.fromImage(self.last_image).scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_frame()

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(6000)
        event.accept()
