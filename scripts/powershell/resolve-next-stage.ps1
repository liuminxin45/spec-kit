#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$FeatureDir = "",
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"

if ($Help) {
    Write-Output "Usage: resolve-next-stage.ps1 [-RepoRoot <path>] [-FeatureDir <dir>] [-Json]"
    Write-Output "Resolves the deterministic next Spec Kit stage from feature state, artifacts, and closure gates."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Get-SpecKitRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json } catch { return $null }
}

function Get-Prop {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    if ($Object.PSObject.Properties.Name -contains $Name) { return $Object.$Name }
    return $null
}

function Has-Artifact {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($FeatureDir)) { return $false }
    return (Test-Path -LiteralPath (Join-Path $FeatureDir $Name) -PathType Leaf)
}

function Get-Status {
    param($State, [string]$Name)
    $node = Get-Prop $State $Name
    $status = Get-Prop $node "status"
    if ($status) { return ([string]$status).ToLowerInvariant() }
    $stages = Get-Prop $State "stage_statuses"
    $stageStatus = Get-Prop $stages $Name
    if ($stageStatus) { return ([string]$stageStatus).ToLowerInvariant() }
    return ""
}

function Is-CompleteStatus {
    param([string]$Status)
    return ($Status -in @("completed", "complete", "passed", "approved", "done", "ok"))
}

function Is-RequestedStatus {
    param([string]$Status)
    return ($Status -in @("requested", "selected", "required", "in_progress", "active", "running"))
}

function Test-AcceptancePrepared {
    param($State)
    if (Is-CompleteStatus (Get-Status $State "acceptance")) { return $true }
    return (Has-Artifact "acceptance.md")
}

function Test-AcceptancePassed {
    param($State)
    if (Is-CompleteStatus (Get-Status $State "acceptance")) { return $true }
    if (Is-CompleteStatus (Get-Status $State "human-acceptance")) { return $true }
    $gates = Get-Prop $State "human_gates"
    $acceptanceGate = Get-Prop $gates "acceptance"
    if (Is-CompleteStatus ([string](Get-Prop $acceptanceGate "status"))) { return $true }
    return $false
}

function Set-Decision {
    param(
        [string]$Current,
        [string]$Next,
        [string[]]$Missing = @(),
        [string[]]$Blockers = @(),
        [string]$HumanAction = ""
    )
    $commands = @()
    if ($Next) { $commands += $Next }
    [ordered]@{
        current_stage = $Current
        next_stage = $Next
        can_continue = [bool]($Next -and $Blockers.Count -eq 0 -and [string]::IsNullOrWhiteSpace($HumanAction))
        blockers = @($Blockers)
        required_human_action = $HumanAction
        commands_to_run = @($commands)
        missing_artifacts = @($Missing)
    }
}

function Get-ClosureDecision {
    param($State)
    $accepted = Test-AcceptancePassed $State
    $commitDone = (Is-CompleteStatus (Get-Status $State "commit")) -or (Has-Artifact "commit-message.txt")
    $postDone = (Is-CompleteStatus (Get-Status $State "post_commit_self_check")) -or (Has-Artifact "post-commit-self-check.md")
    $rubricDone = (Is-CompleteStatus (Get-Status $State "rubric_score")) -or (Has-Artifact "rubric-score.md")
    $commitRequested = Is-RequestedStatus (Get-Status $State "commit")
    $postRequested = (Is-RequestedStatus (Get-Status $State "post_commit_self_check")) -or (Is-RequestedStatus (Get-Status $State "post-commit-self-check"))
    $rubricRequested = (Is-RequestedStatus (Get-Status $State "rubric_score")) -or (Is-RequestedStatus (Get-Status $State "rubric-score"))
    $completeRequested = (Is-RequestedStatus (Get-Status $State "complete-branch")) -or (Is-RequestedStatus (Get-Status $State "complete_branch"))

    if (-not ($accepted -or $commitDone -or $postDone -or $rubricDone -or $commitRequested -or $postRequested -or $rubricRequested -or $completeRequested)) {
        return $null
    }

    if (-not (Has-Artifact "validation.md")) {
        return Set-Decision "implement" "speckit.implement" @("validation.md")
    }
    if (-not (Has-Artifact "implementation-summary.md")) {
        return Set-Decision "implement" "speckit.implement" @("implementation-summary.md")
    }

    if (($commitRequested -or $completeRequested) -and -not $accepted) {
        return Set-Decision "acceptance" "human-acceptance" @() @() "Approve human acceptance before opt-in commit or branch completion."
    }
    if ($commitRequested -and -not $commitDone) {
        return Set-Decision "human-acceptance" "speckit.commit"
    }

    if (($postRequested -or $rubricRequested) -and -not $commitDone) {
        return Set-Decision "human-acceptance" "speckit.commit"
    }
    if ($postRequested -and -not $postDone) {
        return Set-Decision "commit" "speckit.post-commit-self-check" @("post-commit-self-check.md")
    }
    if (($rubricRequested -or $postDone) -and -not $rubricDone) {
        return Set-Decision "post-commit-self-check" "speckit.rubric-score" @("rubric-score.md")
    }

    if ($completeRequested) {
        if (-not $commitDone) {
            return Set-Decision "human-acceptance" "speckit.commit"
        }
        $gates = Get-Prop $State "human_gates"
        $completeGate = Get-Prop $gates "complete-branch"
        $completeApproved = Is-CompleteStatus ([string](Get-Prop $completeGate "status"))
        if (-not $completeApproved) {
            return Set-Decision "commit" "speckit.complete-branch" @() @() "Approve local branch completion/cherry-pick before running complete-branch."
        }
        return Set-Decision "commit" "speckit.complete-branch"
    }

    return Set-Decision "human-acceptance" ""
}

