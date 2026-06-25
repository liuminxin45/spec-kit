param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [string]$CandidatesPath = "",
    [string]$PackId = "",
    [switch]$Repack,
    [switch]$Force,
    [switch]$Json
)

& "$PSScriptRoot/automation-common.ps1" -Tool "promote-knowledge-candidates" -RepoRoot $RepoRoot -FeatureDir $FeatureDir -CandidatesPath $CandidatesPath -PackId $PackId -Repack:$Repack -Force:$Force -Json:$Json
