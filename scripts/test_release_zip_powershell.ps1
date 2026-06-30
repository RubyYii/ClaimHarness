param(
    [string]$ZipPath = "dist\ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$zipFullPath = (Resolve-Path $ZipPath).Path
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("pb_release_zip_test_" + [System.Guid]::NewGuid().ToString("N"))
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

try {
    New-Item -ItemType Directory -Force $testRoot | Out-Null
    Expand-Archive -Path $zipFullPath -DestinationPath $testRoot -Force

    $packageDir = Get-ChildItem -Path $testRoot -Directory | Select-Object -First 1
    if ($null -eq $packageDir) {
        throw "No package directory found after extracting $zipFullPath"
    }

    $requiredFiles = @(
        "README.md",
        "README.zh-CN.md",
        "NON_AI_USER_GUIDE.md",
        "RUN_PROBLEMBRIDGE_WINDOWS.bat",
        "scripts/run_problembridge_ui_windows.bat",
        "apps/problem_bridge_wizard.py",
        "problem_bridge/document_intake.py",
        "docs/static_showcase/index.html",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
        "pyproject.toml"
    )

    foreach ($relative in $requiredFiles) {
        $path = Join-Path $packageDir.FullName ($relative -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $path)) {
            throw "Missing required file in release zip: $relative"
        }
    }

    $uiPath = Join-Path $packageDir.FullName "apps\problem_bridge_wizard.py"
    & $python -m py_compile $uiPath

    $intakePath = Join-Path $packageDir.FullName "problem_bridge\document_intake.py"
    & $python -m py_compile $intakePath

    Write-Host "Release zip test passed: $zipFullPath"
}
finally {
    if (Test-Path $testRoot) {
        Remove-Item -Recurse -Force $testRoot
    }
}
