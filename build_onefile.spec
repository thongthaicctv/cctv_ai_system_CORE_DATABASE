# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules


hiddenimports = ["zxingcpp", "et_xmlfile"] + collect_submodules("openpyxl")

binaries = []
ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
if os.path.exists(ffmpeg_path):
    binaries.append((ffmpeg_path, "."))

datas = [
    ("assets", "assets"),
    ("note", "note"),
    ("db", "db"),
    
    ("icon.ico", "."),
    ("logo.png", "."),
    ("logo_app.png", "."),
    ("banner.png", "."),
    ("hr/employees.json", "hr"),
]

if os.path.exists(os.path.join("data", "report.db")):
    datas.append((os.path.join("data", "report.db"), "data"))

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
