import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.log_file = "logs/camera_events.log"
        self.last_size = 0

        layout = QVBoxLayout(self)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.document().setMaximumBlockCount(250)
        self.log_box.setStyleSheet(
            """
            background-color: #0b0f14;
            color: #00ff9c;
            font-family: Consolas;
            font-size: 12px;
            border: 1px solid #222;
            """
        )
        layout.addWidget(self.log_box)

        self.timer = QTimer()
        self.timer.timeout.connect(self.load_new_logs)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_new_logs()
        self.timer.start(1000)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def load_new_logs(self):
        if not os.path.exists(self.log_file):
            return

        size = os.path.getsize(self.log_file)
        if size < self.last_size:
            self.last_size = 0
            self.log_box.clear()

        if size == self.last_size:
            return

        with open(self.log_file, "r", encoding="utf-8") as file_obj:
            file_obj.seek(self.last_size)
            new_data = file_obj.read()

        self.last_size = size
        if not new_data:
            return

        self.log_box.appendPlainText(new_data.strip())
        cursor = self.log_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_box.setTextCursor(cursor)
