import argparse
import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit


def redact(text):
    text = str(text or "")
    marker = "rtsp://"
    lowered = text.lower()
    start = lowered.find(marker)
    while start >= 0:
        auth_start = start + len(marker)
        at = text.find("@", auth_start)
        slash = text.find("/", auth_start)
        if at >= 0 and (slash < 0 or at < slash):
            text = text[:auth_start] + "***:***" + text[at:]
        lowered = text.lower()
        start = lowered.find(marker, auth_start + 7)
    return " ".join(text.split())[-500:]


def tcp_open(url, timeout=1.5):
    parsed = urlsplit(url)
    host = parsed.hostname
    port = parsed.port or 554
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, (time.perf_counter() - started) * 1000
    except OSError:
        return False, (time.perf_counter() - started) * 1000


def measure(ffmpeg, url, timeout=15):
    command = [
        ffmpeg,
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
        "2000000",
        "-probesize",
        "4000000",
        "-i",
        url,
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-an",
        "-f",
        "null",
        "NUL",
    ]
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return elapsed_ms, result.returncode, redact(result.stderr)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return elapsed_ms, 124, redact(exc.stderr)


def measure_record_start(ffmpeg, url, run_seconds):
    with tempfile.TemporaryDirectory(prefix="tt_rtsp_") as temp_dir:
        output = Path(temp_dir) / "probe.ts"
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
            "2000000",
            "-probesize",
            "4000000",
            "-i",
            url,
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-sn",
            "-dn",
            "-flush_packets",
            "1",
            "-f",
            "mpegts",
            str(output),
        ]
        started = time.perf_counter()
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        first_byte_ms = None
        deadline = started + run_seconds
        while time.perf_counter() < deadline and process.poll() is None:
            if output.exists() and output.stat().st_size > 0:
                first_byte_ms = (time.perf_counter() - started) * 1000
                break
            time.sleep(0.05)
        remaining = max(0.0, deadline - time.perf_counter())
        if remaining:
            time.sleep(remaining)
        if process.poll() is None:
            process.terminate()
        try:
            _stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            _stdout, stderr = process.communicate()
        size = output.stat().st_size if output.exists() else 0
        return first_byte_ms, size, process.returncode, redact(stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", action="append", required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--record-seconds", type=float, default=0)
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found")

    data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cameras = {str(cam.get("id")): cam for cam in data.get("cameras", [])}

    for camera_id in args.camera:
        cam = cameras.get(str(camera_id))
        if not cam:
            print(f"CAM={camera_id} ERROR=not_found")
            continue
        url = str(cam.get("rtsp_main") or cam.get("rtsp") or cam.get("rtsp_sub") or "")
        opened, tcp_ms = tcp_open(url)
        print(f"CAM={camera_id} TCP554={opened} TCP_MS={tcp_ms:.0f}")
        for trial in range(1, max(1, args.trials) + 1):
            elapsed_ms, exit_code, error = measure(ffmpeg, url)
            print(
                f"CAM={camera_id} TRY={trial} FIRST_FRAME_MS={elapsed_ms:.0f} "
                f"EXIT={exit_code} ERROR={error or '-'}"
            )
        if args.record_seconds > 0:
            first_byte_ms, size, exit_code, error = measure_record_start(
                ffmpeg, url, args.record_seconds
            )
            first_byte = "NONE" if first_byte_ms is None else f"{first_byte_ms:.0f}"
            print(
                f"CAM={camera_id} RECORD_FIRST_BYTE_MS={first_byte} SIZE={size} "
                f"EXIT={exit_code} ERROR={error or '-'}"
            )


if __name__ == "__main__":
    main()
