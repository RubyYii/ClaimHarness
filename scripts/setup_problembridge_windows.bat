@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_problembridge_windows.ps1" %*
if errorlevel 1 (
    echo ProblemBridge first-run setup failed.
    pause
    exit /b 1
)

endlocal
