# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller onefile spec for cctv_ai_system_CORE_DATABASE.

Update for commit 8b24409:
- Do NOT bundle old SQLite runtime databases such as db/packing.db or data/report.db.
- Bundle only SQL install scripts needed by the Database setup dialog.
- Ensure PyMySQL and its submodules are collected for MariaDB/MySQL LAN mode.
- Keep runtime config.json external next to the EXE; do not force-bundle it as editable config.
"""

import os
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

ROOT = Path.cwd()


def exists(path: str) -> bool:
    return (ROOT / path).exists()


hiddenimports = [
    # Core runtime / UI
    "cv2",
    "numpy",
    "requests",
    "urllib3",
    "psutil",
    "vlc",

    # Images / QR assets
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "qrcode",

    # Excel export
    "openpyxl",
    "et_xmlfile",

    # MariaDB/MySQL LAN core
    "pymysql",
    "pymysql._auth",
    "pymysql.charset",
    "pymysql.connections",
    "pymysql.cursors",
    "pymysql.constants",
    "pymysql.converters",
    "pymysql.err",
    "pymysql.optionfile",
    "pymysql.protocol",

    # QR/barcode optional backend
    "zxingcpp",

    # PySide6 modules that are often missed in onefile builds
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtNetwork",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",

    # License / HTTPS compatibility if used by license modules
    "cryptography",
    "cryptography.fernet",
    "nacl",
    "nacl.bindings",
    "nacl.signing",
]

# Collect package submodules safely.
hiddenimports += collect_submodules("openpyxl")
hiddenimports += collect_submodules("pymysql")

binaries = []
binaries += collect_dynamic_libs("cv2")

# FFmpeg is mandatory for recording on machines that do not have ffmpeg installed.
ffmpeg_candidates = [
    str(ROOT / "bin" / "ffmpeg.exe"),
    r"C:\ffmpeg\bin\ffmpeg.exe",
]
ffmpeg_from_path = shutil.which("ffmpeg")
if ffmpeg_from_path:
    ffmpeg_candidates.append(ffmpeg_from_path)

ffmpeg_path = next((path for path in ffmpeg_candidates if path and os.path.exists(path)), "")
if not ffmpeg_path:
    raise SystemExit(
        "Missing ffmpeg.exe. Put ffmpeg.exe in project bin\\ffmpeg.exe "
        "or install FFmpeg in C:\\ffmpeg\\bin before building onefile EXE."
    )
binaries.append((ffmpeg_path, "bin"))


datas = []


def add_data(src: str, dest: str):
    """Add data file/folder only if it exists, so build does not fail on optional assets."""
    if exists(src):
        datas.append((src, dest))


# Static assets.
add_data("assets", "assets")
add_data("note", "note")
add_data("hr/employees.json", "hr")

# SQL setup scripts. Keep these, but do not bundle db/packing.db.
add_data("db/mysql_schema_atg_order_system.sql", "db")
add_data("db/create_mysql_user.sql", "db")
add_data("requirements_mysql.txt", ".")

# Branding/icon files.
add_data("icon.ico", ".")
add_data("logo.png", ".")
add_data("logo_app.png", ".")
add_data("banner.png", ".")

# WeChat QRCode model folders, if present.
for source_dir in (
    os.path.join("data", "wechat_qrcode_models"),
    os.path.join("assets", "wechat_qrcode_models"),
    "wechat_qrcode_models",
):
    if os.path.isdir(source_dir):
        datas.append((source_dir, source_dir))

# Do not add these runtime databases to onefile:
# - db/packing.db
# - data/report.db
# They must be replaced by MySQL/MariaDB runtime data.

icon_path = "icon.ico" if exists("icon.ico") else None


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ATG_AI_SYSTEM_RECORD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
