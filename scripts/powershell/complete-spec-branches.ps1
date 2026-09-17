#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$Branch = "",
    [string]$BaseBranch = "",
    [switch]$KeepBranch,
    [switch]$DeleteBranch,
    [switch]$AllowDirty,
    [switch]$ConfirmCompletion,
    [switch]$PreflightOnly,
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Output "Usage: complete-spec-branches.ps1 [-Branch <name>] [-BaseBranch <branch>] [-KeepBranch] [-DeleteBranch] [-AllowDirty] [-PreflightOnly] [-ConfirmCompletion] [-Json]"
    Write-Output "Cherry-picks local spec branch commits into the entry branch captured when the spec branch was created; -BaseBranch overrides all recorded targets."
    Write-Output "Use -DeleteBranch only when the user explicitly asks to delete the local spec branch."
    Write-Output "Use -PreflightOnly to inspect every repository without cherry-picking commits."
    Write-Output "Requires default closure artifacts before completion: implementation-summary.md and validation.md."
    Write-Output "Requires -ConfirmCompletion for the branch-state mutation path; preflight remains safe without confirmation."
    exit 0
}

. "$PSScriptRoot/common.ps1"
. "$PSScriptRoot/worktree-common.ps1"

function Get-WorkspaceConfig {
    param([string]$RepoRoot)
    $configPath = Join-Path $RepoRoot ".specify/workspace.yml"
    $workspaceRoot = $RepoRoot
    $baseBranch = "master"
    $primaryRepo = ""
    $remoteKind = "generic"
    $workflowPushAllowed = $true
    $forbidSpecMergeCommits = $true
    $requireExistingRemoteEntryBranch = $false
    $repos = @([PSCustomObject]@{ name = (Split-Path -Leaf $RepoRoot); path = "."; required = $true; participates_in_spec_branches = $true })

    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $rootText = Select-String -Path $configPath -Pattern '^\s*root:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($rootText) {
            $rootValue = $rootText.Matches[0].Groups[1].Value.Trim("'`"")
            $workspaceRoot = if ([System.IO.Path]::IsPathRooted($rootValue)) { $rootValue } else { Join-Path $RepoRoot $rootValue }
        }
        $baseText = Select-String -Path $configPath -Pattern '^\s*default_base_branch:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($baseText) { $baseBranch = $baseText.Matches[0].Groups[1].Value.Trim("'`"") }
        $primaryText = Select-String -Path $configPath -Pattern '^\s*primary_repo:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($primaryText) { $primaryRepo = $primaryText.Matches[0].Groups[1].Value.Trim("'`"") }
        $remoteKindText = Select-String -Path $configPath -Pattern '^\s*remote_kind:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($remoteKindText) { $remoteKind = $remoteKindText.Matches[0].Groups[1].Value.Trim("'`"") }
        $pushAllowedText = Select-String -Path $configPath -Pattern '^\s*workflow_push_allowed:\s*(true|false)\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pushAllowedText) { $workflowPushAllowed = ($pushAllowedText.Matches[0].Groups[1].Value -eq "true") }
        $forbidMergesText = Select-String -Path $configPath -Pattern '^\s*forbid_spec_merge_commits:\s*(true|false)\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($forbidMergesText) { $forbidSpecMergeCommits = ($forbidMergesText.Matches[0].Groups[1].Value -eq "true") }
        $requireRemoteText = Select-String -Path $configPath -Pattern '^\s*require_existing_remote_entry_branch:\s*(true|false)\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($requireRemoteText) { $requireExistingRemoteEntryBranch = ($requireRemoteText.Matches[0].Groups[1].Value -eq "true") }

        $parsedRepos = @()
        $current = $null
        foreach ($line in Get-Content -LiteralPath $configPath) {
            if ($line -match '^\s*-\s*name:\s*"?([^"]+)"?\s*$') {
                if ($current) { $parsedRepos += [PSCustomObject]$current }
                $current = @{ name = $Matches[1].Trim("'`""); path = ""; required = $false; participates_in_spec_branches = $true }
            } elseif ($current -and $line -match '^\s*path:\s*"?([^"]+)"?\s*$') {
                $current.path = $Matches[1].Trim("'`"")
            } elseif ($current -and $line -match '^\s*required:\s*(true|false)\s*$') {
                $current.required = ($Matches[1] -eq "true")
            } elseif ($current -and $line -match '^\s*participates_in_spec_branches:\s*(true|false)\s*$') {
                $current.participates_in_spec_branches = ($Matches[1] -eq "true")
            }
        }
        if ($current) { $parsedRepos += [PSCustomObject]$current }
        if ($parsedRepos.Count -gt 0) { $repos = $parsedRepos }
    }

    $workspaceRoot = (Resolve-Path -LiteralPath $workspaceRoot).Path
    [PSCustomObject]@{
        default_base_branch = $baseBranch
        primary_repo = $primaryRepo
        remote_kind = $remoteKind
        workflow_push_allowed = $workflowPushAllowed
        forbid_spec_merge_commits = $forbidSpecMergeCommits
        require_existing_remote_entry_branch = $requireExistingRemoteEntryBranch
        repositories = @($repos | ForEach-Object {
            $repoPath = if ([System.IO.Path]::IsPathRooted($_.path)) { $_.path } else { Join-Path $workspaceRoot $_.path }
            [PSCustomObject]@{ name = $_.name; path = $repoPath; required = [bool]$_.required; participates_in_spec_branches = [bool]$_.participates_in_spec_branches }
        })
    }
}

