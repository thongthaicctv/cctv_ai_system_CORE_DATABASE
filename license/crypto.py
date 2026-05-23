import base64
import json

SECRET = "CCTV_AI_SYSTEM_2026"


def encrypt_data(data: dict):
    raw = json.dumps(data).encode()
    return base64.b64encode(raw).decode()


def decrypt_data(data: str):
    raw = base64.b64decode(data.encode())
    return json.loads(raw.decode())