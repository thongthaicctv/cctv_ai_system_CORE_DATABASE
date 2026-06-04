import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from license.crypto import create_signed_token, verify_signed_token
from license.hardware import get_device_id, get_hardware_hash


DEFAULT_PRIVATE_KEY_FILE = r"D:\PYTHON-TCR\ATG_LICENSE_PRIVATE_KEY_DO_NOT_SHIP.txt"


def _read_private_key(path: str) -> str:
    path = path or os.environ.get("ATG_LICENSE_PRIVATE_KEY_FILE") or DEFAULT_PRIVATE_KEY_FILE
    return Path(path).read_text(encoding="ascii").strip()


def _base_payload(args):
    return {
        "license_id": args.license_id or f"ATG-{datetime.now():%Y%m%d%H%M%S}",
        "customer": args.customer,
        "device_id": args.device_id,
        "hardware_hash": args.hardware_hash,
        "max_camera": int(args.max_camera),
        "expire_date": args.expire_date,
        "offline_days": int(args.offline_days),
        "status": args.status,
        "issued_at": datetime.now().isoformat(timespec="seconds"),
        "features": [item.strip() for item in args.features.split(",") if item.strip()],
    }


def cmd_create(args):
    private_key = _read_private_key(args.private_key_file)
    payload = _base_payload(args)
    token = create_signed_token(payload, private_key)
    if args.out:
        Path(args.out).write_text(token, encoding="utf-8")
    print(token)


def cmd_current_machine(args):
    args.device_id = get_device_id()
    args.hardware_hash = get_hardware_hash()
    cmd_create(args)


def cmd_verify(args):
    token = Path(args.token_file).read_text(encoding="utf-8") if args.token_file else args.token
    payload = verify_signed_token(token)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="ATG signed license token admin tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_create_args(p):
        p.add_argument("--private-key-file", default="")
        p.add_argument("--license-id", default="")
        p.add_argument("--customer", default="ATG Customer")
        p.add_argument("--device-id", required=True)
        p.add_argument("--hardware-hash", required=True)
        p.add_argument("--max-camera", type=int, required=True)
        p.add_argument("--expire-date", required=True, help="YYYY-MM-DD")
        p.add_argument("--offline-days", type=int, default=30)
        p.add_argument("--status", default="active", choices=["active", "disabled", "blocked"])
        p.add_argument("--features", default="record,mysql,packing")
        p.add_argument("--out", default="")

    p_create = sub.add_parser("create", help="Create token for a specific machine")
    add_create_args(p_create)
    p_create.set_defaults(func=cmd_create)

    p_current = sub.add_parser("current-machine", help="Create token for this machine")
    p_current.add_argument("--private-key-file", default="")
    p_current.add_argument("--license-id", default="")
    p_current.add_argument("--customer", default="ATG Local Machine")
    p_current.add_argument("--max-camera", type=int, required=True)
    p_current.add_argument("--expire-date", required=True, help="YYYY-MM-DD")
    p_current.add_argument("--offline-days", type=int, default=30)
    p_current.add_argument("--status", default="active", choices=["active", "disabled", "blocked"])
    p_current.add_argument("--features", default="record,mysql,packing")
    p_current.add_argument("--out", default="")
    p_current.set_defaults(func=cmd_current_machine)

    p_verify = sub.add_parser("verify", help="Verify and print token payload")
    p_verify.add_argument("--token", default="")
    p_verify.add_argument("--token-file", default="")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
