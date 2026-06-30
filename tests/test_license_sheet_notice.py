import unittest
from unittest.mock import patch

from license.google_sync import fetch_license_from_google
from license.license_manager import LicenseManager


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class LicenseSheetNoticeTests(unittest.TestCase):
    def test_fetch_license_reads_note_column(self):
        csv_text = (
            "DEVICE_ID,SIGNED_TOKEN,NOTE\n"
            "ATG-TEST-1,test-token,can update phan mem\n"
        )

        with patch("license.google_sync.requests.get", return_value=_Response(csv_text)):
            with patch(
                "license.google_sync.verify_signed_token",
                return_value={"device_id": "ATG-TEST-1"},
            ):
                data, msg = fetch_license_from_google("ATG-TEST-1")

        self.assertEqual(msg, "GOOGLE_SYNC_OK")
        self.assertEqual(data["sheet_note"], "can update phan mem")

    def test_none_note_is_not_startup_notice(self):
        manager = LicenseManager.__new__(LicenseManager)
        manager.data = {"_sheet_note": "none"}
        self.assertIsNone(manager._sheet_notice_from_data())

    def test_text_note_is_startup_notice(self):
        manager = LicenseManager.__new__(LicenseManager)
        manager.data = {"_sheet_note": "can update phan mem"}
        self.assertEqual(manager._sheet_notice_from_data(), "can update phan mem")


if __name__ == "__main__":
    unittest.main()
