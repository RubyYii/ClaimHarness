@echo off
setlocal

cd /d "%~dp0\.." || (
    echo Could not change to the ProblemBridge project root.
    pause
    exit /b 1
)

set "VENV_PYTHON=.venv\Scripts\python.exe"
set "SETUP_MARKER=.venv\.claimharness_setup_v0.4.0"

if not exist "%VENV_PYTHON%" goto setup
if not exist "%SETUP_MARKER%" goto setup
goto launch

:setup
echo First run or version change detected; preparing the local environment once...
call scripts\setup_problembridge_windows.bat
if errorlevel 1 exit /b 1
if not exist "%VENV_PYTHON%" (
    echo The local Python environment could not be prepared.
    pause
    exit /b 1
)

:launch
echo Starting ProblemBridge local UI...
echo If the browser does not open, visit http://127.0.0.1:8501
start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8501'"

"%VENV_PYTHON%" -m streamlit run apps/problem_bridge_wizard.py --server.headless true --server.address 127.0.0.1 --server.port 8501
if errorlevel 1 (
    echo ProblemBridge UI failed to start.
    pause
    exit /b 1
)

endlocal
