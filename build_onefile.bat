@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Khong tim thay .venv\Scripts\python.exe
    echo [INFO] Se dung python hien tai trong PATH
    set "PYTHON_BIN=python"
) else (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
)

%PYTHON_BIN% -m pip install --upgrade -r requirements_mysql.txt
if errorlevel 1 goto :error

%PYTHON_BIN% -m PyInstaller --noconfirm --clean build_onefile.spec
if errorlevel 1 goto :error

echo.
echo [DONE] EXE: dist\ATG_AI_SYSTEM_RECORD.exe
exit /b 0

:error
echo.
echo [ERROR] Build that bai
exit /b 1
