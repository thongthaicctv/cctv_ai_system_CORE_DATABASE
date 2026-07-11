import unittest
from unittest.mock import patch

from license.license_manager import LicenseManager


class LicenseManagerTests(unittest.TestCase):
    def test_device_not_found_blocks_even_when_cache_exists(self):
        cached_license = {
            "device_id": "ATG-TEST-0000-0000",
            "hardware_hash": "abc",
            "status": "active",
        }

        with patch("license.license_manager.get_device_id", return_value="ATG-TEST-0000-0000"), patch(
            "license.license_manager.get_hardware_hash", return_value="abc"
        ), patch("license.license_manager.CacheManager.load", return_value=cached_license), patch(
            "license.license_manager.update_cache_from_google",
            return_value=(False, "DEVICE_ID_NOT_FOUND"),
        ):
            manager = LicenseManager()
            ok, msg = manager.check()

        self.assertFalse(ok)
        self.assertIn("DEVICE_ID", msg)


if __name__ == "__main__":
    unittest.main()
