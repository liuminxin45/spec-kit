param(
    [string]$RepoRoot = "",
    [string]$FeatureDir = "",
    [string]$RequestSummary = "",
    [string[]]$TargetRepositories = @(),
    [string[]]$TargetComponents = @(),
    [string[]]$BuildTargets = @(),
    [string[]]$DeliveryTargets = @(),
    [string[]]$SelectedGates = @(),
    [string[]]$SelectedKnowledge = @(),
    [switch]$Record,
    [switch]$Json
)

. "$PSScriptRoot/common.ps1"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Get-SpecKitRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function New-DriftResult {
    [ordered]@{
        tool = "inspect-workflow-drift"
        status = "ok"
        facts = [ordered]@{}
        blockers = @()
        unknowns = @()
        hints = @()
    }
}

function Write-DriftResult($Result) {
    if ($Json) {
        $Result | ConvertTo-Json -Depth 20
    } else {
        $Result | Format-List
    }
}

function Normalize-Values([object[]]$Values) {
    @($Values | ForEach-Object { ([string]$_).Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Sort-Object -Unique)
}

function Get-ObjectValue($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) { return $Object[$Name] }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-MarkdownSection([string]$Text, [string]$Heading) {
    $match = [regex]::Match(
        $Text,
        '(?ms)^##\s+' + [regex]::Escape($Heading) + '\s*$\s*(.*?)(?=^##\s|\z)'
    )
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return ""
}

function Get-LabeledValue([string]$Section, [string]$Label) {
    $match = [regex]::Match(
        $Section,
        '(?im)^-\s*' + [regex]::Escape($Label) + '\s*:\s*(.+?)\s*$'
    )
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return ""
}

function Get-Sha256Text([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $normalized = (($Text -split "`r?`n") | ForEach-Object { $_.TrimEnd() }) -join "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized.Trim())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Test-SameValues($Left, $Right) {
    $leftJson = @(Normalize-Values @($Left)) | ConvertTo-Json -Compress
    $rightJson = @(Normalize-Values @($Right)) | ConvertTo-Json -Compress
    return $leftJson -eq $rightJson
}

$result = New-DriftResult

if ([string]::IsNullOrWhiteSpace($FeatureDir)) {
    $featurePath = Join-Path $RepoRoot ".specify/feature.json"
    if (Test-Path -LiteralPath $featurePath -PathType Leaf) {
        try {
            $feature = Get-Content -LiteralPath $featurePath -Raw | ConvertFrom-Json
            $FeatureDir = [string](Get-ObjectValue $feature "feature_directory")
        } catch {
            $result.blockers += ".specify/feature.json is not valid JSON"
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($FeatureDir) -and -not [IO.Path]::IsPathRooted($FeatureDir)) {
    $FeatureDir = Join-Path $RepoRoot $FeatureDir
}
if ([string]::IsNullOrWhiteSpace($FeatureDir) -or -not (Test-Path -LiteralPath $FeatureDir -PathType Container)) {
    $result.status = "blocked"
    $result.blockers += "feature directory is required and must exist"
    Write-DriftResult $result
    exit 0
}
$FeatureDir = (Resolve-Path -LiteralPath $FeatureDir).Path
$statePath = Join-Path $FeatureDir "workflow-state.json"
$planPath = Join-Path $FeatureDir "plan.md"
$state = [pscustomobject]@{}
if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    try {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    } catch {
        $result.status = "blocked"
        $result.blockers += "workflow-state.json is not valid JSON"
        Write-DriftResult $result
        exit 0
    }
}

$proof = ""
if (Test-Path -LiteralPath $planPath -PathType Leaf) {
    $proof = Get-MarkdownSection (Get-Content -LiteralPath $planPath -Raw) "Implementation Target Proof"
}

if ($TargetRepositories.Count -eq 0) {
    $value = Get-LabeledValue $proof "Target repositories"
    if ($value) { $TargetRepositories = @($value -split '\s*[,;]\s*') }
}
if ($TargetComponents.Count -eq 0) {
    $value = Get-LabeledValue $proof "Target components, source paths, and key symbols"
    if ($value) { $TargetComponents = @($value -split '\s*[,;]\s*') }
}
if ($BuildTargets.Count -eq 0) {
    $value = Get-LabeledValue $proof "Build target and expected output"
    if ($value) { $BuildTargets = @($value) }
}
if ($DeliveryTargets.Count -eq 0) {
    $installValue = Get-LabeledValue $proof "Install / deploy target and exact input"
    $validationValue = Get-LabeledValue $proof "Real validation host, entry, and expected loaded resource"
    $DeliveryTargets = @($installValue, $validationValue)
}

$previous = Get-ObjectValue $state "workflow_drift"
$previousRevision = 0
if ($null -ne $previous) {
    $rawRevision = Get-ObjectValue $previous "scope_revision"
    if ($null -ne $rawRevision) { $previousRevision = [int]$rawRevision }
}
$current = [ordered]@{
    scope_revision = if ($previousRevision -gt 0) { $previousRevision } else { 1 }
    request_summary_sha256 = Get-Sha256Text $RequestSummary
    implementation_target_proof_sha256 = Get-Sha256Text $proof
    target_proof_summary = if ($proof.Length -gt 600) { $proof.Substring(0, 600) } else { $proof }
    target_repositories = Normalize-Values $TargetRepositories
    target_components = Normalize-Values $TargetComponents
    build_targets = Normalize-Values $BuildTargets
    delivery_targets = Normalize-Values $DeliveryTargets
    selected_gates = Normalize-Values $SelectedGates
    selected_knowledge = Normalize-Values $SelectedKnowledge
}

$scopeDimensions = @(
    "request_summary_sha256",
    "implementation_target_proof_sha256",
    "target_repositories",
    "target_components",
    "build_targets",
    "delivery_targets"
)
$routingDimensions = @("selected_gates", "selected_knowledge")
$scopeChanges = @()
$routingChanges = @()
if ($null -ne $previous) {
    foreach ($dimension in $scopeDimensions) {
        $old = Get-ObjectValue $previous $dimension
        $new = $current[$dimension]
        $same = if ($new -is [array] -or $old -is [array]) {
            Test-SameValues $old $new
        } else {
            [string]$old -eq [string]$new
        }
        if (-not $same) { $scopeChanges += $dimension }
    }
    foreach ($dimension in $routingDimensions) {
        if (-not (Test-SameValues (Get-ObjectValue $previous $dimension) $current[$dimension])) {
            $routingChanges += $dimension
        }
    }
}

$scopeAmendmentRequired = ($null -ne $previous -and $scopeChanges.Count -gt 0)
$rerouteRequired = ($null -eq $previous -or $scopeChanges.Count -gt 0 -or $routingChanges.Count -gt 0)
if ($scopeAmendmentRequired) {
    $current.scope_revision = $previousRevision + 1
    $result.status = "blocked"
    $result.blockers += "scope_amendment_required: " + ($scopeChanges -join ", ")
    $result.hints += "Update the existing spec/plan/tasks for a bounded scope change; create a follow-up workflow for an independent issue."
}

if ($Record) {
    $current.recorded_at = (Get-Date).ToUniversalTime().ToString("o")
    if ($state.PSObject.Properties.Name -contains "workflow_drift") {
        $state.workflow_drift = [pscustomobject]$current
    } else {
        $state | Add-Member -NotePropertyName "workflow_drift" -NotePropertyValue ([pscustomobject]$current)
    }
    $state | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $statePath -Encoding utf8
}

$result.facts.feature_dir = $FeatureDir
$result.facts.workflow_state = $statePath
$result.facts.previous_snapshot = $previous
$result.facts.current_snapshot = $current
$result.facts.changed_dimensions = @($scopeChanges + $routingChanges)
$result.facts.scope_amendment_required = $scopeAmendmentRequired
$result.facts.reroute_required = $rerouteRequired
$result.facts.recorded = [bool]$Record
Write-DriftResult $result
