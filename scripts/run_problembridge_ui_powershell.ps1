$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$setupMarker = Join-Path $repoRoot ".venv\.claimharness_setup_v0.4.0"

if (-not (Test-Path $venvPython) -or -not (Test-Path $setupMarker)) {
    Write-Host "First run or version change detected; preparing the local environment once..."
    & (Join-Path $PSScriptRoot "setup_problembridge_windows.ps1")
    if (-not (Test-Path $venvPython) -or -not (Test-Path $setupMarker)) {
        throw "ProblemBridge setup did not complete successfully."
    }
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
