param(
    [string]$ZipPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    $pyprojectText = Get-Content -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Raw
    $versionMatch = [regex]::Match($pyprojectText, '(?m)^version\s*=\s*"([^"]+)"\s*$')
    if (-not $versionMatch.Success) {
        throw "Could not derive the release ZIP name from pyproject.toml."
    }
    $ZipPath = Join-Path $repoRoot (
        "dist\ProblemBridge-ClaimHarness-v$($versionMatch.Groups[1].Value)-local-webapp.zip"
    )
}

$zipFullPath = (Resolve-Path $ZipPath).Path
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "pb_release_zip_test_" + [System.Guid]::NewGuid().ToString("N")
)

# The repository interpreter is used only to create a new venv and preflight
# syntax. No repository-installed dependency is available to the smoke tests.
$repoVenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $repoVenvPython -PathType Leaf) {
    $bootstrapPython = $repoVenvPython
    $bootstrapArgs = @()
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $bootstrapPython = "py"
    $bootstrapArgs = @("-3")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $bootstrapPython = "python"
    $bootstrapArgs = @()
}
else {
    throw "Python 3.10+ is required to test the release ZIP."
}

$oldNoUserSite = $env:PYTHONNOUSERSITE
$oldRequireVenv = $env:PIP_REQUIRE_VIRTUALENV
try {
    New-Item -ItemType Directory -Force $testRoot | Out-Null
    Expand-Archive -Path $zipFullPath -DestinationPath $testRoot -Force

    $packageDirectories = @(Get-ChildItem -Path $testRoot -Directory)
    if ($packageDirectories.Count -ne 1) {
        throw "Release ZIP must contain exactly one package root directory."
    }
    $packageDir = $packageDirectories[0]

    $requiredFiles = @(
        ".gitattributes",
        "README.md",
        "README.zh-CN.md",
        "NON_AI_USER_GUIDE.md",
        "RUN_PROBLEMBRIDGE_WINDOWS.bat",
        "scripts/run_problembridge_ui_windows.bat",
        "apps/problem_bridge_wizard.py",
        "claim_harness/__init__.py",
        "claim_harness/__main__.py",
        "claim_harness/cli.py",
        "claim_harness/run_records.py",
        "claim_harness/evidence_contract.py",
        "claim_harness/evaluation.py",
        "claim_harness/eval_data/gold_claims.jsonl",
        "claim_harness/prompts/audit_summary.md",
        "claim_harness/demo_data/manuscript.md",
        "claim_harness/demo_data/references.md",
        "claim_harness/demo_data/tables/table1_metrics.csv",
        "claim_harness/demo_data/tables/table2_ablation.csv",
        "problem_bridge/__init__.py",
        "problem_bridge/__main__.py",
        "problem_bridge/cli.py",
        "problem_bridge/document_intake.py",
        "problem_bridge/revision_governance.py",
        "problem_bridge/project_lifecycle.py",
        "problem_bridge/demo_data/problem.md",
        "examples/problem_bridge/quality_inspection/problem.md",
        "examples/problem_bridge/cultural_archive/problem.md",
        "examples/problem_bridge/training_policy/problem.md",
        "docs/static_showcase/index.html",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
        "docs/v0.4_upgrade.md",
        "docs/sample_outputs/claimharness_lab_report_audit_demo/run_identity.json",
        "docs/sample_outputs/claimharness_lab_report_audit_demo/run_complete.json",
        "docs/sample_outputs/quality_inspection_alignment/run_identity.json",
        "docs/sample_outputs/quality_inspection_alignment/run_complete.json",
        "docs/sample_outputs/cultural_archive_alignment/run_identity.json",
        "docs/sample_outputs/cultural_archive_alignment/run_complete.json",
        "docs/sample_outputs/training_policy_alignment/run_identity.json",
        "docs/sample_outputs/training_policy_alignment/run_complete.json",
        "requirements/constraints.txt",
        "scripts/evaluate_gold_set.py",
        "scripts/setup_problembridge_windows.ps1",
        "scripts/setup_problembridge_windows.bat",
        "pyproject.toml"
    )

    foreach ($relative in $requiredFiles) {
        $path = Join-Path $packageDir.FullName ($relative -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing required file in release zip: $relative"
        }
    }

    $pythonFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $packageDir.FullName "claim_harness") -Recurse -File -Filter "*.py"
        Get-ChildItem -LiteralPath (Join-Path $packageDir.FullName "problem_bridge") -Recurse -File -Filter "*.py"
        Get-ChildItem -LiteralPath (Join-Path $packageDir.FullName "apps") -Recurse -File -Filter "*.py"
    )
    if ($pythonFiles.Count -eq 0) {
        throw "No Python package files were found in the extracted release zip."
    }
    foreach ($pythonFile in $pythonFiles) {
        $relative = $pythonFile.FullName.Replace(
            $packageDir.FullName + [System.IO.Path]::DirectorySeparatorChar,
            ""
        )
        & $bootstrapPython @bootstrapArgs -m py_compile $pythonFile.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Python syntax check failed for release file: $relative (exit code $LASTEXITCODE)."
        }
    }

    $smokeVenv = Join-Path $testRoot "clean-smoke-venv"
    & $bootstrapPython @bootstrapArgs -m venv $smokeVenv
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the clean release-test venv (exit code $LASTEXITCODE)."
    }
    $venvPython = Join-Path $smokeVenv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        $venvPython = Join-Path $smokeVenv "bin/python"
    }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "The clean release-test venv does not contain a Python interpreter."
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PIP_REQUIRE_VIRTUALENV = "true"
    $constraints = Join-Path $packageDir.FullName "requirements\constraints.txt"

    & $venvPython -m pip install --disable-pip-version-check -c $constraints "pip==25.0.1" "setuptools==75.6.0" "wheel==0.45.1" "build==1.2.2.post1"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install constrained build tooling in the clean venv (exit code $LASTEXITCODE)."
    }

    Push-Location $packageDir.FullName
    try {
        & $venvPython -m pip install --disable-pip-version-check --no-build-isolation -c $constraints ".[dev,ui]"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install the extracted release under constraints (exit code $LASTEXITCODE)."
        }
    }
    finally {
        Pop-Location
    }

    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw "The clean release-test venv has incompatible dependencies (exit code $LASTEXITCODE)."
    }

    $installGate = @'
