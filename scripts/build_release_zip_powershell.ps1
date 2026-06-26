param(
    [string]$Version = "v0.3.2"
)

$ErrorActionPreference = "Stop"

# Default output: ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

New-Item -ItemType Directory -Force "dist" | Out-Null

$packageName = "ProblemBridge-ClaimHarness-$Version-local-webapp.zip"
$outputPath = Join-Path "dist" $packageName
$prefix = "ProblemBridge-ClaimHarness-$Version/"

if (Test-Path $outputPath) {
    Remove-Item $outputPath -Force
}

git archive --format=zip --prefix=$prefix --output=$outputPath HEAD

$resolved = (Resolve-Path $outputPath).Path
Write-Host "Release package written to $resolved"
