param(
    [string]$RepoRoot = "",
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [switch]$Json
)

. "$PSScriptRoot/common.ps1"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Get-SpecKitRoot }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function New-DeliveryResult {
    [ordered]@{
        tool = "validate-plugin-delivery-chain"
        status = "ok"
        facts = [ordered]@{ plugins = @() }
        blockers = @()
        unknowns = @()
        hints = @()
    }
}

function Get-Value($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Resolve-ManifestPathValue([string]$Value, [string]$BaseDir) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $candidate = if ([IO.Path]::IsPathRooted($Value)) { $Value } else { Join-Path $BaseDir $Value }
    try { return [IO.Path]::GetFullPath($candidate) } catch { return $candidate }
}

function Get-FileHashValue([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return "" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Add-PluginBlocker($Result, [string]$PluginId, [string]$Message) {
    $Result.status = "blocked"
    $Result.blockers += "[$PluginId] $Message"
}

function Get-ArtifactBoundaryPath($Artifact, [string]$PropertyName, [string]$DefaultRoot, [string]$DefaultRelative, [string]$BaseDir) {
    $explicit = [string](Get-Value $Artifact $PropertyName)
    if (-not [string]::IsNullOrWhiteSpace($explicit)) {
        return Resolve-ManifestPathValue $explicit $BaseDir
    }
    if (-not [string]::IsNullOrWhiteSpace($DefaultRoot) -and -not [string]::IsNullOrWhiteSpace($DefaultRelative)) {
        return Join-Path $DefaultRoot $DefaultRelative
    }
    return ""
}

$result = New-DeliveryResult
if (-not [IO.Path]::IsPathRooted($ManifestPath)) { $ManifestPath = Join-Path $RepoRoot $ManifestPath }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    $result.status = "blocked"
    $result.blockers += "delivery manifest does not exist: $ManifestPath"
} else {
    $ManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
}
if ($result.status -eq "blocked") {
    if ($Json) { $result | ConvertTo-Json -Depth 30 } else { $result | Format-List }
    exit 0
}

try {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
} catch {
    $result.status = "blocked"
    $result.blockers += "delivery manifest is not valid JSON"
    if ($Json) { $result | ConvertTo-Json -Depth 30 } else { $result | Format-List }
    exit 0
}
$baseDir = Split-Path -Parent $ManifestPath
$plugins = @(Get-Value $manifest "plugins")
if ($plugins.Count -eq 0) {
    $result.status = "blocked"
    $result.blockers += "delivery manifest must contain at least one plugin"
}

foreach ($plugin in $plugins) {
    $pluginId = [string](Get-Value $plugin "plugin_id")
    if ([string]::IsNullOrWhiteSpace($pluginId)) { $pluginId = "<missing-plugin-id>" }
    $sourceRoot = Resolve-ManifestPathValue ([string](Get-Value $plugin "source_root")) $baseDir
    $buildOutput = Resolve-ManifestPathValue ([string](Get-Value $plugin "build_output")) $baseDir
    $stagingRoot = Resolve-ManifestPathValue ([string](Get-Value $plugin "staging_root")) $baseDir
    $packagePath = Resolve-ManifestPathValue ([string](Get-Value $plugin "package_path")) $baseDir
    $installInput = Resolve-ManifestPathValue ([string](Get-Value $plugin "install_input")) $baseDir
    $packagePayloadRoot = Resolve-ManifestPathValue ([string](Get-Value $plugin "package_payload_root")) $baseDir
    $installPayloadRoot = Resolve-ManifestPathValue ([string](Get-Value $plugin "install_input_payload_root")) $baseDir
    $installedRuntime = Resolve-ManifestPathValue ([string](Get-Value $plugin "installed_runtime")) $baseDir
    $selectionMode = [string](Get-Value $plugin "install_selection_mode")

    $pluginFact = [ordered]@{
        plugin_id = $pluginId
        source_root = $sourceRoot
        build_output = $buildOutput
        staging_root = $stagingRoot
        package_path = $packagePath
        install_input = $installInput
        installed_runtime = $installedRuntime
        install_selection_mode = $selectionMode
        package_sha256 = ""
        install_input_sha256 = ""
        artifact_hashes = @()
        registry = $null
        closure = "blocked"
    }

    foreach ($requiredDirectory in @(
        [ordered]@{ name = "source_root"; path = $sourceRoot },
        [ordered]@{ name = "build_output"; path = $buildOutput },
        [ordered]@{ name = "staging_root"; path = $stagingRoot },
        [ordered]@{ name = "installed_runtime"; path = $installedRuntime }
    )) {
        if ([string]::IsNullOrWhiteSpace($requiredDirectory.path) -or
            -not (Test-Path -LiteralPath $requiredDirectory.path -PathType Container)) {
            Add-PluginBlocker $result $pluginId "$($requiredDirectory.name) directory is missing: $($requiredDirectory.path)"
        }
    }
    foreach ($requiredFile in @(
        [ordered]@{ name = "package_path"; path = $packagePath },
        [ordered]@{ name = "install_input"; path = $installInput }
    )) {
        if ([string]::IsNullOrWhiteSpace($requiredFile.path) -or
            -not (Test-Path -LiteralPath $requiredFile.path -PathType Leaf)) {
            Add-PluginBlocker $result $pluginId "$($requiredFile.name) file is missing: $($requiredFile.path)"
        }
    }
    if ($selectionMode -ne "explicit-build-result") {
        Add-PluginBlocker $result $pluginId "install_selection_mode must be explicit-build-result; directory scans and inferred packages are not delivery proof"
    }

    $pluginFact.package_sha256 = Get-FileHashValue $packagePath
    $pluginFact.install_input_sha256 = Get-FileHashValue $installInput
    if ($pluginFact.package_sha256 -and $pluginFact.install_input_sha256 -and
        $pluginFact.package_sha256 -ne $pluginFact.install_input_sha256) {
        Add-PluginBlocker $result $pluginId "install input is not content-identical to the package produced by this build"
    }
    $expectedPackageHash = ([string](Get-Value $plugin "expected_package_sha256")).ToLowerInvariant()
    if ($expectedPackageHash -and $pluginFact.package_sha256 -ne $expectedPackageHash) {
        Add-PluginBlocker $result $pluginId "package SHA256 differs from expected_package_sha256"
    }

    $criticalArtifacts = @(Get-Value $plugin "critical_artifacts")
    if ($criticalArtifacts.Count -eq 0) {
        Add-PluginBlocker $result $pluginId "critical_artifacts must identify native/resource delivery boundaries"
    }
    foreach ($artifact in $criticalArtifacts) {
        $relativePath = [string](Get-Value $artifact "relative_path")
        $artifactId = [string](Get-Value $artifact "id")
        if (-not $artifactId) { $artifactId = $relativePath }
        $paths = [ordered]@{
            source = Get-ArtifactBoundaryPath $artifact "source" "" "" $baseDir
            staging = Get-ArtifactBoundaryPath $artifact "staging" $stagingRoot $relativePath $baseDir
            package_payload = Get-ArtifactBoundaryPath $artifact "package_payload" $packagePayloadRoot $relativePath $baseDir
            install_input_payload = Get-ArtifactBoundaryPath $artifact "install_input_payload" $installPayloadRoot $relativePath $baseDir
            runtime = Get-ArtifactBoundaryPath $artifact "runtime" $installedRuntime $relativePath $baseDir
        }
        $hashes = [ordered]@{}
        foreach ($boundary in @("source", "staging", "package_payload", "install_input_payload", "runtime")) {
            $path = [string]$paths[$boundary]
            if ($boundary -eq "source" -and [string]::IsNullOrWhiteSpace($path)) {
                $hashes[$boundary] = ""
                continue
            }
            if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
                Add-PluginBlocker $result $pluginId "$artifactId missing $boundary file: $path"
                $hashes[$boundary] = ""
            } else {
                $hashes[$boundary] = Get-FileHashValue $path
            }
        }
        $presentHashes = @($hashes.Values | Where-Object { $_ }) | Sort-Object -Unique
        if ($presentHashes.Count -gt 1) {
            Add-PluginBlocker $result $pluginId "$artifactId SHA256 differs across source/staging/package/install/runtime"
        }
        $pluginFact.artifact_hashes += [ordered]@{ id = $artifactId; relative_path = $relativePath; paths = $paths; sha256 = $hashes }
    }

    $runtimeEvidence = Get-Value $plugin "frontend_runtime"
    if ($null -ne $runtimeEvidence) {
        $registryFile = Resolve-ManifestPathValue ([string](Get-Value $runtimeEvidence "registry_file")) $baseDir
        $registryRuntimePath = [string](Get-Value $runtimeEvidence "registry_runtime_path")
        $resourceUrl = [string](Get-Value $runtimeEvidence "resource_url")
        $loadedResource = Resolve-ManifestPathValue ([string](Get-Value $runtimeEvidence "loaded_resource")) $baseDir
        $expectedRuntimeResource = Resolve-ManifestPathValue ([string](Get-Value $runtimeEvidence "expected_runtime_resource")) $baseDir
        $pluginFact.registry = [ordered]@{
            file = $registryFile
            runtime_path = $registryRuntimePath
            resource_url = $resourceUrl
            loaded_resource = $loadedResource
            expected_runtime_resource = $expectedRuntimeResource
        }
        if (-not (Test-Path -LiteralPath $registryFile -PathType Leaf)) {
            Add-PluginBlocker $result $pluginId "frontend registry evidence is missing"
        } else {
            $registryText = Get-Content -LiteralPath $registryFile -Raw
            foreach ($expected in @($pluginId, $registryRuntimePath, $resourceUrl)) {
                if ([string]::IsNullOrWhiteSpace($expected) -or $registryText -notmatch [regex]::Escape($expected)) {
                    Add-PluginBlocker $result $pluginId "frontend registry does not prove plugin id, runtime path, and resource URL together"
                    break
                }
            }
        }
        $loadedHash = Get-FileHashValue $loadedResource
        $runtimeHash = Get-FileHashValue $expectedRuntimeResource
        if (-not $loadedHash -or -not $runtimeHash -or $loadedHash -ne $runtimeHash) {
            Add-PluginBlocker $result $pluginId "actual loaded resource is not content-identical to the expected installed runtime resource"
        }
    }

    $pluginBlockers = @($result.blockers | Where-Object { ([string]$_).StartsWith("[$pluginId]") })
    if ($pluginBlockers.Count -eq 0) { $pluginFact.closure = "passed" }
    $result.facts.plugins += $pluginFact
}

if ($result.status -eq "ok") {
    $result.hints += "All affected plugins closed source -> staging -> package payload -> install input -> installed runtime -> loaded resource where frontend evidence was supplied."
} else {
    $result.hints += "A direct runtime overwrite may support temporary diagnosis but does not satisfy final delivery closure."
}
if ($Json) { $result | ConvertTo-Json -Depth 30 } else { $result | Format-List }
