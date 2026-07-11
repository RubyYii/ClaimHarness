param(
    [string]$ZipPath = "dist\ProblemBridge-ClaimHarness-v0.3.3-local-webapp.zip"
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
        "claim_harness/__init__.py",
        "claim_harness/__main__.py",
        "claim_harness/cli.py",
        "claim_harness/run_records.py",
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
        "problem_bridge/demo_data/problem.md",
        "examples/problem_bridge/quality_inspection/problem.md",
        "examples/problem_bridge/cultural_archive/problem.md",
        "examples/problem_bridge/training_policy/problem.md",
        "docs/static_showcase/index.html",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
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
        & $python -m py_compile $pythonFile.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Python syntax check failed for release file: $relative (exit code $LASTEXITCODE)."
        }
    }

    # The repository interpreter supplies already-installed third-party dependencies only.
    # sys.path is rebuilt so both demos must import their own code and resources from the
    # extracted artifact, never from the repository checkout or the smoke-test cwd.
    $isolatedRunner = @'
import importlib
import runpy
import sys
from pathlib import Path

package_root = Path(sys.argv[1]).resolve()
repository_root = Path(sys.argv[2]).resolve()
package_name = sys.argv[3]
module_args = sys.argv[4:]
smoke_cwd = Path.cwd().resolve()

isolated_path = [str(package_root)]
for entry in sys.path:
    if not entry:
        continue
    try:
        resolved = Path(entry).resolve()
    except OSError:
        resolved = None
    if resolved in {package_root, repository_root, smoke_cwd}:
        continue
    isolated_path.append(entry)
sys.path[:] = isolated_path

package = importlib.import_module(package_name)
origin = Path(package.__file__).resolve()
if package_root != origin and package_root not in origin.parents:
    raise RuntimeError(f'{package_name} was imported from outside the extracted release: {origin}')

sys.argv = [package_name, *module_args]
exit_code = 0
try:
    runpy.run_module(f'{package_name}.__main__', run_name='__main__')
except SystemExit as exc:
    exit_code = exc.code or 0

for name, loaded_module in list(sys.modules.items()):
    if name != package_name and not name.startswith(package_name + '.'):
        continue
    loaded_file = getattr(loaded_module, '__file__', None)
    if not loaded_file:
        continue
    loaded_origin = Path(loaded_file).resolve()
    if package_root != loaded_origin and package_root not in loaded_origin.parents:
        raise RuntimeError(f'{name} was imported from outside the extracted release: {loaded_origin}')

if exit_code:
    raise SystemExit(exit_code)
'@

    $smokeRoot = Join-Path $testRoot "unrelated-smoke-cwd"
    $claimOut = Join-Path $smokeRoot "claim-harness-demo"
    $problemOut = Join-Path $smokeRoot "problem-bridge-demo"
    New-Item -ItemType Directory -Force $smokeRoot | Out-Null

    Push-Location $smokeRoot
    try {
        & $python -c $isolatedRunner $packageDir.FullName $repoRoot "claim_harness" "demo" "--out" $claimOut
        if ($LASTEXITCODE -ne 0) {
            throw "ClaimHarness packaged demo failed (exit code $LASTEXITCODE)."
        }

        & $python -c $isolatedRunner $packageDir.FullName $repoRoot "problem_bridge" "demo" "--out" $problemOut
        if ($LASTEXITCODE -ne 0) {
            throw "ProblemBridge packaged demo failed (exit code $LASTEXITCODE)."
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
        "project_summary_log.md"
    )
    foreach ($relative in $problemOutputs) {
        if (-not (Test-Path -LiteralPath (Join-Path $problemOut $relative) -PathType Leaf)) {
            throw "ProblemBridge packaged demo did not produce: $relative"
        }
    }

    Write-Host "Release zip test passed: $zipFullPath"
}
finally {
    if (Test-Path $testRoot) {
        Remove-Item -Recurse -Force $testRoot
    }
}
