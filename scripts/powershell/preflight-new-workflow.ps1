#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string[]]$AllowedBaseBranches = @(),
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"

if ($Help) {
    Write-Output "Usage: preflight-new-workflow.ps1 [-RepoRoot <repo>] [-AllowedBaseBranches <branches>] [-Json]"
    Write-Output "Blocks unsafe Spec Kit workflow starts when the workspace is dirty, on a non-base branch, or has an unfinished active feature."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Get-SpecKitRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Get-Prop {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    if ($Object.PSObject.Properties.Name -contains $Name) { return $Object.$Name }
    return $null
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    } catch {
        return "__INVALID_JSON__"
    }
}

function ConvertTo-SafeRelativePath {
    param([string]$Root, [string]$Path)
    try {
        return [System.IO.Path]::GetRelativePath($Root, $Path).Replace("\", "/")
    } catch {
        return $Path
    }
}

function Test-GeneratedOrTempPath {
    param([string]$Path)
    $normalized = $Path.Replace("\", "/").Trim('"').ToLowerInvariant()
    if ($normalized -match '(^|/)(\.agents|\.specify|ai|specs|sdkarchive|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.cache|node_modules|dist|build|export|plugin-out|coverage|logs?|tmp|temp)(/|$)') {
        return $true
    }
    return ($normalized -match '\.(log|tmp|temp|bak|swp|pid|dmp|cache|pyc|pyo|obj|ilk|pdb)$' -or
        $normalized -match '(^|/)(thumbs\.db|\.ds_store)$')
}

function Get-WorkspaceConfig {
    param([string]$Root)

    $configPath = Join-Path $Root ".specify/workspace.yml"
    $workspaceRoot = $Root
    $baseBranch = "main"
    $repos = @(
        [PSCustomObject]@{
            name = (Split-Path -Leaf $Root)
            path = "."
            role = "primary"
            required = $true
            participates_in_spec_branches = $true
        }
    )

    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $rootText = Select-String -Path $configPath -Pattern '^\s*root:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($rootText -and $rootText.Matches[0].Groups[1].Value) {
            $rootValue = $rootText.Matches[0].Groups[1].Value.Trim("'`"")
            $workspaceRoot = if ([System.IO.Path]::IsPathRooted($rootValue)) { $rootValue } else { Join-Path $Root $rootValue }
        }

        $baseText = Select-String -Path $configPath -Pattern '^\s*default_base_branch:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($baseText -and $baseText.Matches[0].Groups[1].Value) {
            $baseBranch = $baseText.Matches[0].Groups[1].Value.Trim("'`"")
        }

        $parsedRepos = @()
        $current = $null
        foreach ($line in Get-Content -LiteralPath $configPath) {
            if ($line -match '^\s*-\s*name:\s*"?([^"]+)"?\s*$') {
                if ($current) { $parsedRepos += [PSCustomObject]$current }
                $current = @{ name = $Matches[1].Trim("'`""); path = ""; role = ""; required = $false; participates_in_spec_branches = $true }
            } elseif ($current -and $line -match '^\s*path:\s*"?([^"]+)"?\s*$') {
                $current.path = $Matches[1].Trim("'`"")
            } elseif ($current -and $line -match '^\s*role:\s*"?([^"]+)"?\s*$') {
                $current.role = $Matches[1].Trim("'`"")
            } elseif ($current -and $line -match '^\s*required:\s*(true|false)\s*$') {
                $current.required = ($Matches[1] -eq "true")
            } elseif ($current -and $line -match '^\s*participates_in_spec_branches:\s*(true|false)\s*$') {
                $current.participates_in_spec_branches = ($Matches[1] -eq "true")
            }
        }
        if ($current) { $parsedRepos += [PSCustomObject]$current }
        if ($parsedRepos.Count -gt 0) { $repos = $parsedRepos }
    }

    $resolvedWorkspace = (Resolve-Path -LiteralPath $workspaceRoot).Path
    $resolvedRepos = @()
    foreach ($repo in $repos) {
        $repoPath = if ([System.IO.Path]::IsPathRooted($repo.path)) { $repo.path } else { Join-Path $resolvedWorkspace $repo.path }
        $resolvedRepos += [PSCustomObject]@{
            name = $repo.name
            path = $repoPath
            role = if ([string]::IsNullOrWhiteSpace($repo.role)) { "unspecified" } else { $repo.role }
            required = [bool]$repo.required
            participates_in_spec_branches = [bool]$repo.participates_in_spec_branches
        }
    }

    [PSCustomObject]@{
        workspace_root = $resolvedWorkspace
        default_base_branch = $baseBranch
        repositories = $resolvedRepos
    }
}

function Invoke-Git {
    param([string]$Path, [string[]]$GitArgs)
    $out = & git -C $Path @GitArgs 2>$null
    [PSCustomObject]@{ exit_code = $LASTEXITCODE; output = @($out) }
}

function Get-RepoFacts {
    param([object]$Repo, [string[]]$AllowedBranches)

    $entry = [ordered]@{
        name = [string]$Repo.name
        path = [string]$Repo.path
        exists = Test-Path -LiteralPath $Repo.path -PathType Container
        required = [bool]$Repo.required
        participates_in_spec_branches = [bool]$Repo.participates_in_spec_branches
        is_git = $false
        branch = ""
        on_allowed_base_branch = $null
        dirty = $false
        dirty_entries = @()
        tracked_dirty = @()
        untracked_dirty = @()
        generated_or_temp_dirty = @()
    }

    if (-not $entry.exists) { return [PSCustomObject]$entry }
    $inside = Invoke-Git -Path $Repo.path -GitArgs @("rev-parse", "--is-inside-work-tree")
    if ($inside.exit_code -ne 0) { return [PSCustomObject]$entry }

    $entry.is_git = $true
    $branch = Invoke-Git -Path $Repo.path -GitArgs @("rev-parse", "--abbrev-ref", "HEAD")
    if ($branch.exit_code -eq 0 -and $branch.output.Count -gt 0) {
        $entry.branch = [string]$branch.output[0]
    }
    $entry.on_allowed_base_branch = ($entry.branch -in $AllowedBranches)

    $status = Invoke-Git -Path $Repo.path -GitArgs @("status", "--porcelain", "--untracked-files=all")
    if ($status.exit_code -eq 0) {
        foreach ($line in $status.output) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $candidate = if ($line.Length -gt 3) { $line.Substring(3).Trim() } else { $line.Trim() }
            if ($candidate -match ' -> ') { $candidate = ($candidate -split ' -> ')[-1].Trim() }
            $entry.dirty_entries += $candidate
            if ($line.StartsWith("?? ")) {
                if (Test-GeneratedOrTempPath $candidate) {
                    $entry.generated_or_temp_dirty += $candidate
                } else {
                    $entry.untracked_dirty += $candidate
                }
            } else {
                $entry.tracked_dirty += $candidate
            }
        }
    }
    $entry.dirty = ($entry.dirty_entries.Count -gt 0)
    return [PSCustomObject]$entry
}

function Get-WorkflowNodeStatus {
    param($State, [string]$Name)
    $node = Get-Prop $State $Name
    $status = Get-Prop $node "status"
    if ($status) { return ([string]$status).ToLowerInvariant() }
    $stages = Get-Prop $State "stage_statuses"
    $stageStatus = Get-Prop $stages $Name
    if ($stageStatus) { return ([string]$stageStatus).ToLowerInvariant() }
    return ""
}

function Test-TerminalFeatureState {
    param($State)
    if ($null -eq $State -or $State -eq "__INVALID_JSON__") { return $false }
    $status = ([string](Get-Prop $State "status")).ToLowerInvariant()
    if ($status -in @("completed", "complete", "aborted", "cancelled")) { return $true }
    foreach ($name in @("complete_branch", "complete-branch")) {
        if ((Get-WorkflowNodeStatus -State $State -Name $name) -in @("completed", "complete", "passed", "done", "ok", "aborted")) {
            return $true
        }
    }
    return $false
}

function Get-ActiveFeatureFacts {
    param([string]$Root)
    $featureJsonPath = Join-Path $Root ".specify/feature.json"
    $facts = [ordered]@{
        feature_json = $featureJsonPath
        exists = Test-Path -LiteralPath $featureJsonPath -PathType Leaf
        valid_json = $null
        feature_directory = ""
        feature_directory_exists = $false
        spec_branch = ""
        workflow_state = ""
        workflow_state_exists = $false
        workflow_state_valid_json = $null
        terminal = $false
        status = ""
    }
    if (-not $facts.exists) { return [PSCustomObject]$facts }

    $feature = Read-JsonFile $featureJsonPath
    if ($feature -eq "__INVALID_JSON__") {
        $facts.valid_json = $false
        return [PSCustomObject]$facts
    }
    $facts.valid_json = $true
    $featureDir = [string](Get-Prop $feature "feature_directory")
    $facts.spec_branch = [string](Get-Prop $feature "spec_branch")
    if (-not [string]::IsNullOrWhiteSpace($featureDir)) {
        if (-not [System.IO.Path]::IsPathRooted($featureDir)) {
            $featureDir = Join-Path $Root $featureDir
        }
        $facts.feature_directory = $featureDir
        $facts.feature_directory_exists = Test-Path -LiteralPath $featureDir -PathType Container
        $facts.workflow_state = Join-Path $featureDir "workflow-state.json"
        $facts.workflow_state_exists = Test-Path -LiteralPath $facts.workflow_state -PathType Leaf
        if ($facts.workflow_state_exists) {
            $state = Read-JsonFile $facts.workflow_state
            if ($state -eq "__INVALID_JSON__") {
                $facts.workflow_state_valid_json = $false
            } else {
                $facts.workflow_state_valid_json = $true
                $facts.status = ([string](Get-Prop $state "status")).ToLowerInvariant()
                $facts.terminal = Test-TerminalFeatureState -State $state
            }
        }
    }
    return [PSCustomObject]$facts
}

function Get-RunFacts {
    param([string]$Root)
    $runsRoot = Join-Path $Root ".specify/workflows/runs"
    $active = @()
    if (-not (Test-Path -LiteralPath $runsRoot -PathType Container)) { return @() }
    foreach ($runDir in Get-ChildItem -LiteralPath $runsRoot -Directory -ErrorAction SilentlyContinue) {
        $statePath = Join-Path $runDir.FullName "state.json"
        if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { continue }
        $state = Read-JsonFile $statePath
        $status = if ($state -eq "__INVALID_JSON__") { "invalid-json" } else { ([string](Get-Prop $state "status")).ToLowerInvariant() }
        if ($status -in @("paused", "failed", "invalid-json")) {
            $active += [ordered]@{
                run_id = $runDir.Name
                status = $status
                state_path = ConvertTo-SafeRelativePath -Root $Root -Path $statePath
            }
        }
    }
    return @($active)
}

$workspace = Get-WorkspaceConfig -Root $RepoRoot
$allowed = @()
if ($AllowedBaseBranches.Count -gt 0) {
    $allowed += $AllowedBaseBranches
} else {
    $allowed += $workspace.default_base_branch
    $allowed += @("main", "master", "develop")
}
$allowed = @($allowed | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

$blockers = @()
$unknowns = @()
$hints = @(
    "Do not auto-stash, auto-clean, switch branches, or overwrite .specify/feature.json without explicit user authorization.",
    "Recommended manual actions: resume the active workflow, commit/stash/clean current changes, or start the new task in a separate git worktree."
)
$repoFacts = @()
foreach ($repo in $workspace.repositories) {
    $facts = Get-RepoFacts -Repo $repo -AllowedBranches $allowed
    $repoFacts += $facts
    if (-not $facts.exists) {
        if ($facts.required) { $blockers += "Required repository is missing: $($facts.name) ($($facts.path))" }
        continue
    }
    if (-not $facts.is_git) {
        $unknowns += "Repository is not a git work tree; branch and dirty checks skipped: $($facts.name)"
        continue
    }
    if (-not $facts.on_allowed_base_branch) {
        $blockers += "Repository '$($facts.name)' is on branch '$($facts.branch)', not an allowed base branch ($($allowed -join ', '))."
    }
    if ($facts.dirty) {
        $blockers += "Repository '$($facts.name)' has uncommitted or untracked changes; new workflow start is blocked until the user handles them."
    }
}

$activeFeature = Get-ActiveFeatureFacts -Root $RepoRoot
if ($activeFeature.exists) {
    if ($activeFeature.valid_json -eq $false) {
        $blockers += ".specify/feature.json is not valid JSON; resolve or archive it before starting a new workflow."
    } elseif ([string]::IsNullOrWhiteSpace($activeFeature.feature_directory)) {
        $blockers += ".specify/feature.json exists but has no feature_directory; resolve stale active-feature state before starting a new workflow."
    } elseif (-not $activeFeature.feature_directory_exists) {
        $blockers += ".specify/feature.json points to a missing feature directory; resolve stale active-feature state before starting a new workflow."
    } elseif (-not $activeFeature.workflow_state_exists) {
        $blockers += "Active feature has no workflow-state.json; resume or explicitly archive the existing Spec Kit task before starting a new workflow."
    } elseif ($activeFeature.workflow_state_valid_json -eq $false) {
        $blockers += "Active feature workflow-state.json is not valid JSON; resolve it before starting a new workflow."
    } elseif (-not $activeFeature.terminal) {
        $blockers += "Active Spec Kit feature is not terminal; resume or complete it before starting a new workflow."
    } else {
        $hints += "Previous active feature appears terminal; .specify/feature.json may be overwritten by the new workflow."
    }
}

$activeRuns = Get-RunFacts -Root $RepoRoot
if ($activeRuns.Count -gt 0) {
    $blockers += "There are active or unresolved workflow run states under .specify/workflows/runs; resume or archive them before starting a new workflow."
}

$decision = "ok"
if ($blockers.Count -gt 0) {
    $decision = if ($activeFeature.exists -and -not $activeFeature.terminal) { "resume_required" } else { "human_decision_required" }
}

$payload = [ordered]@{
    tool = "preflight-new-workflow"
    status = if ($blockers.Count -gt 0) { "blocked" } else { "ok" }
    facts = [ordered]@{
        repo_root = $RepoRoot
        workspace_root = $workspace.workspace_root
        default_base_branch = $workspace.default_base_branch
        allowed_base_branches = @($allowed)
        decision = $decision
        required_human_action = if ($blockers.Count -gt 0) { "Handle the existing workspace state manually, or explicitly authorize the AI to perform a named safe action before retrying." } else { "" }
        repositories = @($repoFacts)
        active_feature = $activeFeature
        active_runs = @($activeRuns)
    }
    blockers = @($blockers)
    unknowns = @($unknowns)
    hints = @($hints)
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 10 -Compress
} elseif ($payload.status -eq "ok") {
    Write-Output "New workflow preflight passed."
} else {
    foreach ($blocker in $blockers) { [Console]::Error.WriteLine(" - $blocker") }
}
if ($payload.status -eq "blocked") { exit 1 }