from importlib import metadata
from pathlib import Path
import sys

venv = Path(sys.argv[1]).resolve()
repo = Path(sys.argv[2]).resolve()
expected = {'typer': '0.15.1', 'click': '8.1.8'}
if Path(sys.prefix).resolve() != venv:
    raise RuntimeError(f'Smoke interpreter is outside the clean venv: {sys.prefix}')
for distribution, version in expected.items():
    actual = metadata.version(distribution)
    if actual != version:
        raise RuntimeError(f'{distribution} resolved to {actual}, expected {version}')
for package_name in ('claim_harness', 'problem_bridge'):
    module = __import__(package_name)
    origin = Path(module.__file__).resolve()
    if repo == origin or repo in origin.parents:
        raise RuntimeError(f'{package_name} leaked from repository checkout: {origin}')
    if venv not in origin.parents:
        raise RuntimeError(f'{package_name} is outside the clean venv: {origin}')
'@
    $sampleGate = @'
import json
from pathlib import Path
import sys

from problem_bridge.project_lifecycle import load_run_completion

root = Path(sys.argv[1]).resolve()
samples = (
    'claimharness_lab_report_audit_demo',
    'quality_inspection_alignment',
    'cultural_archive_alignment',
    'training_policy_alignment',
)
for name in samples:
    sample = root / 'docs' / 'sample_outputs' / name
    identity = json.loads((sample / 'run_identity.json').read_text(encoding='utf-8'))
    completion = load_run_completion(sample)
    if identity['project_id'] != completion['project_id']:
        raise RuntimeError(f'Sample project identity mismatch: {name}')
    if identity['run_id'] != completion['run_id']:
        raise RuntimeError(f'Sample run identity mismatch: {name}')
