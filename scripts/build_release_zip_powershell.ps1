param(
    [string]$Version = ""
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

function Read-ReleaseVersion {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing version source: $Path"
    }
    $content = Get-Content -LiteralPath $Path -Raw
    $match = [regex]::Match($content, $Pattern)
    if (-not $match.Success) {
        throw "Could not read $Label version from $Path"
    }
    return $match.Groups[1].Value
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$workingTreeStatus = git status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) {
    throw "git status failed while checking release readiness (exit code $LASTEXITCODE)."
}
if ($workingTreeStatus) {
    throw "Working tree is dirty. Commit or explicitly remove tracked and untracked changes before building a release package."
}

$projectVersion = Read-ReleaseVersion `
    -Path (Join-Path $repoRoot "pyproject.toml") `
    -Pattern '(?m)^version\s*=\s*"([^"]+)"\s*$' `
    -Label "pyproject"
$claimHarnessVersion = Read-ReleaseVersion `
    -Path (Join-Path $repoRoot "claim_harness\__init__.py") `
    -Pattern '(?m)^__version__\s*=\s*"([^"]+)"\s*$' `
    -Label "claim_harness package"
$problemBridgeVersion = Read-ReleaseVersion `
    -Path (Join-Path $repoRoot "problem_bridge\__init__.py") `
    -Pattern '(?m)^__version__\s*=\s*"([^"]+)"\s*$' `
    -Label "problem_bridge package"

if ($claimHarnessVersion -ne $projectVersion -or $problemBridgeVersion -ne $projectVersion) {
    throw (
        "Release version mismatch: pyproject=$projectVersion, " +
        "claim_harness=$claimHarnessVersion, problem_bridge=$problemBridgeVersion."
    )
}

$derivedVersion = "v$projectVersion"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $derivedVersion
}
elseif ($Version -ne $derivedVersion) {
    throw "Requested release version $Version does not match project version $derivedVersion."
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
    Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue
    throw "git archive failed while building the release package (exit code $LASTEXITCODE)."
}

try {
$commit = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) {
    throw "git rev-parse failed while recording release provenance (exit code $LASTEXITCODE)."
}

# Verify the archive boundary before publishing provenance. This catches an
# unexpected root, empty archives, and repository-local state leaking into ZIPs.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $outputPath))
try {
    $archiveFiles = @($archive.Entries | Where-Object { -not [string]::IsNullOrEmpty($_.Name) })
    $releaseTextExtensions = @(
        ".bat", ".csv", ".css", ".html", ".ini", ".js", ".json", ".jsonl",
        ".md", ".ps1", ".py", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"
    )
    $archiveTextEntryCount = 0
    if ($archiveFiles.Count -eq 0) {
        throw "Release archive contains no files."
    }
    foreach ($entry in $archiveFiles) {
        if (-not $entry.FullName.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            throw "Release archive entry is outside the expected root: $($entry.FullName)"
        }
        $relative = $entry.FullName.Substring($prefix.Length)
        if ($relative -match '(^|/)(\.git|\.venv|dist)(/|$)') {
            throw "Release archive contains forbidden repository-local content: $relative"
        }
        $extension = [System.IO.Path]::GetExtension($relative).ToLowerInvariant()
        if ($releaseTextExtensions -contains $extension) {
            $archiveTextEntryCount += 1
            $entryStream = $entry.Open()
            $memory = New-Object System.IO.MemoryStream
            try {
                $entryStream.CopyTo($memory)
                $bytes = $memory.ToArray()
                for ($index = 0; $index -lt ($bytes.Length - 1); $index += 1) {
                    if ($bytes[$index] -eq 13 -and $bytes[$index + 1] -eq 10) {
                        throw "Release archive text is not LF-normalized: $relative"
                    }
                }
            }
            finally {
                $memory.Dispose()
                $entryStream.Dispose()
            }
        }
    }
    $archiveEntryCount = $archiveFiles.Count
}
finally {
    $archive.Dispose()
}

# Validate committed sample run provenance from the archive itself, not from
# the checkout. Completion records bind each generated artifact to SHA-256.
$inspectionRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "pb_release_inspect_" + [System.Guid]::NewGuid().ToString("N")
)
$sampleRuns = @()
try {
    New-Item -ItemType Directory -Force $inspectionRoot | Out-Null
    Expand-Archive -LiteralPath (Resolve-Path $outputPath) -DestinationPath $inspectionRoot
    $archiveRoot = Join-Path $inspectionRoot $prefix.TrimEnd("/")
    $samplePaths = @(
        "docs/sample_outputs/claimharness_lab_report_audit_demo",
        "docs/sample_outputs/quality_inspection_alignment",
        "docs/sample_outputs/cultural_archive_alignment",
        "docs/sample_outputs/training_policy_alignment"
    )
    foreach ($samplePath in $samplePaths) {
        $sampleDirectory = Join-Path $archiveRoot ($samplePath -replace '/', [System.IO.Path]::DirectorySeparatorChar)
        $identityPath = Join-Path $sampleDirectory "run_identity.json"
        $completionPath = Join-Path $sampleDirectory "run_complete.json"
        if (-not (Test-Path -LiteralPath $identityPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $completionPath -PathType Leaf)) {
            throw "Sample provenance is incomplete in release archive: $samplePath"
        }
        $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
        $completion = Get-Content -LiteralPath $completionPath -Raw | ConvertFrom-Json
        if ([int]$identity.schema_version -ne 2 -or [int]$completion.schema_version -ne 2) {
            throw "Sample lifecycle schema is not current in release archive: $samplePath"
        }
        if ([string]::IsNullOrWhiteSpace($identity.project_id) -or
            [string]::IsNullOrWhiteSpace($identity.run_id) -or
            $identity.project_id -ne $completion.project_id -or
            $identity.run_id -ne $completion.run_id) {
            throw "Sample project/run identity mismatch in release archive: $samplePath"
        }
        $identityHash = Get-Sha256Hex -LiteralPath $identityPath
        if ($identityHash -ne [string]$completion.run_identity_sha256) {
            throw "Sample run identity SHA-256 mismatch in release archive: $samplePath"
        }
        $artifactProperties = @($completion.artifact_sha256.PSObject.Properties)
        if ($artifactProperties.Count -eq 0) {
            throw "Sample completion record contains no artifact hashes: $samplePath"
        }
        foreach ($artifact in $artifactProperties) {
            $artifactName = $artifact.Name
            if ([System.IO.Path]::GetFileName($artifactName) -ne $artifactName) {
                throw "Unsafe sample artifact path in completion record: $artifactName"
            }
            $artifactPath = Join-Path $sampleDirectory $artifactName
            if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
                throw "Sample completion artifact is missing from archive: $samplePath/$artifactName"
            }
            $artifactHash = Get-Sha256Hex -LiteralPath $artifactPath
            if ($artifactHash -ne [string]$artifact.Value) {
                throw "Sample completion SHA-256 mismatch: $samplePath/$artifactName"
            }
        }
        $sampleRuns += [ordered]@{
            path = $samplePath
            project_id = [string]$identity.project_id
            run_id = [string]$identity.run_id
            identity_sha256 = $identityHash
            completion_sha256 = Get-Sha256Hex -LiteralPath $completionPath
            artifact_count = $artifactProperties.Count
        }
    }
}
finally {
    if (Test-Path -LiteralPath $inspectionRoot) {
        Remove-Item -LiteralPath $inspectionRoot -Recurse -Force
    }
}

$hash = Get-Sha256Hex -LiteralPath $outputPath
$manifestPath = "$outputPath.manifest.json"
$shaPath = "$outputPath.sha256"
$manifest = [ordered]@{
    schema_version = 2
    package = $packageName
    version = $Version
    project_version = $projectVersion
    git_commit = $commit.Trim()
    archive_root = $prefix.TrimEnd("/")
    archive_entry_count = $archiveEntryCount
    archive_text_entry_count = $archiveTextEntryCount
    sha256 = $hash
    sample_runs = $sampleRuns
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
"$hash  $packageName" | Set-Content -LiteralPath $shaPath -Encoding ascii

$resolved = (Resolve-Path $outputPath).Path
Write-Host "Release package written to $resolved"
Write-Host "Release manifest written to $((Resolve-Path $manifestPath).Path)"
Write-Host "SHA-256 written to $((Resolve-Path $shaPath).Path)"
}
catch {
    Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$outputPath.manifest.json" -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$outputPath.sha256" -Force -ErrorAction SilentlyContinue
    throw
}
