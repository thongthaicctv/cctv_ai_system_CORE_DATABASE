from datetime import datetime
import threading


class RuntimeState:
    def __init__(self):
        self.states = {}
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)

    def _ensure_camera_locked(self, cam_id):
        if cam_id not in self.states:
            self.states[cam_id] = self.default_state()

    def _touch_locked(self, cam_id, record_changed=False):
        state = self.states[cam_id]
        state["version"] = int(state.get("version", 0)) + 1
        if record_changed:
            state["record_version"] = int(state.get("record_version", 0)) + 1
        self._changed.notify_all()

    def add_camera(self, cam_id):
        with self._changed:
            self._ensure_camera_locked(cam_id)

    def remove_camera(self, cam_id):
        with self._changed:
            if cam_id in self.states:
                del self.states[cam_id]
                self._changed.notify_all()

    def default_state(self):
        return {
            "online": False,
            "status": "CHECKING",
            "latency": 0,
            "last_check": "-",
            "recording": False,
            "record_requested": False,
            "record_pending": False,
            "employee_id": "",
            "employee_name": "",
            "order_code": "",
            "shift_code": "",
            "video_file": "",
            "employee_started_at": "",
            "started_at": "",
            "stopped_at": "",
            "scan_text": "",
            "error": "",
            "record_error": "",
            "version": 0,
            "record_version": 0,
        }

    def get(self, cam_id):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            return dict(self.states[cam_id])

    def all(self):
        with self._changed:
            return {cam_id: dict(state) for cam_id, state in self.states.items()}

    def wait_for_record_update(self, cam_id, last_record_version, timeout=1.0):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            if self.states[cam_id]["record_version"] != last_record_version:
                return dict(self.states[cam_id])
            self._changed.wait(timeout)
            self._ensure_camera_locked(cam_id)
            return dict(self.states[cam_id])

    def update_network(self, cam_id, online=False, latency=0):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["online"] = online
            state["latency"] = latency
            state["last_check"] = datetime.now().strftime("%H:%M:%S")
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id)

    def _refresh_status_locked(self, cam_id):
        state = self.states[cam_id]
        if state["recording"]:
            state["status"] = "RECORDING"
        elif state.get("record_pending"):
            state["status"] = "RECORD_WAIT"
        elif state.get("record_error"):
            state["status"] = "RECORD_ERROR"
        elif state.get("error"):
            state["status"] = "ERROR"
        elif state["employee_id"]:
            state["status"] = "WORKING"
        else:
            state["status"] = "ONLINE" if state["online"] else "OFFLINE"

    def assign_employee(self, cam_id, employee_id="", employee_name="", shift_code=""):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["employee_id"] = employee_id
            state["employee_name"] = employee_name
            state["shift_code"] = shift_code
            state["employee_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not state["recording"]:
                state["order_code"] = ""
                state["video_file"] = ""
                state["started_at"] = ""
                state["stopped_at"] = ""

            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id)

    def start_record(
        self,
        cam_id,
        employee_id="",
        employee_name="",
        order_code="",
        shift_code="",
    ):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["recording"] = False
            state["record_requested"] = True
            state["record_pending"] = True
            state["record_error"] = ""

            if employee_id:
                state["employee_id"] = employee_id
            if employee_name:
                state["employee_name"] = employee_name
            if shift_code:
                state["shift_code"] = shift_code

            state["order_code"] = order_code
            state["video_file"] = ""
            state["started_at"] = ""
            state["stopped_at"] = ""
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id, record_changed=True)

    def stop_record(self, cam_id, clear_employee=False):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["recording"] = False
            state["record_requested"] = False
            state["record_pending"] = False
            state["record_error"] = ""
            state["stopped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["order_code"] = ""
            state["video_file"] = ""

            if clear_employee:
                state["employee_id"] = ""
                state["employee_name"] = ""
                state["shift_code"] = ""
                state["employee_started_at"] = ""

            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id, record_changed=True)

    def mark_record_started(self, cam_id, file_path=""):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["recording"] = True
            state["record_requested"] = True
            state["record_pending"] = False
            state["record_error"] = ""
            state["video_file"] = file_path or state.get("video_file", "")
            if not state.get("started_at"):
                state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["stopped_at"] = ""
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id, record_changed=True)

    def set_record_error(self, cam_id, msg):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            self.states[cam_id]["record_error"] = msg
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id)

    def fail_record(self, cam_id, message, clear_employee=False):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            state = self.states[cam_id]
            state["recording"] = False
            state["record_requested"] = False
            state["record_pending"] = False
            state["record_error"] = message
            state["stopped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["order_code"] = ""
            state["video_file"] = ""

            if clear_employee:
                state["employee_id"] = ""
                state["employee_name"] = ""
                state["shift_code"] = ""
                state["employee_started_at"] = ""

            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id, record_changed=True)

    def set_scan(self, cam_id, text):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            self.states[cam_id]["scan_text"] = text
            self._touch_locked(cam_id)

    def set_video(self, cam_id, file_path):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            self.states[cam_id]["video_file"] = file_path
            self._touch_locked(cam_id)

    def set_error(self, cam_id, msg):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            self.states[cam_id]["error"] = msg
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id)

    def clear_error(self, cam_id):
        with self._changed:
            self._ensure_camera_locked(cam_id)
            if not self.states[cam_id]["error"]:
                return
            self.states[cam_id]["error"] = ""
            self._refresh_status_locked(cam_id)
            self._touch_locked(cam_id)
