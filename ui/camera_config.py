# File: ui/camera_config.py
# Module: Camera Config Pro
# Python 3.10+
# pip install PySide6

import json
import os


from core.resource_paths import resource_path

from core.config_manager import load_config as load_app_config, save_config as save_app_config
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMessageBox, QFileDialog, QDialog,
    QFormLayout, QSpinBox
)
from utils.url_helper import camera_rtsp_url, open_rtsp_capture

from PySide6.QtWidgets import QApplication



CONFIG_FILE = "config.json"


# =============================
# LOAD / SAVE CONFIG
# =============================
def load_config():
    data = load_app_config(force=True)
    if "cameras" not in data:
        data["cameras"] = []
    return data


def save_config(data):
    save_app_config(data)


# =============================
# CAMERA FORM
# =============================
class CameraDialog(QDialog):
    def __init__(self, camera=None):
        super().__init__()

        self.setWindowTitle("Cấu hình Camera")
        self.resize(500, 300)

        self.id_input = QLineEdit()
        self.name_input = QLineEdit()
        self.ip_input = QLineEdit()
        self.rtsp_main_input = QLineEdit()
        self.rtsp_sub_input = QLineEdit()
        self.area_input = QLineEdit()

        form = QFormLayout()
        form.addRow("ID Camera:", self.id_input)
        form.addRow("Tên hiển thị:", self.name_input)
        form.addRow("IP:", self.ip_input)
        form.addRow("RTSP Main:", self.rtsp_main_input)
        form.addRow("RTSP Sub:", self.rtsp_sub_input)
        form.addRow("Khu vực:", self.area_input)

        btn_save = QPushButton("Lưu")
        btn_cancel = QPushButton("Hủy")

        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(buttons)

        if camera:
            self.id_input.setText(camera["id"])
            self.name_input.setText(camera["name"])
            self.ip_input.setText(camera["ip"])
            self.rtsp_main_input.setText(
                camera.get("rtsp_main", camera.get("rtsp", ""))
            )

            self.rtsp_sub_input.setText(
                camera.get("rtsp_sub", "")
            )
            self.area_input.setText(camera.get("area", ""))

    def get_data(self):
        return {
            "id": self.id_input.text().strip(),
            "name": self.name_input.text().strip(),
            "ip": self.ip_input.text().strip(),

            "rtsp_main": self.rtsp_main_input.text().strip(),
            "rtsp_sub": self.rtsp_sub_input.text().strip(),

            "area": self.area_input.text().strip(),
            "enabled": True
        }


