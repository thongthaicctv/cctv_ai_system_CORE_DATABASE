import threading

from services.qr_worker import QRWorker
from system_logger import log
from utils.url_helper import camera_rtsp_url

ENGINE_INSTANCE = None


def manual_qr_command(text):
    global ENGINE_INSTANCE

    if ENGINE_INSTANCE:
        ENGINE_INSTANCE.handle_manual_command(text)


class QREngine:
    def __init__(self, state):
        self.state = state
        self.workers = {}
        self.threads = {}
        self.command_worker = QRWorker({"id": "manual", "name": "MANUAL"}, state)

        global ENGINE_INSTANCE
        ENGINE_INSTANCE = self

    @staticmethod
    def scan_camera_ids(cameras, record_mapping=None):
        camera_ids = [
            str(cam.get("id", "")).strip()
            for cam in cameras
            if str(cam.get("id", "")).strip()
        ]

        if record_mapping is None:
            return set(camera_ids)

        normalized_mapping = {
            str(cam_id).strip(): [
                str(target_id).strip()
                for target_id in (target_ids or [])
                if str(target_id).strip()
            ]
            for cam_id, target_ids in (record_mapping or {}).items()
        }

        return {
            cam_id
            for cam_id in camera_ids
            if normalized_mapping.get(cam_id)
        }

    def start_camera(self, cam):
        if not cam.get("enabled", True):
            return

        cam_id = str(cam["id"])

        if cam_id in self.workers:
            return

        worker = QRWorker(cam, self.state)
        thread = threading.Thread(target=worker.run, daemon=True)

        thread.start()

        self.workers[cam_id] = worker
        self.threads[cam_id] = thread

    def stop_camera(self, cam_id):
        cam_id = str(cam_id)
        worker = self.workers.pop(cam_id, None)
        if worker is None:
            return

        worker.stop()
        self.threads.pop(cam_id, None)

    def start_all(self, cameras, record_mapping=None):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)

        scan_camera_ids = self.scan_camera_ids(cameras, record_mapping)
        scan_source_urls = set()

        for cam in cameras:
            cam_id = str(cam.get("id", ""))
            if cam_id not in scan_camera_ids:
                continue

            source_url = camera_rtsp_url(cam, prefer="sub") or camera_rtsp_url(cam, prefer="main")
            if source_url and source_url in scan_source_urls:
                log(f"QR SCAN SKIP DUPLICATE SOURCE: CAM-{cam_id} {cam.get('name', '')}")
                continue

            if source_url:
                scan_source_urls.add(source_url)
            self.start_camera(cam)

        active_scan_ids = list(self.workers.keys())
        log(
            "QR SCAN ACTIVE: "
            + (", ".join(active_scan_ids) if active_scan_ids else "none")
        )

    def stop_all(self):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)

    def handle_manual_command(self, text):
        scan_cam_id = "manual"
        cmd = self.command_worker._parse_manual_cmd(text)

        if cmd:
            scanner_id, _body = cmd
            scan_cam_id = self.command_worker._find_camera_by_sub(scanner_id) or scan_cam_id
        else:
            action_states = getattr(self.command_worker, "packing_action_state", {})
            active_scanners = [
                scanner_id
                for scanner_id, state in action_states.items()
                if state and state.get("mode")
            ]
            if len(active_scanners) == 1:
                scan_cam_id = (
                    self.command_worker._find_camera_by_sub(active_scanners[0])
                    or scan_cam_id
                )

        self.command_worker._handle_command(scan_cam_id, text)
