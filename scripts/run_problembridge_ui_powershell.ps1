$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
& .\.venv\Scripts\python.exe -m streamlit run apps/problem_bridge_wizard.py

