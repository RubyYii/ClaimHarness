param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$setupMarker = Join-Path $repoRoot ".venv\.claimharness_setup_v0.4.0"
$constraints = Join-Path $repoRoot "requirements\constraints.txt"

if ((Test-Path $venvPython) -and (Test-Path $setupMarker) -and -not $Force) {
    Write-Host "ProblemBridge v0.4.0 environment is already prepared."
    exit 0
}

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
if (-not (Test-Path $constraints)) {
    throw "Dependency constraints are missing: $constraints"
}

Write-Host "Installing the tested ProblemBridge UI dependency set..."
& $venvPython -m pip install "pip==25.0.1"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install the tested pip version (exit code $LASTEXITCODE)."
}

& $venvPython -m pip install --only-binary=:all: -c $constraints -e ".[dev,ui]"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install the tested ProblemBridge UI dependency wheels (exit code $LASTEXITCODE). Check package-index access and wheel availability for this Python/platform."
}

New-Item -ItemType File -Force $setupMarker | Out-Null
Write-Host "ProblemBridge v0.4.0 environment is ready."
