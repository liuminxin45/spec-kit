#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Remote = "origin",
    [string]$Branch = "",
    [switch]$ForcePush,
    [switch]$AllowProtectedBranch,
    [switch]$AllowForce,
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"

if ($Help) {
    Write-Output "Usage: preflight-push.ps1 [-RepoRoot <repo>] [-Remote origin] [-Branch <branch>] [-ForcePush] [-AllowProtectedBranch] [-AllowForce] [-Json]"
    Write-Output "Blocks unsafe remote writes such as protected-branch pushes, unrelated history, behind-upstream pushes, force-push without override, and project knowledge leakage."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Get-CurrentRepoRoot
}
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Get-Location).Path
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Git-Out {
    param([string[]]$GitArgs)
    $out = & git -C $RepoRoot @GitArgs 2>$null
    [PSCustomObject]@{ exit_code = $LASTEXITCODE; output = @($out) }
}

$blockers = @()
$hints = @()
$facts = [ordered]@{
    repo_root = $RepoRoot
    remote = $Remote
    branch = ""
    upstream = ""
    protected_branch = $false
    ahead = $null
    behind = $null
    merge_base = ""
    changed_files = @()
    leaked_knowledge_candidates = @()
    readme_exists = Test-Path -LiteralPath (Join-Path $RepoRoot "README.md") -PathType Leaf
}

$inside = Git-Out @("rev-parse", "--is-inside-work-tree")
if ($inside.exit_code -ne 0) {
    $blockers += "RepoRoot is not a git work tree."
} else {
    if ([string]::IsNullOrWhiteSpace($Branch)) {
        $current = Git-Out @("rev-parse", "--abbrev-ref", "HEAD")
        if ($current.exit_code -eq 0) { $Branch = [string]$current.output[0] }
    }
    $facts.branch = $Branch
    $facts.protected_branch = ($Branch -in @("main", "master", "trunk", "release"))
    if ($facts.protected_branch -and -not $AllowProtectedBranch) {
        $blockers += "Direct push to protected branch '$Branch' is blocked; create a PR branch instead."
    }
    if ($ForcePush -and -not $AllowForce) {
        $blockers += "Force push requires explicit -AllowForce and should normally be replaced by a PR."
    }
    if (-not $facts.readme_exists) {
        $blockers += "README.md is missing at repository root."
    }

    $remoteInfo = Git-Out @("remote", "get-url", $Remote)
    if ($remoteInfo.exit_code -ne 0) {
        $blockers += "Remote '$Remote' is not configured."
    }

    $upstream = Git-Out @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if ($upstream.exit_code -ne 0 -or $upstream.output.Count -eq 0) {
        $blockers += "Current branch has no upstream; push through a PR branch with explicit upstream setup."
    } else {
        $facts.upstream = [string]$upstream.output[0]
        $mergeBase = Git-Out @("merge-base", "HEAD", $facts.upstream)
        if ($mergeBase.exit_code -ne 0 -or $mergeBase.output.Count -eq 0) {
            $blockers += "HEAD and upstream have no merge base; unrelated history push is blocked."
        } else {
            $facts.merge_base = [string]$mergeBase.output[0]
            $counts = Git-Out @("rev-list", "--left-right", "--count", "HEAD...$($facts.upstream)")
            if ($counts.exit_code -eq 0 -and $counts.output.Count -gt 0) {
                $parts = ([string]$counts.output[0]) -split "\s+"
                if ($parts.Count -ge 2) {
                    $facts.ahead = [int]$parts[0]
                    $facts.behind = [int]$parts[1]
                    if ($facts.behind -gt 0) {
                        $blockers += "Local branch is behind upstream by $($facts.behind) commit(s); rebase/merge intentionally before any push."
                    }
                }
            }
            $changed = Git-Out @("diff", "--name-only", "$($facts.upstream)...HEAD")
            if ($changed.exit_code -eq 0) {
                $facts.changed_files = @($changed.output | ForEach-Object { ([string]$_) -replace "\\", "/" })
            }
        }
    }

    $leaked = @($facts.changed_files | Where-Object {
        ($_ -match '(^|/)ai/knowledge/repositories/.+\.md$' -and $_ -notmatch '(^|/)ai/knowledge/repositories/README\.md$') -or
        ($_ -match '(^|/)templates/ai/knowledge/repositories/.+\.md$' -and $_ -notmatch '(^|/)templates/ai/knowledge/repositories/README\.md$')
    })
    if ($leaked.Count -gt 0) {
        $facts.leaked_knowledge_candidates = $leaked
        $blockers += "Repository-specific knowledge guides are present in the push diff: $($leaked -join ', ')"
    }

    if ($facts.protected_branch) {
        $hints += "Open-source default is PR-first. Direct protected-branch push should be an exceptional maintainer action."
    }
}

$payload = [ordered]@{
    tool = "preflight-push"
    status = if ($blockers.Count -gt 0) { "blocked" } else { "ok" }
    facts = $facts
    blockers = $blockers
    unknowns = @()
    hints = $hints
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 8 -Compress
} elseif ($payload.status -eq "ok") {
    Write-Output "Push preflight passed."
} else {
    foreach ($blocker in $blockers) { [Console]::Error.WriteLine(" - $blocker") }
}
if ($payload.status -eq "blocked") { exit 1 }
