import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QComboBox,
    QDateEdit,
    QVBoxLayout,
    QWidget,
)

from core.resource_paths import resource_path
from license.crypto import create_signed_token, verify_signed_token
from tools.create_license_token import DEFAULT_PRIVATE_KEY_FILE


class LicenseTokenWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATG License Token Tool")
        self.resize(900, 620)
        self.setMinimumSize(760, 560)
        icon = QIcon(resource_path("icon.ico"))
        if not icon.isNull():
            self.setWindowIcon(icon)
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.setCentralWidget(scroll)

        root = QWidget()
        scroll.setWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(16, 14, 16, 14)
        main.setSpacing(9)

        title = QLabel("ATG Signed License Token")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#ffffff;")
        main.addWidget(title)

        note = QLabel(
            "Private key chi dung tren may admin. Khong gui private key hoac tool nay cho khach."
        )
        note.setStyleSheet("color:#facc15;font-size:12px;")
        main.addWidget(note)

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(18)
        form_grid.setVerticalSpacing(8)

        left_form = QFormLayout()
        left_form.setHorizontalSpacing(10)
        left_form.setVerticalSpacing(8)
        left_form.setLabelAlignment(Qt.AlignRight)

        right_form = QFormLayout()
        right_form.setHorizontalSpacing(10)
        right_form.setVerticalSpacing(8)
        right_form.setLabelAlignment(Qt.AlignRight)

        self.private_key_file = QLineEdit(DEFAULT_PRIVATE_KEY_FILE)
        btn_key = QPushButton("Chon")
        btn_key.setFixedWidth(70)
        btn_key.clicked.connect(self.pick_private_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.private_key_file, 1)
        key_row.addWidget(btn_key)

        self.customer = QLineEdit("ATG Customer")
        self.device_id = QLineEdit()
        self.hardware_hash = QLineEdit()
        self.max_camera = QSpinBox()
        self.max_camera.setRange(1, 1000)
        self.max_camera.setValue(16)
        self.expire_date = QDateEdit()
        self.expire_date.setCalendarPopup(True)
        self.expire_date.setDisplayFormat("yyyy-MM-dd")
        self.expire_date.setDate(QDate.currentDate().addYears(1))
        self.offline_days = QSpinBox()
        self.offline_days.setRange(1, 3650)
        self.offline_days.setValue(30)
        self.status = QComboBox()
        self.status.addItems(["active", "disabled", "blocked"])
        self.features = QLineEdit("record,mysql,packing")

        left_form.addRow("Private key", key_row)
        left_form.addRow("Khach hang", self.customer)
        left_form.addRow("DEVICE_ID", self.device_id)
        left_form.addRow("HARDWARE_HASH", self.hardware_hash)

        right_form.addRow("MAX_CAMERA", self.max_camera)
        right_form.addRow("EXPIRE_DATE", self.expire_date)
        right_form.addRow("OFFLINE_DAYS", self.offline_days)
        right_form.addRow("STATUS", self.status)
        right_form.addRow("FEATURES", self.features)

        form_grid.addLayout(left_form, 0, 0)
        form_grid.addLayout(right_form, 0, 1)
        form_grid.setColumnStretch(0, 3)
        form_grid.setColumnStretch(1, 2)
        main.addLayout(form_grid)

        btn_grid = QGridLayout()
        self.btn_paste_machine = QPushButton("Dan thong tin may")
        self.btn_create = QPushButton("Tao token")
        self.btn_copy = QPushButton("Copy token")
        self.btn_save = QPushButton("Luu file token")
        self.btn_verify = QPushButton("Verify token")
        self.btn_clear = QPushButton("Xoa form")

        self.btn_paste_machine.clicked.connect(self.paste_machine_info)
        self.btn_create.clicked.connect(self.create_token)
        self.btn_copy.clicked.connect(self.copy_token)
        self.btn_save.clicked.connect(self.save_token)
        self.btn_verify.clicked.connect(self.verify_token)
        self.btn_clear.clicked.connect(self.clear_form)

        for index, button in enumerate(
            [
                self.btn_paste_machine,
                self.btn_create,
                self.btn_copy,
                self.btn_save,
                self.btn_verify,
                self.btn_clear,
            ]
        ):
            button.setMinimumHeight(34)
            btn_grid.addWidget(button, index // 3, index % 3)

        main.addLayout(btn_grid)

        self.token_box = QPlainTextEdit()
        self.token_box.setPlaceholderText("SIGNED_TOKEN se hien thi tai day...")
        self.token_box.setMinimumHeight(130)
        main.addWidget(self.token_box, 1)

        self.payload_box = QPlainTextEdit()
        self.payload_box.setReadOnly(True)
        self.payload_box.setPlaceholderText("Payload verify...")
        self.payload_box.setMinimumHeight(90)
        main.addWidget(self.payload_box)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background:#111111;
                color:#eeeeee;
                font-family:'Segoe UI';
                font-size:12px;
            }
            QLineEdit, QPlainTextEdit, QSpinBox, QDateEdit, QComboBox {
                background:#1b1b1b;
                color:#eeeeee;
                border:1px solid #333333;
                border-radius:6px;
                padding:5px;
                min-height:22px;
            }
            QPushButton {
                background:#0f62fe;
                color:white;
                border:none;
                border-radius:8px;
                padding:7px 12px;
                font-weight:700;
            }
            QPushButton:hover {
                background:#1d74ff;
            }
            QLabel {
                color:#eeeeee;
            }
        """)

    def pick_private_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chon private key file",
            self.private_key_file.text().strip() or str(ROOT),
            "Text files (*.txt);;All files (*.*)",
        )
        if path:
            self.private_key_file.setText(path)

    def paste_machine_info(self):
        text = QApplication.clipboard().text() or ""
        values = {}
        for raw_line in text.replace(";", "\n").splitlines():
            if "=" in raw_line:
                key, value = raw_line.split("=", 1)
                values[key.strip().upper()] = value.strip()

        if values.get("DEVICE_ID"):
            self.device_id.setText(values["DEVICE_ID"])
        if values.get("HARDWARE_HASH"):
            self.hardware_hash.setText(values["HARDWARE_HASH"])

        if not values:
            self.device_id.setText(text.strip())

    def _read_private_key(self):
        path = Path(self.private_key_file.text().strip())
        if not path.exists():
            raise FileNotFoundError(f"Khong thay private key file: {path}")
        return path.read_text(encoding="ascii").strip()

    def _payload(self):
        return {
            "license_id": f"ATG-{datetime.now():%Y%m%d%H%M%S}",
            "customer": self.customer.text().strip() or "ATG Customer",
            "device_id": self.device_id.text().strip(),
            "hardware_hash": self.hardware_hash.text().strip(),
            "max_camera": int(self.max_camera.value()),
            "expire_date": self.expire_date.date().toString("yyyy-MM-dd"),
            "offline_days": int(self.offline_days.value()),
            "status": self.status.currentText(),
            "issued_at": datetime.now().isoformat(timespec="seconds"),
            "features": [
                item.strip()
                for item in self.features.text().split(",")
                if item.strip()
            ],
        }

    def create_token(self):
        try:
            payload = self._payload()
            if not payload["device_id"]:
                raise ValueError("Thieu DEVICE_ID")
            if not payload["hardware_hash"]:
                raise ValueError("Thieu HARDWARE_HASH")
            token = create_signed_token(payload, self._read_private_key())
            self.token_box.setPlainText(token)
            self.payload_box.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception as exc:
            QMessageBox.critical(self, "Loi tao token", str(exc))

    def copy_token(self):
        token = self.token_box.toPlainText().strip()
        if not token:
            QMessageBox.warning(self, "Chua co token", "Hay tao token truoc.")
            return
        QApplication.clipboard().setText(token)
        QMessageBox.information(self, "Da copy", "Da copy SIGNED_TOKEN vao clipboard.")

    def save_token(self):
        token = self.token_box.toPlainText().strip()
        if not token:
            QMessageBox.warning(self, "Chua co token", "Hay tao token truoc.")
            return

        device = self.device_id.text().strip().replace(":", "-") or "license"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Luu token",
            str(Path.cwd() / f"{device}.token"),
            "Token files (*.token);;Text files (*.txt);;All files (*.*)",
        )
        if path:
            Path(path).write_text(token, encoding="utf-8")
            QMessageBox.information(self, "Da luu", f"Da luu token:\n{path}")

    def verify_token(self):
        token = self.token_box.toPlainText().strip()
        if not token:
            QMessageBox.warning(self, "Chua co token", "Hay dan hoac tao token truoc.")
            return
        try:
            payload = verify_signed_token(token)
            self.payload_box.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
            QMessageBox.information(self, "Token hop le", "Chu ky token hop le.")
        except Exception as exc:
            QMessageBox.critical(self, "Token khong hop le", str(exc))

    def clear_form(self):
        self.device_id.clear()
        self.hardware_hash.clear()
        self.token_box.clear()
        self.payload_box.clear()


def main():
    if "--self-test" in sys.argv:
        import _cffi_backend  # noqa: F401
        import nacl.bindings  # noqa: F401
        import nacl.signing  # noqa: F401
        return

    app = QApplication(sys.argv)
    window = LicenseTokenWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
