param([string]$RepoRoot = (Get-Location).Path, [switch]$Json)
& "$PSScriptRoot/automation-common.ps1" -Tool "validate-generated-context" -RepoRoot $RepoRoot -Json:$Json
