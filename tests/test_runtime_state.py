import unittest

from core.runtime_state import RuntimeState


class RuntimeStateTests(unittest.TestCase):
    def test_start_record_sets_waiting_status_until_worker_confirms(self):
        state = RuntimeState()
        state.add_camera("1")

        state.start_record("1", order_code="ORDER-1")
        snapshot = state.get("1")

        self.assertFalse(snapshot["recording"])
        self.assertTrue(snapshot["record_requested"])
        self.assertTrue(snapshot["record_pending"])
        self.assertEqual(snapshot["status"], "RECORD_WAIT")

    def test_mark_record_started_promotes_state_to_recording(self):
        state = RuntimeState()
        state.add_camera("1")
        state.start_record("1", order_code="ORDER-1")

        state.mark_record_started("1", "D:/videos/a.mkv")
        snapshot = state.get("1")

        self.assertTrue(snapshot["recording"])
        self.assertTrue(snapshot["record_requested"])
        self.assertFalse(snapshot["record_pending"])
        self.assertEqual(snapshot["video_file"], "D:/videos/a.mkv")
        self.assertEqual(snapshot["status"], "RECORDING")

    def test_fail_record_exposes_record_error_status(self):
        state = RuntimeState()
        state.add_camera("1")
        state.start_record("1", order_code="ORDER-1")

        state.fail_record("1", "Cannot start FFmpeg recording")
        snapshot = state.get("1")

        self.assertFalse(snapshot["recording"])
        self.assertFalse(snapshot["record_requested"])
        self.assertFalse(snapshot["record_pending"])
        self.assertEqual(snapshot["record_error"], "Cannot start FFmpeg recording")
        self.assertEqual(snapshot["status"], "RECORD_ERROR")


if __name__ == "__main__":
    unittest.main()
