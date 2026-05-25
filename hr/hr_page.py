# FILE: hr/hr_page.py
# Trang "Tra cứu" – tích hợp vào main_window.py tại stack index 3
# Gồm 2 tab: 👥 Nhân sự  |  🎬 Video

import os
import subprocess
import sys
import traceback

from datetime import datetime


from hr.report_excel_exporter import export_all_reports_excel, export_handover_excel


from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSizePolicy,
    QCheckBox, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,QFormLayout,
)

from PySide6.QtWidgets import QApplication
import requests

from core.config_manager import load_config

from hr.qr_generator import employee_qr_bytes, make_employee_qr, save_employee_qr, text_qr_bytes
from hr.employee_manager import (
    add_employee, delete_employee, get_stats,
    load_employees, search_employees, update_employee,
)
from hr.video_index_manager import generate_html_report, load_index
try:
    from hr.video_index_manager import scan_and_build_index
except ImportError:
    from hr.video_index_manager import build_index as scan_and_build_index

# ──────────────────────────────────────
# Màu sắc khớp theme main_window.py
# ──────────────────────────────────────
_BG     = "#111111"
_PANEL  = "#1b1b1b"
_PANEL2 = "#161616"
_BORDER = "#2a2a2a"
_ACCENT = "#0f62fe"
_TEXT   = "#dddddd"
_MUTED  = "#888888"
_GREEN  = "#22c55e"
_RED    = "#ef4444"
_ORANGE = "#f59e0b"
_YELLOW = "#eab308"

_BASE = f"""
    QWidget   {{ background:{_BG}; color:{_TEXT}; font-family:'Segoe UI',sans-serif; font-size:13px; }}
    QFrame    {{ background:{_PANEL}; border:1px solid {_BORDER}; border-radius:8px; }}
    QLineEdit, QComboBox {{
        background:{_PANEL}; border:1px solid {_BORDER}; color:{_TEXT};
        padding:6px 10px; border-radius:6px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color:{_ACCENT}; }}
    QTableWidget {{
        background:{_PANEL}; border:1px solid {_BORDER};
        gridline-color:{_BORDER}; color:{_TEXT};
    }}
    QTableWidget::item:selected {{ background:rgba(15,98,254,.2); color:{_TEXT}; }}
    QHeaderView::section {{
        background:{_BG}; color:{_MUTED}; border:none;
        padding:6px 10px; font-weight:600; font-size:11px;
        text-transform:uppercase; letter-spacing:1px;
    }}
    QScrollBar:vertical {{ width:6px; background:transparent; }}
    QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; }}
    QPushButton {{
        background:{_PANEL}; color:{_TEXT}; border:1px solid {_BORDER};
        padding:7px 14px; border-radius:8px; font-weight:600;
        text-align:center;
    }}
    QPushButton:hover {{ border-color:{_ACCENT}; color:#ffffff; }}
"""

_BTN_PRIMARY = f"""
    QPushButton {{
        background:{_ACCENT}; color:#fff; border:none;
        padding:7px 18px; border-radius:8px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#1d74ff; }}
"""
_BTN_GREEN = f"""
    QPushButton {{
        background:{_GREEN}; color:#000; border:none;
        padding:5px 12px; border-radius:6px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#4ade80; }}
"""
_BTN_BLUE = f"""
    QPushButton {{
        background:#2563eb; color:#fff; border:none;
        padding:5px 12px; border-radius:6px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#3b82f6; }}

"""
_BTN_DANGER = f"""
    QPushButton {{
        background:{_RED}; color:#fff; border:none;
        padding:7px 14px; border-radius:8px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#f87171; }}
"""


# ─────────────────────────────────────────────
# STAT CARD
# ─────────────────────────────────────────────
class _StatCard(QFrame):
    def __init__(self, label: str, value, color: str = _ACCENT):
        super().__init__()
        self.setFixedHeight(82)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 10, 16, 10)
        self._val = QLabel(str(value))
        self._val.setStyleSheet(
            f"color:{color};font-size:26px;font-weight:700;border:none;background:transparent;"
        )
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color:{_MUTED};font-size:11px;border:none;background:transparent;"
        )
        lo.addWidget(self._val)
        lo.addWidget(self._lbl)

    def set_value(self, v):
        self._val.setText(str(v))


