import unittest
from unittest.mock import patch

from services.qr_engine import QREngine
from services.qr_worker import QRWorker


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
            def _parse_manual_cmd(self, text):
                return ("s01", "test-order")

            def _find_camera_by_sub(self, prefix):
                return "1" if prefix == "s01" else None

            def _handle_command(self, scan_cam_id, text):
                calls.append((scan_cam_id, text))

        engine.command_worker = StubCommandWorker()
        engine.workers.clear()

        engine.handle_manual_command("s01test-order")

        self.assertEqual(calls, [("1", "s01test-order")])

    def test_s_prefix_uses_real_configured_camera_id(self):
        worker = QRWorker.__new__(QRWorker)
        config = {
            "cameras": [
                {"id": "1", "name": "DEBUG-1"},
                {"id": "2", "name": "Si-1"},
                {"id": "3", "name": "Si-2"},
                {"id": "4", "name": "Si-3"},
                {"id": "5", "name": "Si-4"},
            ]
        }

        with patch("services.qr_worker.load_config", return_value=config):
            self.assertEqual(worker._find_camera_by_sub("s01"), "1")
            self.assertEqual(worker._find_camera_by_sub("s04"), "4")
            self.assertEqual(worker._find_camera_by_sub("s05"), "5")
            self.assertEqual(worker._find_camera_by_sub("c04"), "4")

    def test_s_prefix_uses_camera_id_even_when_card_position_differs(self):
        worker = QRWorker.__new__(QRWorker)
        config = {
            "cameras": [
                {"id": "1", "name": "DEBUG-1"},
                {"id": "7", "name": "VP-T2-1"},
                {"id": "8", "name": "Ecom-1"},
            ]
        }

        with patch("services.qr_worker.load_config", return_value=config):
            self.assertEqual(worker._find_camera_by_sub("s07"), "7")
            self.assertEqual(worker._find_camera_by_sub("s08"), "8")
            self.assertIsNone(worker._find_camera_by_sub("s02"))
            self.assertEqual(worker._find_camera_by_sub("c07"), "7")

    def test_scan_camera_id_maps_to_scanner_id_from_real_camera_id(self):
        worker = QRWorker.__new__(QRWorker)
        config = {
            "cameras": [
                {"id": "5", "name": "Si-4"},
                {"id": "8", "name": "Ecom-1"},
            ]
        }

        with patch("services.qr_worker.load_config", return_value=config):
            self.assertEqual(worker._scanner_id_for_scan_camera("5"), "s05")
            self.assertEqual(worker._scanner_id_for_scan_camera("8"), "s08")

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

    def test_unprefixed_camera_scan_records_from_scanning_camera_mapping(self):
        worker = QRWorker.__new__(QRWorker)
        worker._handle_raw_business_scan = lambda _scan_cam_id, _text: False

        calls = []
        worker._start_order_targets = lambda targets, order: calls.append((targets, order)) or True

        config = {
            "cameras": [{"id": "1"}, {"id": "8"}],
            "record_mapping": {"1": ["1"], "8": ["8"]},
        }

        with patch("services.qr_worker.load_config", return_value=config), patch(
            "services.qr_worker.order_ok"
        ):
            worker._handle_command("8", "861881404914")

        self.assertEqual(calls, [(["8"], "861881404914")])

    def test_unprefixed_manual_command_still_uses_default_s01_mapping(self):
        worker = QRWorker.__new__(QRWorker)
        worker._handle_raw_business_scan = lambda _scan_cam_id, _text: False

        calls = []
        worker._start_order_targets = lambda targets, order: calls.append((targets, order)) or True

        config = {
            "cameras": [{"id": "1"}, {"id": "8"}],
            "record_mapping": {"1": ["1", "2"], "8": ["8"]},
        }

        with patch("services.qr_worker.load_config", return_value=config), patch(
            "services.qr_worker.order_ok"
        ):
            worker._handle_command("manual", "ORDER-MANUAL")

        self.assertEqual(calls, [(["1", "2"], "ORDER-MANUAL")])

    def test_unprefixed_stop_from_camera_stops_scanning_camera_mapping(self):
        worker = QRWorker.__new__(QRWorker)
        worker._handle_raw_business_scan = lambda _scan_cam_id, _text: False
        worker._has_active_handover_flow = lambda _scanner_id: False
        worker._save_mysql_ecom_video_before_stop = lambda *_args, **_kwargs: None
        worker.packing_action_state = {}

        class State:
            def __init__(self):
                self.stopped = []

            def get(self, _cam_id):
                return {}

            def stop_record(self, cam_id, clear_employee=False):
                self.stopped.append((cam_id, clear_employee))

        worker.state = State()
        config = {
            "cameras": [{"id": "1"}, {"id": "8"}],
            "record_mapping": {"1": ["1"], "8": ["8"]},
        }

        with patch("services.qr_worker.load_config", return_value=config), patch(
            "services.qr_worker.stop_ok"
        ):
            worker._handle_command("8", "STOP")

        self.assertEqual(worker.state.stopped, [("8", False)])

    def test_duplicate_order_does_not_restart_recording(self):
        worker = QRWorker.__new__(QRWorker)
        worker._record_worker_for_target = lambda _target_id: object()
        worker._save_mysql_ecom_video_before_stop = lambda *_args, **_kwargs: None

        class State:
            def __init__(self):
                self.started = []
                self.current = {"record_requested": True, "order_code": "ORDER-1"}

            def get(self, _cam_id):
                return dict(self.current)

            def start_record(self, cam_id, order_code=""):
                self.started.append((cam_id, order_code))
                self.current = {"record_requested": True, "order_code": order_code}

        worker.state = State()

        self.assertFalse(worker._start_order_targets(["8"], "ORDER-1"))
        self.assertEqual(worker.state.started, [])

        self.assertTrue(worker._start_order_targets(["8"], "ORDER-2"))
        self.assertEqual(worker.state.started, [("8", "ORDER-2")])

    def test_db_packing_session_is_stale_after_restart(self):
        worker = QRWorker.__new__(QRWorker)
        worker.packing_record_targets = {}
        self.assertFalse(
            worker._is_runtime_packing_session(
                "s01",
                {"id": 42, "master_order_code": "ORDER-1"},
            )
        )

    def test_packing_session_opened_in_runtime_is_active(self):
        worker = QRWorker.__new__(QRWorker)
        worker.packing_record_targets = {"packing:42:s01": ["1"]}
        self.assertTrue(
            worker._is_runtime_packing_session(
                "s01",
                {"id": 42, "master_order_code": "ORDER-1"},
            )
        )

    def test_same_visible_qr_is_not_accepted_every_five_seconds(self):
        worker = QRWorker.__new__(QRWorker)
        worker.cam = {"qr_duplicate_seconds": 5}
        worker.last_seen = {}

        with patch("services.qr_worker.time.time", side_effect=[1, 5, 9, 15]):
            self.assertTrue(worker._should_accept("QR-1"))
            self.assertFalse(worker._should_accept("QR-1"))
            self.assertFalse(worker._should_accept("QR-1"))
            self.assertTrue(worker._should_accept("QR-1"))

    def test_qr_worker_uses_global_scan_config_with_camera_override(self):
        worker = QRWorker.__new__(QRWorker)
        worker.cam = {"qr_scan_interval": 0.05}
        worker.qr_config = {
            "scan_interval": 0.02,
            "full_scan_every_frames": 3,
            "slow_scan_every_frames": 15,
            "max_width": 960,
            "heavy_scan_max_width": 1280,
            "drop_stale_frames": 1,
        }

        self.assertEqual(worker._qr_setting("scan_interval", 1.0), 0.05)
        self.assertEqual(worker._qr_setting("max_width", 1600), 960)
        self.assertEqual(worker._qr_setting("slow_scan_every_frames", 4), 15)


if __name__ == "__main__":
    unittest.main()
