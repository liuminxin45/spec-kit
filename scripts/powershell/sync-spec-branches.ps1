#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Branch = "",
    [string]$Remote = "origin",
    [switch]$PreflightOnly,
    [switch]$ConfirmSync,
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"
. "$PSScriptRoot/worktree-common.ps1"

if ($Help) {
    Write-Output "Usage: sync-spec-branches.ps1 [-RepoRoot <workspace>] [-Branch <spec>] [-Remote origin] [-PreflightOnly|-ConfirmSync] [-Json]"
    Write-Output "Fetches recorded Gerrit entry branches and rebases local-only Spec branches without pull, merge, upstream creation, or push."
    exit 0
}
if ($PreflightOnly -and $ConfirmSync) { throw "Choose either -PreflightOnly or -ConfirmSync." }
if (-not $PreflightOnly -and -not $ConfirmSync) { $PreflightOnly = $true }
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Get-SpecKitRoot }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Test-IgnorablePath {
    param([string]$Path)
    $normalized = $Path.Replace("\", "/").Trim('"').ToLowerInvariant()
    return ($normalized -match '(^|/)(\.agents|\.specify|ai|specs|__pycache__|\.pytest_cache|\.cache|node_modules|dist|build|export|plugin-out|coverage|logs?|tmp|temp)(/|$)' -or $normalized -match '\.(log|tmp|temp|bak|pyc|obj|pdb)$')
}

$inspector = Join-Path $PSScriptRoot "inspect-spec-branch-history.ps1"
$raw = & $inspector -RepoRoot $RepoRoot -Branch $Branch -Remote $Remote -Fetch -Json
$inspectExit = $LASTEXITCODE
$inspection = $raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($Branch)) { $Branch = [string]$inspection.facts.branch }
$blockers = @($inspection.blockers)
$preflight = @()
foreach ($record in @($inspection.facts.repositories)) {
    if ($record.status -eq "skipped") { $preflight += $record; continue }
    if (-not (Test-Path -LiteralPath $record.path -PathType Container)) { $preflight += $record; continue }
    $record | Add-Member -NotePropertyName entry_path -NotePropertyValue $record.path -Force
    $trees = @(Get-SpecKitWorktrees -Path $record.path)
    $owner = @($trees | Where-Object { $_.branch -eq $Branch })
    if ($owner.Count -eq 1) { $record.path = $owner[0].path }
    $record | Add-Member -NotePropertyName worktrees -NotePropertyValue $trees -Force
    $record | Add-Member -NotePropertyName original_head -NotePropertyValue (git -C $record.path rev-parse HEAD) -Force
    $statusLines = @(git -C $record.path status --porcelain)
    $tracked = @($statusLines | Where-Object { $_ -and -not $_.StartsWith("?? ") })
    $unclassified = @($statusLines | Where-Object { $_.StartsWith("?? ") } | ForEach-Object { $_.Substring(3).Trim() } | Where-Object { -not (Test-IgnorablePath $_) })
    $record | Add-Member -NotePropertyName tracked_dirty -NotePropertyValue $tracked -Force
    $record | Add-Member -NotePropertyName unclassified_untracked -NotePropertyValue $unclassified -Force
    $record | Add-Member -NotePropertyName original_branch -NotePropertyValue ([string](git -C $record.path branch --show-current)).Trim() -Force
    $plannedAction = if ($record.needs_rebase) { "fetch-rebase" } else { "none" }
    $record | Add-Member -NotePropertyName planned_action -NotePropertyValue $plannedAction -Force
    if ($tracked.Count -gt 0 -or $unclassified.Count -gt 0) {
        $record.status = "dirty"
        $blockers += "$($record.repository): tracked or unclassified worktree changes block rebase"
    }
    $preflight += $record
}

$payload = [ordered]@{
    tool = "sync-spec-branches"
    status = if ($blockers.Count -gt 0 -or $inspectExit -ne 0) { "blocked" } else { "ok" }
    action = if ($PreflightOnly) { "preflight-only" } else { "sync" }
    confirmed = [bool]$ConfirmSync
    facts = [ordered]@{ branch = $Branch; remote = $Remote; repositories = $preflight; pushed = $false; upstream_created = $false }
    blockers = @($blockers | Select-Object -Unique)
    unknowns = @()
    hints = @()
}
if ($payload.status -eq "blocked") {
    if ($Json) { $payload | ConvertTo-Json -Depth 10 -Compress } else { $payload }
    exit 1
}
if ($PreflightOnly) {
    if ($Json) { $payload | ConvertTo-Json -Depth 10 -Compress } else { $payload }
    exit 0
}

$results = @()
foreach ($record in @($preflight)) {
    if ($record.status -eq "skipped") { $results += $record; continue }
    if (-not $record.needs_rebase) {
        $record.status = "already-linear"
        $results += $record
        continue
    }
    $originalBranch = [string]$record.original_branch
    git -C $record.path switch $Branch | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not switch $($record.repository) to Spec branch '$Branch'." }
    git -C $record.path rebase "$Remote/$($record.base)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        git -C $record.path rebase --abort | Out-Null
        $restoreFailed = $false
        if ($originalBranch -and $originalBranch -ne $Branch) {
            git -C $record.path switch $originalBranch | Out-Null
            $restoreFailed = ($LASTEXITCODE -ne 0)
        }
        if (-not $originalBranch) {
            git -C $record.path switch --detach $record.original_head | Out-Null
            $restoreFailed = ($LASTEXITCODE -ne 0)
        }
        $record.status = "rebase-conflict"
        $record | Add-Member -NotePropertyName restored_original_branch -NotePropertyValue (-not $restoreFailed) -Force
        $payload.status = "blocked"
        $payload.action = "aborted"
        $payload.blockers = @("$($record.repository): rebase failed; rebase was aborted and no conflict was auto-resolved.")
        if ($restoreFailed) { $payload.blockers += "$($record.repository): failed to restore original branch '$originalBranch'." }
        $payload.facts.repositories = @($results + $record)
        if ($Json) { $payload | ConvertTo-Json -Depth 10 -Compress } else { $payload }
        exit 1
    }
    $verifyRaw = & $inspector -RepoRoot $record.path -Branch $Branch -BaseBranch $record.base -Remote $Remote -Json
    $verifyExit = $LASTEXITCODE
    $verify = $verifyRaw | ConvertFrom-Json
    if ($verifyExit -ne 0 -or -not $verify.facts.repositories[0].linear_history_ready) {
        throw "Post-rebase linear-history verification failed in $($record.repository)."
    }
    $record.status = "rebased-linear"
    $record.linear_history_ready = $true
    if ($originalBranch -and $originalBranch -ne $Branch) {
        git -C $record.path switch $originalBranch | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Rebase succeeded but original branch '$originalBranch' could not be restored in $($record.repository)." }
    }
    if (-not $originalBranch) {
        git -C $record.path switch --detach $record.original_head | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not restore detached worktree.' }
    }
    $record | Add-Member -NotePropertyName restored_original_branch -NotePropertyValue $true -Force
    $results += $record
}
$payload.action = "completed"
$payload.facts.repositories = $results
if ($Json) { $payload | ConvertTo-Json -Depth 10 -Compress } else { $payload }
