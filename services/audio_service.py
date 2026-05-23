import os
import threading
import winsound

from core.resource_paths import resource_path

SOUND_DIR = resource_path("assets", "sounds")


def _play(filename):
    path = os.path.join(SOUND_DIR, filename)

    if os.path.exists(path):
        winsound.PlaySound(
            path,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    else:
        winsound.MessageBeep()


def play_sound(filename):
    threading.Thread(
        target=_play,
        args=(filename,),
        daemon=True
    ).start()


def employee_ok():
    play_sound("employee_ok.wav")


def order_ok():
    play_sound("order_ok.wav")


def stop_ok():
    play_sound("stop_ok.wav")


def record_error():
    play_sound("eror.wav")

def disk_low():
    play_sound("disk_low.wav")
def play_event_sound(sound_name):
    """
    Phát âm thanh theo tên sự kiện nghiệp vụ đóng/giao hàng.
    File wav đặt trong assets/sounds/.
    """

    mapping = {
        "packing_start": "packing_start.wav",
        "item_scan_ok": "item_scan_ok.wav",
        "packing_stop": "packing_stop.wav",
        "packing_delete_ok": "packing_delete_ok.wav",

        "prompt_scan_packing_order": "prompt_scan_packing_order.wav",
        "prompt_scan_packing_items": "prompt_scan_packing_items.wav",
        "prompt_scan_delivery_order": "prompt_scan_delivery_order.wav",
        "prompt_scan_delivery_box": "prompt_scan_delivery_box.wav",

        # alias cũ
        "ready_for_packing": "prompt_scan_packing_order.wav",
        "box_confirm_ok": "prompt_scan_packing_items.wav",
        "invite_scan_order": "prompt_scan_delivery_order.wav",
        "invite_scan_box": "prompt_scan_delivery_box.wav",

        "order_not_packed": "order_not_packed.wav",
        "ready_for_handover": "ready_for_handover.wav",
        "handover_success": "handover_success.wav",
        "handover_error": "handover_error.wav",
        "order_already_delivered": "order_already_delivered.wav",

        "error_session_running": "error_session_running.wav",
        "error_no_session": "error_no_session.wav",
    }

    filename = mapping.get(sound_name)

    if not filename:
        print("[SOUND UNKNOWN]", sound_name)
        winsound.MessageBeep()
        return False

    play_sound(filename)
    return True