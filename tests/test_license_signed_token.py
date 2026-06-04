import json
import unittest
from unittest.mock import patch

from nacl.signing import SigningKey

from license.crypto import _b64url_decode, _b64url_encode, create_signed_token, verify_signed_token


class SignedLicenseTokenTests(unittest.TestCase):
    def test_signed_token_verifies_payload(self):
        signing_key = SigningKey.generate()
        private_key = signing_key.encode().hex()
        public_key = signing_key.verify_key.encode().hex()
        payload = {
            "device_id": "ATG-TEST-0001",
            "hardware_hash": "hash",
            "max_camera": 4,
            "expire_date": "2026-12-31",
            "status": "active",
        }

        with patch("license.crypto.PUBLIC_KEY_HEX", public_key):
            token = create_signed_token(payload, private_key)
            verified = verify_signed_token(token)

        self.assertEqual(verified["device_id"], "ATG-TEST-0001")
        self.assertEqual(verified["max_camera"], 4)

    def test_tampered_token_is_rejected(self):
        signing_key = SigningKey.generate()
        private_key = signing_key.encode().hex()
        public_key = signing_key.verify_key.encode().hex()
        payload = {
            "device_id": "ATG-TEST-0001",
            "hardware_hash": "hash",
            "max_camera": 4,
            "expire_date": "2026-12-31",
            "status": "active",
        }

        with patch("license.crypto.PUBLIC_KEY_HEX", public_key):
            token = create_signed_token(payload, private_key)
            envelope = json.loads(token)
            tampered_payload = json.loads(_b64url_decode(envelope["payload"]).decode("utf-8"))
            tampered_payload["max_camera"] = 99
            envelope["payload"] = _b64url_encode(
                json.dumps(
                    tampered_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            tampered = json.dumps(envelope, separators=(",", ":"))

            with self.assertRaises(ValueError):
                verify_signed_token(tampered)


if __name__ == "__main__":
    unittest.main()
