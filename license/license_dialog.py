from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QApplication
)
from PySide6.QtCore import Qt


class LicenseDialog(QDialog):
    def __init__(self, device_id, message):
        super().__init__()

        self.setWindowTitle("Kích hoạt License")
        self.setFixedSize(520, 300)

        layout = QVBoxLayout(self)

        title = QLabel("ATG AI SYSTEM - LICENSE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20px;font-weight:bold;color:white;")

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-size:14px;color:#ffcc66;")

        device = QLabel(f"Device ID:\n{device_id}")
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

        btn_copy = QPushButton("Copy Device ID")
        btn_close = QPushButton("Thoát")

        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(device_id))
        btn_close.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(btn_copy)
        btns.addWidget(btn_close)

        layout.addWidget(title)
        layout.addWidget(msg)
        layout.addWidget(device)
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