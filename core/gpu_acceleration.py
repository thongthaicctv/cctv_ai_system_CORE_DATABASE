import os
import shutil
import subprocess


_ACCELERATION_INFO = None
NVIDIA_SMI_PATHS = (
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    r"C:\Windows\System32\nvidia-smi.exe",
)


def find_nvidia_smi():
    path = shutil.which("nvidia-smi")
    if path:
        return path

    for path in NVIDIA_SMI_PATHS:
        if os.path.exists(path):
            return path

    return ""


def _gpu_names_from_nvidia_smi():
    nvidia_smi = find_nvidia_smi()
    if not nvidia_smi:
        return []

    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def query_nvidia_gpu_status():
    nvidia_smi = find_nvidia_smi()
    if not nvidia_smi:
        return None

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=utilization.gpu,encoder.stats.sessionCount,encoder.stats.averageFps",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    first_line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not first_line:
        return None

    parts = [part.strip() for part in first_line.split(",")]
    try:
        utilization = float(parts[0])
    except (IndexError, ValueError):
        utilization = 0.0

    try:
        encoder_sessions = int(float(parts[1]))
    except (IndexError, ValueError):
        encoder_sessions = 0

    try:
        encoder_fps = float(parts[2])
    except (IndexError, ValueError):
        encoder_fps = 0.0

    return {
        "utilization": utilization,
        "encoder_sessions": encoder_sessions,
        "encoder_fps": encoder_fps,
    }


def _gpu_names_from_wmic():
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    names = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name or name.lower() == "name":
            continue
        names.append(name)

    return names


def detect_system_gpus():
    names = []
    seen = set()

    for name in _gpu_names_from_nvidia_smi() + _gpu_names_from_wmic():
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)

    return names


def _preferred_opencl_vendor():
    for gpu_name in detect_system_gpus():
        name = gpu_name.lower()
        if "nvidia" in name:
            return "NVIDIA"
        if "amd" in name or "radeon" in name:
            return "AMD"
        if "intel" in name:
            return "Intel"

    return ""


def prepare_gpu_runtime():
    os.environ.setdefault("QT_OPENGL", "desktop")
    os.environ.setdefault("OPENCV_DNN_OPENCL_ALLOW_ALL_DEVICES", "1")

    if "OPENCV_OPENCL_DEVICE" not in os.environ:
        vendor = _preferred_opencl_vendor()
        os.environ["OPENCV_OPENCL_DEVICE"] = f"{vendor}:GPU:" if vendor else ":GPU:"


def configure_opencv_acceleration(force=False):
    global _ACCELERATION_INFO

    if _ACCELERATION_INFO is not None and not force:
        return dict(_ACCELERATION_INFO)

    prepare_gpu_runtime()

    import cv2

    info = {
        "mode": "cpu",
        "system_gpus": detect_system_gpus(),
        "cuda_devices": 0,
        "opencl_enabled": False,
        "opencl_available": False,
        "device_name": "",
        "device_vendor": "",
        "is_discrete_gpu": False,
        "message": "OpenCV acceleration: CPU",
    }

    try:
        cuda_count = int(getattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)())
    except Exception:
        cuda_count = 0

    info["cuda_devices"] = cuda_count
    if cuda_count > 0:
        try:
            cv2.cuda.setDevice(0)
        except Exception:
            pass
        info["mode"] = "cuda"
        gpu_label = ", ".join(info["system_gpus"]) or f"{cuda_count} device"
        info["message"] = f"OpenCV acceleration: CUDA ({gpu_label})"
        _ACCELERATION_INFO = info
        return dict(info)

    try:
        have_opencl = bool(cv2.ocl.haveOpenCL())
        cv2.ocl.setUseOpenCL(have_opencl)
        use_opencl = bool(cv2.ocl.useOpenCL())
    except Exception:
        have_opencl = False
        use_opencl = False

    info["opencl_available"] = have_opencl

    if use_opencl:
        try:
            device = cv2.ocl.Device_getDefault()
            device_name = str(device.name())
            device_vendor = str(device.vendorName())
            device_type = int(device.type())
        except Exception:
            device_name = ""
            device_vendor = ""
            device_type = 0

        vendor_lower = device_vendor.lower()
        is_discrete = (
            device_type == getattr(cv2.ocl, "Device_TYPE_DGPU", -1)
            or ("nvidia" in vendor_lower)
            or ("amd" in vendor_lower)
            or ("radeon" in vendor_lower)
        )

        info.update(
            {
                "mode": "opencl",
                "opencl_enabled": True,
                "device_name": device_name,
                "device_vendor": device_vendor,
                "is_discrete_gpu": is_discrete,
            }
        )

        target_label = "dGPU" if is_discrete else "GPU"
        device_label = " / ".join(x for x in (device_vendor, device_name) if x) or "default device"
        info["message"] = f"OpenCV acceleration: OpenCL {target_label} ({device_label})"
    elif info["system_gpus"]:
        gpu_label = ", ".join(info["system_gpus"])
        if have_opencl:
            info["message"] = f"OpenCV acceleration: CPU (GPU detected: {gpu_label}, OpenCL not active)"
        else:
            info["message"] = f"OpenCV acceleration: CPU (GPU detected: {gpu_label}, OpenCV has no usable CUDA/OpenCL)"

    _ACCELERATION_INFO = info
    return dict(info)


def opencl_processing_enabled():
    info = configure_opencv_acceleration()
    return bool(info.get("opencl_enabled"))


def to_processing_buffer(image):
    if image is None or not opencl_processing_enabled():
        return image

    import cv2

    try:
        return cv2.UMat(image)
    except Exception:
        return image


def to_host_array(image):
    if hasattr(image, "get"):
        try:
            return image.get()
        except Exception:
            return image
    return image


def video_capture_params(cv2, open_timeout_msec=None, read_timeout_msec=None):
    params = []

    hw_accel = getattr(cv2, "CAP_PROP_HW_ACCELERATION", None)
    hw_use_opencl = getattr(cv2, "CAP_PROP_HW_ACCELERATION_USE_OPENCL", None)
    accel_any = getattr(cv2, "VIDEO_ACCELERATION_ANY", None)

    if hw_accel is not None and accel_any is not None:
        params.extend([hw_accel, int(accel_any)])

    if hw_use_opencl is not None:
        params.extend([hw_use_opencl, 1])

    open_timeout_prop = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
    if open_timeout_prop is not None and open_timeout_msec is not None:
        params.extend([open_timeout_prop, int(open_timeout_msec)])

    read_timeout_prop = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if read_timeout_prop is not None and read_timeout_msec is not None:
        params.extend([read_timeout_prop, int(read_timeout_msec)])

    return params
