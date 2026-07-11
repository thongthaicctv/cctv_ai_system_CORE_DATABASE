# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


ROOT = Path.cwd()


def exists(path: str) -> bool:
    return (ROOT / path).exists()


hiddenimports = [
    "_cffi_backend",
    "cffi",
    "nacl",
    "nacl.bindings",
    "nacl.signing",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "requests",
    "certifi",
]

hiddenimports += collect_submodules("nacl")
hiddenimports += collect_submodules("cffi")

binaries = []
binaries += collect_dynamic_libs("nacl")
binaries += collect_dynamic_libs("cffi")

cffi_backend = importlib.util.find_spec("_cffi_backend")
if cffi_backend and cffi_backend.origin:
    binaries.append((cffi_backend.origin, "."))

datas = []
if exists("icon.ico"):
    datas.append(("icon.ico", "."))

icon_path = "icon.ico" if exists("icon.ico") else None


a = Analysis(
    ["tools/device_id_check_tool.py"],
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
    name="ATG_DEVICE_ID_CHECK_TOOL",
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
