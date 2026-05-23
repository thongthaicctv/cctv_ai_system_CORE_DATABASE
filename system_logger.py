import os
from datetime import datetime, time

LOG_FILE = "logs/camera_events.log"

os.makedirs("logs", exist_ok=True)

def log(message):
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"{time} | {message}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")