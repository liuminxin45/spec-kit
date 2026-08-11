#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Branch = "",
    [string]$BaseBranch = "",
    [string]$Remote = "origin",
    [switch]$Fetch,
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"

if ($Help) {
    Write-Output "Usage: inspect-spec-branch-history.ps1 [-RepoRoot <workspace>] [-Branch <spec>] [-BaseBranch <entry>] [-Remote origin] [-Fetch] [-Json]"
    Write-Output "Inspects local-only Spec branches against recorded Gerrit entry branches without writing any remote ref."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Get-SpecKitRoot }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$workspacePath = Join-Path $RepoRoot ".specify/workspace.yml"
$featurePath = Join-Path $RepoRoot ".specify/feature.json"
$feature = if (Test-Path -LiteralPath $featurePath -PathType Leaf) { Get-Content -Raw -LiteralPath $featurePath | ConvertFrom-Json } else { $null }
if ([string]::IsNullOrWhiteSpace($Branch) -and $feature) { $Branch = [string]$feature.spec_branch }

function Get-YamlScalar {
    param([string]$Path, [string]$Key, [string]$Default = "")
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $Default }
    $match = Select-String -Path $Path -Pattern ('^\s*' + [regex]::Escape($Key) + ':\s*(.+?)\s*$') | Select-Object -First 1
    if (-not $match) { return $Default }
    return (($match.Matches[0].Groups[1].Value -split '#', 2)[0]).Trim().Trim("'`"")
}

function Get-YamlBool {
    param([string]$Path, [string]$Key, [bool]$Default = $false)
    $value = (Get-YamlScalar -Path $Path -Key $Key).ToLowerInvariant()
    if ($value -eq "true") { return $true }
    if ($value -eq "false") { return $false }
    return $Default
}

function Get-WorkspaceRepositories {
    $workspaceRoot = $RepoRoot
    $rootValue = Get-YamlScalar -Path $workspacePath -Key "root" -Default "."
    if (-not [string]::IsNullOrWhiteSpace($rootValue)) {
        $workspaceRoot = if ([System.IO.Path]::IsPathRooted($rootValue)) { $rootValue } else { Join-Path $RepoRoot $rootValue }
    }
    $workspaceRoot = (Resolve-Path -LiteralPath $workspaceRoot).Path
    if (-not (Test-Path -LiteralPath $workspacePath -PathType Leaf)) {
        return @([PSCustomObject]@{ name = Split-Path -Leaf $RepoRoot; path = $RepoRoot; required = $true; participates = $true })
    }
    $repos = @()
    $current = $null
    foreach ($line in Get-Content -LiteralPath $workspacePath) {
        if ($line -match '^\s*-\s*name:\s*"?([^"#]+)') {
            if ($current) { $repos += [PSCustomObject]$current }
            $current = @{ name = $Matches[1].Trim(); path = ""; required = $false; participates = $true }
        } elseif ($current -and $line -match '^\s*path:\s*"?([^"#]+)') {
            $current.path = $Matches[1].Trim()
        } elseif ($current -and $line -match '^\s*required:\s*(true|false)') {
            $current.required = ($Matches[1] -eq "true")
        } elseif ($current -and $line -match '^\s*participates_in_spec_branches:\s*(true|false)') {
            $current.participates = ($Matches[1] -eq "true")
        }
    }
    if ($current) { $repos += [PSCustomObject]$current }
    return @($repos | ForEach-Object {
        $path = if ([System.IO.Path]::IsPathRooted($_.path)) { $_.path } else { Join-Path $workspaceRoot $_.path }
        [PSCustomObject]@{ name = $_.name; path = $path; required = [bool]$_.required; participates = [bool]$_.participates }
    })
}

function Get-RecordedBase {
    param([object]$Repo)
    if (-not [string]::IsNullOrWhiteSpace($BaseBranch)) { return $BaseBranch }
    if ($feature) {
        $target = @($feature.completion_targets | Where-Object { [string]$_.repository -eq [string]$Repo.name } | Select-Object -First 1)
        if ($target.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$target[0].branch)) { return [string]$target[0].branch }
        if (-not [string]::IsNullOrWhiteSpace([string]$feature.entry_branch)) { return [string]$feature.entry_branch }
    }
    return (Get-YamlScalar -Path $workspacePath -Key "default_base_branch" -Default "master")
}

function Git-Lines {
    param([string]$Path, [string[]]$Arguments)
    $output = @(& git -C $Path @Arguments 2>$null)
    return [PSCustomObject]@{ exit_code = $LASTEXITCODE; output = @($output) }
}

$requireRemote = Get-YamlBool -Path $workspacePath -Key "require_existing_remote_entry_branch" -Default $false
$forbidMerges = Get-YamlBool -Path $workspacePath -Key "forbid_spec_merge_commits" -Default $true
$records = @()
$blockers = @()

