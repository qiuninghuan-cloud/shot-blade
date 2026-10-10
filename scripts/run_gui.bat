@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PY="

rem 1) Recommended: repo-local venv created at <repo>\.venv
if exist "%SCRIPT_DIR%..\.venv\Scripts\pythonw.exe" set "VENV_PY=%SCRIPT_DIR%..\.venv\Scripts\pythonw.exe"

rem 2) venv placed next to this script
if not defined VENV_PY if exist "%SCRIPT_DIR%.venv\Scripts\pythonw.exe" set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"

rem 3) Fall back to pythonw available on PATH
if not defined VENV_PY for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined VENV_PY set "VENV_PY=%%i"
if not defined VENV_PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined VENV_PY set "VENV_PY=%%i"

if not defined VENV_PY (
    echo [ERROR] Python not found.
    echo.
    echo Prepare the environment first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install "scenedetect[opencv]"
    echo.
    pause
    exit /b 1
)

start "" "%VENV_PY%" "%SCRIPT_DIR%video_shot_splitter_gui.py"
endlocal
