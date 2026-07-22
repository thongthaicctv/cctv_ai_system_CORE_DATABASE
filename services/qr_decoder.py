import json
import os
import re
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

try:
    import zxingcpp
except Exception:
    zxingcpp = None


FIELD_ALIASES = {
    "EMP": "employee_id",
    "EMPLOYEE": "employee_id",
    "EMPLOYEE_ID": "employee_id",
    "ID": "employee_id",
    "NAME": "employee_name",
    "EMPLOYEE_NAME": "employee_name",
    "ORDER": "order_code",
    "ORDER_CODE": "order_code",
    "SHIFT": "shift_code",
    "SHIFT_CODE": "shift_code",
}

_THREAD_LOCAL = threading.local()
_UNINITIALIZED = object()
_WARNED_KEYS = set()
_WARN_LOCK = threading.Lock()
_MAX_WIDTH = 1280
_WECHAT_MODEL_FILES = (
    "detect.prototxt",
    "detect.caffemodel",
    "sr.prototxt",
    "sr.caffemodel",
)
_ZXING_QR_FORMATS = None
_SHARPEN_KERNEL = np.array(
    [
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0],
    ],
    dtype=np.float32,
)


def _warn_once(key, message):
    with _WARN_LOCK:
        if key in _WARNED_KEYS:
            return
        _WARNED_KEYS.add(key)
    print(message)


def _unique_paths(paths):
    unique = []
    seen = set()
    for path in paths:
        try:
            resolved = Path(path).resolve()
        except Exception:
            resolved = Path(path)

        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def _runtime_base_dirs():
    bases = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        bases.append(meipass)

    try:
        bases.append(Path(__file__).resolve().parents[1])
    except Exception:
        pass

    bases.append(Path.cwd())

    try:
        bases.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    return _unique_paths(bases)


def _wechat_model_dirs():
    candidates = []

    env_dir = os.environ.get("WECHAT_QRCODE_MODEL_DIR", "").strip()
    if env_dir:
        candidates.append(env_dir)

    for base in _runtime_base_dirs():
        candidates.extend(
            [
                base / "wechat_qrcode_models",
                base / "data" / "wechat_qrcode_models",
                base / "assets" / "wechat_qrcode_models",
            ]
        )

    return _unique_paths(candidates)


def _find_wechat_model_paths():
    for model_dir in _wechat_model_dirs():
        model_paths = tuple(model_dir / filename for filename in _WECHAT_MODEL_FILES)
        if all(path.is_file() for path in model_paths):
            return tuple(str(path) for path in model_paths)
    return None


def _create_wechat_detector():
    if not hasattr(cv2, "wechat_qrcode_WeChatQRCode"):
        _warn_once(
            "wechat-opencv-missing",
            "[QR] OpenCV hien tai khong co WeChatQRCode. Can opencv-contrib-python.",
        )
        return None

    model_paths = _find_wechat_model_paths()
    if not model_paths:
        _warn_once(
            "wechat-models-missing",
            (
                "[QR] Chua tim thay model WeChatQRCode. Dat 4 file detect.prototxt, "
                "detect.caffemodel, sr.prototxt, sr.caffemodel vao data/wechat_qrcode_models "
                "hoac assets/wechat_qrcode_models, hoac set bien moi truong WECHAT_QRCODE_MODEL_DIR."
            ),
        )
        return None

    try:
        return cv2.wechat_qrcode_WeChatQRCode(*model_paths)
    except Exception as exc:
        _warn_once("wechat-init-failed", f"[QR] Khoi tao WeChatQRCode that bai: {exc}")
        return None


def _get_wechat_detector():
    detector = getattr(_THREAD_LOCAL, "wechat_detector", _UNINITIALIZED)
    if detector is _UNINITIALIZED:
        detector = _create_wechat_detector()
        _THREAD_LOCAL.wechat_detector = detector if detector is not None else False

    if detector is False:
        return None

    return detector


def _get_opencv_detector():
    detector = getattr(_THREAD_LOCAL, "opencv_detector", _UNINITIALIZED)
    if detector is _UNINITIALIZED:
        try:
            detector = cv2.QRCodeDetector()
        except Exception:
            detector = None
        _THREAD_LOCAL.opencv_detector = detector if detector is not None else False

    if detector is False:
        return None

    return detector


