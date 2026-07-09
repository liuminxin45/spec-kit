#!/usr/bin/env pwsh
# Setup implementation plan for a feature

[CmdletBinding()]
param(
    [switch]$Json,
    [string]$DeliveryProfile = "",
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

# Show help if requested
if ($Help) {
    Write-Output "Usage: ./setup-plan.ps1 [-Json] [-DeliveryProfile <profile>] [-Help]"
    Write-Output "  -Json                    Output results in JSON format"
    Write-Output "  -DeliveryProfile <name>  Optional explicit delivery profile"
    Write-Output "  -Help                    Show this help message"
    exit 0
}

# Load common functions
. "$PSScriptRoot/common.ps1"

# Get all paths and variables from common functions
$paths = Get-FeaturePathsEnv

if (-not (Test-FeatureBranch -Branch $paths.CURRENT_BRANCH -HasGit $paths.HAS_GIT)) {
    exit 1
}

# Ensure the feature directory exists
New-Item -ItemType Directory -Path $paths.FEATURE_DIR -Force | Out-Null

$profile = Get-FeatureDeliveryProfile -RepoRoot $paths.REPO_ROOT -FeatureDir $paths.FEATURE_DIR -ExplicitProfile $DeliveryProfile
$isLean = Test-LeanDeliveryProfile $profile

if ($isLean) {
    $artifactPath = $paths.WORKPACK
    $artifactKind = "workpack"
    $templateName = "workpack-template"
} else {
    $artifactPath = $paths.IMPL_PLAN
    $artifactKind = "plan"
    $templateName = "plan-template"
}

# Copy the selected template if it exists, otherwise note it or create empty file.
$template = Resolve-Template -TemplateName $templateName -RepoRoot $paths.REPO_ROOT
if ($template -and (Test-Path $template)) {
    $content = [System.IO.File]::ReadAllText($template)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($artifactPath, $content, $utf8NoBom)
} else {
    Write-Warning "$templateName not found"
    New-Item -ItemType File -Path $artifactPath -Force | Out-Null
}

# Output results
if ($Json) {
    $result = [PSCustomObject]@{
        FEATURE_SPEC = $paths.FEATURE_SPEC
        IMPL_PLAN = $paths.IMPL_PLAN
        WORKPACK = $paths.WORKPACK
        ARTIFACT = $artifactPath
        ARTIFACT_KIND = $artifactKind
        DELIVERY_PROFILE = $profile
        SPECS_DIR = $paths.FEATURE_DIR
        BRANCH = $paths.CURRENT_BRANCH
        HAS_GIT = $paths.HAS_GIT
    }
    $result | ConvertTo-Json -Compress
} else {
    Write-Output "FEATURE_SPEC: $($paths.FEATURE_SPEC)"
    Write-Output "IMPL_PLAN: $($paths.IMPL_PLAN)"
    Write-Output "WORKPACK: $($paths.WORKPACK)"
    Write-Output "ARTIFACT: $artifactPath"
    Write-Output "ARTIFACT_KIND: $artifactKind"
    Write-Output "DELIVERY_PROFILE: $profile"
    Write-Output "SPECS_DIR: $($paths.FEATURE_DIR)"
    Write-Output "BRANCH: $($paths.CURRENT_BRANCH)"
    Write-Output "HAS_GIT: $($paths.HAS_GIT)"
}
