@echo off

echo.
echo [1] XOA __pycache__
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo.
echo [2] XOA FILE .pyc
for /r %%f in (*.pyc) do del /f /q "%%f"

echo.
echo [3] XOA BUILD
if exist build rd /s /q build

echo.
echo [4] XOA DIST
if exist dist rd /s /q dist

echo.
echo [5] XOA LOGS
if exist logs rd /s /q logs

echo.
echo [6] XOA TMP
if exist temp rd /s /q temp
if exist tmp rd /s /q tmp
if exist tmpoeico_do rd /s /q tmpoeico_do

echo.
echo [7] TAO .gitignore
(
echo __pycache__/
echo *.pyc
echo build/
echo dist/
echo logs/
echo recordings/
echo *.log
echo *.db-journal
echo tmp/
echo temp/
echo tmpoeico_do/
) > .gitignore

echo.
echo [8] GIT CLEAN CACHE
if exist .git (
    git rm -r --cached . >nul 2>&1
    git add .
)

echo.
echo ================================
echo CLEAN DONE
echo ================================

pause