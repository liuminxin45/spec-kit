#!/usr/bin/env pwsh

# Consolidated prerequisite checking script (PowerShell)
#
# This script provides unified prerequisite checking for Spec-Driven Development workflow.
# It replaces the functionality previously spread across multiple scripts.
#
# Usage: ./check-prerequisites.ps1 [OPTIONS]
#
# OPTIONS:
#   -Json               Output in JSON format
#   -RequireTasks       Require tasks.md to exist (for implementation phase)
#   -IncludeTasks       Include tasks.md in AVAILABLE_DOCS list
#   -PathsOnly          Only output path variables (no validation)
#   -SpecOnly           Require feature directory and spec.md only (clarify phase)
#   -Stage              Workflow stage for profile-aware artifact checks
#   -DeliveryProfile    Optional explicit delivery profile
#   -Help, -h           Show help message

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RequireTasks,
    [switch]$IncludeTasks,
    [switch]$PathsOnly,
    [switch]$SpecOnly,
    [string]$Stage = "",
    [string]$DeliveryProfile = "",
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

# Show help if requested
if ($Help) {
    Write-Output @"
Usage: check-prerequisites.ps1 [OPTIONS]

Consolidated prerequisite checking for Spec-Driven Development workflow.

OPTIONS:
  -Json               Output in JSON format
  -RequireTasks       Require tasks.md to exist (for implementation phase)
  -IncludeTasks       Include tasks.md in AVAILABLE_DOCS list
  -PathsOnly          Only output path variables (no prerequisite validation)
  -SpecOnly           Require feature directory and spec.md only (clarify phase)
  -Stage <stage>      Workflow stage for profile-aware artifact checks
  -DeliveryProfile <profile>
                       Optional explicit delivery profile
  -Help, -h           Show this help message

EXAMPLES:
  # Check task prerequisites (plan.md required)
  .\check-prerequisites.ps1 -Json

  # Check implementation prerequisites (plan.md + tasks.md required)
  .\check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks

  # Check lean implementation prerequisites (workpack.md for lean profiles)
  .\check-prerequisites.ps1 -Json -Stage implement -IncludeTasks

  # Get feature paths only (no validation)
  .\check-prerequisites.ps1 -PathsOnly

  # Check clarify prerequisites (feature directory + spec.md only)
  .\check-prerequisites.ps1 -Json -SpecOnly

"@
    exit 0
}

# Source common functions
. "$PSScriptRoot/common.ps1"

# Get feature paths and validate the local Spec branch.
$paths = Get-FeaturePathsEnv
$profile = Get-FeatureDeliveryProfile -RepoRoot $paths.REPO_ROOT -FeatureDir $paths.FEATURE_DIR -ExplicitProfile $DeliveryProfile
$stageKey = $Stage.Trim().ToLowerInvariant()
$leanWorkpackStages = @(
    "implement",
    "acceptance",
    "commit",
    "retrospective",
    "promote-lessons",
    "simplify",
    "test-hardening",
    "converge"
)
$usesLeanWorkpack = (Test-LeanDeliveryProfile $profile) -and ($leanWorkpackStages -contains $stageKey)
$planningArtifactPath = if ($usesLeanWorkpack) { $paths.WORKPACK } else { $paths.IMPL_PLAN }
$planningArtifactName = if ($usesLeanWorkpack) { "workpack.md" } else { "plan.md" }

if (-not (Test-FeatureBranch -Branch $paths.CURRENT_BRANCH -HasGit:$paths.HAS_GIT)) {
    exit 1
}

# If paths-only mode, output paths and exit (support combined -Json -PathsOnly)
if ($PathsOnly) {
    if ($Json) {
        [PSCustomObject]@{
            REPO_ROOT    = $paths.REPO_ROOT
            BRANCH       = $paths.CURRENT_BRANCH
            FEATURE_DIR  = $paths.FEATURE_DIR
            FEATURE_SPEC = $paths.FEATURE_SPEC
            IMPL_PLAN    = $paths.IMPL_PLAN
            WORKPACK     = $paths.WORKPACK
            TASKS        = $paths.TASKS
            DELIVERY_PROFILE = $profile
        } | ConvertTo-Json -Compress
    } else {
        Write-Output "REPO_ROOT: $($paths.REPO_ROOT)"
        Write-Output "BRANCH: $($paths.CURRENT_BRANCH)"
        Write-Output "FEATURE_DIR: $($paths.FEATURE_DIR)"
        Write-Output "FEATURE_SPEC: $($paths.FEATURE_SPEC)"
        Write-Output "IMPL_PLAN: $($paths.IMPL_PLAN)"
        Write-Output "WORKPACK: $($paths.WORKPACK)"
        Write-Output "TASKS: $($paths.TASKS)"
        Write-Output "DELIVERY_PROFILE: $profile"
    }
    exit 0
}

