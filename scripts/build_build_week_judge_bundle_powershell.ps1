param(
    [string]$Version = "",
    [string]$PythonExe = "",
    [string]$Gpt56RunPath = ""
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    $resolvedPath = (Resolve-Path -LiteralPath $LiteralPath).Path
    $stream = [System.IO.File]::OpenRead($resolvedPath)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha256.ComputeHash($stream)
            return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Resolve-BundlePython {
    param(
        [string]$RepositoryRoot,
        [string]$ExplicitPython
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPython)) {
        if (-not (Test-Path -LiteralPath $ExplicitPython -PathType Leaf)) {
            throw "Explicit Python executable was not found: $ExplicitPython"
        }
        return [ordered]@{
            command = (Resolve-Path -LiteralPath $ExplicitPython).Path
            prefix_args = @()
        }
    }

    $repoPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $repoPython -PathType Leaf) {
        return [ordered]@{
            command = (Resolve-Path -LiteralPath $repoPython).Path
            prefix_args = @()
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return [ordered]@{
            command = "py"
            prefix_args = @("-3")
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return [ordered]@{
            command = "python"
            prefix_args = @()
        }
    }
    throw "Python 3.10+ with project dependencies is required to build the judge bundle."
}

function Assert-SafeTemporaryPath {
    param([string]$Path)

    $temporaryRoot = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    ).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $candidate = [System.IO.Path]::GetFullPath($Path)
    $requiredPrefix = $temporaryRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith(
        $requiredPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to use a judge-bundle staging directory outside the system temporary root."
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$pyprojectText = Get-Content `
    -LiteralPath (Join-Path $repoRoot "pyproject.toml") `
    -Raw
$versionMatch = [regex]::Match(
    $pyprojectText,
    '(?m)^version\s*=\s*"([^"]+)"\s*$'
)
if (-not $versionMatch.Success) {
    throw "Could not derive the project version from pyproject.toml."
}
$projectVersion = $versionMatch.Groups[1].Value
$derivedVersion = "v$projectVersion"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $derivedVersion
}
elseif ($Version -ne $derivedVersion) {
    throw "Requested bundle version $Version does not match project version $derivedVersion."
}

$releaseArgs = @{ Version = $Version }
if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
    $releaseArgs.PythonExe = $PythonExe
}
& (Join-Path $PSScriptRoot "build_and_test_release_powershell.ps1") @releaseArgs

$releaseName = "ProblemBridge-ClaimHarness-$Version-local-webapp.zip"
$releasePath = Join-Path $repoRoot "dist\$releaseName"
$releaseManifestPath = "$releasePath.manifest.json"
$releaseShaPath = "$releasePath.sha256"
foreach ($requiredReleaseFile in @(
    $releasePath,
    $releaseManifestPath,
    $releaseShaPath
)) {
    if (-not (Test-Path -LiteralPath $requiredReleaseFile -PathType Leaf)) {
        throw "Verified local release artifact is missing: $requiredReleaseFile"
    }
}

$python = Resolve-BundlePython `
    -RepositoryRoot $repoRoot `
    -ExplicitPython $PythonExe
$pythonCommand = [string]$python.command
$pythonPrefixArgs = @($python.prefix_args)
$bundleName = "ProblemBridge-ClaimHarness-$Version-build-week-2026-judge-bundle"
$bundleZip = Join-Path $repoRoot "dist\$bundleName.zip"
$bundleManifestPath = "$bundleZip.manifest.json"
$bundleShaPath = "$bundleZip.sha256"
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "pb_build_week_bundle_" + [System.Guid]::NewGuid().ToString("N")
)
Assert-SafeTemporaryPath -Path $stagingRoot
$bundleRoot = Join-Path $stagingRoot $bundleName
$gpt56EvidenceIncluded = $false

