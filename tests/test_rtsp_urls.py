import unittest

from utils.url_helper import camera_record_rtsp_urls


class RtspUrlTests(unittest.TestCase):
    def test_camera_record_rtsp_urls_prefers_lowercase_main_variant(self):
        cam = {
            "rtsp_main": "rtsp://admin:pass@192.168.1.10:554/live/0/MAIN",
            "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
        }

        self.assertEqual(
            camera_record_rtsp_urls(cam),
            [
                "rtsp://admin:pass@192.168.1.10:554/live/0/main",
                "rtsp://admin:pass@192.168.1.10:554/live/0/MAIN",
                "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
            ],
        )

    def test_camera_record_rtsp_urls_removes_duplicates(self):
        cam = {
            "rtsp_main": "rtsp://admin:pass@192.168.1.10:554/live/0/main",
            "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/main",
        }

        self.assertEqual(
            camera_record_rtsp_urls(cam),
            ["rtsp://admin:pass@192.168.1.10:554/live/0/main"],
        )


if __name__ == "__main__":
    unittest.main()