class DatabaseConfigDialog(QDialog):
    def __init__(self, config_data=None, parent=None):
        super().__init__(parent)
        self.config_data = config_data or {}
        self.setWindowTitle("Cài đặt Database MariaDB/MySQL")
        self.resize(560, 430)

        db = {
            "type": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "atg_order_system",
            "user": "atg_app",
            "password": "atg_password",
            "charset": "utf8mb4",
            "connect_timeout": 5,
        }
        db.update(self.config_data.get("db", {}) or {})

        self.host_input = QLineEdit(str(db.get("host", "127.0.0.1")))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(db.get("port", 3306) or 3306))
        self.database_input = QLineEdit(str(db.get("database", "atg_order_system")))
        self.user_input = QLineEdit(str(db.get("user", "atg_app")))
        self.password_input = QLineEdit(str(db.get("password", "")))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.charset_input = QLineEdit(str(db.get("charset", "utf8mb4")))
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 60)
        self.timeout_input.setValue(int(db.get("connect_timeout", 5) or 5))

        self.host_input.setPlaceholderText("VD: 127.0.0.1 hoặc 192.168.1.100")
        self.database_input.setPlaceholderText("VD: atg_order_system")
        self.user_input.setPlaceholderText("VD: root khi cài DB, atg_app khi chạy app")
        self.password_input.setPlaceholderText("Mật khẩu MariaDB/MySQL")
        self.charset_input.setPlaceholderText("utf8mb4")

        form = QFormLayout()
        form.addRow("IP máy chủ:", self._field_with_hint(
            self.host_input,
            "Máy cài MariaDB. Nếu chạy trên máy này dùng 127.0.0.1; máy khác trong LAN dùng IP máy chủ."
        ))
        form.addRow("Cổng:", self._field_with_hint(
            self.port_input,
            "Cổng MariaDB/MySQL, mặc định là 3306."
        ))
        form.addRow("Tên database:", self._field_with_hint(
            self.database_input,
            "Database dùng chung cho hệ thống. Mặc định: atg_order_system."
        ))
        form.addRow("Tài khoản:", self._field_with_hint(
            self.user_input,
            "Dùng root/admin để bấm Cài database. Sau khi cài xong có thể dùng atg_app để chạy phần mềm."
        ))
        form.addRow("Mật khẩu:", self._field_with_hint(
            self.password_input,
            "Mật khẩu của tài khoản MariaDB/MySQL ở trên."
        ))
        form.addRow("Bảng mã:", self._field_with_hint(
            self.charset_input,
            "Giữ utf8mb4 để lưu tiếng Việt và mã đơn an toàn."
        ))
        form.addRow("Timeout:", self._field_with_hint(
            self.timeout_input,
            "Số giây chờ khi test kết nối. LAN nội bộ thường dùng 5 giây."
        ))

        self.status_label = QLabel("Nhập thông số rồi bấm Test hoặc Cài database.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "padding:8px;border:1px solid #444;border-radius:6px;color:#dddddd;"
        )

        self.btn_test = QPushButton("Test kết nối")
        self.btn_install = QPushButton("Cài database")
        self.btn_save = QPushButton("Lưu cấu hình")
        self.btn_close = QPushButton("Đóng")

        self.btn_test.clicked.connect(self.test_connection)
        self.btn_install.clicked.connect(self.install_database)
        self.btn_save.clicked.connect(self.save_and_accept)
        self.btn_close.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_test)
        buttons.addWidget(self.btn_install)
        buttons.addStretch()
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_close)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addLayout(buttons)

    def _field_with_hint(self, field, hint):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color:#666;font-size:11px;")
        layout.addWidget(field)
        layout.addWidget(hint_label)
        return box

    def get_db_config(self):
        return {
            "type": "mysql",
            "host": self.host_input.text().strip() or "127.0.0.1",
            "port": int(self.port_input.value()),
            "database": self.database_input.text().strip() or "atg_order_system",
            "user": self.user_input.text().strip() or "atg_app",
            "password": self.password_input.text(),
            "charset": self.charset_input.text().strip() or "utf8mb4",
            "connect_timeout": int(self.timeout_input.value()),
        }

    def _set_status(self, message, ok=None):
        color = "#dddddd"
        if ok is True:
            color = "#22c55e"
        elif ok is False:
            color = "#ef4444"
        self.status_label.setStyleSheet(
            f"padding:8px;border:1px solid #444;border-radius:6px;color:{color};"
        )
        self.status_label.setText(message)

    def _connect(self, with_database=True):
        import pymysql

        cfg = self.get_db_config()
        kwargs = {
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "charset": cfg["charset"],
            "connect_timeout": cfg["connect_timeout"],
            "autocommit": True,
        }
        if with_database:
            kwargs["database"] = cfg["database"]
        return pymysql.connect(**kwargs)

    def test_connection(self):
        try:
            with self._connect(with_database=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT VERSION(), DATABASE()")
                    version, database = cur.fetchone()
            self._set_status(
                f"Kết nối OK\nMariaDB/MySQL: {version}\nDatabase: {database}",
                ok=True,
            )
        except ModuleNotFoundError:
            self._set_status("Thiếu thư viện PyMySQL. Cài: pip install PyMySQL", ok=False)
        except Exception as exc:
            self._set_status(f"Kết nối thất bại:\n{exc}", ok=False)

    def _sql_statements(self, sql_text):
        statements = []
        current = []
        for line in sql_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            current.append(line)
            if stripped.endswith(";"):
                statement = "\n".join(current).strip().rstrip(";").strip()
                if statement:
                    statements.append(statement)
                current = []
        tail = "\n".join(current).strip()
        if tail:
            statements.append(tail)
        return statements

    def install_database(self):
        schema_path = resource_path("db", "mysql_schema_atg_order_system.sql")
        if not os.path.exists(schema_path):
            QMessageBox.warning(self, "Thiếu schema", f"Không tìm thấy file:\n{schema_path}")
            return

        if QMessageBox.question(
            self,
            "Cài database",
            "Chạy schema để tạo/cập nhật database atg_order_system?",
        ) != QMessageBox.Yes:
            return

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                statements = self._sql_statements(f.read())

            with self._connect(with_database=False) as conn:
                with conn.cursor() as cur:
                    for statement in statements:
                        cur.execute(statement)

            self._set_status(
                f"Cài database OK. Đã chạy {len(statements)} câu SQL từ schema.",
                ok=True,
            )
        except ModuleNotFoundError:
            self._set_status("Thiếu thư viện PyMySQL. Cài: pip install PyMySQL", ok=False)
        except Exception as exc:
            self._set_status(
                "Cài database thất bại. Kiểm tra user có quyền CREATE/ALTER/INSERT "
                f"hoặc dùng tài khoản root/admin.\n\n{exc}",
                ok=False,
            )

    def save_and_accept(self):
        self.config_data["db"] = self.get_db_config()
        self.accept()


# =============================
# MAIN CONFIG PAGE
# =============================
class CameraConfigPage(QWidget):
    def __init__(self):
        super().__init__()

        self.data = load_config()

        title = QLabel("QUẢN LÝ CAMERA")
        title.setStyleSheet("font-size:20px;font-weight:bold;")

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tên camera", "IP", "RTSP SUB", "Khu vực", "Trạng thái"
        ])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Buttons
        self.btn_add = QPushButton("➕ Thêm")
        self.btn_edit = QPushButton("✏️ Sửa")
        self.btn_delete = QPushButton("🗑️ Xóa")
        self.btn_test = QPushButton("📡 Test")
        self.btn_database = QPushButton("Database")


        self.btn_help = QPushButton("📘 Hướng dẫn")
        self.btn_help.clicked.connect(self.open_guide)

  


        self.btn_import = QPushButton("📥 Import")
        self.btn_export = QPushButton("📤 Export")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_test)

        
        btn_row.addWidget(self.btn_help)
        
        btn_row.addStretch()
        btn_row.addWidget(self.btn_database)
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_export)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        # events
        self.btn_add.clicked.connect(self.add_camera)
        self.btn_edit.clicked.connect(self.edit_camera)
        self.btn_delete.clicked.connect(self.delete_camera)
        self.btn_test.clicked.connect(self.test_camera)
        self.btn_database.clicked.connect(self.open_database_config)



        self.btn_import.clicked.connect(self.import_json)
        self.btn_export.clicked.connect(self.export_json)

        self.refresh_table()

    def open_database_config(self):
        self.data = load_config()
        dlg = DatabaseConfigDialog(self.data, self)
        if dlg.exec() == QDialog.Accepted:
            self.data["db"] = dlg.get_db_config()
            save_config(self.data)
            QMessageBox.information(
                self,
                "Database",
                "Đã lưu cấu hình database vào config.json."
            )

    # =============================
    # TABLE
    # =============================
    def refresh_table(self):
        cams = self.data["cameras"]
        self.table.setRowCount(len(cams))

        for row, cam in enumerate(cams):
            self.table.setItem(row, 0, QTableWidgetItem(cam["id"]))
            self.table.setItem(row, 1, QTableWidgetItem(cam["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(cam["ip"]))
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    "MAIN / SUB"
                )
            )
            self.table.setItem(row, 4, QTableWidgetItem(cam.get("area", "")))

            status = "Bật" if cam.get("enabled", True) else "Tắt"
            self.table.setItem(row, 5, QTableWidgetItem(status))

    def get_selected_index(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return row

    # =============================
    # ACTIONS
    # =============================
    def add_camera(self):

        dlg = CameraDialog()

        if dlg.exec():

            # reload config mới nhất
            self.data = load_config()

            license_manager = QApplication.instance().license_manager

            max_camera = int(
                license_manager.data.get("max_camera", 0)
            )

            current_camera = len(
                self.data.get("cameras", [])
            )

            print("MAX CAMERA:", max_camera)
            print("CURRENT CAMERA:", current_camera)

            print(license_manager.data)
            print(type(max_camera))

            # check limit
            if current_camera >= max_camera:

                msg = QMessageBox(self)

                msg.setWindowTitle("Giới hạn License")

                msg.setIcon(QMessageBox.Warning)

                msg.setText(
                    f"License hiện tại chỉ cho phép tối đa "
                    f"{max_camera} camera."
                )

                msg.setInformativeText(
                    f"Device ID:\n"
                    f"{license_manager.device_id}\n\n"
                    f"Vui lòng liên hệ 0904143113 để mở rộng license và thêm camera mới."
                )
                msg.setStyleSheet("""
                QMessageBox {
                    background-color: #202020;
                }

                QLabel {
                    color: white;
                    font-size: 13px;
                    min-width: 320px;
                }

                QPushButton {
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 6px;
                    padding: 6px 12px;
                    min-width: 80px;
                    min-height: 30px;
                }

                QPushButton:hover {
                    background-color: #3a3a3a;
                }
                """)
                msg.exec()

                return

            # add camera
            cam = dlg.get_data()

            self.data["cameras"].append(cam)

            save_config(self.data)

            self.refresh_table()

    def edit_camera(self):
        idx = self.get_selected_index()
        if idx is None:
            return

        cam = self.data["cameras"][idx]
        dlg = CameraDialog(cam)

        if dlg.exec():
            self.data["cameras"][idx] = dlg.get_data()
            save_config(self.data)
            self.refresh_table()

    def delete_camera(self):
        idx = self.get_selected_index()
        if idx is None:
            return

        reply = QMessageBox.question(
            self,
            "Xác nhận",
            "Xóa camera đã chọn?"
        )

        if reply == QMessageBox.Yes:
            self.data["cameras"].pop(idx)
            save_config(self.data)
            self.refresh_table()

    def test_camera(self):
        idx = self.get_selected_index()
        if idx is None:
            return

        cam = self.data["cameras"][idx]

        rtsp = camera_rtsp_url(cam, prefer="sub")

        try:
            cap = open_rtsp_capture(rtsp)

            ok, frame = cap.read()

            cap.release()

            if ok:
                cam["enabled"] = True

                save_config(self.data)
                self.refresh_table()

                QMessageBox.information(
                    self,
                    "Kết quả",
                    f"{cam['name']}\nRTSP OK"
                )

            else:
                raise Exception("No frame")

        except:
            cam["enabled"] = False

            save_config(self.data)
            self.refresh_table()

            QMessageBox.warning(
                self,
                "Kết quả",
                f"{cam['name']}\nRTSP FAIL"
            )

    def import_json(self):

        file, _ = QFileDialog.getOpenFileName(
            self,
            "Import Config",
            "",
            "JSON Files (*.json)"
        )

        if not file:
            return

        with open(file, "r", encoding="utf-8") as f:
            import_data = json.load(f)

        # =========================
        # LICENSE CHECK
        # =========================
        license_manager = QApplication.instance().license_manager

        max_camera = int(
            license_manager.data.get("max_camera", 0)
        )

        cams = import_data.get("cameras", [])

        total_camera = len(cams)

        print("IMPORT CAMERA:", total_camera)
        print("MAX CAMERA:", max_camera)

        # block import
        if total_camera > max_camera:

            msg = QMessageBox(self)

            msg.setWindowTitle("Giới hạn License")

            msg.setIcon(QMessageBox.Warning)

            msg.setText(
                f"File import có {total_camera} camera.\n\n"
                f"License hiện tại chỉ cho phép "
                f"tối đa {max_camera} camera."
            )

            msg.setInformativeText(
                f"Device ID:\n"
                f"{license_manager.device_id}\n\n"
                f"Vui lòng mở rộng license để import thêm camera."
            )

            msg.setStyleSheet("""
            QMessageBox {
                background-color: #202020;
            }

            QLabel {
                color: white;
                font-size: 13px;
                min-width: 320px;
            }

            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 80px;
                min-height: 30px;
            }

            QPushButton:hover {
                background-color: #3a3a3a;
            }
            """)

            msg.exec()

            return

        # =========================
        # IMPORT
        # =========================
        self.data = import_data

        save_config(self.data)

        self.refresh_table()

        QMessageBox.information(
            self,
            "Import",
            "Đã import cấu hình camera thành công."
        )

    def export_json(self):
        file, _ = QFileDialog.getSaveFileName(
            self,
            "Export Config",
            "camera_config.json",
            "JSON Files (*.json)"
        )

        if not file:
            return

        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

        QMessageBox.information(self, "Thành công", "Đã xuất cấu hình.")


    def open_guide(self):
        file_path = resource_path("note", "huong_dan_cai_dat.txt")

        if not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "Không tìm thấy hướng dẫn",
                f"Không tìm thấy file:\n{file_path}"
            )
            return

        try:
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi mở hướng dẫn",
                str(e)
            )