# Validate required directories and files
if (-not (Test-Path $paths.FEATURE_DIR -PathType Container)) {
    Write-Output "ERROR: Feature directory not found: $($paths.FEATURE_DIR)"
    Write-Output "Run /speckit.specify first to create the feature structure."
    exit 1
}

if ($SpecOnly) {
    if (-not (Test-Path $paths.FEATURE_SPEC -PathType Leaf)) {
        Write-Output "ERROR: spec.md not found in $($paths.FEATURE_DIR)"
        Write-Output "Run /speckit.specify first to create the feature specification."
        exit 1
    }

    if ($Json) {
        [PSCustomObject]@{
            FEATURE_DIR = $paths.FEATURE_DIR
            FEATURE_SPEC = $paths.FEATURE_SPEC
            AVAILABLE_DOCS = @()
        } | ConvertTo-Json -Compress
    } else {
        Write-Output "FEATURE_DIR:$($paths.FEATURE_DIR)"
        Write-Output "FEATURE_SPEC:$($paths.FEATURE_SPEC)"
        Write-Output "AVAILABLE_DOCS:"
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $planningArtifactPath -PathType Leaf)) {
    Write-Output "ERROR: $planningArtifactName not found in $($paths.FEATURE_DIR)"
    if ($usesLeanWorkpack) {
        Write-Output "Run /speckit.plan first to create the lean workpack."
    } else {
        Write-Output "Run /speckit.plan first to create the implementation plan."
    }
    exit 1
}

# Check for tasks.md if required
if ($RequireTasks -and -not (Test-Path $paths.TASKS -PathType Leaf)) {
    Write-Output "ERROR: tasks.md not found in $($paths.FEATURE_DIR)"
    Write-Output "Run /speckit.tasks first to create the task list."
    exit 1
}

# Build list of available documents
$docs = @()

# Include compact planning artifact when present
if (Test-Path -LiteralPath $paths.WORKPACK -PathType Leaf) { $docs += 'workpack.md' }

# Always check these optional docs
if (Test-Path -LiteralPath $paths.RESEARCH -PathType Leaf) { $docs += 'research.md' }
if (Test-Path -LiteralPath $paths.DATA_MODEL -PathType Leaf) { $docs += 'data-model.md' }

# Check contracts directory (only if it exists and has files)
if ((Test-Path -LiteralPath $paths.CONTRACTS_DIR -PathType Container) -and (Get-ChildItem -LiteralPath $paths.CONTRACTS_DIR -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    $docs += 'contracts/'
}

if (Test-Path -LiteralPath $paths.QUICKSTART -PathType Leaf) { $docs += 'quickstart.md' }

# Include tasks.md if requested and it exists
if ($IncludeTasks -and (Test-Path -LiteralPath $paths.TASKS -PathType Leaf)) {
    $docs += 'tasks.md'
}

# Output results
if ($Json) {
    # JSON output
    [PSCustomObject]@{
        FEATURE_DIR = $paths.FEATURE_DIR
        AVAILABLE_DOCS = $docs
        DELIVERY_PROFILE = $profile
        PLANNING_ARTIFACT = $planningArtifactName
    } | ConvertTo-Json -Compress
} else {
    # Text output
    Write-Output "FEATURE_DIR:$($paths.FEATURE_DIR)"
    Write-Output "DELIVERY_PROFILE:$profile"
    Write-Output "PLANNING_ARTIFACT:$planningArtifactName"
    Write-Output "AVAILABLE_DOCS:"

    # Show status of each potential document
    Test-FileExists -Path $paths.WORKPACK -Description 'workpack.md' | Out-Null
    Test-FileExists -Path $paths.RESEARCH -Description 'research.md' | Out-Null
    Test-FileExists -Path $paths.DATA_MODEL -Description 'data-model.md' | Out-Null
    Test-DirHasFiles -Path $paths.CONTRACTS_DIR -Description 'contracts/' | Out-Null
    Test-FileExists -Path $paths.QUICKSTART -Description 'quickstart.md' | Out-Null

    if ($IncludeTasks) {
        Test-FileExists -Path $paths.TASKS -Description 'tasks.md' | Out-Null
    }
}
