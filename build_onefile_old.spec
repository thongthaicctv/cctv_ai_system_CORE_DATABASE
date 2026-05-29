# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules


hiddenimports = [
    "cv2",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "pymysql",
    "requests",
    "zxingcpp",
    "et_xmlfile",
    "PySide6.QtPrintSupport",
] + collect_submodules("openpyxl") + collect_submodules("pymysql")

binaries = []
ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
if os.path.exists(ffmpeg_path):
    binaries.append((ffmpeg_path, "."))

datas = [
    ("assets", "assets"),
    ("note", "note"),
    ("db/mysql_schema_atg_order_system.sql", "db"),
    
    ("icon.ico", "."),
    ("logo.png", "."),
    ("logo_app.png", "."),
    ("banner.png", "."),
    ("hr/employees.json", "hr"),
    ("requirements_mysql.txt", "."),
]

for source_dir in (
    os.path.join("data", "wechat_qrcode_models"),
    os.path.join("assets", "wechat_qrcode_models"),
    "wechat_qrcode_models",
):
    if os.path.isdir(source_dir):
        datas.append((source_dir, source_dir))


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
    icon="icon.ico",
)