'@
    Push-Location $testRoot
    try {
        & $venvPython -c $installGate $smokeVenv $repoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Clean venv isolation or constrained dependency check failed (exit code $LASTEXITCODE)."
        }

        & $venvPython -c $sampleGate $packageDir.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Packaged sample provenance validation failed (exit code $LASTEXITCODE)."
        }
    }
    finally {
        Pop-Location
    }

    $smokeRoot = Join-Path $testRoot "unrelated-smoke-cwd"
    $claimOut = Join-Path $smokeRoot "claim-harness-demo"
    $problemOut = Join-Path $smokeRoot "problem-bridge-demo"
    $evaluationOut = Join-Path $smokeRoot "synthetic-evaluation"
    New-Item -ItemType Directory -Force $smokeRoot | Out-Null

    Push-Location $smokeRoot
    try {
        & $venvPython -m claim_harness demo --out $claimOut
        if ($LASTEXITCODE -ne 0) {
            throw "ClaimHarness packaged demo failed (exit code $LASTEXITCODE)."
        }

        & $venvPython -m problem_bridge demo --out $problemOut
        if ($LASTEXITCODE -ne 0) {
            throw "ProblemBridge packaged demo failed (exit code $LASTEXITCODE)."
        }

        & $venvPython (Join-Path $packageDir.FullName "scripts\evaluate_gold_set.py") --out $evaluationOut
        if ($LASTEXITCODE -ne 0) {
            throw "Packaged synthetic evaluation failed (exit code $LASTEXITCODE)."
        }
    }
    finally {
        Pop-Location
    }

    $claimOutputs = @(
        "claim_table.csv",
        "evidence_map.json",
        "audit_report.md",
        "revision_suggestions.md",
        "agent_trace.jsonl",
        "run_manifest.json",
        "project_summary_log.md",
        "run_identity.json",
        "run_complete.json",
        "index.html"
    )
    foreach ($relative in $claimOutputs) {
        if (-not (Test-Path -LiteralPath (Join-Path $claimOut $relative) -PathType Leaf)) {
            throw "ClaimHarness packaged demo did not produce: $relative"
        }
    }

    $problemOutputs = @(
        "problem_card.md",
        "workflow_map.md",
        "painpoint_opportunity_matrix.csv",
        "concept_alignment_table.csv",
        "ai_task_spec.yaml",
        "evidence_contract.yaml",
        "evaluation_protocol.md",
        "misalignment_risk_report.md",
        "human_in_loop_plan.md",
        "implementation_routes.md",
        "alignment_trace.jsonl",
        "project_record.json",
        "project_summary_log.md",
        "run_identity.json",
        "run_complete.json"
    )
    foreach ($relative in $problemOutputs) {
        if (-not (Test-Path -LiteralPath (Join-Path $problemOut $relative) -PathType Leaf)) {
            throw "ProblemBridge packaged demo did not produce: $relative"
        }
    }

    foreach ($relative in @("evaluation_metrics.json", "evaluation_report.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $evaluationOut $relative) -PathType Leaf)) {
            throw "Packaged synthetic evaluation did not produce: $relative"
        }
    }

    Write-Host "Release zip test passed: $zipFullPath"
}
finally {
    if ($null -eq $oldNoUserSite) {
        Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
    if ($null -eq $oldRequireVenv) {
        Remove-Item Env:PIP_REQUIRE_VIRTUALENV -ErrorAction SilentlyContinue
    }
    else {
        $env:PIP_REQUIRE_VIRTUALENV = $oldRequireVenv
    }
    if (Test-Path $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
