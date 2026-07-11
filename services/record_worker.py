import os
import shutil
import subprocess
import threading
import time
from datetime import datetime

from PySide6.QtWidgets import QApplication

from core.resource_paths import resource_path
from services.audio_service import record_error
from services.record_video_db import upsert_closed_record_video
from system_logger import log
from utils.url_helper import camera_record_rtsp_urls, camera_source_key


DEFAULT_RECORD_AUTO_STOP_SECONDS = 300
WAIT_RECORD_UPDATE_TIMEOUT_SECONDS = 1.0
RETRY_DELAY_SECONDS = 1.0
RECORD_ERROR_SOUND_INTERVAL_SECONDS = 10.0
FFMPEG_STARTUP_CHECK_SECONDS = 2.0
FFMPEG_POLL_DELAY_SECONDS = 0.2
DEFAULT_RECORD_STARTUP_READY_TIMEOUT_SECONDS = 10.0
DEFAULT_RECORD_STARTUP_MIN_FILE_BYTES = 512
DEFAULT_RECORD_STARTUP_PROBE_TIMEOUT_SECONDS = 12.0
SHARED_RECORD_JOIN_WINDOW_SECONDS = 0.4
SHARED_RECORD_WAIT_SECONDS = 15.0
FFMPEG_STDERR_TAIL_CHARS = 4000
RECORD_CONTAINER_MKV = "matroska"
RECORD_CONTAINER_MPEGTS = "mpegts"
RECORD_EXTENSION_MKV = ".mkv"
RECORD_EXTENSION_MPEGTS = ".ts"
FFMPEG_PATHS = (
    r"C:\ffmpeg\bin\ffmpeg.exe",
    "ffmpeg",
)


def hidden_process_flags():
    startupinfo = None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    if os.name == "nt" and hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)

    return startupinfo, creationflags


class SharedSourceRegistry:
    def __init__(self):
        self._changed = threading.Condition()
        self._sessions = {}

    def _is_running_locked(self, session):
        process = session.get("process")
        return process is not None and process.poll() is None

    def _cleanup_locked(self, source_key=None):
        keys = [source_key] if source_key is not None else list(self._sessions.keys())
        for key in keys:
            session = self._sessions.get(key)
            if not session:
                continue
            if session.get("status") == "running" and not self._is_running_locked(session):
                self._sessions.pop(key, None)

    def claim_opening(self, source_key, leader_id, order_code):
        with self._changed:
            self._cleanup_locked(source_key)
            session = self._sessions.get(source_key)
            if session is not None:
                return False
            self._sessions[source_key] = {
                "status": "opening",
                "leader_id": str(leader_id),
                "order_code": order_code,
            }
            self._changed.notify_all()
            return True

    def publish_running(
        self,
        source_key,
        leader_id,
        order_code,
        member_ids,
        output_paths,
        process,
        started_mono,
    ):
        with self._changed:
            self._sessions[source_key] = {
                "status": "running",
                "leader_id": str(leader_id),
                "order_code": order_code,
                "member_ids": [str(cam_id) for cam_id in member_ids],
                "output_paths": {str(cam_id): path for cam_id, path in output_paths.items()},
                "process": process,
                "started_mono": started_mono,
            }
            self._changed.notify_all()

    def fail_opening(self, source_key):
        with self._changed:
            self._sessions.pop(source_key, None)
            self._changed.notify_all()

    def wait_for_running(self, source_key, order_code, cam_id, timeout):
        end_time = time.monotonic() + timeout
        cam_id = str(cam_id)

        with self._changed:
            while True:
                self._cleanup_locked(source_key)
                session = self._sessions.get(source_key)
                if (
                    session
                    and session.get("status") == "running"
                    and session.get("order_code") == order_code
                    and cam_id in session.get("member_ids", [])
                    and self._is_running_locked(session)
                ):
                    return dict(session)

                remaining = end_time - time.monotonic()
                if remaining <= 0:
                    return None

                self._changed.wait(remaining)

    def get_running(self, source_key):
        with self._changed:
            self._cleanup_locked(source_key)
            session = self._sessions.get(source_key)
            if (
                session
                and session.get("status") == "running"
                and self._is_running_locked(session)
            ):
                return dict(session)
            return None

    def stop(self, source_key):
        with self._changed:
            session = self._sessions.pop(source_key, None)
            self._changed.notify_all()
            return session