try {
    New-Item -ItemType Directory -Force $bundleRoot | Out-Null
    $documents = Join-Path $bundleRoot "documents"
    $release = Join-Path $bundleRoot "release"
    $mockOutput = Join-Path $bundleRoot "mock_demo_output"
    New-Item -ItemType Directory -Force $documents | Out-Null
    New-Item -ItemType Directory -Force $release | Out-Null

    Copy-Item `
        -LiteralPath (Join-Path $repoRoot "JUDGE_START_HERE.md") `
        -Destination (Join-Path $bundleRoot "START_HERE.md")
    foreach ($documentName in @(
        "BUILD_WEEK_DELTA.md",
        "BUILD_WEEK_SUBMISSION.md",
        "DEMO_SCRIPT_BUILD_WEEK_3MIN.md",
        "DEVPOST_DRAFT.md",
        "MODEL_PROVIDER_GUIDE.md"
    )) {
        Copy-Item `
            -LiteralPath (Join-Path $repoRoot $documentName) `
            -Destination (Join-Path $documents $documentName)
    }
    Copy-Item -LiteralPath $releasePath -Destination $release
    Copy-Item -LiteralPath $releaseManifestPath -Destination $release
    Copy-Item -LiteralPath $releaseShaPath -Destination $release

    & $pythonCommand @pythonPrefixArgs `
        -m problem_bridge build-week-demo `
        --out $mockOutput `
        --llm mock
    if ($LASTEXITCODE -ne 0) {
        throw "Could not generate the deterministic mock output for the judge bundle."
    }
    $mockRuntime = Get-Content `
        -LiteralPath (Join-Path $mockOutput "gpt_5_6_runtime.json") `
        -Raw | ConvertFrom-Json
    if ([bool]$mockRuntime.gpt_5_6_used -or [bool]$mockRuntime.contains_api_key) {
        throw "Mock judge output violates the no-key runtime truth boundary."
    }

    if (-not [string]::IsNullOrWhiteSpace($Gpt56RunPath)) {
        if (-not (Test-Path -LiteralPath $Gpt56RunPath -PathType Container)) {
            throw "GPT-5.6 evidence run directory was not found: $Gpt56RunPath"
        }
        $resolvedGptRun = (Resolve-Path -LiteralPath $Gpt56RunPath).Path
        $runtimePath = Join-Path $resolvedGptRun "gpt_5_6_runtime.json"
        if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
            throw "GPT-5.6 evidence run has no gpt_5_6_runtime.json."
        }
        $gptRuntime = Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
        if (
            -not [bool]$gptRuntime.gpt_5_6_used -or
            [bool]$gptRuntime.contains_api_key -or
            [string]$gptRuntime.provider -ne "openai" -or
            -not ([string]$gptRuntime.model).StartsWith(
                "gpt-5.6",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "The optional evidence directory is not a verified non-secret GPT-5.6 run."
        }

        $gptEvidence = Join-Path $bundleRoot "gpt56_runtime_evidence"
        New-Item -ItemType Directory -Force $gptEvidence | Out-Null
        foreach ($evidenceName in @(
            "gpt_5_6_runtime.json",
            "build_record.jsonl",
            "claim_decisions.csv",
            "build_contract.md",
            "run_identity.json",
            "run_complete.json"
        )) {
            $source = Join-Path $resolvedGptRun $evidenceName
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
                throw "GPT-5.6 evidence run is missing: $evidenceName"
            }
            Copy-Item -LiteralPath $source -Destination $gptEvidence
        }
        $gpt56EvidenceIncluded = $true
    }

    $commit = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not record the judge-bundle Git commit."
    }
    $bundleRootPrefix = $bundleRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $contentFiles = @(
        Get-ChildItem -LiteralPath $bundleRoot -Recurse -File |
        Sort-Object FullName |
        ForEach-Object {
            [ordered]@{
                path = $_.FullName.Substring($bundleRootPrefix.Length).Replace("\", "/")
                size_bytes = $_.Length
                sha256 = Get-Sha256Hex -LiteralPath $_.FullName
            }
        }
    )
    $contentManifest = [ordered]@{
        schema_version = 1
        project = "ProblemBridge + ClaimHarness"
        competition = "OpenAI Build Week 2026"
        project_version = $projectVersion
        git_commit = $commit
        mock_demo_included = $true
        gpt56_runtime_evidence_included = $gpt56EvidenceIncluded
        files = $contentFiles
    }
    $contentManifest |
        ConvertTo-Json -Depth 6 |
        Set-Content `
            -LiteralPath (Join-Path $bundleRoot "BUNDLE_CONTENT_MANIFEST.json") `
            -Encoding utf8

    foreach ($output in @($bundleZip, $bundleManifestPath, $bundleShaPath)) {
        if (Test-Path -LiteralPath $output) {
            Remove-Item -LiteralPath $output -Force
        }
    }
    Compress-Archive `
        -LiteralPath $bundleRoot `
        -DestinationPath $bundleZip `
        -CompressionLevel Optimal
    if (-not (Test-Path -LiteralPath $bundleZip -PathType Leaf)) {
        throw "Judge bundle ZIP was not created."
    }

    $bundleHash = Get-Sha256Hex -LiteralPath $bundleZip
    $outerManifest = [ordered]@{
        schema_version = 1
        package = [System.IO.Path]::GetFileName($bundleZip)
        project_version = $projectVersion
        git_commit = $commit
        sha256 = $bundleHash
        mock_demo_included = $true
        gpt56_runtime_evidence_included = $gpt56EvidenceIncluded
        local_release_package = $releaseName
    }
    $outerManifest |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $bundleManifestPath -Encoding utf8
    "$bundleHash  $([System.IO.Path]::GetFileName($bundleZip))" |
        Set-Content -LiteralPath $bundleShaPath -Encoding ascii

    Write-Host "Build Week judge bundle written to $((Resolve-Path $bundleZip).Path)"
    Write-Host "Bundle manifest written to $((Resolve-Path $bundleManifestPath).Path)"
    Write-Host "Bundle SHA-256 written to $((Resolve-Path $bundleShaPath).Path)"
    if (-not $gpt56EvidenceIncluded) {
        Write-Warning (
            "No real GPT-5.6 runtime evidence was added. Rebuild with " +
            "-Gpt56RunPath after completing a synthetic --llm openai run."
        )
    }
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Assert-SafeTemporaryPath -Path $stagingRoot
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
