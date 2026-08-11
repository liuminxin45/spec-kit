param(
    [string]$RepoRoot = "",
    [string]$WorkspaceRoot = "",
    [string]$OutputDir = "",
    [string[]]$KnowledgePack = @(),
    [switch]$Json
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = (Resolve-Path -LiteralPath (Join-Path $RepoRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $versionResult = & (Join-Path $PSScriptRoot "get-spec-kit-version.ps1") -RepoRoot $RepoRoot -Json | ConvertFrom-Json
    if ($versionResult.status -ne "ok") { throw ($versionResult.blockers -join "; ") }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $WorkspaceRoot ".specify\distributions\spec-kit-local-$($versionResult.facts.version)-$stamp"
}

foreach ($packName in $KnowledgePack) {
    $packPath = Join-Path $WorkspaceRoot ".specify\knowledge\exports\$packName"
    $validation = & (Join-Path $PSScriptRoot "validate-knowledge-pack.ps1") -PackRoot $packPath -Json | ConvertFrom-Json
    if ($validation.status -ne "ok") {
        throw "Knowledge pack validation failed for ${packName}: $($validation.blockers -join '; ')"
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python 3.11+ is required to build the local distribution." }
$pythonVersion = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or [version]$pythonVersion -lt [version]"3.11") {
    throw "Python 3.11+ is required to build the local distribution; found $pythonVersion."
}
$pythonArgs = @(
    (Join-Path $RepoRoot "scripts\python\build_local_distribution.py"),
    "--repo-root", $RepoRoot,
    "--workspace-root", $WorkspaceRoot,
    "--output-dir", $OutputDir,
    "--json"
)
foreach ($packName in $KnowledgePack) { $pythonArgs += @("--knowledge-pack", $packName) }
& $python.Source @pythonArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