function Test-GitRepo {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
    $null = git -C $Path rev-parse --is-inside-work-tree 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Test-GeneratedOrTempPath {
    param([string]$Path)
    $normalized = $Path.Replace("\", "/").Trim('"').ToLowerInvariant()
    if ($normalized -match '(^|/)(\.agents|\.specify|ai|specs|sdkarchive|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.cache|node_modules|dist|build|export|plugin-out|coverage|logs?|tmp|temp)(/|$)') {
        return $true
    }
    if ($normalized -match '(^|/)mock_data/api/pluginmanager(/|$)') {
        return $true
    }
    return ($normalized -match '\.(log|tmp|temp|bak|swp|pid|dmp|cache|pyc|pyo|obj|ilk|pdb)$' -or
        $normalized -match '(^|/)(thumbs\.db|\.ds_store)$')
}

function Get-BlockingDirtyEntries {
    param([string]$Path)
    $classification = Get-DirtyClassification -Path $Path
    return @($classification.tracked_changes + $classification.unclassified_untracked)
}

function Get-DirtyClassification {
    param([string]$Path)
    $status = @(git -C $Path status --porcelain)
    $tracked = @()
    $ignoredUntracked = @()
    $unclassifiedUntracked = @()
    foreach ($line in $status) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line.StartsWith("?? ")) {
            $candidate = $line.Substring(3).Trim()
            if (Test-GeneratedOrTempPath -Path $candidate) {
                $ignoredUntracked += $candidate
            } else {
                $unclassifiedUntracked += $candidate
            }
            continue
        }
        $tracked += $line
    }
    return [PSCustomObject]@{
        tracked_changes = $tracked
        ignored_untracked = $ignoredUntracked
        unclassified_untracked = $unclassifiedUntracked
        has_tracked_changes = ($tracked.Count -gt 0)
        has_unclassified_untracked = ($unclassifiedUntracked.Count -gt 0)
        has_ignored_untracked = ($ignoredUntracked.Count -gt 0)
    }
}

function Test-DirtyBlocksCompletion {
    param(
        [object]$Dirty,
        [int]$CommitCount
    )
    if ($Dirty.has_tracked_changes) { return $true }
    if ($CommitCount -gt 0 -and $Dirty.has_unclassified_untracked) { return $true }
    return $false
}

function Test-Dirty {
    param([string]$Path)
    return (@(Get-BlockingDirtyEntries -Path $Path).Count -gt 0)
}

function Test-BranchExists {
    param([string]$Path, [string]$BranchName)
    $null = git -C $Path show-ref --verify --quiet "refs/heads/$BranchName"
    return ($LASTEXITCODE -eq 0)
}

