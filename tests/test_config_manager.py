import unittest

from core.config_manager import _normalize_config, find_duplicate_camera_sources


class ConfigManagerTests(unittest.TestCase):
    def test_find_duplicate_camera_sources_groups_enabled_cameras(self):
        data = {
            "cameras": [
                {
                    "id": "1",
                    "name": "CAM-1",
                    "enabled": True,
                    "rtsp_main": "rtsp://admin:pass@192.168.1.10:554/live/0/main",
                    "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
                },
                {
                    "id": "2",
                    "name": "CAM-2",
                    "enabled": True,
                    "rtsp_main": "rtsp://admin:pass@192.168.1.10:554/live/0/main",
                    "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
                },
                {
                    "id": "3",
                    "name": "CAM-3",
                    "enabled": False,
                    "rtsp_main": "rtsp://admin:pass@192.168.1.10:554/live/0/main",
                    "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
                },
            ]
        }

        groups = find_duplicate_camera_sources(data)

        self.assertEqual(len(groups), 1)
        self.assertEqual([item["id"] for item in groups[0]], ["1", "2"])

    def test_legacy_slow_qr_config_is_migrated_to_stable_defaults(self):
        data = {
            "qr": {
                "scan_interval": 0.18,
                "full_scan_every_frames": 10,
                "slow_scan_every_frames": 15,
                "max_width": 960,
            }
        }

        normalized = _normalize_config(data)

        self.assertEqual(
            normalized["qr"],
            {
                "scan_interval": 0.01,
                "full_scan_every_frames": 2,
                "slow_scan_every_frames": 5,
                "max_width": 960,
                "heavy_scan_max_width": 1280,
                "drop_stale_frames": 1,
            },
        )

    def test_legacy_fast_qr_config_is_migrated_to_stable_defaults(self):
        data = {
            "qr": {
                "scan_interval": 0.01,
                "full_scan_every_frames": 2,
                "slow_scan_every_frames": 8,
                "max_width": 1280,
            }
        }

        normalized = _normalize_config(data)

        self.assertEqual(
            normalized["qr"],
            {
                "scan_interval": 0.01,
                "full_scan_every_frames": 2,
                "slow_scan_every_frames": 5,
                "max_width": 960,
                "heavy_scan_max_width": 1280,
                "drop_stale_frames": 1,
            },
        )

    def test_legacy_turbo_qr_config_is_migrated_to_stable_defaults(self):
        data = {
            "qr": {
                "scan_interval": 0.003,
                "full_scan_every_frames": 1,
                "slow_scan_every_frames": 4,
                "max_width": 1600,
            }
        }

        normalized = _normalize_config(data)

        self.assertEqual(
            normalized["qr"],
            {
                "scan_interval": 0.01,
                "full_scan_every_frames": 2,
                "slow_scan_every_frames": 5,
                "max_width": 960,
                "heavy_scan_max_width": 1280,
                "drop_stale_frames": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
