from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QFrame
from PySide6.QtCore import QTimer, Qt
import psutil
import shutil
import os


import time
from services.audio_service import disk_low


from core.config_manager import load_config
from core.gpu_acceleration import query_nvidia_gpu_status



class InfoCard(QFrame):
    def __init__(self, title):
        super().__init__()

        self.setMinimumHeight(130)


                

        self.setStyleSheet("""
        QFrame{
            background:#0f0f0f;
            border:1px solid #2d2d2d;
            border-radius:10px;
        }
        QLabel{
            color:white;
            border:none;
        }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("""
            font-size:45px;
            font-weight:bold;
            color:#ffffff;
            letter-spacing:1px;
        """)

        self.lbl_value = QLabel("...")
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setStyleSheet("""
            font-size:34px;
            font-weight:bold;
            color:#00ffaa;
        """)

        layout.addWidget(self.lbl_title)
        layout.addStretch()
        layout.addWidget(self.lbl_value)
        layout.addStretch()

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        self.record_path = self.load_storage_path()

        self.cards = {}
        
        self.last_disk_alert_time = 0
        self.disk_alert_limit_gb = 5
        self.disk_alert_interval_sec = 5 * 60


        grid = QGridLayout(self)
        grid.setContentsMargins(25, 25, 25, 25)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i, name in enumerate(["CPU", "RAM", "GPU", "DISK"]):
            card = InfoCard(name)
            self.cards[name] = card
            grid.addWidget(card, i // 2, i % 2)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_info)

    def showEvent(self, e):
        self.update_info()
        self.timer.start(3000)   # 3 giây update 1 lần

    def hideEvent(self, e):
        self.timer.stop()


    def get_video_storage_disk_path(self):
        """
        Chỉ lấy đúng ổ/thư mục đang lưu video theo storage_path trong config.json.
        Ví dụ:
            G:/ProVideoAiSystem  -> G:\
            D:/VIDEO             -> D:\
            C:/recordings        -> C:\
        """
        try:
            self.record_path = self.load_storage_path()

            path = os.path.abspath(self.record_path)

            drive = os.path.splitdrive(path)[0]

            if drive:
                return drive + "\\"

            # fallback nếu path không có drive
            return path

        except Exception as e:
            print("[DISK PATH ERROR]", e)
            return "C:\\"
    
    
    def update_info(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        try:
            disk_path = self.get_video_storage_disk_path()

            disk = shutil.disk_usage(disk_path)

            used = round(disk.used / 1024 / 1024 / 1024)
            total = round(disk.total / 1024 / 1024 / 1024)
            free = round(disk.free / 1024 / 1024 / 1024)

        except Exception as e:
            print("DISK ERROR:", e)

            disk_path = "N/A"
            used = 0
            total = 0
            free = 0
        
        

        except Exception as e:
            print("DISK ERROR:", e)

            used = 0
            total = 0
            free = 0

        self.check_disk_audio_alert(free)

        gpu = 0.0
        gpu_text = "N/A"
        gpu_status = query_nvidia_gpu_status()
        if gpu_status:
            gpu = gpu_status["utilization"]
            sessions = gpu_status["encoder_sessions"]
            if sessions > 0:
                gpu_text = f"{gpu:.0f}% | ENC {sessions}"
            else:
                gpu_text = f"{gpu:.0f}%"

        self.cards["CPU"].lbl_value.setText(f"{cpu}%")
        self.cards["RAM"].lbl_value.setText(f"{ram}%")
        self.cards["GPU"].lbl_value.setText(gpu_text)
        
        
        self.cards["DISK"].lbl_value.setText(
            f"{disk_path}  {used}/{total} GB\nFree {free} GB"
        )

        # Màu cảnh báo
        self.cards["CPU"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if cpu >= 95 else '#00ffaa'};"
        )

        self.cards["RAM"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if ram >= 95 else '#00ffaa'};"
        )

        self.cards["GPU"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if gpu >= 95 else '#00ffaa'};"
        )

        self.cards["DISK"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if free < 10 else '#00ffaa'};"
        )

    def load_storage_path(self):
        try:
            config = load_config()
            return config.get("storage_path", "C:\\")
        except Exception as e:
            print("LOAD CONFIG ERROR:", e)
            return "C:\\"

    def check_disk_audio_alert(self, free_gb):
        try:
            if free_gb >= self.disk_alert_limit_gb:
                return

            now = time.monotonic()

            if now - self.last_disk_alert_time < self.disk_alert_interval_sec:
                return

            self.last_disk_alert_time = now

            print(
                f"[DISK WARNING] Ổ lưu video còn thấp: {free_gb} GB "
                f"< {self.disk_alert_limit_gb} GB"
            )

            disk_low()

        except Exception as e:
            print("[DISK AUDIO ALERT ERROR]", e)