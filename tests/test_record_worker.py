import unittest
import os
import tempfile
import threading
import time

from services.record_worker import RecordWorker


class DummyState:
    def get(self, _cam_id):
        return {}

    def set_video(self, _cam_id, _file_path):
        pass

    def clear_error(self, _cam_id):
        pass

    def set_error(self, _cam_id, _message):
        pass

    def set_record_error(self, _cam_id, _message):
        pass

    def mark_record_started(self, _cam_id, _file_path):
        pass

    def fail_record(self, _cam_id, _message, clear_employee=False):
        pass

    def stop_record(self, _cam_id, clear_employee=False):
        pass


class RecordWorkerTests(unittest.TestCase):
    def test_ffmpeg_copy_command_supports_multiple_outputs(self):
        worker = RecordWorker(
            {"id": "1", "name": "CAM-1"},
            DummyState(),
            "G:/recordings",
            300,
        )

        command = worker._ffmpeg_copy_command(
            "ffmpeg.exe",
            "rtsp://camera/main",
            ["G:/a.mkv", "G:/b.mkv"],
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe",
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-rtsp_transport",
                "tcp",
                "-fflags",
                "+genpts",
                "-use_wallclock_as_timestamps",
                "1",
                "-i",
                "rtsp://camera/main",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c",
                "copy",
                "-f",
                "matroska",
                "G:/a.mkv",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c",
                "copy",
                "-f",
                "matroska",
                "G:/b.mkv",
            ],
        )

    def test_wait_for_output_ready_requires_real_file_growth(self):
        worker = RecordWorker(
            {
                "id": "1",
                "name": "CAM-1",
                "record_startup_ready_timeout_seconds": 1.0,
                "record_startup_min_file_bytes": 32,
            },
            DummyState(),
            "G:/recordings",
            300,
        )

        class DummyProcess:
            stderr = None

            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "sample.mkv")

            def writer():
                time.sleep(0.1)
                with open(output_path, "wb") as fh:
                    fh.write(b"x" * 16)
                    fh.flush()
                time.sleep(0.25)
                with open(output_path, "ab") as fh:
                    fh.write(b"y" * 32)
                    fh.flush()

            thread = threading.Thread(target=writer, daemon=True)
            thread.start()

            ready, message = worker._wait_for_output_ready(DummyProcess(), [output_path])
            thread.join(timeout=1.0)

        self.assertTrue(ready, message)
        self.assertEqual(message, "")

    def test_wait_for_output_ready_rejects_static_empty_output(self):
        worker = RecordWorker(
            {
                "id": "1",
                "name": "CAM-1",
                "record_startup_ready_timeout_seconds": 0.4,
                "record_startup_min_file_bytes": 32,
            },
            DummyState(),
            "G:/recordings",
            300,
        )

        class DummyProcess:
            stderr = None

            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "sample.mkv")
            ready, message = worker._wait_for_output_ready(DummyProcess(), [output_path])

        self.assertFalse(ready)
        self.assertIn("startup verify timeout", message)

    def test_ffmpeg_probe_command_reads_single_video_frame(self):
        worker = RecordWorker(
            {"id": "1", "name": "CAM-1"},
            DummyState(),
            "G:/recordings",
            300,
        )

        command = worker._ffmpeg_probe_command("ffmpeg.exe", "rtsp://camera/sub")

        self.assertEqual(
            command,
            [
                "ffmpeg.exe",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-rtsp_transport",
                "tcp",
                "-fflags",
                "+genpts",
                "-use_wallclock_as_timestamps",
                "1",
                "-i",
                "rtsp://camera/sub",
                "-map",
                "0:v:0",
                "-an",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
        )


if __name__ == "__main__":
    unittest.main()
