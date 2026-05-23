import cv2
from datetime import datetime
import json
import os
import sys
import time
from pathlib import Path

try:
    from services.qr_decoder import decode_qr_texts, decode_qr_texts_fast
    from utils.url_helper import open_rtsp_capture, safe_rtsp
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from services.qr_decoder import decode_qr_texts, decode_qr_texts_fast
    from utils.url_helper import open_rtsp_capture, safe_rtsp

RTSP_URL = "rtsp://admin:Antn%402016@192.168.1.185:554/media/video2"

SAVE_LOG = True
LOG_FILE = "barcode_log.json"
WINDOW_NAME = "RTSP QR SCANNER"


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(records):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def smart_decode(frame):
    results = decode_qr_texts_fast(frame, include_barcodes=True)
    if results:
        return results

    return decode_qr_texts(frame, include_barcodes=True)

def main():
    print("Dang ket noi RTSP...")

    rtsp_url = safe_rtsp(RTSP_URL)
    cap = open_rtsp_capture(rtsp_url)

    if not cap.isOpened():
        print("Khong mo duoc RTSP")
        return

    log_records = load_log()
    session_scanned = {}

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Mat frame... reconnect")
            cap.release()
            time.sleep(1)
            cap = open_rtsp_capture(rtsp_url)
            continue

        barcodes = smart_decode(frame)

        for data in barcodes:
            print(data)

        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
