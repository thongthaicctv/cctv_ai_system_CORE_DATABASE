from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import load_config, save_config


class StoragePage(QWidget):
    settings_saved = Signal(dict)

    def __init__(self):
        super().__init__()
        self.cameras = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title = QLabel("CÀI ĐẶT GHI HÌNH VÀ LƯU TRỮ")
        title.setStyleSheet("font-size:26px;font-weight:bold;color:white;")
        layout.addWidget(title)

        self.btn_save = QPushButton("Lưu cấu hình")
        self.btn_save.setFixedHeight(52)
        self.btn_save.setStyleSheet("""
            QPushButton{
                background:#2563eb;
                color:white;
                border:2px solid #3b82f6;
                border-radius:12px;

                font-size:18px;
                font-weight:900;

                padding-left:18px;
                padding-right:18px;
            }

            QPushButton:hover{
                background:#3b82f6;
                border:2px solid #60a5fa;
            }

            QPushButton:pressed{
                background:#1d4ed8;
            }
        """)
        

        self.btn_save.clicked.connect(self.save_data)

        layout.addWidget(self.btn_save)

        row = QHBoxLayout()
        row.setSpacing(12)

        # --- Auto stop ---
        row.addWidget(QLabel("Tự động dừng (giây):"))

        self.spin_stop = QSpinBox()
        self.spin_stop.setRange(10, 7200)
        self.spin_stop.setValue(300)
        self.spin_stop.setFixedWidth(120)
        row.addWidget(self.spin_stop)

        # --- Path ---
        row.addSpacing(20)
        row.addWidget(QLabel("Thư mục:"))

        self.txt_path = QLineEdit()
        row.addWidget(self.txt_path, 1)

        btn_browse = QPushButton("Chọn")
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self.pick_folder)
        row.addWidget(btn_browse)

        layout.addLayout(row)

        cleanup_row = QHBoxLayout()
        cleanup_row.setSpacing(12)

        self.chk_cleanup = QCheckBox("Xoá video cũ theo ngày")
        cleanup_row.addWidget(self.chk_cleanup)

        cleanup_row.addWidget(QLabel("Giữ lại:"))

        self.spin_keep_days = QSpinBox()
        self.spin_keep_days.setRange(1, 3650)
        self.spin_keep_days.setValue(240)
        self.spin_keep_days.setSuffix(" ngày")
        self.spin_keep_days.setFixedWidth(130)
        cleanup_row.addWidget(self.spin_keep_days)

        cleanup_note = QLabel(
            "Chỉ xoá thư mục video dạng YYYY-MM-DD cũ hơn số ngày giữ lại."
        )
        cleanup_note.setStyleSheet("color:#9ca3af;font-size:12px;")
        cleanup_row.addWidget(cleanup_note, 1)

        layout.addLayout(cleanup_row)

       

        

        mapping_title = QLabel("Bảng Mapping Scan -> Record")
        mapping_title.setStyleSheet("font-size:18px;font-weight:bold;color:white;")
        layout.addWidget(mapping_title)

        mapping_hint = QLabel("Hàng = Chọn camera quét QR | Cột = Chọn camera ghi hình")
        mapping_hint.setStyleSheet("color:#9ca3af;font-size:12px;")
        layout.addWidget(mapping_hint)

        table_wrap = QFrame()
        table_wrap.setStyleSheet("""
            QFrame{
                background:#101010;
                border:1px solid #2a2a2a;
                border-radius:10px;
            }
        """)
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.mapping_table = QTableWidget()
        self.mapping_table.setStyleSheet("""
            QTableWidget{
                background:#141414;
                color:white;
                gridline-color:#333333;
                border:none;
            }
            QHeaderView::section{
                background:#1e1e1e;
                color:white;
                border:1px solid #333333;
                padding:6px;
                font-weight:bold;
            }
        """)
        self.mapping_table.setAlternatingRowColors(False)
        self.mapping_table.verticalHeader().setDefaultSectionSize(34)
        self.mapping_table.horizontalHeader().setDefaultSectionSize(72)
        table_layout.addWidget(self.mapping_table)

        layout.addWidget(table_wrap, 1)

        self.load_data()

    def load_data(self):
        data = load_config()
        self.cameras = list(data.get("cameras", []))

        self.spin_stop.setValue(data.get("record_auto_stop_seconds", 300))
        self.txt_path.setText(data.get("storage_path", "videos"))
        self.chk_cleanup.setChecked(bool(data.get("cleanup_enabled", False)))
        try:
            keep_days = int(data.get("keep_index_days", 240) or 240)
        except Exception:
            keep_days = 240
        self.spin_keep_days.setValue(keep_days)
        self._build_mapping_table(data.get("record_mapping", {}))

    def _build_mapping_table(self, mapping):
        cameras = self.cameras
        labels = [
            self._camera_matrix_label(cam)
            for cam in cameras
        ]

        self.mapping_table.clear()
        self.mapping_table.setRowCount(len(cameras))
        self.mapping_table.setColumnCount(len(cameras))
        self.mapping_table.setVerticalHeaderLabels(labels)
        self.mapping_table.setHorizontalHeaderLabels(labels)

        for row, scan_cam in enumerate(cameras):
            scan_id = str(scan_cam.get("id", ""))
            target_ids = {str(target) for target in mapping.get(scan_id, [])}

            for col, record_cam in enumerate(cameras):
                record_id = str(record_cam.get("id", ""))
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if record_id in target_ids else Qt.Unchecked
                )
                self.mapping_table.setItem(row, col, item)

    def _camera_matrix_label(self, cam):
        cam_id = str(cam.get("id", "")).strip()
        name = str(cam.get("name", cam_id)).strip() or cam_id
        try:
            scanner_id = f"s{int(cam_id):02d}"
        except ValueError:
            scanner_id = f"s{cam_id}"
        return f"{scanner_id} / ID {cam_id} - {name}"

    def _read_mapping(self):
        mapping = {}

        for row, scan_cam in enumerate(self.cameras):
            scan_id = str(scan_cam.get("id", ""))
            targets = []

            for col, record_cam in enumerate(self.cameras):
                item = self.mapping_table.item(row, col)
                if item and item.checkState() == Qt.Checked:
                    targets.append(str(record_cam.get("id", "")))

            mapping[scan_id] = targets

        return mapping

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Chon thu muc luu video",
        )

        if folder:
            self.txt_path.setText(folder)

    def save_data(self):
        data = load_config()
        data["record_auto_stop_seconds"] = self.spin_stop.value()
        data["storage_path"] = self.txt_path.text().strip()
        data["record_mapping"] = self._read_mapping()
        data["cleanup_enabled"] = self.chk_cleanup.isChecked()
        data["keep_index_days"] = self.spin_keep_days.value()

        save_config(data)
        self.settings_saved.emit(load_config())
