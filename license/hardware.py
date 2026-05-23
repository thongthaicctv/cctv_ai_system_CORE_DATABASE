import hashlib
import subprocess


CREATE_NO_WINDOW = getattr(
    subprocess,
    "CREATE_NO_WINDOW",
    0
)


def _run(cmd):
    try:
        output = subprocess.check_output(
            cmd,
            shell=True,
            creationflags=CREATE_NO_WINDOW
        )

        return (
            output.decode(errors="ignore")
            .strip()
            .split("\n")[-1]
            .strip()
        )

    except Exception:
        return "UNKNOWN"


def get_cpu_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_Processor).ProcessorId"'
    )


def get_bios_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_BIOS).SerialNumber"'
    )


def get_baseboard_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_BaseBoard).SerialNumber"'
    )


def get_hardware_string():

    parts = [
        get_cpu_id(),
        get_bios_id(),
        get_baseboard_id(),
    ]

    clean_parts = [
        str(p).strip().upper()
        for p in parts
        if p and str(p).strip() not in ("", "UNKNOWN")
    ]

    return "|".join(clean_parts)


def get_hardware_hash():

    raw = get_hardware_string()

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()


def get_device_id():

    hw = get_hardware_hash().upper()

    return f"ATG-{hw[:4]}-{hw[4:8]}-{hw[8:12]}"