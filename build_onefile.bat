@echo off
setlocal EnableExtensions

rem Tu dong xin quyen Administrator khi double-click.
fltmc >nul 2>&1
if errorlevel 1 (
    set "BUILD_BAT=%~f0"
    set "BUILD_DIR=%~dp0"
    echo [INFO] Dang yeu cau quyen Administrator...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process -FilePath $env:BUILD_BAT -WorkingDirectory $env:BUILD_DIR -Verb RunAs"
    if errorlevel 1 (
        echo [ERROR] Khong the mo cua so Administrator.
        pause
        exit /b 1
    )
    exit /b 0
)

cd /d "%~dp0"

set "APP_NAME=T&T VISION AI"

echo ============================================================
echo Building "%APP_NAME%"
echo Project: "%CD%"
echo ============================================================

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

"%PYTHON_BIN%" -m pip install --upgrade -r requirements_mysql.txt
if errorlevel 1 goto :error

"%PYTHON_BIN%" -m PyInstaller --noconfirm --clean build_onefile.spec
if errorlevel 1 goto :error

if not exist "dist\%APP_NAME%.exe" (
    echo [ERROR] PyInstaller ket thuc nhung khong tim thay EXE.
    goto :error
)

if exist "config.json" copy /Y "config.json" "dist\config.json" >nul

echo.
echo [DONE] EXE: "%CD%\dist\%APP_NAME%.exe"
if /I not "%~1"=="--no-pause" pause
exit /b 0

:error
echo.
echo [ERROR] Build that bai
if /I not "%~1"=="--no-pause" pause
exit /b 1
