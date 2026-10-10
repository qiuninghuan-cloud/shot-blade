@echo off
setlocal
set "VENV_PY=C:\Users\NING MEI\.workbuddy\venvs\shot-splitter-gui\Scripts\python.exe"
set "SCRIPT_DIR=%~dp0"
set "TCL_LIBRARY=C:\Users\NING MEI\AppData\Local\Programs\Python\Python312\tcl\tcl8.6"
set "TK_LIBRARY=C:\Users\NING MEI\AppData\Local\Programs\Python\Python312\tcl\tk8.6"

if not exist "%VENV_PY%" (
    echo [ERROR] venv python not found.
    pause
    exit /b 1
)
"%VENV_PY%" "%SCRIPT_DIR%video_shot_splitter_gui.py"
echo.
echo [DEBUG END] If there is a red traceback above, screenshot it and send to me.
pause
endlocal