def _resize_keep_ratio(frame, max_width=_MAX_WIDTH):
    if frame is None or max_width is None:
        return frame

    h, w = frame.shape[:2]
    if w <= max_width:
        return frame

    scale = max_width / float(w)
    return cv2.resize(
        frame,
        (int(w * scale), int(h * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _normalize_text(raw):
    if raw is None:
        return ""

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")

    return str(raw).replace("\x00", "").strip()


def _append_unique(results, text):
    text = _normalize_text(text)
    if text and text not in results:
        results.append(text)


def _crop_by_points(frame, points, padding=24):
    if points is None:
        return None

    try:
        pts = np.array(points, dtype=np.int32).reshape(-1, 2)
        x1 = max(0, int(np.min(pts[:, 0])) - padding)
        y1 = max(0, int(np.min(pts[:, 1])) - padding)
        x2 = min(frame.shape[1], int(np.max(pts[:, 0])) + padding)
        y2 = min(frame.shape[0], int(np.max(pts[:, 1])) + padding)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2].copy()
    except Exception:
        return None


def _make_wechat_variants(frame, fast=False):
    image = _resize_keep_ratio(frame)
    if image is None:
        return []

    variants = [image]
    h, w = image.shape[:2]
    if min(h, w) < 360 and max(h, w) <= 960:
        variants.append(
            cv2.resize(
                image,
                None,
                fx=2.0,
                fy=2.0,
                interpolation=cv2.INTER_CUBIC,
            )
        )

    if not fast:
        variants.append(cv2.filter2D(image, -1, _SHARPEN_KERNEL))

    return variants


def _make_zxing_variants(frame, fast=False):
    image = _resize_keep_ratio(frame)
    if image is None:
        return []

    variants = [("original", image)]

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variants.append(("gray", gray))

        if fast:
            return variants

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        clahe_img = clahe.apply(gray)
        variants.append(("clahe", clahe_img))

        threshold = cv2.adaptiveThreshold(
            clahe_img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
        variants.append(("adaptive_threshold", threshold))

        variants.append(("sharpen", cv2.filter2D(image, -1, _SHARPEN_KERNEL)))
    except Exception:
        pass

    return variants


def _decode_with_wechat(frame, fast=False):
    detector = _get_wechat_detector()
    if detector is None:
        return []

    results = []
    seen = set()

    for image in _make_wechat_variants(frame, fast=fast):
        try:
            texts, points = detector.detectAndDecode(image)
        except Exception:
            continue

        if not texts:
            continue

        for index, text in enumerate(texts):
            text = _normalize_text(text)
            if not text or text in seen:
                continue

            seen.add(text)
            pts = None
            try:
                pts = points[index]
            except Exception:
                pts = None

            results.append(
                {
                    "text": text,
                    "points": pts,
                }
            )

        if results:
            return results

    return results


def _decode_with_opencv(frame, fast=False):
    detector = _get_opencv_detector()
    if detector is None:
        return []

    image = _resize_keep_ratio(frame)
    if image is None:
        return []

    variants = [image]
    if not fast:
        try:
            variants.append(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
        except Exception:
            pass

    results = []
    for variant in variants:
        if fast:
            try:
                decoded = detector.detectAndDecode(variant)
                text = decoded[0] if decoded else ""
                _append_unique(results, text)
                if results:
                    return results
            except Exception:
                pass
            continue

        try:
            if hasattr(detector, "detectAndDecodeMulti"):
                decoded = detector.detectAndDecodeMulti(variant)
                if decoded:
                    ok = decoded[0]
                    decoded_info = decoded[1] if len(decoded) > 1 else []
                    if ok:
                        for text in decoded_info:
                            _append_unique(results, text)
                        if results:
                            return results
        except Exception:
            pass

        try:
            decoded = detector.detectAndDecode(variant)
            text = decoded[0] if decoded else ""
            _append_unique(results, text)
            if results:
                return results
        except Exception:
            pass

    return results


def _qr_formats():
    global _ZXING_QR_FORMATS

    if _ZXING_QR_FORMATS is not None or zxingcpp is None:
        return _ZXING_QR_FORMATS

    formats = [zxingcpp.BarcodeFormat.QRCode]
    micro_qr = getattr(zxingcpp.BarcodeFormat, "MicroQRCode", None)
    if micro_qr is not None:
        formats.append(micro_qr)

    _ZXING_QR_FORMATS = tuple(formats)
    return _ZXING_QR_FORMATS


def _decode_with_zxing_single_image(image, include_barcodes):
    if zxingcpp is None:
        _warn_once("zxing-missing", "[QR] Chua import duoc zxingcpp. Can cai goi zxing-cpp.")
        return []

    kwargs = {
        "try_rotate": True,
        "try_downscale": True,
        "try_invert": True,
    }
    if not include_barcodes:
        kwargs["formats"] = _qr_formats()

    try:
        decoded_list = zxingcpp.read_barcodes(image, **kwargs)
    except Exception:
        return []

    results = []
    for item in decoded_list:
        text = _normalize_text(getattr(item, "text", ""))
        if text:
            results.append(text)

    return results


def _decode_with_zxing(frame, include_barcodes=False, fast=False):
    results = []
    seen = set()

    for _name, image in _make_zxing_variants(frame, fast=fast):
        for text in _decode_with_zxing_single_image(image, include_barcodes):
            if text in seen:
                continue
            seen.add(text)
            results.append(text)

        if results and fast and not include_barcodes:
            return results

    return results


def _decode_combined(frame, include_barcodes=False, fast=False):
    final = []
    seen = set()

    prepared = _resize_keep_ratio(frame)
    if prepared is None:
        return final

    # ZXing-C++ is substantially faster than the OpenCV/WeChat detector chain
    # for clean QR frames. Try the original image first on the real-time path
    # so a visible code does not wait behind the heavier detectors.
    if fast:
        for text in _decode_with_zxing_single_image(prepared, include_barcodes):
            if text in seen:
                continue
            seen.add(text)
            final.append(text)
        if final and not include_barcodes:
            return final

    for text in _decode_with_opencv(prepared, fast=fast):
        if text in seen:
            continue
        seen.add(text)
        final.append(text)

        if fast and not include_barcodes:
            return final

    wechat_results = _decode_with_wechat(prepared, fast=fast)
    for result in wechat_results:
        text = result["text"]
        if text in seen:
            continue
        seen.add(text)
        final.append(text)

    if final and fast and not include_barcodes:
        return final

    for result in wechat_results:
        crop = _crop_by_points(prepared, result.get("points"), padding=30)
        if crop is None:
            continue

        for text in _decode_with_zxing(crop, include_barcodes=include_barcodes, fast=True):
            if text in seen:
                continue
            seen.add(text)
            final.append(text)

        if final and fast and not include_barcodes:
            return final

    for text in _decode_with_zxing(prepared, include_barcodes=include_barcodes, fast=fast):
        if text in seen:
            continue
        seen.add(text)
        final.append(text)

        if fast and not include_barcodes:
            return final

    return final


def decode_qr_texts_fast(frame, include_barcodes=False):
    return _decode_combined(frame, include_barcodes=include_barcodes, fast=True)


def decode_qr_texts_opencv_fast(frame):
    return _decode_with_opencv(frame, fast=True)


def decode_qr_texts(frame, include_barcodes=False):
    return _decode_combined(frame, include_barcodes=include_barcodes, fast=False)


def _parse_json_payload(text):
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}

    if not isinstance(payload, dict):
        return {}

    fields = {}
    for key, value in payload.items():
        field = FIELD_ALIASES.get(str(key).strip().upper())
        if field and value is not None:
            fields[field] = str(value).strip()

    return fields


def _parse_key_value_payload(text):
    fields = {}

    for token in re.split(r"[|;,\n]+", text):
        token = token.strip()
        if not token:
            continue

        if ":" in token:
            key, value = token.split(":", 1)
        elif "=" in token:
            key, value = token.split("=", 1)
        else:
            continue

        field = FIELD_ALIASES.get(key.strip().upper())
        value = value.strip()
        if field and value:
            fields[field] = value

    return fields


def parse_qr_command(text):
    text = _normalize_text(text)
    upper_text = text.upper()

    if upper_text == "STOP":
        return {
            "action": "stop",
            "raw": text,
        }

    fields = _parse_json_payload(text)
    if not fields:
        fields = _parse_key_value_payload(text)

    employee_id = fields.get("employee_id", "")
    if upper_text.startswith("EMP:") or employee_id:
        if not employee_id and ":" in text:
            employee_id = text.split(":", 1)[1].strip()

        return {
            "action": "employee",
            "raw": text,
            "employee_id": employee_id,
            "employee_name": fields.get("employee_name", ""),
            "shift_code": fields.get("shift_code", ""),
        }

    order_code = fields.get("order_code", "")
    if not order_code:
        order_code = text

    if order_code:
        return {
            "action": "order",
            "raw": text,
            "order_code": order_code,
        }

    return {
        "action": "scan",
        "raw": text,
    }