SHARED_SOURCE_REGISTRY = SharedSourceRegistry()


class RecordWorker:
    def __init__(self, cam, state, storage_path, auto_stop_seconds):
        self.cam = cam
        self.state = state
        self.storage_path = storage_path
        self.auto_stop_seconds = int(auto_stop_seconds or DEFAULT_RECORD_AUTO_STOP_SECONDS)
        self.running = True

        self.ffmpeg_process = None
        self.current_file = ""
        self.current_order = ""
        self.current_employee = ""
        self.current_employee_name = ""
        self.record_started_at = None
        self.record_started_mono = 0.0
        self.last_error_sound_mono = 0.0
        self.shared_source_key = None
        self.shared_member_ids = []
        self.shared_is_leader = False

    def run(self):
        cam_id = self.cam["id"]

        while self.running:
            snapshot = self.state.get(cam_id)

            if not self._record_requested(snapshot) or not snapshot.get("order_code"):
                self._close_session("STOP")
                snapshot = self.state.wait_for_record_update(
                    cam_id,
                    snapshot.get("record_version", 0),
                    timeout=WAIT_RECORD_UPDATE_TIMEOUT_SECONDS,
                )
                if not self.running:
                    break
                if not self._record_requested(snapshot) or not snapshot.get("order_code"):
                    continue

            if not self._has_active_session():
                if not self._open_session(snapshot):
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
            elif self.current_order != snapshot.get("order_code", ""):
                self._close_session("SWITCH")
                if not self._open_session(snapshot):
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
            else:
                self.current_employee = snapshot.get("employee_id", "")
                self.current_employee_name = snapshot.get("employee_name", "")

            if self._auto_stop_due():
                self._close_session("AUTO")
                self._stop_group_states(clear_employee=False)
                continue

            if self.shared_source_key:
                if not self._has_active_session():
                    message = "Shared source recording stopped unexpectedly"
                    self._log_runtime_stream_issue(message)
                    self._close_session("FAIL")
                    self._fail_group_states(message, clear_employee=False)
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
            else:
                if self.ffmpeg_process is None:
                    message = "FFmpeg process missing during recording"
                    self._log_runtime_stream_issue(message)
                    self._close_session("FAIL")
                    self._fail_group_states(message, clear_employee=False)
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue

                if self.ffmpeg_process.poll() is not None:
                    message = "FFmpeg recording stopped unexpectedly"
                    self._log_runtime_stream_issue(message)
                    self._close_session("FAIL")
                    self._fail_group_states(message, clear_employee=False)
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue

            time.sleep(FFMPEG_POLL_DELAY_SECONDS)

        self._close_session("STOP")

    def _open_session(self, snapshot):
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            self._set_startup_record_error("Missing ffmpeg for recording", play_sound=True)
            return False

        rtsp_candidates = self._record_rtsp_candidates()
        if not rtsp_candidates:
            self._set_startup_record_error("Missing main RTSP URL for recording", play_sound=True)
            return False

        order_code = snapshot.get("order_code", "")
        shared_source_ids = self._shared_source_camera_ids()
        if len(shared_source_ids) > 1:
            time.sleep(SHARED_RECORD_JOIN_WINDOW_SECONDS)

        candidate_ids = self._shared_source_candidate_ids(order_code)
        if len(candidate_ids) <= 1:
            return self._open_single_session(snapshot, ffmpeg, rtsp_candidates)

        source_key = self._shared_source_key()
        leader_id = self._leader_camera_id(candidate_ids)
        if str(self.cam["id"]) != leader_id:
            session = SHARED_SOURCE_REGISTRY.wait_for_running(
                source_key,
                order_code,
                self.cam["id"],
                timeout=SHARED_RECORD_WAIT_SECONDS,
            )
            if session:
                return self._attach_shared_session(session, snapshot)

            refreshed_ids = self._shared_source_candidate_ids(order_code)
            if self._leader_camera_id(refreshed_ids or [self.cam["id"]]) != str(self.cam["id"]):
                message = "Shared source leader did not start recording"
                self._set_startup_record_error(message, play_sound=True)
                return False

        if not SHARED_SOURCE_REGISTRY.claim_opening(source_key, str(self.cam["id"]), order_code):
            session = SHARED_SOURCE_REGISTRY.wait_for_running(
                source_key,
                order_code,
                self.cam["id"],
                timeout=SHARED_RECORD_WAIT_SECONDS,
            )
            if session:
                return self._attach_shared_session(session, snapshot)
            return self._open_single_session(snapshot, ffmpeg, rtsp_candidates)

        return self._open_shared_session(snapshot, ffmpeg, rtsp_candidates, candidate_ids, source_key)

    def _open_single_session(self, snapshot, ffmpeg, rtsp_candidates):
        startup_errors = []

        for attempt_index, rtsp in enumerate(rtsp_candidates):
            opened = self._open_record_process(
                snapshot,
                ffmpeg,
                rtsp,
                {str(self.cam["id"]): self.cam},
            )
            process = opened.get("process")
            if process is None:
                startup_errors.append(
                    self._describe_rtsp_candidate(rtsp, opened.get("error") or "startup failed")
                )
                continue

            output_path = opened["output_paths"][str(self.cam["id"])]
            self.ffmpeg_process = process
            self.current_file = output_path
            self.current_order = snapshot.get("order_code", "")
            self.current_employee = snapshot.get("employee_id", "")
            self.current_employee_name = snapshot.get("employee_name", "")
            self.record_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.record_started_mono = time.monotonic()
            self.shared_source_key = None
            self.shared_member_ids = [str(self.cam["id"])]
            self.shared_is_leader = False

            self._mark_record_started(self.cam["id"], output_path)

            if attempt_index > 0:
                self._set_record_issue(
                    self.cam["id"],
                    f"RTSP main lỗi, đang ghi bằng {self._rtsp_label(rtsp)}",
                )
                log(
                    f"{self.cam['name']} REC URL FALLBACK {self._describe_rtsp_candidate(rtsp, 'ok')}"
                )

            log(f"{self.cam['name']} START {self.current_order}")
            if opened.get("container") == RECORD_CONTAINER_MPEGTS:
                log(f"{self.cam['name']} REC FALLBACK MPEGTS {self.current_order}")
            return True

        error_message = self._startup_error_message(startup_errors)
        log(f"{self.cam['name']} REC START FAIL - | {error_message}")
        self._set_startup_record_error(error_message, play_sound=True)
        return False

    def _open_shared_session(self, snapshot, ffmpeg, rtsp_candidates, candidate_ids, source_key):
        startup_errors = []
        order_code = snapshot.get("order_code", "")
        output_cameras = {
            str(cam_id): self._camera_for_id(cam_id)
            for cam_id in candidate_ids
        }

        for attempt_index, rtsp in enumerate(rtsp_candidates):
            opened = self._open_record_process(
                snapshot,
                ffmpeg,
                rtsp,
                output_cameras,
            )
            process = opened.get("process")
            if process is None:
                startup_errors.append(
                    self._describe_rtsp_candidate(rtsp, opened.get("error") or "startup failed")
                )
                continue

            output_paths = opened["output_paths"]
            started_mono = time.monotonic()
            SHARED_SOURCE_REGISTRY.publish_running(
                source_key,
                self.cam["id"],
                order_code,
                candidate_ids,
                output_paths,
                process,
                started_mono,
            )

            self.ffmpeg_process = process
            self.current_file = output_paths[str(self.cam["id"])]
            self.current_order = order_code
            self.current_employee = snapshot.get("employee_id", "")
            self.current_employee_name = snapshot.get("employee_name", "")
            self.record_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.record_started_mono = started_mono
            self.shared_source_key = source_key
            self.shared_member_ids = [str(cam_id) for cam_id in candidate_ids]
            self.shared_is_leader = True

            if attempt_index > 0:
                for cam_id in candidate_ids:
                    self._set_record_issue(
                        cam_id,
                        f"RTSP main lỗi, đang ghi bằng {self._rtsp_label(rtsp)}",
                    )
                    log(
                        f"{self._camera_name(cam_id)} REC URL FALLBACK "
                        f"{self._describe_rtsp_candidate(rtsp, 'ok')}"
                    )

            for cam_id in candidate_ids:
                self._mark_record_started(cam_id, output_paths[cam_id])
                log(f"{self._camera_name(cam_id)} START {order_code}")
                if opened.get("container") == RECORD_CONTAINER_MPEGTS:
                    log(f"{self._camera_name(cam_id)} REC FALLBACK MPEGTS {order_code}")

            return True

        SHARED_SOURCE_REGISTRY.fail_opening(source_key)

        error_message = self._startup_error_message(startup_errors)
        for cam_id in candidate_ids:
            log(f"{self._camera_name(cam_id)} REC START FAIL - | {error_message}")
            self._fail_record(cam_id, error_message)

        self._play_error_sound_once()
        return False

    def _attach_shared_session(self, session, snapshot):
        cam_id = str(self.cam["id"])
        output_path = session.get("output_paths", {}).get(cam_id, "")
        self.ffmpeg_process = None
        self.current_file = output_path
        self.current_order = snapshot.get("order_code", "")
        self.current_employee = snapshot.get("employee_id", "")
        self.current_employee_name = snapshot.get("employee_name", "")
        self.record_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.record_started_mono = float(session.get("started_mono", time.monotonic()))
        self.shared_source_key = self._shared_source_key()
        self.shared_member_ids = list(session.get("member_ids", []))
        self.shared_is_leader = False

        if output_path:
            self._mark_record_started(cam_id, output_path)
        return True

    def _auto_stop_due(self):
        seconds = int(self.cam.get("record_auto_stop_seconds", self.auto_stop_seconds))
        if seconds <= 0 or self.record_started_mono <= 0:
            return False
        return (time.monotonic() - self.record_started_mono) >= seconds

    def _has_active_session(self):
        if self.shared_source_key:
            session = SHARED_SOURCE_REGISTRY.get_running(self.shared_source_key)
            if not session:
                return False
            return str(self.cam["id"]) in session.get("member_ids", [])

        return self.ffmpeg_process is not None and self.ffmpeg_process.poll() is None

    def _find_ffmpeg(self):
        configured = str(self.cam.get("ffmpeg_path", "")).strip()
        candidates = [configured] if configured else []
        candidates.extend(
            [
                resource_path("bin", "ffmpeg.exe"),
                resource_path("ffmpeg.exe"),
            ]
        )
        candidates.extend(FFMPEG_PATHS)

        for candidate in candidates:
            if not candidate:
                continue
            resolved = shutil.which(candidate) if candidate.lower() == "ffmpeg" else candidate
            if resolved and os.path.exists(resolved):
                return resolved

        return ""

    def _record_formats(self):
        formats = [(RECORD_CONTAINER_MKV, RECORD_EXTENSION_MKV)]
        if bool(self.cam.get("record_mpegts_fallback", True)):
            formats.append((RECORD_CONTAINER_MPEGTS, RECORD_EXTENSION_MPEGTS))
        return formats

    def _build_output_paths(self, snapshot, cameras_by_id, extension):
        paths = {}
        for cam_id, cam in cameras_by_id.items():
            cam_id = str(cam_id)
            cam_snapshot = snapshot if cam_id == str(self.cam["id"]) else self.state.get(cam_id)
            paths[cam_id] = self._build_output_path(cam_snapshot, cam, extension=extension)
        return paths

    def _open_record_process(self, snapshot, ffmpeg, rtsp, cameras_by_id):
        last_error = ""

        for index, (container, extension) in enumerate(self._record_formats()):
            output_paths = self._build_output_paths(snapshot, cameras_by_id, extension)
            process = self._start_ffmpeg(
                self._ffmpeg_copy_command(
                    ffmpeg,
                    rtsp,
                    list(output_paths.values()),
                    container=container,
                )
            )
            if process is None:
                self._cleanup_failed_files(output_paths.values())
                last_error = "spawn failed"
                continue

            time.sleep(FFMPEG_STARTUP_CHECK_SECONDS)
            if process.poll() is None:
                return {
                    "process": process,
                    "output_paths": output_paths,
                    "container": container,
                }

            err = self._read_ffmpeg_error_tail(process)
            self._terminate_ffmpeg_process(process)
            self._cleanup_failed_files(output_paths.values())

            if err:
                log(f"{self.cam['name']} FFMPEG STARTUP ERROR: {err}")
            last_error = self._summarize_ffmpeg_startup_error(err)

            if index == 0 and self._should_try_mpegts_fallback(err):
                log(f"{self.cam['name']} REC RETRY MPEGTS because {last_error}")
                continue

            break

        return {
            "process": None,
            "output_paths": {},
            "container": "",
            "error": last_error or "startup failed",
        }

    def _should_try_mpegts_fallback(self, error_text):
        if not bool(self.cam.get("record_mpegts_fallback", True)):
            return False

        text = str(error_text or "").lower()
        return any(
            marker in text
            for marker in (
                "vps 0 does not exist",
                "sps 0 does not exist",
                "pps 0 does not exist",
                "could not write header",
                "incorrect codec parameters",
                "invalid data found when processing input",
                "error initializing output stream",
            )
        )

    def _summarize_ffmpeg_startup_error(self, error_text):
        text = " ".join(str(error_text or "").split())
        if not text:
            return "startup failed"
        if "VPS 0 does not exist" in text:
            return "HEVC missing VPS, MKV header failed"
        if "Could not write header" in text:
            return "container header failed"
        return text[-240:]

    def _ffmpeg_copy_command(
        self,
        ffmpeg,
        rtsp,
        output_paths,
        container=RECORD_CONTAINER_MKV,
    ):
        # Stable RTSP recording profile:
        # - MKV by default, MPEG-TS fallback for HEVC streams missing VPS/SPS/PPS at startup
        # - RTSP over TCP
        # - copy video stream, no re-encode
        # - default video-only to avoid bad audio/data/metadata streams on OEM/H.265 cameras
        video_only = bool(self.cam.get("record_video_only", True))

        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-rtsp_transport",
            "tcp",
            "-rtsp_flags",
            "prefer_tcp",
            "-fflags",
            "+genpts+discardcorrupt",
            "-err_detect",
            "ignore_err",
            "-use_wallclock_as_timestamps",
            "1",
            "-analyzeduration",
            str(int(self.cam.get("record_analyzeduration_us", 20000000))),
            "-probesize",
            str(int(self.cam.get("record_probesize_bytes", 20000000))),
            "-i",
            rtsp,
        ]

        for output_path in output_paths:
            output_options = [
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-sn",
                "-dn",
                "-avoid_negative_ts",
                "make_zero",
                "-flush_packets",
                "1",
                "-f",
                container,
                output_path,
            ]

            if video_only:
                output_options[4:4] = ["-an"]
            else:
                output_options[4:4] = ["-map", "0:a?", "-c:a", "copy"]

            command.extend(output_options)

        return command

    def _start_ffmpeg(self, command):
        startupinfo, creationflags = hidden_process_flags()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            self._start_ffmpeg_stderr_drain(process)
            return process
        except Exception as e:
            log(f"[FFMPEG SPAWN ERROR] {e}")
            return None

    def _start_ffmpeg_stderr_drain(self, process):
        if process is None or process.stderr is None:
            return

        process._stderr_tail = ""

        def drain():
            try:
                for line in process.stderr:
                    tail = f"{getattr(process, '_stderr_tail', '')}{line}"
                    process._stderr_tail = tail[-FFMPEG_STDERR_TAIL_CHARS:]
            except Exception:
                pass

        thread = threading.Thread(
            target=drain,
            name=f"ffmpeg-stderr-{self.cam.get('id', 'cam')}",
            daemon=True,
        )
        process._stderr_drain_thread = thread
        thread.start()

    def _wait_for_output_ready(self, process, output_paths):
        timeout_seconds = self._startup_ready_timeout_seconds()
        min_file_bytes = self._startup_min_file_bytes()
        deadline = time.monotonic() + timeout_seconds
        last_sizes = {path: -1 for path in output_paths}
        growth_seen = {path: False for path in output_paths}

        while time.monotonic() < deadline:
            if process is None:
                return False, "ffmpeg process missing during startup verify"

            if process.poll() is not None:
                return False, "ffmpeg exited before receiving video packet"

            all_ready = True
            size_parts = []
            for output_path in output_paths:
                size = self._safe_file_size(output_path)
                size_parts.append(f"{os.path.basename(output_path)}={size}")
                previous_size = last_sizes[output_path]
                if previous_size >= 0 and size > previous_size:
                    growth_seen[output_path] = True
                last_sizes[output_path] = size

                if size < min_file_bytes or not growth_seen[output_path]:
                    all_ready = False

            if all_ready:
                return True, ""

            time.sleep(FFMPEG_POLL_DELAY_SECONDS)

        size_summary = ", ".join(
            f"{os.path.basename(path)}={max(0, last_sizes[path])}"
            for path in output_paths
        )
        return False, (
            "no video data written after startup verify timeout"
            f" ({size_summary})"
        )

    def _verify_rtsp_candidate(self, ffmpeg, rtsp):
        command = self._ffmpeg_probe_command(ffmpeg, rtsp)
        startupinfo, creationflags = hidden_process_flags()

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception as e:
            return False, f"probe spawn failed: {e}"

        try:
            _, stderr_text = process.communicate(
                timeout=self._startup_probe_timeout_seconds()
            )
        except subprocess.TimeoutExpired:
            self._terminate_ffmpeg_process(process)
            return False, "probe timeout waiting for first video frame"
        except Exception as e:
            self._terminate_ffmpeg_process(process)
            return False, f"probe error: {e}"

        stderr_text = (stderr_text or "").strip()
        if process.returncode == 0:
            return True, ""

        if stderr_text:
            return False, stderr_text[-400:]
        return False, f"probe failed with exit code {process.returncode}"

    def _ffmpeg_probe_command(self, ffmpeg, rtsp):
        return [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-rtsp_transport",
            "tcp",
            "-rtsp_flags",
            "prefer_tcp",
            "-timeout",
            "10000000",
            "-rw_timeout",
            "10000000",
            "-thread_queue_size",
            "512",
            "-fflags",
            "+genpts+discardcorrupt",
            "-err_detect",
            "ignore_err",
            "-max_delay",
            "500000",
            "-analyzeduration",
            "10000000",
            "-probesize",
            "10000000",
            "-use_wallclock_as_timestamps",
            "1",
            "-i",
            rtsp,
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-t",
            "1",
            "-f",
            "null",
            "-",
        ]

    def _terminate_ffmpeg_process(self, process):
        if process is None or process.poll() is not None:
            return

        try:
            if process.stdin:
                process.stdin.write("q\n")
                process.stdin.flush()
            process.wait(timeout=8)
        except Exception:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _set_startup_record_error(self, message, play_sound=False):
        self._fail_record(self.cam["id"], message)
        if not play_sound:
            return
        self._play_error_sound_once()

    def _play_error_sound_once(self):
        now = time.monotonic()
        if now - self.last_error_sound_mono < RECORD_ERROR_SOUND_INTERVAL_SECONDS:
            return

        self.last_error_sound_mono = now
        record_error()

    def _log_runtime_stream_issue(self, message):
        log(f"{self.cam['name']} REC RETRY {message}")
        self._play_error_sound_once()

    def _record_rtsp_candidates(self):
        return camera_record_rtsp_urls(
            self.cam,
            allow_sub_fallback=bool(self.cam.get("record_sub_fallback", True)),
        )

    def _describe_rtsp_candidate(self, rtsp, suffix):
        if "/live/0/main" in rtsp:
            label = "main"
        elif "/live/0/sub" in rtsp:
            label = "sub"
        else:
            label = rtsp
        return f"{label}: {suffix}"

    def _shared_source_key(self):
        return camera_source_key(self.cam)

    def _record_engine(self):
        app = QApplication.instance()
        if app is None:
            return None
        return getattr(app, "record_engine", None)

    def _shared_source_camera_ids(self):
        engine = self._record_engine()
        if engine is None:
            return [str(self.cam["id"])]
        camera_ids = engine.get_source_camera_ids(self._shared_source_key())
        return camera_ids or [str(self.cam["id"])]

    def _shared_source_candidate_ids(self, order_code):
        candidate_ids = []
        for cam_id in self._shared_source_camera_ids():
            snapshot = self.state.get(cam_id)
            if self._record_requested(snapshot) and snapshot.get("order_code") == order_code:
                candidate_ids.append(str(cam_id))
        return sorted(set(candidate_ids), key=self._camera_sort_key)

    def _leader_camera_id(self, candidate_ids):
        if not candidate_ids:
            return str(self.cam["id"])
        return sorted([str(cam_id) for cam_id in candidate_ids], key=self._camera_sort_key)[0]

    def _camera_sort_key(self, cam_id):
        text = str(cam_id)
        return (0, int(text)) if text.isdigit() else (1, text)

    def _camera_for_id(self, cam_id):
        engine = self._record_engine()
        if engine is not None:
            cam = engine.get_camera(cam_id)
            if cam is not None:
                return cam
        return self.cam if str(self.cam["id"]) == str(cam_id) else {"id": str(cam_id), "name": str(cam_id)}

    def _camera_name(self, cam_id):
        cam = self._camera_for_id(cam_id)
        return str(cam.get("name", cam_id))

    def _startup_error_message(self, startup_errors):
        error_message = "Cannot start FFmpeg recording"
        if startup_errors:
            error_message = f"{error_message} ({'; '.join(startup_errors[:3])})"
        return error_message

    def _close_session(self, reason=None):
        if self.shared_source_key:
            self._close_shared_session(reason)
            return

        if self.current_order:
            status = {
                "AUTO": f"REC AUTO STOP {self.current_order}",
                "FAIL": f"REC FAIL {self.current_order}",
            }.get(reason, f"REC STOP {self.current_order}")
            log(f"{self.cam['name']} {status}")

        if self.ffmpeg_process is not None:
            self._terminate_ffmpeg_process(self.ffmpeg_process)
            self.ffmpeg_process = None

        self._persist_closed_video(reason)
        self._reset_session_fields()

    def _close_shared_session(self, reason=None):
        session = SHARED_SOURCE_REGISTRY.stop(self.shared_source_key)
        member_ids = list(self.shared_member_ids)
        current_order = self.current_order

        if session is not None:
            process = session.get("process")
            if process is not None:
                self._terminate_ffmpeg_process(process)

            if current_order:
                status = {
                    "AUTO": f"REC AUTO STOP {current_order}",
                    "FAIL": f"REC FAIL {current_order}",
                }.get(reason, f"REC STOP {current_order}")
                for cam_id in session.get("member_ids", []):
                    log(f"{self._camera_name(cam_id)} {status}")

        self._persist_closed_video(reason)
        self._reset_session_fields()

        if member_ids and reason in {"STOP", "SWITCH", "AUTO", "FAIL"}:
            for cam_id in member_ids:
                if str(cam_id) == str(self.cam["id"]):
                    continue
                state = self.state.get(cam_id)
                if self._record_requested(state) or state.get("order_code"):
                    self.state.stop_record(cam_id, clear_employee=False)

    def _reset_session_fields(self):
        self.ffmpeg_process = None
        self.current_file = ""
        self.current_order = ""
        self.current_employee = ""
        self.current_employee_name = ""
        self.record_started_at = None
        self.record_started_mono = 0.0
        self.shared_source_key = None
        self.shared_member_ids = []
        self.shared_is_leader = False

    def _cleanup_failed_files(self, file_paths):
        for file_path in file_paths:
            try:
                if not file_path or not os.path.exists(file_path):
                    continue

                size = os.path.getsize(file_path)

                # File 1KB / vài KB là file lỗi do ffmpeg mở ra rồi chết.
                if size < 100 * 1024:
                    os.remove(file_path)
                    log(f"[RECORD CLEANUP] Xóa file lỗi nhỏ: {file_path}, size={size} bytes")
            except OSError as e:
                log(f"[RECORD CLEANUP ERROR] {file_path}: {e}")

    def _build_output_dir(self):
        day = datetime.now().strftime("%Y-%m-%d")
        directory = os.path.join(self.storage_path, day)
        os.makedirs(directory, exist_ok=True)
        return directory

    def _build_output_path(self, snapshot, cam=None, extension=RECORD_EXTENSION_MKV):
        cam = cam or self.cam
        base_dir = self._build_output_dir()
        base_name = self._build_output_name(snapshot, cam)
        extension = str(extension or RECORD_EXTENSION_MKV)
        if not extension.startswith("."):
            extension = f".{extension}"
        return os.path.abspath(os.path.join(base_dir, f"{base_name}{extension}"))

    def _build_output_name(self, snapshot, cam):
        now = datetime.now()
        date_text = now.strftime("%Y%m%d")
        time_text = now.strftime("%H%M%S")
        employee_id = self._safe_name(snapshot.get("employee_id", "NOEMP")) or "NA"
        order_code = self._safe_name(snapshot.get("order_code", "NOORDER"))
        cam_id = self._safe_name(cam.get("id", "NA"))
        return f"{order_code}_C{cam_id}_{employee_id}_{date_text}_{time_text}"

    def _safe_name(self, value):
        cleaned = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in str(value).strip()
        )
        return cleaned or "NA"

    def _persist_closed_video(self, reason=None):
        if not self.current_order or not self.current_file:
            return
        if reason == "FAIL":
            return

        try:
            duration_seconds = 0
            if self.record_started_mono:
                duration_seconds = max(0, time.monotonic() - self.record_started_mono)

            video_id = upsert_closed_record_video(
                order_code=self.current_order,
                file_path=self.current_file,
                camera_id=str(self.cam.get("id", "")),
                camera_name=str(self.cam.get("name", self.cam.get("id", ""))),
                employee_code=self.current_employee,
                employee_name=self.current_employee_name,
                start_time=self.record_started_at,
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                duration_seconds=duration_seconds,
                result="auto_stop" if reason == "AUTO" else "done",
            )
            log(
                f"[MYSQL VIDEO UPSERT] camera={self.cam.get('id')} "
                f"order={self.current_order} video_id={video_id} file={self.current_file}"
            )
        except Exception as exc:
            log(
                f"[MYSQL VIDEO UPSERT ERROR] camera={self.cam.get('id')} "
                f"order={self.current_order} file={self.current_file} error={exc}"
            )

    def _stop_group_states(self, clear_employee=False):
        member_ids = self.shared_member_ids or [str(self.cam["id"])]
        for cam_id in member_ids:
            state = self.state.get(cam_id)
            if self._record_requested(state) or state.get("order_code"):
                self.state.stop_record(cam_id, clear_employee=clear_employee)

    def stop(self):
        self.running = False

    def _record_requested(self, snapshot):
        return bool(snapshot.get("record_requested", snapshot.get("recording", False)))

    def _mark_record_started(self, cam_id, output_path):
        if hasattr(self.state, "mark_record_started"):
            self.state.mark_record_started(cam_id, output_path)
            return
        self.state.set_video(cam_id, output_path)
        if hasattr(self.state, "clear_error"):
            self.state.clear_error(cam_id)

    def _set_record_issue(self, cam_id, message):
        if hasattr(self.state, "set_record_error"):
            self.state.set_record_error(cam_id, message)
            return
        if hasattr(self.state, "set_error"):
            self.state.set_error(cam_id, message)

    def _fail_record(self, cam_id, message, clear_employee=False):
        if hasattr(self.state, "fail_record"):
            self.state.fail_record(cam_id, message, clear_employee=clear_employee)
            return
        if hasattr(self.state, "set_error"):
            self.state.set_error(cam_id, message)
        if hasattr(self.state, "stop_record"):
            self.state.stop_record(cam_id, clear_employee=clear_employee)

    def _fail_group_states(self, message, clear_employee=False):
        member_ids = self.shared_member_ids or [str(self.cam["id"])]
        for cam_id in member_ids:
            self._fail_record(cam_id, message, clear_employee=clear_employee)

    def _rtsp_label(self, rtsp):
        text = str(rtsp or "")
        if "/live/0/main" in text:
            return "main"
        if "/live/0/sub" in text:
            return "sub"
        return text

    def _startup_ready_timeout_seconds(self):
        value = self.cam.get("record_startup_ready_timeout_seconds")
        if value is None:
            value = self.cam.get("record_startup_verify_timeout_seconds")
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            timeout = DEFAULT_RECORD_STARTUP_READY_TIMEOUT_SECONDS
        return max(timeout, FFMPEG_POLL_DELAY_SECONDS)

    def _startup_min_file_bytes(self):
        value = self.cam.get("record_startup_min_file_bytes")
        try:
            min_bytes = int(value)
        except (TypeError, ValueError):
            min_bytes = DEFAULT_RECORD_STARTUP_MIN_FILE_BYTES
        return max(min_bytes, 1)

    def _startup_probe_timeout_seconds(self):
        value = self.cam.get("record_startup_probe_timeout_seconds")
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            timeout = DEFAULT_RECORD_STARTUP_PROBE_TIMEOUT_SECONDS
        return max(timeout, 1.0)

    def _safe_file_size(self, file_path):
        try:
            if file_path and os.path.exists(file_path):
                return os.path.getsize(file_path)
        except OSError:
            return 0
        return 0
    
    def _read_ffmpeg_error_tail(self, process, max_chars=2000):
        if process is None or process.stderr is None:
            return ""

        thread = getattr(process, "_stderr_drain_thread", None)
        if process.poll() is not None and thread is not None:
            try:
                thread.join(timeout=0.2)
            except Exception:
                pass

        tail = getattr(process, "_stderr_tail", "")
        if tail:
            return str(tail)[-max_chars:].strip()

        try:
            text = process.stderr.read() or ""
            return text[-max_chars:].strip()
        except Exception:
            return ""
