from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class CameraCard(QFrame):
    def __init__(self, name, status="CHECKING"):
        super().__init__()

        self._last_status = None
        self._last_render_key = None

        self.setMinimumHeight(170)

        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(QFont("Segoe UI", 11, QFont.Bold))

        self.lbl_status = QLabel()
        self.lbl_employee = QLabel("NV: -")
        self.lbl_order = QLabel("Don van: -")
        self.lbl_scan = QLabel("Scan: -")

        for label in (
            self.lbl_status,
            self.lbl_employee,
            self.lbl_order,
            self.lbl_scan,
        ):
            label.setFont(QFont("Segoe UI", 9))
            label.setWordWrap(False)

        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setFixedHeight(36)
        self.btn_preview.setStyleSheet(
            """
            QPushButton{
                background:#1f2937;
                color:#ffffff;
                border:1px solid #334155;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#273447;
            }
            """
        )

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setStyleSheet(
            """
            QPushButton{
                background:#7f1d1d;
                color:#ffffff;
                border:1px solid #b91c1c;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#991b1b;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 18)
        layout.setSpacing(6)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.lbl_employee)
        layout.addWidget(self.lbl_order)
        layout.addWidget(self.lbl_scan)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_stop)
        layout.addLayout(btn_row)

        self.set_status(status)

    def apply_state(self, cam, info):
        cam_id = str(cam.get("id", "")).strip()
        name = str(cam.get("name", "")).strip()

        if cam_id:
            title = f"ID_CAM: {cam_id}    |    Name: {name} " if name else f"ID: {cam_id}"
        else:
            title = name or "Camera"

        if self.lbl_name.text() != title:
            self.lbl_name.setText(title)

        

        status = info.get("status", "CHECKING")
        if status != self._last_status:
            self.set_status(status)

        employee_id = info.get("employee_id", "")
        employee_name = info.get("employee_name", "")
        order_code = info.get("order_code", "")
        scan_text = info.get("scan_text", "")
        started_at = info.get("started_at", "")
        stopped_at = info.get("stopped_at", "")
        latency = info.get("latency", 0)
        last_check = info.get("last_check", "-")
        recording = bool(info.get("recording", False))
        record_requested = bool(info.get("record_requested", recording))
        record_pending = bool(info.get("record_pending", False))
        error = info.get("error", "")
        record_error = info.get("record_error", "")
        ip = cam.get("ip", "-")

        render_key = (
            employee_id,
            employee_name,
            order_code,
            scan_text,
            started_at,
            stopped_at,
            latency,
            last_check,
            recording,
            record_requested,
            record_pending,
            error,
            record_error,
            ip,
        )
        if render_key == self._last_render_key:
            return

        employee_text = employee_id or "N/A"
        if employee_name:
            employee_text = f"{employee_text} | {employee_name}"

        order_text = f"Don van: {order_code}" if order_code else "Don van: -"

        if recording and started_at:
            order_text = f"{order_text} | REC {started_at[-8:]}"
        elif record_pending:
            order_text = f"{order_text} | WAIT RTSP"
        elif stopped_at:
            order_text = f"{order_text} | STOP {stopped_at[-8:]}"

        self.lbl_employee.setText(f"NV: {employee_text}")
        self.lbl_order.setText(order_text)
        self.lbl_scan.setText(f"Scan: {scan_text or '-'}")
        tooltip = f"{ip} | {latency}ms | {last_check}"
        if record_error:
            tooltip = f"{tooltip} | RECORD: {record_error}"
        if error:
            tooltip = f"{tooltip} | ERROR: {error}"
        self.lbl_status.setToolTip(tooltip)
        self.btn_stop.setVisible(record_requested or recording or record_pending)

        self._last_render_key = render_key

    def set_status(self, status):
        self._last_status = status

        styles = {
            "ONLINE": ("ONLINE", "#16261a", "#2ea043", "#ffffff", 9),
            "OFFLINE": ("OFFLINE", "#241616", "#d73a49", "#ffffff", 9),
            "CHECKING": ("CHECKING", "#2a2412", "#d29922", "#ffffff", 9),
            "WORKING": ("WORKING", "#241f12", "#d29922", "#ffffff", 9),
            "ERROR": ("ERROR", "#2b1217", "#d73a49", "#ffffff", 10),
            "RECORD_WAIT": ("REC WAIT", "#2a2412", "#d29922", "#ffffff", 11),
            "RECORD_ERROR": ("REC ERROR", "#2b1217", "#d73a49", "#ffffff", 11),
            "RECORDING": ("RECORDING", "#16261a", "#2ea043", "#ff2b2b", 18),
        }

        text, bg, border, txt_color, font_size = styles.get(
            status,
            ("WAITING", "#1c1c1c", "#333333", "#ffffff", 9),
        )

        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(
            f"""
            color:{txt_color};
            font-size:{font_size}px;
            font-weight:bold;
            background:transparent;
            border:none;
            """
        )

        self.setStyleSheet(
            f"""
            QFrame{{
                background:{bg};
                border:1px solid {border};
                border-radius:12px;
            }}
            QLabel{{
                color:#ffffff;
                background:transparent;
                border:none;
            }}
            """
        )
