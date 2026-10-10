@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PY="

if exist "%SCRIPT_DIR%..\.venv\Scripts\python.exe" set "VENV_PY=%SCRIPT_DIR%..\.venv\Scripts\python.exe"
if not defined VENV_PY if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not defined VENV_PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined VENV_PY set "VENV_PY=%%i"

if not defined VENV_PY (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

echo [RUN] %VENV_PY%
"%VENV_PY%" "%SCRIPT_DIR%_selftest.py"
echo.
echo ============================================
echo  Selftest finished.
echo  Attach the [OK] / [FAIL] lines to the issue.
echo ============================================
pause
endlocal
