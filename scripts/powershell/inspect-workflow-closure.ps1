param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [string]$Stage = "final-response",
    [switch]$Json
)

& "$PSScriptRoot/automation-common.ps1" -Tool "inspect-workflow-closure" -RepoRoot $RepoRoot -FeatureDir $FeatureDir -Stage $Stage -Json:$Json
