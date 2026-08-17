param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [switch]$SkipKnowledgePacks,
    [switch]$ForceManagedAssetRefresh,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

trap {
    $message = $_.Exception.Message
    if ($Json) {
        [ordered]@{
            status = "blocked"
            blockers = @($message)
        } | ConvertTo-Json -Depth 4
    } else {
        Write-Error $message
    }
    exit 1
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
    if ($jsonStart -lt 0) {
        throw "specify $($Arguments -join ' ') did not return JSON"
    }
    try {
        return ($output.Substring($jsonStart) | ConvertFrom-Json)
    }
    catch {
        throw "specify $($Arguments -join ' ') returned invalid JSON: $($_.Exception.Message)"
    }
}

function Assert-BundleChecksums {
    param([string]$BundleRoot)
    $checksumPath = Join-Path $BundleRoot "SHA256SUMS.json"
    if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
        throw "SHA256SUMS.json not found in bundle"
    }
    $failures = @()
    foreach ($item in @(Get-Content -LiteralPath $checksumPath -Raw | ConvertFrom-Json)) {
        $relative = [string]$item.path
        $parts = @($relative -split '[\\/]')
        if ([IO.Path]::IsPathRooted($relative) -or $parts -contains '..') {
            throw "Unsafe checksum path: $relative"
        }
        $candidate = [IO.Path]::GetFullPath((Join-Path $BundleRoot $relative))
        $prefix = $BundleRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Checksum path escapes bundle root: $relative"
        }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $failures += "$relative (missing)"
            continue
        }
        $actual = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne ([string]$item.sha256).ToLowerInvariant()) {
            $failures += "$relative (hash mismatch)"
        }
    }
    if ($failures) {
        throw "Bundle checksum verification failed: $($failures -join ', ')"
    }
}

$bundleRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
Assert-BundleChecksums -BundleRoot $bundleRoot

$manifestPath = Join-Path $bundleRoot "bundle-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "bundle-manifest.json not found in bundle"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$wheelRelative = [string]$manifest.spec_kit.wheel
if ([string]::IsNullOrWhiteSpace($wheelRelative)) {
    throw "bundle manifest is missing spec_kit.wheel"
}
$wheel = [IO.Path]::GetFullPath((Join-Path $bundleRoot $wheelRelative))
if (-not (Test-Path -LiteralPath $wheel -PathType Leaf)) {
    throw "Spec Kit wheel not found: $wheelRelative"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required." }

& uv tool install $wheel --force --reinstall
if ($LASTEXITCODE -ne 0) { throw "uv failed to install the bundled Spec Kit wheel" }
$installedVersion = (& specify --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "installed specify executable did not report a version" }

if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
    New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
}
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$existing = Test-Path -LiteralPath (Join-Path $project ".specify") -PathType Container
$upgradedIntegrations = @()

if ($existing) {
    $upgradeArgs = @("upgrade", "--project-dir", $project)
    if ($ForceManagedAssetRefresh) { $upgradeArgs += "--force" }
    $projectPlan = Invoke-SpecifyJson -Arguments @($upgradeArgs + @("--dry-run", "--json"))
    if ($projectPlan.status -ne "planned") {
        throw "Project asset upgrade preflight did not pass"
    }

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
        $integrationPlan = Invoke-SpecifyJson -Arguments @($integrationArgs + @("--dry-run", "--json"))
        if ($integrationPlan.status -ne "planned") {
            throw "Integration upgrade preflight did not pass: $key"
        }
    }

    Invoke-SpecifyChecked -Arguments $upgradeArgs | Out-Null
    foreach ($key in $integrationKeys) {
        $integrationArgs = @("integration", "upgrade", [string]$key, "--project-dir", $project)
        if ($ForceManagedAssetRefresh) { $integrationArgs += "--force" }
        Invoke-SpecifyChecked -Arguments $integrationArgs | Out-Null
        $upgradedIntegrations += [string]$key
    }
} else {
    Push-Location $project
    try {
        Invoke-SpecifyChecked -Arguments @("init", "--here", "--force", "--no-git", "--ignore-agent-tools") | Out-Null
    }
    finally { Pop-Location }
}

$packIds = @()
if (-not $SkipKnowledgePacks) {
    $packsById = @{}
    foreach ($pack in @($manifest.knowledge_packs)) {
        $packsById[[string]$pack.id] = $pack
    }
    $packIds = @($manifest.default_compose_order | ForEach-Object { [string]$_ })
    if ($packIds.Count -ne $packsById.Count) {
        throw "default_compose_order must contain every bundled knowledge pack exactly once"
    }
    $installScript = Join-Path $project ".specify\scripts\powershell\install-knowledge-pack.ps1"
    $composeScript = Join-Path $project ".specify\scripts\powershell\compose-knowledge-packs.ps1"
    foreach ($packId in $packIds) {
        if (-not $packsById.ContainsKey($packId)) {
            throw "default_compose_order references unknown pack: $packId"
        }
        $packPath = Join-Path $bundleRoot ([string]$packsById[$packId].directory)
        $result = & $installScript -RepoRoot $project -PackPath $packPath -Force -Json | ConvertFrom-Json
        if ($result.status -ne "ok") { throw ($result.blockers -join "; ") }
    }
    if ($packIds) {
        $compose = & $composeScript -RepoRoot $project -PackId $packIds -Json | ConvertFrom-Json
        if ($compose.status -ne "ok") { throw ($compose.blockers -join "; ") }
    }
}

$validations = @()
foreach ($tool in @("validate-generated-context", "validate-knowledge-index", "validate-context-budget")) {
    $script = Join-Path $project ".specify\scripts\powershell\$tool.ps1"
    $result = & $script -RepoRoot $project -Json | ConvertFrom-Json
    $validations += $result
    if ($result.status -ne "ok") { throw ($result.blockers -join "; ") }
}

$selfCheck = Invoke-SpecifyJson -Arguments @("self", "check", "--project-dir", $project, "--json")
if ($selfCheck.status -in @("outdated", "incomplete")) {
    throw "Installed project did not pass final version/integrity verification: $($selfCheck.status)"
}
$finalStatus = if ($selfCheck.status -eq "current") { "ok" } else { "warning" }
$summary = [ordered]@{
    status = $finalStatus
    project = $project
    spec_kit_wheel = $wheel
    installed_version = $installedVersion
    upgraded_integrations = $upgradedIntegrations
    knowledge_packs = $packIds
    promotion_performed = $false
    self_check = [ordered]@{
        status = $selfCheck.status
        assets = $selfCheck.project.assets.status
        integrations = @($selfCheck.project.integrations | ForEach-Object { [ordered]@{ key = $_.key; status = $_.status } })
    }
    validations = @($validations | ForEach-Object { [ordered]@{ tool = $_.tool; status = $_.status } })
}
if ($Json) { $summary | ConvertTo-Json -Depth 8 } else { $summary | Format-List }
