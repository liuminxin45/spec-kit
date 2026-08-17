param(
    [string]$SpecKitSourcePath = "",
    [string]$ProjectPath = "",
    [switch]$Editable,
    [switch]$NoForce,
    [switch]$SkipProjectUpgrade,
    [switch]$ForceManagedAssetRefresh,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Output "Usage: install.ps1 [-SpecKitSourcePath <path>] [-ProjectPath <path>] [-Editable] [-NoForce] [-SkipProjectUpgrade] [-ForceManagedAssetRefresh] [-Help]"
    Write-Output "Installs specify-cli from this workspace-level spec-kit source."
    Write-Output "  -SpecKitSourcePath       Override the default spec-kit source root."
    Write-Output "  -ProjectPath             Upgrade this initialized Spec Kit project after CLI install."
    Write-Output "  -Editable                Install from the local source in editable mode."
    Write-Output "  -NoForce                 Do not pass --force to uv tool install."
    Write-Output "  -SkipProjectUpgrade      Install only the CLI even when a parent project is detected."
    Write-Output "  -ForceManagedAssetRefresh  Overwrite customized managed project/integration files."
    exit 0
}

function Invoke-SpecifyChecked {
    param([string[]]$Arguments)
    $output = & specify @Arguments 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "specify $($Arguments -join ' ') failed: $($output.Trim())"
    }
    return $output
}

function Invoke-SpecifyJson {
    param([string[]]$Arguments)
    $output = Invoke-SpecifyChecked -Arguments $Arguments
    $jsonStart = $output.IndexOf('{')
    if ($jsonStart -lt 0) { throw "specify $($Arguments -join ' ') did not return JSON" }
    return ($output.Substring($jsonStart) | ConvertFrom-Json)
}

$SpecKitRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($SpecKitSourcePath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:SPEC_KIT_SOURCE)) {
        $SpecKitSourcePath = $env:SPEC_KIT_SOURCE
    } else {
        $SpecKitSourcePath = $SpecKitRoot
    }
}
$SpecKitPath = (Resolve-Path -LiteralPath $SpecKitSourcePath -ErrorAction SilentlyContinue).Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install uv first, then rerun this script."
}
if (-not $SpecKitPath -or -not (Test-Path -LiteralPath (Join-Path $SpecKitPath "pyproject.toml"))) {
    throw "Spec Kit source is missing: $SpecKitSourcePath"
}

$uvArgs = @("tool", "install", $SpecKitPath)
if ($Editable) { $uvArgs = @("tool", "install", "--editable", $SpecKitPath) }
if (-not $NoForce) { $uvArgs += @("--force", "--reinstall") }

Write-Host "Installing specify-cli from $SpecKitPath"
& uv @uvArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& specify --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SkipProjectUpgrade) { exit 0 }

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Split-Path -Parent $SpecKitPath
}
$resolvedProject = Resolve-Path -LiteralPath $ProjectPath -ErrorAction SilentlyContinue
if (-not $resolvedProject -or -not (Test-Path -LiteralPath (Join-Path $resolvedProject.Path ".specify") -PathType Container)) {
    Write-Host "No initialized Spec Kit project detected; CLI installation is complete."
    exit 0
}
$project = $resolvedProject.Path
Write-Host "Upgrading project assets and integrations in $project"

$upgradeArgs = @("upgrade", "--project-dir", $project, "--source", $SpecKitPath)
if ($ForceManagedAssetRefresh) { $upgradeArgs += "--force" }
$projectPlan = Invoke-SpecifyJson -Arguments @($upgradeArgs + @("--dry-run", "--json"))
if ($projectPlan.status -ne "planned") { throw "Project asset upgrade preflight did not pass" }

$integrationStatePath = Join-Path $project ".specify\integration.json"
$integrationKeys = @()
if (Test-Path -LiteralPath $integrationStatePath -PathType Leaf) {
    $integrationState = Get-Content -LiteralPath $integrationStatePath -Raw | ConvertFrom-Json
    $integrationKeys = @($integrationState.installed_integrations)
    if (-not $integrationKeys -and $integrationState.integration) {
        $integrationKeys = @([string]$integrationState.integration)
    }
}
foreach ($key in $integrationKeys) {
    $integrationArgs = @("integration", "upgrade", [string]$key, "--project-dir", $project)
    if ($ForceManagedAssetRefresh) { $integrationArgs += "--force" }
    $plan = Invoke-SpecifyJson -Arguments @($integrationArgs + @("--dry-run", "--json"))
    if ($plan.status -ne "planned") { throw "Integration upgrade preflight did not pass: $key" }
}

Invoke-SpecifyChecked -Arguments $upgradeArgs | Out-Null
foreach ($key in $integrationKeys) {
    $integrationArgs = @("integration", "upgrade", [string]$key, "--project-dir", $project)
    if ($ForceManagedAssetRefresh) { $integrationArgs += "--force" }
    Invoke-SpecifyChecked -Arguments $integrationArgs | Out-Null
}

foreach ($tool in @("validate-generated-context", "validate-knowledge-index", "validate-context-budget")) {
    $script = Join-Path $project ".specify\scripts\powershell\$tool.ps1"
    $validation = & $script -RepoRoot $project -Json | ConvertFrom-Json
    if ($validation.status -ne "ok") {
        throw "Post-install validation failed ($tool): $($validation.blockers -join '; ')"
    }
}

$selfCheck = Invoke-SpecifyJson -Arguments @("self", "check", "--project-dir", $project, "--json")
if ($selfCheck.status -in @("outdated", "incomplete")) {
    throw "Project upgrade did not pass final version/integrity verification: $($selfCheck.status)"
}
Write-Host "Project verification: $($selfCheck.status)"