function Test-BranchHasUpstream {
    param([string]$Path, [string]$BranchName)
    $null = git -C $Path rev-parse --abbrev-ref "$BranchName@{upstream}" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-FeatureConfig {
    param([string]$RepoRoot)
    $featureJson = Join-Path $RepoRoot ".specify/feature.json"
    if (-not (Test-Path -LiteralPath $featureJson -PathType Leaf)) { return $null }
    return (Get-Content -LiteralPath $featureJson -Raw | ConvertFrom-Json)
}

function Get-RecordedCompletionBranch {
    param(
        [object]$FeatureConfig,
        [object]$Repo,
        [string]$Fallback
    )
    if ($FeatureConfig) {
        foreach ($target in @($FeatureConfig.completion_targets)) {
            if ([string]$target.repository -eq [string]$Repo.name -and -not [string]::IsNullOrWhiteSpace([string]$target.branch)) {
                return [string]$target.branch
            }
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$FeatureConfig.entry_branch)) {
            return [string]$FeatureConfig.entry_branch
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$FeatureConfig.base_branch)) {
            return [string]$FeatureConfig.base_branch
        }
    }
    return $Fallback
}

function Get-RemoteDivergence {
    param([string]$Path, [string]$BranchName)
    $upstream = git -C $Path rev-parse --abbrev-ref "$BranchName@{upstream}" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($upstream)) {
        return [PSCustomObject]@{ upstream = $null; ahead = $null; behind = $null; status = "no-upstream" }
    }
    $counts = git -C $Path rev-list --left-right --count "$BranchName...$upstream" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($counts)) {
        return [PSCustomObject]@{ upstream = [string]$upstream; ahead = $null; behind = $null; status = "unknown" }
    }
    $parts = $counts.Trim() -split '\s+'
    return [PSCustomObject]@{
        upstream = [string]$upstream
        ahead = [int]$parts[0]
        behind = [int]$parts[1]
        status = "known"
    }
}

function Resolve-BaseBranch {
    param([string]$Path, [string]$Preferred)
    foreach ($candidate in @($Preferred, "master", "main")) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-BranchExists -Path $Path -BranchName $candidate) { return $candidate }
    }
    throw "No base branch found in $Path. Tried '$Preferred', master, main."
}

function Switch-ToCompletionBranch {
    param([string]$Path, [string]$Target)
    git -C $Path switch $Target | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not switch to entry branch '$Target' in $Path; completion is incomplete."
    }
    $actual = git -C $Path branch --show-current
    if ($LASTEXITCODE -ne 0 -or [string]$actual -ne $Target) {
        throw "Entry branch verification failed in $Path; expected '$Target', got '$actual'."
    }
}

function Get-CherryPickCommits {
    param([string]$Path, [string]$BaseBranchName, [string]$BranchName)
    $commits = git -C $Path rev-list --reverse "$BaseBranchName..$BranchName"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve cherry-pick commit list for '$BranchName' into '$BaseBranchName' in $Path."
    }
    return @($commits | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Get-SpecMergeCommits {
    param([string]$Path, [string]$BaseReference, [string]$BranchName)
    $commits = @(git -C $Path rev-list --merges "$BaseReference..$BranchName" 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect merge commits for '$BranchName' against '$BaseReference' in $Path." }
    return @($commits | Where-Object { $_ })
}

function Get-GerritEntryState {
    param([string]$Path, [string]$BranchName, [string]$Remote = "origin")
    $state = [ordered]@{
        remote = $Remote
        remote_ref = "$Remote/$BranchName"
        remote_target_exists = $false
        remote_target_oid = ""
        entry_ahead = $null
        entry_behind = $null
        remote_base_is_spec_ancestor = $false
        fetch_ok = $false
    }
    $remoteUrl = git -C $Path remote get-url $Remote 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$remoteUrl)) { return [PSCustomObject]$state }
    $remoteHead = @(git -C $Path ls-remote --exit-code --heads $Remote "refs/heads/$BranchName" 2>$null)
    if ($LASTEXITCODE -ne 0 -or $remoteHead.Count -eq 0) { return [PSCustomObject]$state }
    $state.remote_target_exists = $true
    $state.remote_target_oid = ([string]$remoteHead[0] -split '\s+')[0]
    git -C $Path fetch --no-tags $Remote "+refs/heads/${BranchName}:refs/remotes/${Remote}/${BranchName}" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { return [PSCustomObject]$state }
    $state.fetch_ok = $true
    $counts = git -C $Path rev-list --left-right --count "$BranchName...$Remote/$BranchName" 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$counts)) {
        $parts = ([string]$counts).Trim() -split '\s+'
        $state.entry_ahead = [int]$parts[0]
        $state.entry_behind = [int]$parts[1]
    }
    return [PSCustomObject]$state
}

