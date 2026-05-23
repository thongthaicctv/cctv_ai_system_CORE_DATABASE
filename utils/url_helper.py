import os
import socket
from urllib.parse import quote, unquote

from core.gpu_acceleration import video_capture_params


DEFAULT_RTSP_TIMEOUT_MSEC = 5000
DEFAULT_RTSP_CONNECT_TIMEOUT = 1.5


class ClosedCapture:
    def isOpened(self):
        return False

    def read(self):
        return False, None

    def release(self):
        pass

    def set(self, _prop, _value):
        return False


def camera_rtsp_url(cam, prefer="sub"):
    if prefer == "main":
        raw_url = (
            cam.get("rtsp_main")
            or cam.get("rtsp")
            or cam.get("rtsp_sub")
        )
    else:
        raw_url = (
            cam.get("rtsp_sub")
            or cam.get("rtsp")
            or cam.get("rtsp_main")
        )

    return safe_rtsp(raw_url)


def safe_rtsp(url: str) -> str:
    if not url:
        return url

    url = str(url).strip()
    if not url.lower().startswith("rtsp://"):
        return url

    try:
        body = url[7:]

        if "@" not in body:
            return f"rtsp://{body}"

        auth, host = body.rsplit("@", 1)

        if ":" in auth:
            user, pwd = auth.split(":", 1)
            user = quote(unquote(user), safe="")
            pwd = quote(unquote(pwd), safe="")
            return f"rtsp://{user}:{pwd}@{host}"

        user = quote(unquote(auth), safe="")
        return f"rtsp://{user}@{host}"

    except Exception:
        return url


def rtsp_url_variants(url):
    url = safe_rtsp(url)
    if not url:
        return []

    if "/" in url:
        prefix, tail = url.rsplit("/", 1)
        if tail in {"SUB", "MAIN"}:
            return [f"{prefix}/{tail.lower()}", url]

    return [url]


def unique_rtsp_urls(urls):
    unique_urls = []
    seen = set()

    for url in urls:
        for candidate in rtsp_url_variants(url):
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            unique_urls.append(candidate)

    return unique_urls


def camera_record_rtsp_urls(cam, allow_sub_fallback=True):
    urls = [camera_rtsp_url(cam, prefer="main")]

    if allow_sub_fallback:
        sub_url = camera_rtsp_url(cam, prefer="sub")
        if sub_url:
            urls.append(sub_url)

    return unique_rtsp_urls(urls)


def camera_source_key(cam):
    return (
        camera_rtsp_url(cam, prefer="main") or "",
        camera_rtsp_url(cam, prefer="sub") or "",
    )


def rtsp_endpoint(url):
    url = safe_rtsp(url)
    if not url or not url.lower().startswith("rtsp://"):
        return None, None

    body = url[7:]
    if "@" in body:
        body = body.rsplit("@", 1)[1]

    host_port = body.split("/", 1)[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        try:
            return host, int(port)
        except ValueError:
            return host, 554

    return host_port, 554


def rtsp_port_open(url, timeout=DEFAULT_RTSP_CONNECT_TIMEOUT):
    host, port = rtsp_endpoint(url)
    if not host:
        return True

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def configure_opencv_rtsp():
    os.environ[
        "OPENCV_FFMPEG_CAPTURE_OPTIONS"
    ] = (
        "rtsp_transport;tcp|"
        "stimeout;5000000|"
        "timeout;5000000|"
        "rw_timeout;5000000|"
        "max_delay;500000"
    )


def _open_direct_capture(cv2, url):
    old_options = os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
    try:
        params = video_capture_params(cv2)
        if params:
            try:
                return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
            except Exception:
                pass
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    finally:
        if old_options is not None:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = old_options


def _open_timeout_capture(cv2, url, open_timeout_msec, read_timeout_msec):
    configure_opencv_rtsp()
    params = video_capture_params(
        cv2,
        open_timeout_msec=open_timeout_msec,
        read_timeout_msec=read_timeout_msec,
    )

    try:
        if params:
            return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    except Exception:
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)


def open_rtsp_capture(
    url,
    open_timeout_msec=DEFAULT_RTSP_TIMEOUT_MSEC,
    read_timeout_msec=DEFAULT_RTSP_TIMEOUT_MSEC,
    prefer_direct=True,
    check_port=True,
):
    import cv2

    url = safe_rtsp(url)
    if check_port and not rtsp_port_open(url):
        return ClosedCapture()

    for candidate in rtsp_url_variants(url):
        openers = []
        if prefer_direct:
            openers.append(_open_direct_capture)
        openers.append(_open_timeout_capture)

        for opener in openers:
            if opener is _open_direct_capture:
                cap = opener(cv2, candidate)
            else:
                cap = opener(
                    cv2,
                    candidate,
                    open_timeout_msec,
                    read_timeout_msec,
                )

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                return cap

            cap.release()

    return ClosedCapture()
