@echo off
setlocal

cd /d "%~dp0\.." || (
    echo Could not change to the ProblemBridge project root.
    pause
    exit /b 1
)

set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo Creating local Python environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if not errorlevel 1 (
            python -m venv .venv
        ) else (
            echo Python 3.10 or newer was not found.
            echo Install Python from https://www.python.org/downloads/windows/
            echo During installation, enable "Add python.exe to PATH".
            pause
            exit /b 1
        )
    )
)

if not exist "%VENV_PYTHON%" (
    echo The local Python environment could not be created.
    pause
    exit /b 1
)

echo Installing or updating ProblemBridge UI dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo pip upgrade failed.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install -e ".[dev,ui]"
if errorlevel 1 (
    echo Dependency installation failed. Check your internet connection and Python installation.
    pause
    exit /b 1
)

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