function Get-ConflictFiles {
    param([string]$Path)
    $files = git -C $Path diff --name-only --diff-filter=U
    return @($files | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Resolve-GeneratedArtifactConflicts {
    param([string]$Path, [string[]]$Files)
    $conflicts = @($Files | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($conflicts.Count -eq 0) { return $false }
    foreach ($file in $conflicts) {
        if (-not (Test-GeneratedOrTempPath -Path $file)) { return $false }
    }
    foreach ($file in $conflicts) {
        git -C $Path checkout --ours -- $file | Out-Null
        if ($LASTEXITCODE -ne 0) { return $false }
        git -C $Path add -- $file | Out-Null
        if ($LASTEXITCODE -ne 0) { return $false }
    }
    git -C $Path -c core.editor=true cherry-pick --continue | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }
    git -C $Path cherry-pick --skip | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-GitCherryPick {
    param([string]$Path, [string]$Commit)
    Push-Location -LiteralPath $Path
    try {
        git cherry-pick $Commit | Out-Null
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Resolve-FeatureDirectory {
    param([string]$RepoRoot, [string]$BranchName)
    $featureJson = Join-Path $RepoRoot ".specify/feature.json"
    if (Test-Path -LiteralPath $featureJson -PathType Leaf) {
        $cfg = Get-Content -LiteralPath $featureJson -Raw | ConvertFrom-Json
        $configuredBranch = [string]$cfg.spec_branch
        $configuredFeatureDir = [string]$cfg.feature_directory
        if (-not [string]::IsNullOrWhiteSpace($configuredFeatureDir) -and
            ([string]::IsNullOrWhiteSpace($configuredBranch) -or $configuredBranch -eq $BranchName)) {
            if ([System.IO.Path]::IsPathRooted($configuredFeatureDir)) { return $configuredFeatureDir }
            return (Join-Path $RepoRoot $configuredFeatureDir)
        }
    }
    return (Join-Path (Join-Path $RepoRoot "specs") $BranchName)
}

function Test-ClosureArtifactGate {
    param([string]$RepoRoot, [string]$BranchName)
    $featureDir = Resolve-FeatureDirectory -RepoRoot $RepoRoot -BranchName $BranchName
    $required = @("implementation-summary.md", "validation.md")
    $missing = @()
    foreach ($fileName in $required) {
        $path = Join-Path $featureDir $fileName
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $missing += $fileName }
    }
    [PSCustomObject]@{
        feature_dir = $featureDir
        required = $required
        missing = $missing
        status = if ($missing.Count -eq 0) { "ok" } else { "blocked" }
    }
}

$repoRoot = Get-RepoRoot
$workspace = Get-WorkspaceConfig -RepoRoot $repoRoot
$featureConfigForCompletion = Get-FeatureConfig -RepoRoot $repoRoot
$explicitBaseBranch = -not [string]::IsNullOrWhiteSpace($BaseBranch)

if ([string]::IsNullOrWhiteSpace($Branch)) {
    if ($featureConfigForCompletion) {
        if ($featureConfigForCompletion.spec_branch) { $Branch = [string]$featureConfigForCompletion.spec_branch }
        elseif ($featureConfigForCompletion.feature_directory) { $Branch = Split-Path -Leaf ([string]$featureConfigForCompletion.feature_directory) }
    }
}
if ([string]::IsNullOrWhiteSpace($Branch)) {
    $primaryName = if ($workspace.PSObject.Properties.Name -contains "primary_repo" -and -not [string]::IsNullOrWhiteSpace([string]$workspace.primary_repo)) {
        [string]$workspace.primary_repo
    } else {
        ""
    }
    $primaryRepo = @()
    if (-not [string]::IsNullOrWhiteSpace($primaryName)) {
        $primaryRepo = @($workspace.repositories | Where-Object { $_.name -eq $primaryName } | Select-Object -First 1)
    }
    if ($primaryRepo.Count -eq 0) {
        $primaryRepo = @($workspace.repositories | Select-Object -First 1)
    }
    if ($primaryRepo.Count -gt 0 -and (Test-GitRepo $primaryRepo[0].path)) {
        $Branch = git -C $primaryRepo[0].path rev-parse --abbrev-ref HEAD
    }
}
if ([string]::IsNullOrWhiteSpace($Branch) -or $Branch -eq "HEAD") {
    throw "Could not resolve spec branch. Pass -Branch explicitly."
}
if ($featureConfigForCompletion -and
    -not [string]::IsNullOrWhiteSpace([string]$featureConfigForCompletion.spec_branch) -and
    [string]$featureConfigForCompletion.spec_branch -ne $Branch) {
    $featureConfigForCompletion = $null
}
$hasRecordedCompletionTargets = (
    $featureConfigForCompletion -and (
        @($featureConfigForCompletion.completion_targets).Count -gt 0 -or
        -not [string]::IsNullOrWhiteSpace([string]$featureConfigForCompletion.entry_branch) -or
        -not [string]::IsNullOrWhiteSpace([string]$featureConfigForCompletion.base_branch)
    )
)
$baseBranchSource = if ($explicitBaseBranch) { "argument" } elseif ($hasRecordedCompletionTargets) { "feature.completion_targets" } else { "workspace.default_base_branch" }

$shouldKeepBranch = -not [bool]$DeleteBranch
if ($KeepBranch) { $shouldKeepBranch = $true }

$preflight = @()
$errors = @()
$worktreePlans = @()
$retrospectiveGate = Test-ClosureArtifactGate -RepoRoot $repoRoot -BranchName $Branch
if ($retrospectiveGate.status -ne "ok") {
    $missingText = $retrospectiveGate.missing -join ", "
    $errors += "Closure artifact gate failed for '$Branch': missing $missingText in $($retrospectiveGate.feature_dir). Run speckit.implement/validation before complete-branch."
}
foreach ($repo in $workspace.repositories) {
    $recorded = @($featureConfigForCompletion.completion_targets | Where-Object { $_.repository -eq $repo.name } | Select-Object -First 1)
    if ($repo.participates_in_spec_branches -and $recorded.Count -gt 0 -and $recorded[0].original_path) {
        $originalPath = [string]$recorded[0].original_path
        if (-not [IO.Path]::IsPathRooted($originalPath)) { $originalPath = Join-Path $repoRoot $originalPath }
        $registered = if (Test-GitRepo $repo.path) { @(Get-SpecKitWorktrees -Path $repo.path) } else { @() }
        if (@($registered | Where-Object { Test-SpecKitSamePath $_.path $originalPath }).Count -eq 0) {
            $errors += "$($repo.name): recorded original_path is not a registered worktree of this repository."
        } else { $repo.path = $originalPath }
    }
    $preferredBase = if ($explicitBaseBranch) { $BaseBranch } else { Get-RecordedCompletionBranch -FeatureConfig $featureConfigForCompletion -Repo $repo -Fallback $workspace.default_base_branch }
    if ($repo.participates_in_spec_branches -and (Test-GitRepo $repo.path)) {
        $trees = @(Get-SpecKitWorktrees -Path $repo.path)
        $detach = @($trees | Where-Object { $_.branch -eq $Branch -and -not (Test-SpecKitSamePath $_.path $repo.path) })
        $otherEntry = @($trees | Where-Object { $_.branch -eq $preferredBase -and -not (Test-SpecKitSamePath $_.path $repo.path) })
        foreach ($tree in $detach) {
            $dirty = @(git -C $tree.path status --porcelain --untracked-files=no)
            if ($dirty.Count -gt 0) { $errors += "$($repo.name): Spec worktree '$($tree.path)' has tracked changes; preserve them explicitly before completion." }
        }
        if ($otherEntry.Count -gt 0) { $errors += "$($repo.name): entry branch is checked out in another worktree; resolve its ownership before completion." }
        $worktreePlans += [pscustomobject]@{repository=$repo.name; entry_path=$repo.path; worktrees=$trees; detach_spec_paths=@($detach | ForEach-Object { $_.path })}
    }
    if (-not $repo.participates_in_spec_branches) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "skipped"; branch = $Branch; base = $preferredBase; planned_action = "skip"; participates_in_spec_branches = $false }
        continue
    }
    if (-not (Test-Path -LiteralPath $repo.path -PathType Container)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "missing"; branch = $Branch; base = $preferredBase; planned_action = "skip"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches }
        if ($repo.required) { $errors += "Required repository not found: $($repo.name)" }
        continue
    }
    if (-not (Test-GitRepo $repo.path)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "not-git"; branch = $Branch; base = $preferredBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches }
        $errors += "Repository is not a git work tree: $($repo.name)"
        continue
    }
    $dirtyState = Get-DirtyClassification -Path $repo.path
    try {
        $targetBase = Resolve-BaseBranch -Path $repo.path -Preferred $preferredBase
        $remoteDivergence = Get-RemoteDivergence -Path $repo.path -BranchName $targetBase
    } catch {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "base-missing"; branch = $Branch; base = $preferredBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches }
        $errors += $_.Exception.Message
        continue
    }
    if (-not (Test-BranchExists -Path $repo.path -BranchName $Branch)) {
        if (-not $AllowDirty -and (Test-DirtyBlocksCompletion -Dirty $dirtyState -CommitCount 0)) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "dirty"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
            $errors += "Repository has tracked or blocking dirty changes: $($repo.name). Commit/stash them before completing the spec."
            continue
        }
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "branch-missing"; branch = $Branch; base = $targetBase; planned_action = "switch-to-base"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
        if ($repo.required) { $errors += "Required spec branch '$Branch' missing in $($repo.name)" }
        continue
    }
    if (Test-BranchHasUpstream -Path $repo.path -BranchName $Branch) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "branch-has-upstream"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
        $errors += "Spec branch '$Branch' in $($repo.name) has an upstream; Spec Kit branches must stay local-only."
        continue
    }
    $entryState = $null
    $commitBaseReference = $targetBase
    $fastForwardRequired = $false
    if ($workspace.require_existing_remote_entry_branch) {
        $entryState = Get-GerritEntryState -Path $repo.path -BranchName $targetBase
        if (-not $entryState.remote_target_exists -or -not $entryState.fetch_ok) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "remote-target-missing"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_entry_state = $entryState; dirty_state = $dirtyState }
            $errors += "Recorded Gerrit entry branch 'refs/heads/$targetBase' is missing or could not be fetched for $($repo.name)."
            continue
        }
        if ($entryState.entry_ahead -gt 0 -and $entryState.entry_behind -gt 0) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "entry-branch-diverged"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_entry_state = $entryState; dirty_state = $dirtyState }
            $errors += "Local entry branch '$targetBase' diverged from origin in $($repo.name); merge is forbidden."
            continue
        }
        if ($entryState.entry_ahead -gt 0) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "entry-branch-ahead"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_entry_state = $entryState; dirty_state = $dirtyState }
            $errors += "Local entry branch '$targetBase' has local-only commits in $($repo.name); refusing to overwrite or merge it."
            continue
        }
        $fastForwardRequired = ($entryState.entry_behind -gt 0)
        $commitBaseReference = $entryState.remote_ref
        git -C $repo.path merge-base --is-ancestor $commitBaseReference $Branch 2>$null
        if ($LASTEXITCODE -ne 0) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "needs-rebase"; branch = $Branch; base = $targetBase; planned_action = "sync-spec-branches"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_entry_state = $entryState; dirty_state = $dirtyState }
            $errors += "Spec branch '$Branch' in $($repo.name) is not based on the latest recorded Gerrit entry branch; run sync-spec-branches preflight/rebase."
            continue
        }
    }
    if ($workspace.forbid_spec_merge_commits) {
        $mergeCommits = Get-SpecMergeCommits -Path $repo.path -BaseReference $commitBaseReference -BranchName $Branch
        if ($mergeCommits.Count -gt 0) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "merge-history-blocked"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; merge_commits = @($mergeCommits); remote_entry_state = $entryState; dirty_state = $dirtyState }
            $errors += "Spec branch '$Branch' in $($repo.name) contains merge commit(s): $($mergeCommits -join ', ')."
            continue
        }
    }
    if ($Branch -eq $targetBase) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "branch-is-base"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
        $errors += "Spec branch '$Branch' is the base branch in $($repo.name); refusing to complete."
        continue
    }
    try {
        $commits = Get-CherryPickCommits -Path $repo.path -BaseBranchName $commitBaseReference -BranchName $Branch
    } catch {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "cherry-pick-list-error"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
        $errors += $_.Exception.Message
        continue
    }
    if (-not $AllowDirty -and (Test-DirtyBlocksCompletion -Dirty $dirtyState -CommitCount $commits.Count)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "dirty"; branch = $Branch; base = $targetBase; planned_action = "error"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; dirty_state = $dirtyState }
        $errors += "Repository has tracked or blocking dirty changes: $($repo.name). Commit/stash them before completing the spec."
        continue
    }
    if ($commits.Count -eq 0) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "already-up-to-date"; branch = $Branch; base = $targetBase; planned_action = "switch-to-base"; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; remote_entry_state = $entryState; fast_forward_required = $fastForwardRequired; dirty_state = $dirtyState }
        continue
    }
    $deleteAction = if ($shouldKeepBranch) { "cherry-pick" } else { "cherry-pick-and-delete" }
    $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; status = "ready"; branch = $Branch; base = $targetBase; planned_action = $deleteAction; participates_in_spec_branches = [bool]$repo.participates_in_spec_branches; remote_divergence = $remoteDivergence; remote_entry_state = $entryState; fast_forward_required = $fastForwardRequired; dirty_state = $dirtyState }
}

