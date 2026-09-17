[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FeatureDir,
    [string]$Stage,
    [ValidateSet('pending','requested','in_progress','completed','passed','blocked','failed','skipped')][string]$Status,
    [string]$Evidence,
    [ValidateSet('manual','automatic')][string]$ContinuationMode,
    [string]$AuthorizationEvidence,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
$path = Join-Path (Resolve-Path -LiteralPath $FeatureDir).Path 'workflow-state.json'
$state = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
if (-not $Stage -and -not $ContinuationMode) { throw 'Stage or ContinuationMode is required.' }
if ($Stage -and (-not $Status -or [string]::IsNullOrWhiteSpace($Evidence))) { throw 'Stage changes require Status and Evidence.' }
if ($ContinuationMode -and [string]::IsNullOrWhiteSpace($AuthorizationEvidence)) { throw 'ContinuationMode requires explicit user authorization evidence.' }
if ($Stage) {
    $name = $Stage.Replace('_', '-')
    if (-not $state.stage_statuses) { $state | Add-Member stage_statuses ([pscustomobject]@{}) -Force }
    $state.stage_statuses | Add-Member $name $Status -Force
    $nodeName = $name.Replace('-', '_')
    if (-not $state.$nodeName) { $state | Add-Member $nodeName ([pscustomobject]@{}) -Force }
    $state.$nodeName | Add-Member status $Status -Force
    $state.$nodeName | Add-Member evidence $Evidence -Force
    # Invalidate a cached routing decision; never infer acceptance or other stages.
    $state | Add-Member next_stage_decision ([pscustomobject]@{current_stage=$name; next_stage=''; can_continue=$false; needs_resolution=$true}) -Force
}
if ($ContinuationMode) {
    $state | Add-Member continuation ([pscustomobject]@{mode=$ContinuationMode; authorization_evidence=$AuthorizationEvidence; scope='default-stages-only'}) -Force
}
$temp = "$path.$([guid]::NewGuid().ToString('N')).tmp"
try {
    [IO.File]::WriteAllText($temp, ($state | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temp -Destination $path -Force
} finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp } }
$result = [ordered]@{status='ok'; workflow_state=$path; stage=$Stage; continuation_mode=$ContinuationMode}
if ($Json) { $result | ConvertTo-Json -Compress } else { $result }
