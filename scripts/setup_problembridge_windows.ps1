param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Test-SupportedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$Arguments = @()
    )

    try {
        & $Command @Arguments -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-SupportedPython {
    $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (($null -ne $pythonCommand) -and (Test-SupportedPython -Command $pythonCommand.Source)) {
        return @{ Command = $pythonCommand.Source; Arguments = @() }
    }

    $pyCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $pyCommand) {
        foreach ($version in @("3.13", "3.12", "3.11", "3.10")) {
            $arguments = @("-$version")
            if (Test-SupportedPython -Command $pyCommand.Source -Arguments $arguments) {
                return @{ Command = $pyCommand.Source; Arguments = $arguments }
            }
        }
    }

    return $null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$setupMarker = Join-Path $repoRoot ".venv\.claimharness_setup_v0.4.0"
$constraints = Join-Path $repoRoot "requirements\constraints.txt"

if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    if (-not (Test-SupportedPython -Command $venvPython)) {
        throw "The existing .venv must use Python 3.10 through 3.13. Remove it or recreate it with a supported interpreter."
    }
    if ((Test-Path $setupMarker) -and -not $Force) {
        Write-Host "ProblemBridge v0.4.0 environment is already prepared."
        exit 0
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating local Python environment..."
    $pythonSelection = Find-SupportedPython
    if ($null -eq $pythonSelection) {
        throw 'Python 3.10 through 3.13 was not found. Install a supported version and enable "Add python.exe to PATH".'
    }
    $bootstrapPython = $pythonSelection.Command
    $bootstrapArgs = @($pythonSelection.Arguments)
    & $bootstrapPython @bootstrapArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the local Python environment (exit code $LASTEXITCODE)."
    }
}

if (-not (Test-Path $venvPython)) {
    throw "The local Python environment could not be created."
}
if (-not (Test-SupportedPython -Command $venvPython)) {
    throw "The local Python environment must use Python 3.10 through 3.13."
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
