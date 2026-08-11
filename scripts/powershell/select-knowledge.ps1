param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [string]$Stage = "",
    [string]$DeliveryProfile = "",
    [string]$WorkflowState = "",
    [string]$CandidatesPath = "",
    [string[]]$AffectedRepositories = @(),
    [string[]]$RiskFlags = @(),
    [string[]]$CapabilityTags = @(),
    [string[]]$Terms = @(),
    [string]$RequestSummary = "",
    [switch]$IgnoreActiveFeature,
    [switch]$Json
)

& "$PSScriptRoot/automation-common.ps1" `
    -Tool "select-knowledge" `
    -RepoRoot $RepoRoot `
    -FeatureDir $FeatureDir `
    -Stage $Stage `
    -DeliveryProfile $DeliveryProfile `
    -WorkflowState $WorkflowState `
    -CandidatesPath $CandidatesPath `
    -AffectedRepositories $AffectedRepositories `
    -RiskFlags $RiskFlags `
    -CapabilityTags $CapabilityTags `
    -Terms $Terms `
    -RequestSummary $RequestSummary `
    -IgnoreActiveFeature:$IgnoreActiveFeature `
    -Json:$Json