$preflightPayload = [PSCustomObject]@{
    branch = $Branch
    base_branch = if ($explicitBaseBranch) { $BaseBranch } else { "recorded-entry-branches" }
    default_base_branch = $workspace.default_base_branch
    base_branch_source = $baseBranchSource
    pushed = $false
    confirmed = (-not [bool]$PreflightOnly)
    action = "preflight"
    completion_ready = ($errors.Count -eq 0)
    # Legacy JSON alias retained for older callers. Prefer completion_ready or cherry_pick_ready.
    merge_ready = ($errors.Count -eq 0)
    cherry_pick_ready = ($errors.Count -eq 0)
    keep_branch = $shouldKeepBranch
    preflight = $preflight
    worktree_plans = $worktreePlans
    retrospective_gate = $retrospectiveGate
    errors = $errors
    repositories = @()
}

if ($errors.Count -gt 0) {
    $preflightPayload.action = "preflight-failed"
    if ($Json) {
        $preflightPayload | ConvertTo-Json -Depth 8 -Compress
    } else {
        [Console]::Error.WriteLine("ERROR: Preflight failed before cherry-picking or deleting spec branches:")
        foreach ($errorItem in $errors) {
            [Console]::Error.WriteLine(" - $errorItem")
        }
    }
    exit 1
}

