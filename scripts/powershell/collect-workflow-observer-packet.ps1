param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [switch]$Json
)

& "$PSScriptRoot/automation-common.ps1" -Tool "collect-workflow-observer-packet" -RepoRoot $RepoRoot -FeatureDir $FeatureDir -Json:$Json
