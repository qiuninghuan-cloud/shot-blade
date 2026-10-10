@echo off
setlocal
set "VENV_PY=C:\Users\%USERNAME%\.workbuddy\venvs\shot-splitter-gui\Scripts\python.exe"
set "SCRIPT_DIR=%~dp0"

if not exist "%VENV_PY%" (
    echo [ERROR] venv python not found: %VENV_PY%
    pause
    exit /b 1
)

"%VENV_PY%" "%SCRIPT_DIR%_selftest.py"
echo.
echo ============================================
echo  Selftest finished.
echo  Send the [OK] / [FAIL] lines above to me.
echo ============================================
pause
endlocal