# ─────────────────────────────────────────────
# EMPLOYEE DIALOG  (form + QR preview)
# ─────────────────────────────────────────────
class _EmployeeDialog(QDialog):
    def __init__(self, parent=None, emp: dict | None = None):
        super().__init__(parent)
        self.emp = emp or {}
        self.result_data: dict = {}
        self.setWindowTitle("Thêm nhân viên" if not emp else "Cập nhật nhân viên")
        self.setFixedSize(820, 540)
        self.setStyleSheet(_BASE)
        self._build()
        # Nếu đang sửa – render QR ngay
        if emp and emp.get("id"):
            self._refresh_qr()

    def _build(self):
        # ── Outer: form bên trái | QR bên phải ──
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── LEFT: form ──────────────────────────
        left = QWidget()
        left.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(left)
        lo.setContentsMargins(24, 20, 20, 20)
        lo.setSpacing(10)

        title = QLabel("👤 Thông tin nhân viên")
        title.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{_ACCENT};border:none;background:transparent;"
        )
        lo.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        def _f(ph, default=""):
            w = QLineEdit()
            w.setPlaceholderText(ph)
            w.setText(default)
            return w

        e = self.emp
        self.f_id    = _f("VD: NV006",    e.get("id", ""))
        self.f_name  = _f("Họ và tên",    e.get("name", ""))
        self.f_pos   = _f("Chức vụ",      e.get("position", ""))
        self.f_dept  = _f("Bộ phận",      e.get("department", ""))
        self.f_phone = _f("Điện thoại",   e.get("phone", ""))
        self.f_email = _f("Email",        e.get("email", ""))
        self.f_zone  = _f("VD: ECOM, Kho", ", ".join(e.get("camera_zone", [])))
        self.f_note  = _f("Ghi chú",      e.get("note", ""))

        self.f_shift = QComboBox()
        self.f_shift.addItems([
            "Full (6:00 - 23:00)",
            "Ca sáng (6:00 - 14:00)",
            "Ca chiều (14:00 - 22:00)",
            "Ca đêm (22:00 - 6:00)",
            "Hành chính (8:00 - 17:00)",
        ])
        idx = self.f_shift.findText(e.get("shift", ""))
        if idx >= 0:
            self.f_shift.setCurrentIndex(idx)

        self.f_status = QComboBox()
        self.f_status.addItems(["active", "inactive"])
        self.f_status.setCurrentText(e.get("status", "active"))

        # Live update QR khi thay đổi ID / tên / bộ phận
        self.f_id.textChanged.connect(self._refresh_qr)
        self.f_name.textChanged.connect(self._refresh_qr)
        self.f_dept.textChanged.connect(self._refresh_qr)

        form.addRow("Mã NV *",    self.f_id)
        form.addRow("Họ tên *",   self.f_name)
        form.addRow("Chức vụ",    self.f_pos)
        form.addRow("Bộ phận",    self.f_dept)
        form.addRow("Điện thoại", self.f_phone)
        form.addRow("Email",      self.f_email)
        form.addRow("Khu vực",    self.f_zone)
        form.addRow("Ca làm",     self.f_shift)
        form.addRow("Trạng thái", self.f_status)
        form.addRow("Ghi chú",    self.f_note)
        lo.addLayout(form)

        btns = QHBoxLayout()
        b_cancel = QPushButton("Huỷ")
        b_save   = QPushButton("💾 Lưu")
        b_save.setStyleSheet(_BTN_PRIMARY)
        b_cancel.clicked.connect(self.reject)
        b_save.clicked.connect(self._save)
        btns.addWidget(b_cancel)
        btns.addStretch()
        btns.addWidget(b_save)
        lo.addLayout(btns)
        outer.addWidget(left, stretch=3)

        # ── RIGHT: QR panel ─────────────────────
        right = QFrame()
        right.setStyleSheet(
            f"QFrame{{background:#0d0d0d;border:none;border-left:1px solid {_BORDER};}}"
        )
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 24, 20, 20)
        rl.setSpacing(12)
        rl.setAlignment(Qt.AlignTop)

        qr_title = QLabel("QR Code Nhân viên")
        qr_title.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{_MUTED};text-transform:uppercase;"
            f"letter-spacing:1px;border:none;background:transparent;"
        )
        qr_title.setAlignment(Qt.AlignCenter)
        rl.addWidget(qr_title)

        # QR image label – khung trắng nền tối
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(240, 240)
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setStyleSheet(
            f"background:#ffffff;border:2px solid {_BORDER};border-radius:8px;"
        )
        self._set_qr_placeholder()
        rl.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        # Content label
        self.qr_content_lbl = QLabel("EMP: —")
        self.qr_content_lbl.setAlignment(Qt.AlignCenter)
        self.qr_content_lbl.setStyleSheet(
            f"color:{_MUTED};font-size:11px;font-family:Consolas,monospace;"
            f"border:none;background:transparent;"
        )
        rl.addWidget(self.qr_content_lbl)

        # Nút xuất PNG
        self.btn_export_qr = QPushButton("📥 Xuất QR (PNG)")
        self.btn_export_qr.setStyleSheet(_BTN_PRIMARY)
        self.btn_export_qr.setEnabled(False)
        self.btn_export_qr.clicked.connect(self._export_qr)
        rl.addWidget(self.btn_export_qr)

        # Nút in
        self.btn_print_qr = QPushButton("🖨️ In QR")
        self.btn_print_qr.setEnabled(False)
        self.btn_print_qr.clicked.connect(self._print_qr)
        rl.addWidget(self.btn_print_qr)

        rl.addStretch()
        outer.addWidget(right, stretch=2)


    # ── QR helpers ──────────────────────────────
    def _set_qr_placeholder(self):
        """Hiển thị placeholder khi chưa có mã NV."""
        from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
        pm = QPixmap(220, 220)
        pm.fill(QColor("#f8f8f8"))
        painter = QPainter(pm)
        pen = QPen(QColor("#cccccc"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(10, 10, 200, 200)
        painter.setPen(QColor("#aaaaaa"))
        from PySide6.QtGui import QFont as QF
        f = QF("Segoe UI", 10)
        painter.setFont(f)
        painter.drawText(pm.rect(), Qt.AlignCenter, "Nh\u1eadp m\u00e3 NV\n\u0111\u1ec3 t\u1ea1o QR")
        painter.end()
        self.qr_label.setPixmap(pm)

    def _refresh_qr(self):
        """Vẽ lại QR mỗi khi ID / tên / bộ phận thay đổi."""
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        dept   = self.f_dept.text().strip()

        if not emp_id:
            self._set_qr_placeholder()
            self.qr_content_lbl.setText("EMP: —")
            self.btn_export_qr.setEnabled(False)
            self.btn_print_qr.setEnabled(False)
            return

        try:
            from hr.qr_generator import employee_qr_bytes
            png_bytes = employee_qr_bytes(emp_id, name or emp_id, dept or "—")

            from PySide6.QtGui import QPixmap
            pm = QPixmap()
            pm.loadFromData(png_bytes)
            scaled = pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_label.setPixmap(scaled)
            self.qr_content_lbl.setText(f"EMP:{emp_id}")
            self.btn_export_qr.setEnabled(True)
            self.btn_print_qr.setEnabled(True)
            # Cache bytes để xuất
            self._qr_png_bytes = png_bytes
        except Exception as ex:
            self.qr_content_lbl.setText(f"Lỗi: {ex}")

    def _export_qr(self):
        
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu QR Code",
            f"QR_{emp_id}_{name}.png",
            "PNG Image (*.png)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(self._qr_png_bytes)
            QMessageBox.information(self, "\u2705 \u0110\u00e3 l\u01b0u", f"QR code \u0111\u00e3 l\u01b0u t\u1ea1i:\\n{path}")

    def _print_qr(self):
        """In QR ra máy in mặc định."""
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        dept   = self.f_dept.text().strip()
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QPixmap, QPainter
            from PySide6.QtCore import QRectF

            printer = QPrinter(QPrinter.HighResolution)
            dlg     = QPrintDialog(printer, self)
            if dlg.exec() != QPrintDialog.Accepted:
                return

            pm = QPixmap()
            pm.loadFromData(self._qr_png_bytes)

            painter = QPainter(printer)
            rect    = painter.viewport()
            size    = pm.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pm.rect())
            painter.drawPixmap(0, 0, pm)
            painter.end()
        except Exception as ex:
            QMessageBox.critical(self, "Lỗi in", str(ex))

    def _save(self):
        if not self.f_id.text().strip() or not self.f_name.text().strip():
            QMessageBox.warning(self, "Lỗi", "Mã NV và Họ tên không được để trống!")
            return
        zones = [z.strip() for z in self.f_zone.text().split(",") if z.strip()]
        self.result_data = {
            "id":          self.f_id.text().strip(),
            "name":        self.f_name.text().strip(),
            "position":    self.f_pos.text().strip(),
            "department":  self.f_dept.text().strip(),
            "phone":       self.f_phone.text().strip(),
            "email":       self.f_email.text().strip(),
            "camera_zone": zones,
            "shift":       self.f_shift.currentText(),
            "status":      self.f_status.currentText(),
            "note":        self.f_note.text().strip(),
        }
        self.accept()



# ─────────────────────────────────────────────
# QR VIEW DIALOG  (xem & xuất từ bảng nhân sự)
# ─────────────────────────────────────────────
class _QRViewDialog(QDialog):
    """Dialog hiển thị QR lớn, xuất PNG, in."""

    def __init__(self, parent=None, emp: dict | None = None):
        super().__init__(parent)
        self.emp = emp or {}
        self.setWindowTitle(f"QR Code – {emp.get('name', '')}")
        self.setFixedSize(380, 480)
        self.setStyleSheet(_BASE)
        self._png_bytes = b""
        self._build()
        self._render()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        # Tiêu đề
        t = QLabel("QR Code Nhân viên")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{_MUTED};"
            f"text-transform:uppercase;letter-spacing:1px;border:none;background:transparent;"
        )
        lo.addWidget(t)

        # Khung QR
        self.qr_lbl = QLabel()
        self.qr_lbl.setFixedSize(300, 300)
        self.qr_lbl.setAlignment(Qt.AlignCenter)
        self.qr_lbl.setStyleSheet(
            "background:#ffffff;border:2px solid #333;border-radius:10px;"
        )
        lo.addWidget(self.qr_lbl, alignment=Qt.AlignCenter)

        # Content string
        self.content_lbl = QLabel()
        self.content_lbl.setAlignment(Qt.AlignCenter)
        self.content_lbl.setStyleSheet(
            f"color:{_ACCENT};font-family:Consolas,monospace;font-size:13px;"
            f"font-weight:700;border:none;background:transparent;"
        )
        lo.addWidget(self.content_lbl)

        # Tên + bộ phận
        self.info_lbl = QLabel()
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet(
            f"color:{_MUTED};font-size:12px;border:none;background:transparent;"
        )
        lo.addWidget(self.info_lbl)

        # Nút
        btn_row = QHBoxLayout()
        b_export = QPushButton("📥 Xuất PNG")
        b_export.setStyleSheet(_BTN_PRIMARY)
        b_export.clicked.connect(self._export)
        b_print  = QPushButton("🖨️ In")
        b_print.clicked.connect(self._print)
        b_close  = QPushButton("Đóng")
        b_close.clicked.connect(self.accept)
        btn_row.addWidget(b_export)
        btn_row.addWidget(b_print)
        btn_row.addWidget(b_close)
        lo.addLayout(btn_row)

    def _render(self):
        emp = self.emp
        emp_id = emp.get("id", "")
        name   = emp.get("name", emp_id)
        dept   = emp.get("department", "")
        if not emp_id:
            return
        try:
            from hr.qr_generator import employee_qr_bytes
            self._png_bytes = employee_qr_bytes(emp_id, name, dept)
            from PySide6.QtGui import QPixmap
            pm = QPixmap()
            pm.loadFromData(self._png_bytes)
            scaled = pm.scaled(290, 290, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_lbl.setPixmap(scaled)
            self.content_lbl.setText(f"EMP:{emp_id}")
            self.info_lbl.setText(f"{name}  •  {dept}")
        except Exception as ex:
            self.content_lbl.setText(f"Lỗi: {ex}")

    def _export(self):
        emp_id = self.emp.get("id", "NV")
        name   = self.emp.get("name", "")
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu QR Code", f"QR_{emp_id}_{name}.png", "PNG Image (*.png)"
        )
        if path and self._png_bytes:
            with open(path, "wb") as f:
                f.write(self._png_bytes)
            QMessageBox.information(self, "\u2705 \u0110\u00e3 l\u01b0u", f"\u0110\u00e3 l\u01b0u:\\n{path}")

    def _print(self):
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QPixmap, QPainter
            printer = QPrinter(QPrinter.HighResolution)
            dlg     = QPrintDialog(printer, self)
            if dlg.exec() != QPrintDialog.Accepted:
                return
            pm = QPixmap(); pm.loadFromData(self._png_bytes)
            painter = QPainter(printer)
            rect = painter.viewport()
            size = pm.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pm.rect())
            painter.drawPixmap(0, 0, pm)
            painter.end()
        except Exception as ex:
            QMessageBox.critical(self, "Lỗi in", str(ex))


