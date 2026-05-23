import unittest

from core.config_manager import find_duplicate_camera_sources


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


if __name__ == "__main__":
    unittest.main()