if ($PreflightOnly) {
    $preflightPayload.action = "preflight-only"
    if ($Json) {
        $preflightPayload | ConvertTo-Json -Depth 8 -Compress
    } else {
        Write-Output "SPEC_BRANCH: $Branch"
        Write-Output "PUSHED: false"
        Write-Output "PREFLIGHT: passed"
        foreach ($item in $preflight) {
            Write-Output "$($item.repository): $($item.status) -> $($item.planned_action) on $($item.base)"
        }
    }
    exit 0
}

if (-not $ConfirmCompletion) {
    $preflightPayload.action = "confirmation-required"
    $preflightPayload.confirmed = $false
    $preflightPayload.completion_ready = $false
    $preflightPayload.merge_ready = $false
    $preflightPayload.cherry_pick_ready = $false
    $preflightPayload.errors = @("Branch completion changes local repository state and requires -ConfirmCompletion after explicit human approval.")
    if ($Json) {
        $preflightPayload | ConvertTo-Json -Depth 8 -Compress
    } else {
        [Console]::Error.WriteLine("ERROR: Branch completion requires -ConfirmCompletion after explicit human approval.")
    }
    exit 1
}

$results = @()
foreach ($plan in $worktreePlans) {
    foreach ($path in $plan.detach_spec_paths) {
        if (@(git -C $path status --porcelain --untracked-files=no).Count -gt 0) { throw "Spec worktree changed after preflight: $path" }
        git -C $path switch --detach | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Cannot detach retained Spec worktree '$path'." }
    }
}
foreach ($item in $preflight) {
    if ($item.status -eq "skipped") {
        $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; status = "skipped"; branch = $Branch; base = $item.base; participates_in_spec_branches = $false }
        continue
    }
    if ($item.status -eq "missing") {
        $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; status = $item.status; branch = $Branch; base = $item.base; participates_in_spec_branches = [bool]$item.participates_in_spec_branches }
        continue
    }
    if ($item.status -eq "branch-missing" -or $item.status -eq "already-up-to-date") {
        if ($item.fast_forward_required) {
            Move-SpecKitEntryForward -Path $item.path -Branch $item.base -Reference $item.remote_entry_state.remote_ref
        }
        Switch-ToCompletionBranch -Path $item.path -Target $item.base
        $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; status = "$($item.status); switched-to-$($item.base)"; branch = $Branch; base = $item.base; participates_in_spec_branches = [bool]$item.participates_in_spec_branches }
        continue
    }
    if ($item.fast_forward_required) {
        Move-SpecKitEntryForward -Path $item.path -Branch $item.base -Reference $item.remote_entry_state.remote_ref
    }
    Switch-ToCompletionBranch -Path $item.path -Target $item.base
    $commits = Get-CherryPickCommits -Path $item.path -BaseBranchName $item.base -BranchName $Branch
    $autoResolvedConflicts = @()
    foreach ($commit in $commits) {
        $cherryPickExitCode = Invoke-GitCherryPick -Path $item.path -Commit $commit
        if ($cherryPickExitCode -ne 0) {
            $conflicts = Get-ConflictFiles -Path $item.path
            if (Resolve-GeneratedArtifactConflicts -Path $item.path -Files $conflicts) {
                $autoResolvedConflicts += $conflicts
                continue
            }
            $conflictText = if ($conflicts.Count -gt 0) { $conflicts -join ", " } else { "unknown" }
            throw "Cherry-pick failed in $($item.repository) at $commit. Conflicts: $conflictText"
        }
    }
    if ($item.remote_entry_state -and $item.remote_entry_state.remote_ref) {
        $createdMerges = Get-SpecMergeCommits -Path $item.path -BaseReference $item.remote_entry_state.remote_ref -BranchName $item.base
        if ($createdMerges.Count -gt 0) { throw "Completion created or retained merge commit(s) in $($item.repository): $($createdMerges -join ', ')." }
    }
    $status = "cherry-picked-to-$($item.base)"
    if (-not $shouldKeepBranch) {
        git -C $item.path branch -d $Branch | Out-Null
        $status = "$status; deleted-local-branch"
    } else {
        $status = "$status; kept-local-branch"
    }
    if ($autoResolvedConflicts.Count -gt 0) {
        $uniqueConflicts = @($autoResolvedConflicts | Sort-Object -Unique)
        $status = "$status; auto-resolved-artifact-conflicts=$($uniqueConflicts -join ',')"
    }
    $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; status = $status; branch = $Branch; base = $item.base; participates_in_spec_branches = [bool]$item.participates_in_spec_branches }
}

