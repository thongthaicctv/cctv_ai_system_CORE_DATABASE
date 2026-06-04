import base64
import json

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from .public_key import PUBLIC_KEY_HEX


TOKEN_ALG = "Ed25519"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    text = (text or "").strip()
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def _canonical_json(data: dict) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def create_signed_token(payload: dict, private_key_hex: str) -> str:
    signing_key = SigningKey(bytes.fromhex(private_key_hex.strip()))
    payload_bytes = _canonical_json(dict(payload or {}))
    signature = signing_key.sign(payload_bytes).signature
    return json.dumps(
        {
            "alg": TOKEN_ALG,
            "payload": _b64url_encode(payload_bytes),
            "signature": _b64url_encode(signature),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def verify_signed_token(token: str) -> dict:
    try:
        envelope = json.loads((token or "").strip())
        if envelope.get("alg") != TOKEN_ALG:
            raise ValueError("Unsupported license token algorithm")

        payload_bytes = _b64url_decode(envelope.get("payload", ""))
        signature = _b64url_decode(envelope.get("signature", ""))

        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY_HEX))
        verify_key.verify(payload_bytes, signature)

        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("License payload is not an object")
        return payload
    except BadSignatureError as exc:
        raise ValueError("License signature invalid") from exc
    except Exception as exc:
        raise ValueError(f"License token invalid: {exc}") from exc


def encrypt_data(data: dict):
    raise RuntimeError("Unsigned license cache is no longer supported")


def decrypt_data(data: str):
    return verify_signed_token(data)
