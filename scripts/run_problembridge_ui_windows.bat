@echo off
setlocal

if not exist .venv (
    python -m venv .venv
)

.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
.venv\Scripts\python.exe -m streamlit run apps/problem_bridge_wizard.py

endlocal