$featureJsonPath = Join-Path $RepoRoot ".specify/feature.json"
$feature = Read-JsonFile $featureJsonPath
if ([string]::IsNullOrWhiteSpace($FeatureDir) -and $feature) {
    $configuredDir = [string](Get-Prop $feature "feature_directory")
    if (-not [string]::IsNullOrWhiteSpace($configuredDir)) {
        $FeatureDir = if ([System.IO.Path]::IsPathRooted($configuredDir)) { $configuredDir } else { Join-Path $RepoRoot $configuredDir }
    }
}
if ($FeatureDir -and -not [System.IO.Path]::IsPathRooted($FeatureDir)) {
    $FeatureDir = Join-Path $RepoRoot $FeatureDir
}
if ($FeatureDir -and (Test-Path -LiteralPath $FeatureDir -PathType Container)) {
    $FeatureDir = (Resolve-Path -LiteralPath $FeatureDir).Path
}

$statePath = if ($FeatureDir) { Join-Path $FeatureDir "workflow-state.json" } else { "" }
$state = Read-JsonFile $statePath

$profile = [string](Get-Prop $feature "delivery_profile")
if ([string]::IsNullOrWhiteSpace($profile) -and $state) {
    $workflowModel = Get-Prop $state "workflow_model"
    $profile = [string](Get-Prop $workflowModel "delivery_profile")
}
if ([string]::IsNullOrWhiteSpace($profile) -or $profile -eq "auto") {
    $profile = "standard-bugfix"
}

$riskLevel = [string](Get-Prop $feature "risk_level")
$riskFlags = @()
if ($feature -and (Get-Prop $feature "risk_flags")) {
    $riskFlags = @((Get-Prop $feature "risk_flags") | ForEach-Object { [string]$_ })
}
$needsChecklist = ($riskLevel -in @("high", "blocked")) -or (@($riskFlags | Where-Object { $_ -in @("ui-parity", "host-embedded-ui", "cross-repo-validation", "cross-repo", "public-api", "real-device") }).Count -gt 0)

