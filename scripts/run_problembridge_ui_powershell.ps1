$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating local Python environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the local Python environment with the py launcher (exit code $LASTEXITCODE)."
        }
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the local Python environment with python (exit code $LASTEXITCODE)."
        }
    }
    else {
        throw 'Python 3.10 or newer was not found. Install Python and enable "Add python.exe to PATH".'
    }
}

if (-not (Test-Path $venvPython)) {
    throw "The local Python environment could not be created."
}

Write-Host "Installing or updating ProblemBridge UI dependencies..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in the local Python environment (exit code $LASTEXITCODE)."
}

& $venvPython -m pip install -e ".[dev,ui]"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install ProblemBridge UI dependencies (exit code $LASTEXITCODE)."
}

Write-Host "Starting ProblemBridge local UI..."
Write-Host "If the browser does not open, visit http://127.0.0.1:8501"
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8501'"
)

& $venvPython -m streamlit run apps/problem_bridge_wizard.py --server.headless true --server.address 127.0.0.1 --server.port 8501
if ($LASTEXITCODE -ne 0) {
    throw "ProblemBridge UI exited with code $LASTEXITCODE."
}
