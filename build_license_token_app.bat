@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
) else if exist "C:\Python310\python.exe" (
    echo [INFO] Khong tim thay .venv\Scripts\python.exe
    echo [INFO] Se dung C:\Python310\python.exe
    set "PYTHON_BIN=C:\Python310\python.exe"
) else (
    echo [INFO] Khong tim thay .venv\Scripts\python.exe hoac C:\Python310\python.exe
    echo [INFO] Se dung python hien tai trong PATH
    set "PYTHON_BIN=python"
)

%PYTHON_BIN% -m pip install --upgrade PyInstaller PySide6 PyNaCl
if errorlevel 1 goto :error

%PYTHON_BIN% -m PyInstaller --noconfirm --clean build_license_token_app.spec
if errorlevel 1 goto :error

echo.
echo [DONE] EXE: dist\ATG_LICENSE_TOKEN_TOOL_LAPTOP.exe
exit /b 0

:error
echo.
echo [ERROR] Build that bai
exit /b 1