# Completion covers every participating repository, including zero-commit repos.
foreach ($item in $preflight) {
    if ($item.status -in @("skipped", "missing")) { continue }
    $actual = git -C $item.path branch --show-current
    if ($LASTEXITCODE -ne 0 -or [string]$actual -ne $item.base) {
        throw "Completion is incomplete: $($item.repository) is on '$actual', expected '$($item.base)'."
    }
    if (@(Get-SpecKitWorktrees -Path $item.path | Where-Object { $_.branch -eq $Branch }).Count -gt 0) {
        throw "Completion is incomplete: Spec branch is still checked out in $($item.repository)."
    }
}

$payload = [PSCustomObject]@{
    branch = $Branch
    base_branch = if ($explicitBaseBranch) { $BaseBranch } else { "recorded-entry-branches" }
    default_base_branch = $workspace.default_base_branch
    base_branch_source = $baseBranchSource
    confirmed = $true
    action = "completed"
    completion_ready = $true
    # Legacy JSON alias retained for older callers. Prefer completion_ready or cherry_pick_ready.
    merge_ready = $true
    cherry_pick_ready = $true
    keep_branch = $shouldKeepBranch
    pushed = $false
    retrospective_gate = $retrospectiveGate
    preflight = $preflight
    errors = @()
    repositories = $results
    worktree_plans = $worktreePlans
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 8 -Compress
} else {
    Write-Output "SPEC_BRANCH: $Branch"
    Write-Output "PUSHED: false"
    Write-Output "PREFLIGHT: passed"
    foreach ($result in $results) {
        Write-Output "$($result.repository): $($result.status)"
    }
}
