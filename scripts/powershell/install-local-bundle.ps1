param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [switch]$SkipKnowledgePacks,
    [switch]$ForceManagedAssetRefresh,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$bundleRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$wheel = @(Get-ChildItem -LiteralPath (Join-Path $bundleRoot "spec-kit") -Filter "specify_cli-*.whl" -File)
if ($wheel.Count -ne 1) { throw "Expected exactly one Spec Kit wheel under spec-kit/." }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required." }

& uv tool install $wheel[0].FullName --force --reinstall
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& specify --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
    New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
}
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$existing = Test-Path -LiteralPath (Join-Path $project ".specify\spec-kit.lock.yml") -PathType Leaf
if ($existing) {
    $upgradeArgs = @("upgrade", "--project-dir", $project)
    if ($ForceManagedAssetRefresh) { $upgradeArgs += "--force" }
    & specify @upgradeArgs
    $initExitCode = $LASTEXITCODE
} else {
    Push-Location $project
    try {
        & specify init --here --force --no-git --ignore-agent-tools
        $initExitCode = $LASTEXITCODE
    }
    finally { Pop-Location }
}
if ($initExitCode -ne 0) { exit $initExitCode }

$packIds = @()
if (-not $SkipKnowledgePacks) {
    $manifest = Get-Content -LiteralPath (Join-Path $bundleRoot "bundle-manifest.json") -Raw | ConvertFrom-Json
    $installScript = Join-Path $project ".specify\scripts\powershell\install-knowledge-pack.ps1"
    $composeScript = Join-Path $project ".specify\scripts\powershell\compose-knowledge-packs.ps1"
    foreach ($pack in @($manifest.knowledge_packs)) {
        $packPath = Join-Path $bundleRoot ([string]$pack.directory)
        $result = & $installScript -RepoRoot $project -PackPath $packPath -Force -Json | ConvertFrom-Json
        if ($result.status -ne "ok") { throw ($result.blockers -join "; ") }
        $packIds += [string]$pack.id
    }
    $compose = & $composeScript -RepoRoot $project -PackId $packIds -Json | ConvertFrom-Json
    if ($compose.status -ne "ok") { throw ($compose.blockers -join "; ") }
}

$validations = @()
foreach ($tool in @("validate-generated-context", "validate-knowledge-index", "validate-context-budget")) {
    $script = Join-Path $project ".specify\scripts\powershell\$tool.ps1"
    $result = & $script -RepoRoot $project -Json | ConvertFrom-Json
    $validations += $result
    if ($result.status -ne "ok") { throw ($result.blockers -join "; ") }
}
$summary = [ordered]@{
    status = "ok"
    project = $project
    spec_kit_wheel = $wheel[0].FullName
    knowledge_packs = $packIds
    promotion_performed = $false
    validations = @($validations | ForEach-Object { [ordered]@{ tool = $_.tool; status = $_.status } })
}
if ($Json) { $summary | ConvertTo-Json -Depth 8 } else { $summary | Format-List }
