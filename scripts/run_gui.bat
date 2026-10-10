@echo off
setlocal
set "VENV_PY=C:\Users\NING MEI\.workbuddy\venvs\shot-splitter-gui\Scripts\pythonw.exe"
set "SCRIPT_DIR=%~dp0"
set "TCL_LIBRARY=C:\Users\NING MEI\AppData\Local\Programs\Python\Python312\tcl\tcl8.6"
set "TK_LIBRARY=C:\Users\NING MEI\AppData\Local\Programs\Python\Python312\tcl\tk8.6"

if not exist "%VENV_PY%" (
    echo [ERROR] venv pythonw not found. Please install dependencies first.
    pause
    exit /b 1
)
start "" "%VENV_PY%" "%SCRIPT_DIR%video_shot_splitter_gui.py"
endlocal