foreach ($repo in Get-WorkspaceRepositories) {
    if (-not $repo.participates) {
        $records += [ordered]@{ repository = $repo.name; path = $repo.path; status = "skipped"; participates_in_spec_branches = $false }
        continue
    }
    $base = Get-RecordedBase -Repo $repo
    $record = [ordered]@{
        repository = $repo.name
        path = $repo.path
        status = "unknown"
        branch = $Branch
        base = $base
        remote = $Remote
        remote_entry_ref = "refs/remotes/$Remote/$base"
        remote_target_exists = $false
        remote_target_oid = ""
        ahead = $null
        behind = $null
        entry_ahead = $null
        entry_behind = $null
        merge_commits = @()
        has_upstream = $false
        remote_base_is_ancestor = $false
        needs_rebase = $false
        linear_history_ready = $false
        participates_in_spec_branches = $true
    }
    if (-not (Test-Path -LiteralPath $repo.path -PathType Container) -or (Git-Lines -Path $repo.path -Arguments @("rev-parse", "--is-inside-work-tree")).exit_code -ne 0) {
        $record.status = "missing-or-not-git"
        if ($repo.required) { $blockers += "$($repo.name): required repository is missing or not a git work tree" }
        $records += $record
        continue
    }
    if ([string]::IsNullOrWhiteSpace($Branch) -or (Git-Lines -Path $repo.path -Arguments @("show-ref", "--verify", "--quiet", "refs/heads/$Branch")).exit_code -ne 0) {
        $record.status = "spec-branch-missing"
        if ($repo.required) { $blockers += "$($repo.name): Spec branch '$Branch' is missing" }
        $records += $record
        continue
    }
    $upstream = Git-Lines -Path $repo.path -Arguments @("rev-parse", "--abbrev-ref", "$Branch@{upstream}")
    $record.has_upstream = ($upstream.exit_code -eq 0)

    $remoteInfo = Git-Lines -Path $repo.path -Arguments @("remote", "get-url", $Remote)
    if ($remoteInfo.exit_code -eq 0) {
        $remoteHead = Git-Lines -Path $repo.path -Arguments @("ls-remote", "--exit-code", "--heads", $Remote, "refs/heads/$base")
        if ($remoteHead.exit_code -eq 0 -and $remoteHead.output.Count -gt 0) {
            $record.remote_target_exists = $true
            $record.remote_target_oid = ([string]$remoteHead.output[0] -split '\s+')[0]
            if ($Fetch) {
                $fetchResult = Git-Lines -Path $repo.path -Arguments @("fetch", "--no-tags", $Remote, "+refs/heads/${base}:refs/remotes/${Remote}/${base}")
                if ($fetchResult.exit_code -ne 0) { $blockers += "$($repo.name): fetch of existing Gerrit entry branch '$base' failed" }
            }
        }
    }
    if ($requireRemote -and -not $record.remote_target_exists) {
        $record.status = "remote-target-missing"
        $blockers += "$($repo.name): Gerrit entry branch 'refs/heads/$base' does not exist on '$Remote'"
        $records += $record
        continue
    }

    $remoteRef = "$Remote/$base"
    $reference = $base
    if ($record.remote_target_exists -and (Git-Lines -Path $repo.path -Arguments @("show-ref", "--verify", "--quiet", "refs/remotes/$Remote/$base")).exit_code -eq 0) {
        $reference = $remoteRef
    }
    $counts = Git-Lines -Path $repo.path -Arguments @("rev-list", "--left-right", "--count", "$reference...$Branch")
    if ($counts.exit_code -eq 0 -and $counts.output.Count -gt 0) {
        $parts = ([string]$counts.output[0]).Trim() -split '\s+'
        $record.behind = [int]$parts[0]
        $record.ahead = [int]$parts[1]
    }
    $mergeResult = Git-Lines -Path $repo.path -Arguments @("rev-list", "--merges", "$reference..$Branch")
    if ($mergeResult.exit_code -eq 0) { $record.merge_commits = @($mergeResult.output | Where-Object { $_ }) }
    $ancestor = Git-Lines -Path $repo.path -Arguments @("merge-base", "--is-ancestor", $reference, $Branch)
    $record.remote_base_is_ancestor = ($ancestor.exit_code -eq 0)
    $record.needs_rebase = (-not $record.remote_base_is_ancestor)

    if ((Git-Lines -Path $repo.path -Arguments @("show-ref", "--verify", "--quiet", "refs/heads/$base")).exit_code -eq 0 -and $record.remote_target_exists) {
        $entryCounts = Git-Lines -Path $repo.path -Arguments @("rev-list", "--left-right", "--count", "$base...$remoteRef")
        if ($entryCounts.exit_code -eq 0 -and $entryCounts.output.Count -gt 0) {
            $entryParts = ([string]$entryCounts.output[0]).Trim() -split '\s+'
            $record.entry_ahead = [int]$entryParts[0]
            $record.entry_behind = [int]$entryParts[1]
        }
    }
    if ($record.has_upstream) { $blockers += "$($repo.name): Spec branch '$Branch' has an upstream; Spec branches must stay local-only" }
    if ($forbidMerges -and $record.merge_commits.Count -gt 0) { $blockers += "$($repo.name): Spec range contains merge commit(s): $($record.merge_commits -join ', ')" }
    $record.linear_history_ready = (-not $record.has_upstream -and $record.merge_commits.Count -eq 0 -and $record.remote_base_is_ancestor -and (-not $requireRemote -or $record.remote_target_exists))
    $record.status = if ($record.merge_commits.Count -gt 0) { "merge-history-blocked" } elseif ($record.has_upstream) { "branch-has-upstream" } elseif ($record.needs_rebase) { "needs-rebase" } else { "linear" }
    $records += $record
}

$payload = [ordered]@{
    tool = "inspect-spec-branch-history"
    status = if ($blockers.Count -gt 0) { "blocked" } else { "ok" }
    facts = [ordered]@{ branch = $Branch; remote = $Remote; fetched = [bool]$Fetch; repositories = $records }
    blockers = @($blockers)
    unknowns = @()
    hints = @("Use sync-spec-branches.ps1 -PreflightOnly, then -ConfirmSync after explicit approval; never use git pull or git merge on a Spec branch.")
}
if ($Json) { $payload | ConvertTo-Json -Depth 9 -Compress } else { $payload }
if ($payload.status -eq "blocked") { exit 1 }
