import cv2

from core.gpu_acceleration import opencl_processing_enabled, to_host_array, to_processing_buffer


def preprocess(frame):
    source = to_processing_buffer(frame) if opencl_processing_enabled() else frame
    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)

    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    gray = cv2.equalizeHist(gray)

    _, th = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return to_host_array(th)
