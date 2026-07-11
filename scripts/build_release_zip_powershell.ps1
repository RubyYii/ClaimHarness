param(
    [string]$Version = "v0.3.3"
)

$ErrorActionPreference = "Stop"

# Default output: ProblemBridge-ClaimHarness-v0.3.3-local-webapp.zip
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$workingTreeStatus = git status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) {
    throw "git status failed while checking release readiness (exit code $LASTEXITCODE)."
}
if ($workingTreeStatus) {
    throw "Working tree is dirty. Commit or explicitly remove tracked and untracked changes before building a release package."
}

New-Item -ItemType Directory -Force "dist" | Out-Null

$packageName = "ProblemBridge-ClaimHarness-$Version-local-webapp.zip"
$outputPath = Join-Path "dist" $packageName
$prefix = "ProblemBridge-ClaimHarness-$Version/"

if (Test-Path $outputPath) {
    Remove-Item $outputPath -Force
}

git archive --format=zip --prefix=$prefix --output=$outputPath HEAD
if ($LASTEXITCODE -ne 0) {
    throw "git archive failed while building the release package (exit code $LASTEXITCODE)."
}

$resolved = (Resolve-Path $outputPath).Path
Write-Host "Release package written to $resolved"
