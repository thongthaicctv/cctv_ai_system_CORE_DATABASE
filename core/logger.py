import os
from datetime import datetime

LOG_FILE = "logs/camera_events.log"


def write_log(camera_name, status):
    os.makedirs("logs", exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now} | {camera_name} | {status}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

def write_license_log(message):

    os.makedirs("logs", exist_ok=True)

    log_file = "logs/license.log"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"{now} | {message}\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)