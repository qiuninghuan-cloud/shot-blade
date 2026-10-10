@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PY="

if exist "%SCRIPT_DIR%..\.venv\Scripts\python.exe" set "VENV_PY=%SCRIPT_DIR%..\.venv\Scripts\python.exe"
if not defined VENV_PY if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
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

echo [RUN] %VENV_PY%
"%VENV_PY%" "%SCRIPT_DIR%video_shot_splitter_gui.py"
echo.
echo [DEBUG END] If there is a red traceback above, screenshot it and attach it to the issue.
pause
endlocal
