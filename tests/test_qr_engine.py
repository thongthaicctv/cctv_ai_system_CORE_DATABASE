import unittest

from services.qr_engine import QREngine


class DummyQREngine(QREngine):
    def __init__(self):
        self.started_ids = []
        super().__init__(state=None)

    def start_camera(self, cam):
        if not cam.get("enabled", True):
            return
        self.started_ids.append(str(cam.get("id")))


class QREngineTests(unittest.TestCase):
    def test_scan_camera_ids_only_uses_non_empty_mapping_rows(self):
        cameras = [
            {"id": "1", "enabled": True},
            {"id": "2", "enabled": True},
            {"id": "3", "enabled": True},
        ]
        record_mapping = {
            "1": ["1", "2", "3"],
            "2": [],
            "3": [],
        }

        self.assertEqual(
            QREngine.scan_camera_ids(cameras, record_mapping),
            {"1"},
        )

    def test_start_all_only_starts_scan_source_cameras(self):
        cameras = [
            {"id": "1", "enabled": True},
            {"id": "2", "enabled": True},
            {"id": "3", "enabled": False},
        ]
        record_mapping = {
            "1": ["1", "2"],
            "2": [],
            "3": ["3"],
        }

        engine = DummyQREngine()
        engine.start_all(cameras, record_mapping)

        self.assertEqual(engine.started_ids, ["1"])

    def test_manual_command_does_not_depend_on_running_scan_workers(self):
        engine = QREngine(state=None)

        calls = []

        class StubCommandWorker:
            def _handle_command(self, scan_cam_id, text):
                calls.append((scan_cam_id, text))

        engine.command_worker = StubCommandWorker()
        engine.workers.clear()

        engine.handle_manual_command("s01test-order")

        self.assertEqual(calls, [("manual", "s01test-order")])

    def test_start_all_skips_duplicate_scan_rtsp_sources(self):
        cameras = [
            {
                "id": "1",
                "enabled": True,
                "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
            },
            {
                "id": "2",
                "enabled": True,
                "rtsp_sub": "rtsp://admin:pass@192.168.1.10:554/live/0/sub",
            },
            {
                "id": "3",
                "enabled": True,
                "rtsp_sub": "rtsp://admin:pass@192.168.1.11:554/live/0/sub",
            },
        ]
        record_mapping = {
            "1": ["1"],
            "2": ["2"],
            "3": ["3"],
        }

        engine = DummyQREngine()
        engine.start_all(cameras, record_mapping)

        self.assertEqual(engine.started_ids, ["1", "3"])


if __name__ == "__main__":
    unittest.main()
