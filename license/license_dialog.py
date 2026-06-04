from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .cache_manager import CacheManager
from .hardware import get_hardware_hash


class LicenseDialog(QDialog):
    def __init__(self, device_id, message):
        super().__init__()

        self.device_id = device_id
        self.hardware_hash = get_hardware_hash()
        self.setWindowTitle("Kich hoat License")
        self.setFixedSize(680, 530)

        layout = QVBoxLayout(self)

        title = QLabel("ATG AI SYSTEM - LICENSE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20px;font-weight:bold;color:white;")

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-size:14px;color:#ffcc66;")

        device = QLabel(f"Device ID:\n{device_id}\n\nHardware Hash:\n{self.hardware_hash}")
        device.setAlignment(Qt.AlignCenter)
        device.setTextInteractionFlags(Qt.TextSelectableByMouse)
        device.setStyleSheet("""
            QLabel{
                background:#111;
                color:#00ffaa;
                border:1px solid #00aa66;
                border-radius:8px;
                padding:12px;
                font-size:15px;
                font-weight:bold;
            }
        """)

        self.txt_token = QPlainTextEdit()
        self.txt_token.setPlaceholderText("Dan signed license token tai day...")
        self.txt_token.setFixedHeight(110)

        btn_copy = QPushButton("Copy thong tin may")
        btn_activate = QPushButton("Kich hoat token")
        btn_close = QPushButton("Thoat")

        btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(
                f"DEVICE_ID={device_id}\nHARDWARE_HASH={self.hardware_hash}"
            )
        )
        btn_activate.clicked.connect(self.activate_token)
        btn_close.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(btn_copy)
        btns.addWidget(btn_activate)
        btns.addWidget(btn_close)

        layout.addWidget(title)
        layout.addWidget(msg)
        layout.addWidget(device)
        layout.addWidget(self.txt_token)
        layout.addLayout(btns)

        self.setStyleSheet("""
            QDialog{
                background:#202020;
            }
            QPushButton{
                background:#0f62fe;
                color:white;
                border:none;
                border-radius:8px;
                padding:10px;
                font-size:14px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#0353e9;
            }
            QPlainTextEdit{
                background:#111;
                color:#eeeeee;
                border:1px solid #444;
                border-radius:8px;
                padding:8px;
                font-size:12px;
            }
        """)

    def activate_token(self):
        token = self.txt_token.toPlainText().strip()
        if not token:
            QMessageBox.warning(self, "Thieu token", "Vui long dan signed license token.")
            return

        try:
            CacheManager.install_token(token, expected_device_id=self.device_id)
        except Exception as exc:
            QMessageBox.critical(self, "License token loi", str(exc))
            return

        QMessageBox.information(
            self,
            "Da luu",
            "Da luu license token. Phan mem se kiem tra lai license.",
        )
        self.accept()