# ─────────────────────────────────────────────
# HR TAB – Quản lý nhân sự
# ─────────────────────────────────────────────
class _CommandQRDialog(QDialog):
    """Dialog tao QR lenh tuy y: STOP, DONG, GIAO, s01stop..."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tao QR lenh")
        self.setFixedSize(430, 560)
        self.setStyleSheet(_BASE)
        self._png_bytes = b""
        self._build()
        self._refresh_qr()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        title = QLabel("Tao QR lenh")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size:16px;font-weight:700;color:#ffffff;border:none;background:transparent;"
        )
        lo.addWidget(title)

        self.txt_content = QLineEdit()
        self.txt_content.setPlaceholderText("VD: s01stop, s01DONG, s08GIAO, s01dong:MADON")
        self.txt_content.setText("s01stop")
        self.txt_content.setFixedHeight(38)
        self.txt_content.textChanged.connect(self._refresh_qr)
        lo.addWidget(self.txt_content)

        self.qr_lbl = QLabel()
        self.qr_lbl.setFixedSize(320, 320)
        self.qr_lbl.setAlignment(Qt.AlignCenter)
        self.qr_lbl.setStyleSheet(
            "background:#ffffff;border:2px solid #333;border-radius:8px;"
        )
        lo.addWidget(self.qr_lbl, alignment=Qt.AlignCenter)

        self.note_lbl = QLabel()
        self.note_lbl.setAlignment(Qt.AlignCenter)
        self.note_lbl.setWordWrap(True)
        self.note_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.note_lbl.setStyleSheet(
            f"color:{_YELLOW};font-size:13px;font-weight:700;"
            f"font-family:Consolas,monospace;border:none;background:transparent;"
        )
        lo.addWidget(self.note_lbl)

        hint = QLabel("Nhap noi dung can ma hoa vao QR. Dong ghi chu nay giup kiem tra lai lenh da tao.")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            f"color:{_MUTED};font-size:11px;border:none;background:transparent;"
        )
        lo.addWidget(hint)

        btns = QHBoxLayout()
        btn_save = QPushButton("Luu PNG")
        btn_close = QPushButton("Dong")
        btn_save.setStyleSheet(_BTN_PRIMARY)
        btn_save.clicked.connect(self._save_png)
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_save)
        btns.addStretch()
        btns.addWidget(btn_close)
        lo.addLayout(btns)

    def _set_placeholder(self, text):
        self.qr_lbl.setText(text)
        self.qr_lbl.setPixmap(QPixmap())
        self.qr_lbl.setStyleSheet(
            "background:#ffffff;color:#666;border:2px solid #333;border-radius:8px;"
        )
        self._png_bytes = b""

    def _refresh_qr(self):
        content = self.txt_content.text().strip()
        if not content:
            self.note_lbl.setText("Noi dung QR: -")
            self._set_placeholder("Nhap noi dung QR")
            return

        note = f"Noi dung QR: {content}"
        try:
            self._png_bytes = text_qr_bytes(content, note=note)
            pm = QPixmap()
            pm.loadFromData(self._png_bytes)
            scaled = pm.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_lbl.setPixmap(scaled)
            self.qr_lbl.setStyleSheet(
                "background:#ffffff;border:2px solid #333;border-radius:8px;"
            )
            self.note_lbl.setText(note)
        except Exception as exc:
            self.note_lbl.setText(f"Loi tao QR: {exc}")
            self._set_placeholder("Khong tao duoc QR")

    def _save_png(self):
        content = self.txt_content.text().strip()
        if not content or not self._png_bytes:
            QMessageBox.warning(self, "Thieu noi dung", "Vui long nhap noi dung QR.")
            return

        safe_name = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in content
        ) or "QR_COMMAND"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Luu QR lenh",
            f"QR_{safe_name}.png",
            "PNG Image (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path = f"{path}.png"
        with open(path, "wb") as f:
            f.write(self._png_bytes)
        QMessageBox.information(self, "Da luu", f"Da luu QR:\n{path}")


class _HRTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)
        self._build()
        self._reload()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("👥 Quản lý Nhân sự")
        t.setStyleSheet(
            f"font-size:18px;font-weight:700;color:#ffffff;border:none;background:transparent;"
        )
        hdr.addWidget(t)
        

        hdr.addStretch()

        btn_stop = QPushButton("QR lệnh")
        btn_stop.setStyleSheet("""
        QPushButton{
            background:#7f1d1d;
            color:white;
            border:none;
            padding:7px 16px;
            border-radius:8px;
            font-weight:700;
        }
        QPushButton:hover{
            background:#dc2626;
        }
        """)
        btn_stop.clicked.connect(self._open_command_qr)

        btn_add = QPushButton("+ Thêm nhân viên")
        btn_add.setStyleSheet(_BTN_PRIMARY)
        btn_add.clicked.connect(self._add)

        hdr.addWidget(btn_add)
        hdr.addWidget(btn_stop)

        lo.addLayout(hdr)

        # Stats
        self.c_total    = _StatCard("Tổng nhân viên", 0, _ACCENT)
        self.c_active   = _StatCard("Đang làm",       0, _GREEN)
        self.c_inactive = _StatCard("Tạm nghỉ",       0, _ORANGE)
        self.c_depts    = _StatCard("Bộ phận",         0, _YELLOW)
        row_stats = QHBoxLayout()
        for c in [self.c_total, self.c_active, self.c_inactive, self.c_depts]:
            row_stats.addWidget(c)
        lo.addLayout(row_stats)

        # Search
        row_search = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Tìm tên, mã NV, bộ phận, khu vực...")
        self.txt_search.textChanged.connect(self._search)
        self.txt_search.setFixedHeight(34)
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tất cả", "active", "inactive"])
        self.cmb_status.currentTextChanged.connect(self._search)
        row_search.addWidget(self.txt_search)
        row_search.addWidget(self.cmb_status)
        lo.addLayout(row_search)

        # Table
        cols = ["Mã NV", "Họ & Tên", "Chức vụ", "Bộ phận", "Ca làm", "Khu vực",
                "Điện thoại", "Trạng thái", ""]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lo.addWidget(self.table)

    def _reload(self):
        s = get_stats()
        self.c_total.set_value(s["total"])
        self.c_active.set_value(s["active"])
        self.c_inactive.set_value(s["inactive"])
        self.c_depts.set_value(len(s["departments"]))
        self._fill(load_employees())

    def _fill(self, employees: list):
        self.table.setRowCount(0)
        for emp in employees:
            r = self.table.rowCount()
            self.table.insertRow(r)
            status = emp.get("status", "active")
            sc = _GREEN if status == "active" else _ORANGE
            zones = ", ".join(emp.get("camera_zone", []))
            vals = [
                emp.get("id", ""),
                emp.get("name", ""),
                emp.get("position", ""),
                emp.get("department", ""),
                emp.get("shift", ""),
                zones,
                emp.get("phone", ""),
                status,
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c == 7:
                    item.setForeground(QColor(sc))
                    item.setFont(QFont("Segoe UI", 11, QFont.Bold))
                self.table.setItem(r, c, item)

            
            # Action buttons
            aw = QWidget()
            aw.setStyleSheet("background:transparent;")

            ahl = QHBoxLayout(aw)
            ahl.setContentsMargins(4, 2, 4, 2)
            ahl.setSpacing(6)

            b_edit = QPushButton("Sửa")
            b_edit.setFixedSize(50, 26)
            b_edit.setStyleSheet("""
            QPushButton{
                background:#1e293b;
                color:#93c5fd;
                border:1px solid #334155;
                border-radius:5px;
                font-size:12px;
                font-weight:700;
            }
            QPushButton:hover{
                background:#2563eb;
                color:white;
            }
            """)
            b_edit.clicked.connect(lambda _, e=emp: self._edit(e))

            b_del = QPushButton("Xoá")
            b_del.setFixedSize(50, 26)
            b_del.setStyleSheet("""
            QPushButton{
                background:#3b1111;
                color:#fca5a5;
                border:1px solid #7f1d1d;
                border-radius:5px;
                font-size:12px;
                font-weight:700;
            }
            QPushButton:hover{
                background:#dc2626;
                color:white;
            }
            """)
            b_del.clicked.connect(lambda _, eid=emp["id"]: self._delete(eid))

            b_qr = QPushButton("QR")
            b_qr.setFixedSize(50, 26)
            b_qr.setStyleSheet("""
            QPushButton{
                background:#1e1b4b;
                color:#c4b5fd;
                border:1px solid #4338ca;
                border-radius:5px;
                font-size:12px;
                font-weight:700;
            }
            QPushButton:hover{
                background:#4338ca;
                color:white;
            }
            """)
            b_qr.clicked.connect(lambda _, e=emp: self._show_qr(e))

            ahl.addWidget(b_edit)
            ahl.addWidget(b_del)
            ahl.addWidget(b_qr)

            self.table.setCellWidget(r, 8, aw)

    def _show_qr(self, emp: dict):
        """Mở dialog xem / xuất QR riêng từ bảng nhân sự."""
        dlg = _QRViewDialog(self, emp)
        dlg.exec()

    def _search(self):
        kw = self.txt_search.text()
        sf = self.cmb_status.currentText()
        res = search_employees(kw)
        if sf != "Tất cả":
            res = [e for e in res if e.get("status") == sf]
        self._fill(res)

    def _add(self):
        dlg = _EmployeeDialog(self)
        if dlg.exec() == QDialog.Accepted:
            if add_employee(dlg.result_data):
                self._reload()
                QMessageBox.information(self, "✅", f"Đã thêm {dlg.result_data['name']}")
            else:
                QMessageBox.warning(self, "Lỗi", f"Mã {dlg.result_data['id']} đã tồn tại!")

    def _edit(self, emp: dict):
        dlg = _EmployeeDialog(self, emp)
        if dlg.exec() == QDialog.Accepted:
            update_employee(emp["id"], dlg.result_data)
            self._reload()

    def _delete(self, emp_id: str):
        if QMessageBox.question(
            self, "Xác nhận", f"Xoá nhân viên <b>{emp_id}</b>?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            delete_employee(emp_id)
            self._reload()


    def _open_command_qr(self):
        dlg = _CommandQRDialog(self)
        dlg.exec()

    def _create_stop_qr(self):
        try:
            from PySide6.QtGui import QPixmap
            
            import qrcode

            qr = qrcode.QRCode(
                version=1,
                box_size=12,
                border=3
            )

            qr.add_data("STOP")
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu QR STOP",
                "STOP_QR.png",
                "PNG Image (*.png)"
            )

            if not save_path:
                return

            img.save(save_path)

            QMessageBox.information(
                self,
                "Đã tạo",
                f"Đã lưu QR STOP:\n{save_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi tạo QR STOP",
                str(e)
            )

    
# ─────────────────────────────────────────────
# VIDEO TAB – Tra cứu video đã ghi
# ─────────────────────────────────────────────
class _RebuildThread(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            from hr.video_index_manager import update_index_incremental

            idx = update_index_incremental(self.path)

            self.done.emit(idx)
        except Exception as e:
            self.error.emit(str(e))


class _VideoTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)
        self._thread: _RebuildThread | None = None
        
        self._config = load_config()
        self._storage = self._config.get("storage_path", "records")
        self._videos: list = []
        self._build()
        self._load()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("🎬 Tra cứu Video")
        t.setStyleSheet(
            f"font-size:18px;font-weight:700;color:#ffffff;border:none;background:transparent;"
        )
        hdr.addWidget(t)

        self.chk_cleanup = QCheckBox("Xoá dữ liệu cũ")
        self.chk_cleanup.setChecked(bool(self._config.get("cleanup_enabled", False)))
        self.chk_cleanup.setStyleSheet("""
        QCheckBox{
            color:#dddddd;
            font-size:12px;
            font-weight:600;
            padding:4px 8px;
        }
        QCheckBox::indicator{
            width:16px;
            height:16px;
        }
        """)
        self.chk_cleanup.stateChanged.connect(self._save_cleanup_config)

        self.spin_keep_days = QSpinBox()
        self.spin_keep_days.setRange(1, 3650)
        self.spin_keep_days.setValue(int(self._config.get("keep_index_days", 180)))
        self.spin_keep_days.setSuffix(" ngày")
        self.spin_keep_days.setFixedWidth(105)
        self.spin_keep_days.setStyleSheet("""
        QSpinBox{
            background:#1b1b1b;
            color:#ffffff;
            border:1px solid #2a2a2a;
            border-radius:6px;
            padding:5px 8px;
        }
        """)
        self.spin_keep_days.valueChanged.connect(self._save_cleanup_config)

        hdr.addWidget(self.chk_cleanup)
        hdr.addWidget(self.spin_keep_days)
        hdr.addStretch()


        self.btn_rebuild = QPushButton("🔄 Cập nhật video")
        self.btn_rebuild.setStyleSheet(_BTN_PRIMARY)
        self.btn_rebuild.clicked.connect(self._rebuild)


        # =========================
        # REMOTE WEB VIDEO INDEX
        # =========================
        self.chk_web_remote = QCheckBox("Web từ xa")
        self.chk_web_remote.setChecked(bool(self._config.get("http_enabled", False)))
        self.chk_web_remote.setFixedHeight(34)
        self.chk_web_remote.setStyleSheet("""
        QCheckBox{
            color:#dddddd;
            font-size:12px;
            font-weight:700;
            padding:4px 8px;
        }
        QCheckBox::indicator{
            width:16px;
            height:16px;
        }
        """)
        self.chk_web_remote.stateChanged.connect(self._save_remote_web_config)

        self.btn_copy_remote = QPushButton("📋 Copy link")
        self.btn_copy_remote.setFixedHeight(34)
        self.btn_copy_remote.setStyleSheet(_BTN_PRIMARY)
        self.btn_copy_remote.clicked.connect(self._copy_remote_url)

        self.btn_remote_setting = QPushButton("⚙ Cài đặt")
        self.btn_remote_setting.setFixedHeight(34)
        self.btn_remote_setting.setStyleSheet(_BTN_PRIMARY)
        self.btn_remote_setting.clicked.connect(self._open_remote_setting)


        for b in [self.btn_rebuild]:
            hdr.addWidget(b)
        
        hdr.addWidget(self.chk_web_remote)
        hdr.addWidget(self.btn_copy_remote)
        hdr.addWidget(self.btn_remote_setting)





        lo.addLayout(hdr)

        # Info
        self.lbl_path = QLabel(f"📂 {self._storage}")
        self.lbl_path.setStyleSheet(
            f"color:{_MUTED};font-size:11px;background:transparent;border:none;"
        )
        lo.addWidget(self.lbl_path)

        # Stats
        self.c_total = _StatCard("Tổng video",      0,  _ACCENT)
        self.c_size  = _StatCard("Dung lượng",  "0 MB", _ORANGE)
        self.c_cams  = _StatCard("Camera IDs",      0,  _YELLOW)
        self.c_emps  = _StatCard("Nhân viên",        0,  _GREEN)
        
        
        rr = QHBoxLayout()
        rr.setSpacing(10)

        for c in [self.c_total, self.c_size, self.c_cams, self.c_emps]:
            rr.addWidget(c)

        rr.addStretch()


        





        self.report_from = QLineEdit()
        self.report_from.setPlaceholderText("Từ dd/mm/yyyy")
        self.report_from.setFixedWidth(145)
        self.report_from.setFixedHeight(34)

        self.report_to = QLineEdit()
        self.report_to.setPlaceholderText("Đến dd/mm/yyyy")
        self.report_to.setFixedWidth(145)
        self.report_to.setFixedHeight(34)

        self.btn_report_all = QPushButton("📊 Xuất báo cáo")
        self.btn_report_all.setStyleSheet(_BTN_PRIMARY)
        self.btn_report_all.setFixedHeight(34)
        self.btn_report_all.clicked.connect(self._export_report_all)

        self.btn_handover_report = QPushButton("🚚 Xuất BC giao hàng")
        self.btn_handover_report.setStyleSheet(_BTN_PRIMARY)
        self.btn_handover_report.setFixedHeight(34)
        self.btn_handover_report.clicked.connect(self._export_handover_report)

        rr.addWidget(self.report_from)
        rr.addWidget(self.report_to)
        rr.addWidget(self.btn_report_all)
        rr.addWidget(self.btn_handover_report)

        lo.addLayout(rr)

        

        # Filters
        flt = QHBoxLayout()
        self.f_kw    = QLineEdit(); self.f_kw.setPlaceholderText("🔍 Mã đơn, nhân viên, camera...")
        self.f_kw.textChanged.connect(self._filter)
        self.f_kw.setFixedHeight(34)

        self.f_cam  = QComboBox()
        self.f_cam.addItem("Tất cả camera")
        self.f_cam.currentTextChanged.connect(self._filter)

        self.f_date = QLineEdit()
        self.f_date.setPlaceholderText("Ngày dd/mm/yyyy")
        self.f_date.setFixedWidth(130); self.f_date.setFixedHeight(34)
        self.f_date.textChanged.connect(self._filter)

        self.f_order = QLineEdit(); self.f_order.setPlaceholderText("Mã đơn")
        self.f_order.setFixedWidth(130); self.f_order.setFixedHeight(34)
        self.f_order.textChanged.connect(self._filter)

        flt.addWidget(self.f_kw)
        flt.addWidget(self.f_cam)
        flt.addWidget(self.f_date)
        flt.addWidget(self.f_order)

        self.btn_multiplay = QPushButton("🎞 MultiPlay")
        self.btn_multiplay.setFixedHeight(34)
        self.btn_multiplay.setStyleSheet(_BTN_PRIMARY)
        self.btn_multiplay.clicked.connect(self._open_multiplay)

        flt.addWidget(self.btn_multiplay)

        lo.addLayout(flt)


        

        # Table
        cols = [
            "ID camera",
            "Mã đơn",
            "Nhân viên",
            "Bộ phận",
            "Ngày",
            "Giờ",
            "Thời lượng",
            "Dung lượng",
            ""
        ]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lo.addWidget(self.table)

    def _save_cleanup_config(self):
        from core.config_manager import save_config

        self._config["cleanup_enabled"] = self.chk_cleanup.isChecked()
        self._config["keep_index_days"] = self.spin_keep_days.value()

        save_config(self._config)

        print(
            "[CONFIG] cleanup_enabled =",
            self._config["cleanup_enabled"],
            "| keep_index_days =",
            self._config["keep_index_days"]
        )


    def _remote_url(self):
        domain = self._config.get("ddns_domain", "").strip()
        port = int(self._config.get("http_port", 18080))

        if not domain:
            domain = "WAN_IP"

        return f"http://{domain}:{port}/index.html"


    def _save_remote_web_config(self):
        from core.config_manager import save_config

        self._config["http_enabled"] = self.chk_web_remote.isChecked()
        save_config(self._config)

        QMessageBox.information(
            self,
            "Web từ xa",
            "Đã lưu cấu hình WebServer.\nKhởi động lại phần mềm để áp dụng."
        )


    def _copy_remote_url(self):
        QApplication.clipboard().setText(self._remote_url())

        QMessageBox.information(
            self,
            "Copy link",
            f"Đã copy:\n{self._remote_url()}"
        )


    def _open_remote_setting(self):
        from core.config_manager import save_config
        import socket

        dlg = QDialog(self)
        dlg.setWindowTitle("Cài đặt Web Video Index từ xa")
        dlg.setFixedSize(760, 380)
        
        dlg.setStyleSheet(_BASE)

        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(22, 18, 22, 18)
        lo.setSpacing(12)

        title = QLabel("🌐 Cài đặt truy cập từ xa")
        title.setStyleSheet(
            "font-size:16px;font-weight:700;color:white;"
            "border:none;background:transparent;"
        )
        lo.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # tăng khoảng cách label/input
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        

        txt_domain = QLineEdit()
        txt_domain.setPlaceholderText("VD: mycctv.duckdns.org hoặc WAN IP")
        txt_domain.setText(self._config.get("ddns_domain", ""))

        spin_port = QSpinBox()
        spin_port.setRange(1000, 65535)
        spin_port.setValue(int(self._config.get("http_port", 18080)))

        txt_user = QLineEdit()
        txt_user.setPlaceholderText("VD: admin")
        txt_user.setText(self._config.get("http_user", "admin"))

        txt_pass = QLineEdit()
        txt_pass.setPlaceholderText("Mật khẩu Web")
        txt_pass.setText(self._config.get("http_pass", "123456"))
        txt_pass.setEchoMode(QLineEdit.Password)


        # tăng độ rộng input
        for w in [txt_domain, spin_port, txt_user, txt_pass]:
            w.setMinimumWidth(420)
            w.setMinimumHeight(34)
            

        lbl_url = QLabel()
        lbl_url.setStyleSheet(
            "color:#22c55e;font-size:13px;font-weight:700;"
            "border:none;background:transparent;"
        )

        lbl_status = QLabel("Trạng thái: Chưa kiểm tra")

        lbl_wan = QLabel("Đang tải WAN IP...")
        lbl_wan.setStyleSheet(
            "color:#38bdf8;font-size:12px;font-weight:700;"
            "border:none;background:transparent;"
        )


        lbl_status.setStyleSheet(
            "color:#eab308;font-size:12px;font-weight:700;"
            "border:none;background:transparent;"
        )

        def update_url():
            domain = txt_domain.text().strip() or "WAN_IP"
            port = spin_port.value()
            lbl_url.setText(f"http://{domain}:{port}/index.html")

        def load_wan_ip():
            try:
                ip = requests.get(
                    "https://api.ipify.org",
                    timeout=5
                ).text.strip()

                lbl_wan.setText(ip)

            except Exception:
                lbl_wan.setText("Không lấy được WAN IP")



        def check_port():
            host = txt_domain.text().strip()
            port = spin_port.value()

            if not host:
                QMessageBox.warning(
                    dlg,
                    "Thiếu địa chỉ",
                    "Vui lòng nhập WAN IP hoặc tên miền DDNS."
                )
                return

            try:
                s = socket.create_connection((host, port), timeout=3)
                s.close()

                lbl_status.setText(f"Trạng thái: ✅ Port {port} đang mở")
                lbl_status.setStyleSheet(
                    "color:#22c55e;font-size:12px;font-weight:700;"
                    "border:none;background:transparent;"
                )

            except Exception:
                lbl_status.setText(f"Trạng thái: ❌ Không kết nối được port {port}")
                lbl_status.setStyleSheet(
                    "color:#ef4444;font-size:12px;font-weight:700;"
                    "border:none;background:transparent;"
                )

        txt_domain.textChanged.connect(update_url)
        spin_port.valueChanged.connect(update_url)
        update_url()
        load_wan_ip()

        form.addRow("WAN/DDNS:", txt_domain)
        form.addRow("WAN hiện tại:", lbl_wan)
        form.addRow("Port Web:", spin_port)


        form.addRow("Tài khoản:", txt_user)
        form.addRow("Mật khẩu:", txt_pass)


        form.addRow("Link truy cập:", lbl_url)
        form.addRow("Check port:", lbl_status)

        lo.addLayout(form)

        btns = QHBoxLayout()

        btn_check = QPushButton("🔎 Check port")
        btn_copy = QPushButton("📋 Copy link")
        btn_save = QPushButton("💾 Lưu")
        btn_close = QPushButton("Đóng")

        btn_check.setStyleSheet(_BTN_PRIMARY)
        btn_save.setStyleSheet(_BTN_PRIMARY)

        def copy_url():
            QApplication.clipboard().setText(lbl_url.text())
            QMessageBox.information(dlg, "Copy", "Đã copy link truy cập.")

        def save_setting():
            self._config["ddns_domain"] = txt_domain.text().strip()
            self._config["http_port"] = spin_port.value()
            self._config["http_enabled"] = self.chk_web_remote.isChecked()


            self._config["http_user"] = txt_user.text().strip()
            self._config["http_pass"] = txt_pass.text().strip()

            save_config(self._config)

            QMessageBox.information(
                dlg,
                "Đã lưu",
                "Đã lưu cấu hình.\nKhởi động lại phần mềm để áp dụng WebServer."
            )

            dlg.accept()

        btn_check.clicked.connect(check_port)
        btn_copy.clicked.connect(copy_url)
        btn_save.clicked.connect(save_setting)
        btn_close.clicked.connect(dlg.reject)

        btns.addWidget(btn_check)
        btns.addWidget(btn_copy)
        btns.addStretch()
        btns.addWidget(btn_save)
        btns.addWidget(btn_close)

        lo.addLayout(btns)

        dlg.exec()
    
    def _vn_date_to_iso(self, text: str):
        """
        Nhập kiểu Việt Nam: dd/mm/yyyy
        Trả về ISO: yyyy-mm-dd
        """
        text = (text or "").strip()

        if not text:
            return ""

        try:
            return datetime.strptime(text, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            return None

    def _validate_report_dates(self):
        from_text = self.report_from.text().strip()
        to_text = self.report_to.text().strip()

        if not from_text or not to_text:
            QMessageBox.warning(
                self,
                "Thiếu ngày",
                "Vui lòng nhập đủ Từ ngày và Đến ngày.\nĐịnh dạng: dd/mm/yyyy\nVí dụ: 18/05/2026"
            )
            return None, None

        from_date = self._vn_date_to_iso(from_text)
        to_date = self._vn_date_to_iso(to_text)

        if not from_date or not to_date:
            QMessageBox.warning(
                self,
                "Sai định dạng",
                "Ngày phải có định dạng dd/mm/yyyy\nVí dụ: 18/05/2026"
            )
            return None, None

        return from_date, to_date
    
    def _export_report_all(self):
        from_date, to_date = self._validate_report_dates()
        if not from_date:
            return

        default_name = f"bao_cao_{from_date}_den_{to_date}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu báo cáo",
            default_name,
            "Excel File (*.xlsx)"
        )

        if not save_path:
            return

        if not save_path.lower().endswith(".xlsx"):
            save_path = f"{save_path}.xlsx"

        try:
            export_all_reports_excel(from_date, to_date, save_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Xuáº¥t bÃ¡o cÃ¡o tháº¥t báº¡i",
                f"KhÃ´ng thá»ƒ xuáº¥t bÃ¡o cÃ¡o Excel.\n\n{exc}\n\n{save_path}"
            )
            print(traceback.format_exc())
            return

        QMessageBox.information(
            self,
            "Xuất báo cáo",
            f"Đã xuất báo cáo gồm 2 sheet:\n"
            f"1. Báo cáo tổng hợp\n"
            f"2. Báo cáo nhân viên\n\n"
            f"{save_path}"
        )


    def _export_handover_report(self):
        from_date, to_date = self._validate_report_dates()
        if not from_date:
            return

        default_name = f"bao_cao_giao_hang_{from_date}_den_{to_date}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu báo cáo giao hàng",
            default_name,
            "Excel File (*.xlsx)"
        )

        if not save_path:
            return

        if not save_path.lower().endswith(".xlsx"):
            save_path = f"{save_path}.xlsx"

        try:
            export_handover_excel(from_date, to_date, save_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Xuáº¥t bÃ¡o cÃ¡o giao hÃ ng tháº¥t báº¡i",
                f"KhÃ´ng thá»ƒ xuáº¥t bÃ¡o cÃ¡o giao hÃ ng.\n\n{exc}\n\n{save_path}"
            )
            print(traceback.format_exc())
            return

        QMessageBox.information(
            self,
            "Xuất báo cáo giao hàng",
            f"Đã xuất báo cáo giao hàng:\n\n{save_path}"
        )

        def _export_handover_report(self):
            from_date, to_date = self._validate_report_dates()
            if not from_date:
                return

            default_name = f"bao_cao_giao_hang_{from_date}_den_{to_date}.xlsx"

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu báo cáo giao hàng",
                default_name,
                "Excel File (*.xlsx)"
            )

            if not save_path:
                return

            export_handover_excel(from_date, to_date, save_path)

            QMessageBox.information(
                self,
                "Xuất báo cáo giao hàng",
                f"Đã xuất báo cáo giao hàng:\n\n{save_path}"
            )
                
            
    # ── Data ──────────────────────────────────
    def _load(self):
        idx = load_index(self._storage)
        self._videos = idx.get("videos", [])
        self._update_stats()
        self._update_cam_filter()
        self._fill(self._videos)

    def _update_stats(self):
        total = len(self._videos)
        size  = sum(v.get("file_size_mb") or v.get("size_mb", 0) for v in self._videos)
        cams  = len(set(v.get("camera_id", "") for v in self._videos))
        emps  = len(set(v.get("employee_id", "") for v in self._videos if v.get("employee_id") not in ("NOEMP", "", None)))
        self.c_total.set_value(total)
        self.c_size.set_value(f"{size:.1f} MB")
        self.c_cams.set_value(cams)
        self.c_emps.set_value(emps)

    def _update_cam_filter(self):
        cams = sorted(set(v.get("camera_id", "") for v in self._videos))
        self.f_cam.clear()
        self.f_cam.addItem("Tất cả camera")
        for c in cams:
            self.f_cam.addItem(c)

    def _fill(self, videos: list):
        self.table.setRowCount(0)
        for v in videos:
            r = self.table.rowCount()
            self.table.insertRow(r)

            # ── duration: dùng duration_sec (mới) hoặc duration (alias cũ) ──
            dur     = v.get("duration_sec") or v.get("duration", 0)
            dur_txt = f"{int(dur)//60}:{int(dur)%60:02d}"

            # ── employee ──
            emp = v.get("employee_name") or v.get("employee_id") or "—"

            # ── size: ưu tiên file_size_mb, fallback size_mb (key cũ) ──
            sz_mb = v.get("file_size_mb") or v.get("size_mb", 0)

            # ── order code ──
            order = v.get("order_code") or v.get("qr_code") or "—"

            # ── thời gian: start_time ISO hoặc date+time riêng ──
            start_iso = v.get("start_time", "")
            if start_iso and len(start_iso) > 10:
                time_disp = start_iso[11:16]
                date_disp = start_iso[:10]
            else:
                time_disp = v.get("time", "")[:5]
                date_disp = v.get("date", "")

            cam_item = QTableWidgetItem(v.get("camera_id", ""))
            cam_item.setForeground(QColor(_ACCENT))
            cam_item.setFont(QFont("Consolas", 11, QFont.Bold))

            order_item = QTableWidgetItem(order)
            order_item.setForeground(QColor(_YELLOW))

            size_item = QTableWidgetItem(f"{sz_mb} MB")
            size_item.setForeground(QColor(_ORANGE))

            vals = [
                (cam_item, None),
                (order_item, None),
                (QTableWidgetItem(emp), None),
                (QTableWidgetItem(v.get("department", "—")), None),
                (QTableWidgetItem(date_disp), None),
                (QTableWidgetItem(time_disp), None),
                (QTableWidgetItem(dur_txt), None),
                (size_item, None),
            ]
            for c, (item, _) in enumerate(vals):
                self.table.setItem(r, c, item)

            # ── Actions: full path tuyệt đối ──
            rel = v.get("file_path") or v.get("path") or v.get("filename", "")
            full_path = os.path.normpath(os.path.join(self._storage, rel))
            aw = QWidget(); aw.setStyleSheet("background:transparent;")
            ahl = QHBoxLayout(aw); ahl.setContentsMargins(4, 2, 4, 2); ahl.setSpacing(4)
            b_play = QPushButton("▶")
            b_play.setFixedSize(28, 26)
            b_play.setStyleSheet(_BTN_GREEN.replace("padding:5px 12px", "padding:0"))
            b_play.clicked.connect(lambda _, p=full_path: self._play(p))
            b_dl = QPushButton("⬇")
            b_dl.setFixedSize(28, 26)
            b_dl.setStyleSheet(_BTN_BLUE.replace("padding:5px 12px", "padding:0"))
            
            b_dl.clicked.connect(lambda _, p=full_path, n=v.get("filename",""): self._download(p, n))
            ahl.addWidget(b_play); ahl.addWidget(b_dl)
            self.table.setCellWidget(r, 8, aw)

    def _filter(self):
        kw = self.f_kw.text().lower()
        cam = self.f_cam.currentText()
        date_text = self.f_date.text().strip()
        order = self.f_order.text().strip().lower()

        date = ""
        if date_text:
            date = self._vn_date_to_iso(date_text)
            if date is None:
                self._fill([])
                return
        order = self.f_order.text().strip().lower()
        res = [
            v for v in self._videos
            if (not kw or any(kw in str(v.get(f, "")).lower()
                            for f in ("camera_id","camera_name","order_code","qr_code","employee_id","employee_name","filename","date")))
            and (cam == "Tất cả camera" or v.get("camera_id") == cam)
            and (not date or v.get("date", "").startswith(date))
            and (not order or order in v.get("order_code", "").lower())
        ]
        self._fill(res)

    def _rebuild(self):
        if self._thread and self._thread.isRunning():
            return

        self._config = load_config(force=True)
        self._storage = self._config.get("storage_path", "records")
        self.lbl_path.setText(f"📂 {self._storage}")

        self.btn_rebuild.setEnabled(False)
        self.btn_rebuild.setText("⏳ Đang quét...")
        self._thread = _RebuildThread(self._storage)
        self._thread.done.connect(self._on_rebuild_done)
        self._thread.error.connect(self._on_rebuild_error)
        self._thread.start()

    def _on_rebuild_done(self, idx: dict):
        self.btn_rebuild.setEnabled(True)
        self.btn_rebuild.setText("🔄 Cập nhật index")
        self._videos = idx.get("videos", [])
        self._update_stats()
        self._update_cam_filter()
        self._fill(self._videos)
        QMessageBox.information(
            self, "✅ Xong",
            f"Video mới: {idx.get('new', 0)}\n"
            f"Tổng video: {idx.get('total', 0)}\n"
            f"Đã tạo index.html"
        )

    def _on_rebuild_error(self, msg: str):
        self.btn_rebuild.setEnabled(True)
        self.btn_rebuild.setText("🔄 Cập nhật index")
        QMessageBox.critical(self, "Lỗi", msg)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục video", self._storage)
        if folder:
            self._storage = folder
            self.lbl_path.setText(f"📂 {folder}")
            self._load()

    def _play(self, path: str):
        path = os.path.normpath(path)
        if not os.path.exists(path):
            QMessageBox.warning(self, "Kh\u00f4ng t\u00ecm th\u1ea5y",
                                f"File kh\u00f4ng t\u1ed3n t\u1ea1i:\n{path}\n\n"
                                f"Ki\u1ec3m tra th\u01b0 m\u1ee5c: {self._storage}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi phát video", str(e))

    def _download(self, src: str, filename: str):
        if not os.path.exists(src):
            QMessageBox.warning(self, "Không tìm thấy", f"File không tồn tại:\n{src}")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Lưu video", filename)
        if dest:
            import shutil
            shutil.copy2(src, dest)
            QMessageBox.information(self, "✅ Đã lưu", f"Đã lưu tại:\n{dest}")

    def _open_html(self):
        html_path = os.path.join(self._storage, "index.html")
        if not os.path.exists(html_path):
            generate_html_report(self._storage)
        try:
            if sys.platform == "win32":
                os.startfile(html_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", html_path])
            else:
                subprocess.Popen(["xdg-open", html_path])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


# ─────────────────────────────────────────────
# HR PAGE – Widget chính gắn vào stack index 3
# ─────────────────────────────────────────────
class HRPage(QWidget):
    """
    Trang quản lý nhân sự.
    Chỉ còn Nhân sự, không chứa tab Video nữa.
    """

    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_HRTab())

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ──────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(148)
        sidebar.setStyleSheet(
            f"QFrame{{background:{_PANEL2};border:none;border-right:1px solid {_BORDER};border-radius:0;}}"
        )
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(10, 18, 10, 18)
        sb.setSpacing(6)

        lbl = QLabel("TRA CỨU")
        lbl.setStyleSheet(
            f"color:{_MUTED};font-size:10px;font-weight:700;letter-spacing:2px;background:transparent;border:none;padding:0 4px;"
        )
        sb.addWidget(lbl)

        self._tab_btns = []
        for i, (icon, text) in enumerate([("👥", "Nhân sự"), ("🎬", "Video")]):
            btn = QPushButton(f"{icon}  {text}")
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton{{
                    background:transparent;color:{_MUTED};border:none;
                    text-align:left;padding:10px 12px;border-radius:6px;font-size:13px;
                }}
                QPushButton:hover{{background:rgba(255,255,255,.05);color:{_TEXT};}}
                QPushButton:checked{{background:rgba(15,98,254,.25);color:#ffffff;font-weight:700;}}
            """)
            btn.clicked.connect(lambda _, idx=i: self._switch(idx))
            sb.addWidget(btn)
            self._tab_btns.append(btn)

        sb.addStretch()
        outer.addWidget(sidebar)

        # ── Stacked content ──────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(_HRTab())    # 0
        self._stack.addWidget(_VideoTab()) # 1
        outer.addWidget(self._stack)

        self._switch(0)

    def _switch(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, b in enumerate(self._tab_btns):
            b.setChecked(i == idx)


class VideoPage(_VideoTab):
    
    
    def _open_multiplay(self):
        exe_path = os.path.abspath("multiplay.exe")

        if not os.path.exists(exe_path):
            QMessageBox.warning(
                self,
                "Không tìm thấy",
                f"Không tìm thấy multiplay.exe:\n{exe_path}"
            )
            return

        try:
            subprocess.Popen([exe_path], shell=False)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi mở MultiPlay",
                str(e)
            )