$blockers = @()
if ([string]::IsNullOrWhiteSpace($FeatureDir) -or -not (Test-Path -LiteralPath $FeatureDir -PathType Container)) {
    $blockers += "FeatureDir not found; pass -FeatureDir or create .specify/feature.json with feature_directory."
    $decision = Set-Decision "" "" @() $blockers
} else {
    $closure = Get-ClosureDecision $state
    if ($closure) {
        $decision = $closure
    } elseif ($profile -eq "validation-only") {
        if (-not (Has-Artifact "validation.md")) {
            $decision = Set-Decision "plan" "speckit.validation" @("validation.md")
        } else {
            $decision = Set-Decision "validation" ""
        }
    } elseif ($profile -eq "blocked-investigation") {
        if (-not ((Has-Artifact "investigation.md") -or (Has-Artifact "fact-pack.md"))) {
            $decision = Set-Decision "plan" "speckit.fact-layer" @("investigation.md or fact-pack.md")
        } else {
            $decision = Set-Decision "fact-layer" ""
        }
    } elseif ($profile -eq "micro-fix") {
        if (-not (Has-Artifact "workpack.md")) {
            $decision = Set-Decision "intake" "speckit.plan" @("workpack.md")
        } elseif (-not (Has-Artifact "validation.md")) {
            $decision = Set-Decision "plan" "speckit.implement" @("validation.md")
        } elseif (-not (Has-Artifact "implementation-summary.md")) {
            $decision = Set-Decision "implement" "speckit.implement" @("implementation-summary.md")
        } elseif (-not (Test-AcceptancePrepared $state)) {
            $decision = Set-Decision "implement" "speckit.acceptance"
        } else {
            $decision = Set-Decision "acceptance" "human-acceptance" @() @() "User acceptance must be approved before optional closure stages."
        }
    } elseif ($profile -eq "standard-bugfix-lite") {
        if (-not (Has-Artifact "workpack.md")) {
            $decision = Set-Decision "specify" "speckit.plan" @("workpack.md")
        } elseif (-not (Has-Artifact "validation.md")) {
            $decision = Set-Decision "plan" "speckit.implement" @("validation.md")
        } elseif (-not (Has-Artifact "implementation-summary.md")) {
            $decision = Set-Decision "implement" "speckit.implement" @("implementation-summary.md")
        } elseif (-not (Test-AcceptancePrepared $state)) {
            $decision = Set-Decision "implement" "speckit.acceptance"
        } else {
            $decision = Set-Decision "acceptance" "human-acceptance" @() @() "User acceptance must be approved before optional closure stages."
        }
    } else {
        if (-not (Has-Artifact "spec.md")) {
            $decision = Set-Decision "intake" "speckit.specify" @("spec.md")
        } elseif (-not (Has-Artifact "plan.md")) {
            $decision = Set-Decision "specify" "speckit.plan" @("plan.md")
        } elseif ($profile -eq "full-sdd" -and -not (Has-Artifact "tasks.md")) {
            $decision = Set-Decision "plan" "speckit.tasks" @("tasks.md")
        } elseif ($profile -eq "full-sdd" -and -not (Has-Artifact "analysis.md")) {
            $decision = Set-Decision "plan" "speckit.analyze" @("analysis.md")
        } elseif (($profile -eq "full-sdd" -or $needsChecklist) -and -not (Has-Artifact "checklists/implementation-readiness.md")) {
            $decision = Set-Decision "analyze" "speckit.checklist" @("checklists/implementation-readiness.md")
        } elseif (-not (Has-Artifact "validation.md")) {
            $currentBeforeImplement = if ($profile -eq "full-sdd" -or $needsChecklist) {
                "checklist"
            } elseif (Has-Artifact "analysis.md") {
                "analyze"
            } else {
                "plan"
            }
            $decision = Set-Decision $currentBeforeImplement "speckit.implement" @("validation.md")
        } elseif (-not (Has-Artifact "implementation-summary.md")) {
            $decision = Set-Decision "implement" "speckit.implement" @("implementation-summary.md")
        } elseif (-not (Test-AcceptancePrepared $state)) {
            $decision = Set-Decision "implement" "speckit.acceptance"
        } else {
            $decision = Set-Decision "acceptance" "human-acceptance" @() @() "User acceptance must be approved before optional closure stages."
        }
    }
}

$payload = [ordered]@{
    tool = "resolve-next-stage"
    status = if (@($decision.blockers).Count -gt 0) { "blocked" } else { "ok" }
    current_stage = $decision.current_stage
    next_stage = $decision.next_stage
    can_continue = $decision.can_continue
    blockers = @($decision.blockers)
    unknowns = @()
    hints = @()
    required_human_action = $decision.required_human_action
    commands_to_run = @($decision.commands_to_run)
    missing_artifacts = @($decision.missing_artifacts)
    facts = [ordered]@{
        repo_root = $RepoRoot
        feature_dir = $FeatureDir
        workflow_state = $statePath
        delivery_profile = $profile
        risk_level = $riskLevel
        risk_flags = @($riskFlags)
    }
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 10 -Compress
} else {
    if ($payload.status -eq "blocked") {
        foreach ($blocker in $payload.blockers) { [Console]::Error.WriteLine(" - $blocker") }
    } elseif ($payload.next_stage) {
        Write-Output "NEXT_STAGE: $($payload.next_stage)"
    } else {
        Write-Output "NEXT_STAGE: <none>"
    }
}
if ($payload.status -eq "blocked") { exit 1 }
