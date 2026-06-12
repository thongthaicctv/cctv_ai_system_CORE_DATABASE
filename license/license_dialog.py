from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .hardware import get_hardware_hash


class LicenseDialog(QDialog):
    def __init__(self, device_id, message):
        super().__init__()

        self.device_id = device_id
        self.hardware_hash = get_hardware_hash()
        self.setWindowTitle("Kich hoat License")
        self.setFixedSize(680, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

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

        note = QLabel(
            "Sau khi gui thong tin cho quan tri vien, "
            "bam Load lai license de phan mem dong bo license."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("font-size:12px;color:#cccccc;")

        btn_copy = QPushButton("Copy thong tin may")
        btn_reload = QPushButton("Load lai license")
        btn_close = QPushButton("Thoat")

        btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(
                f"DEVICE_ID={device_id}\nHARDWARE_HASH={self.hardware_hash}"
            )
        )
        btn_reload.clicked.connect(self.accept)
        btn_close.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(btn_copy)
        btns.addWidget(btn_reload)
        btns.addWidget(btn_close)

        layout.addWidget(title)
        layout.addWidget(msg)
        layout.addWidget(device)
        layout.addWidget(note)
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
        """)
