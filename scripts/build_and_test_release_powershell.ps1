param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$pyprojectText = Get-Content -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Raw
$versionMatch = [regex]::Match($pyprojectText, '(?m)^version\s*=\s*"([^"]+)"\s*$')
if (-not $versionMatch.Success) {
    throw "Could not derive the release version from pyproject.toml."
}
$derivedVersion = "v$($versionMatch.Groups[1].Value)"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $derivedVersion
}
elseif ($Version -ne $derivedVersion) {
    throw "Requested release version $Version does not match project version $derivedVersion."
}

$packageName = "ProblemBridge-ClaimHarness-$Version-local-webapp.zip"
$zipPath = Join-Path $repoRoot "dist\$packageName"
$manifestPath = "$zipPath.manifest.json"

& (Join-Path $PSScriptRoot "build_release_zip_powershell.ps1") -Version $Version
if (-not (Test-Path -LiteralPath $zipPath) -or -not (Test-Path -LiteralPath $manifestPath)) {
    throw "Release build did not create the package and manifest."
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($manifest.sha256 -ne $actualHash) {
    throw "Release SHA-256 does not match the release manifest."
}
if ($manifest.version -ne $Version -or $manifest.project_version -ne $versionMatch.Groups[1].Value) {
    throw "Release manifest version does not match pyproject.toml."
}
if (@($manifest.sample_runs).Count -ne 4) {
    throw "Release manifest does not contain provenance for all four committed sample runs."
}

& (Join-Path $PSScriptRoot "test_release_zip_powershell.ps1") -ZipPath $zipPath
Write-Host "Build-and-test release gate passed for $packageName"
