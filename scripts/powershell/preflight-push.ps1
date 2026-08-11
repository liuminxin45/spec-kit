#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Remote = "origin",
    [string]$Branch = "",
    [string]$TargetBranch = "",
    [switch]$ConfirmHumanPush,
    [switch]$ForcePush,
    [switch]$AllowProtectedBranch,
    [switch]$AllowForce,
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/common.ps1"

if ($Help) {
    Write-Output "Usage: preflight-push.ps1 [-RepoRoot <repo>] [-Remote origin] [-Branch <branch>] [-TargetBranch <existing-entry>] [-ConfirmHumanPush] [-ForcePush] [-AllowProtectedBranch] [-AllowForce] [-Json]"
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

function Find-WorkspaceRoot {
    param([string]$RepositoryRoot)
    foreach ($candidate in @($RepositoryRoot, (Split-Path -Parent $RepositoryRoot))) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath (Join-Path $candidate ".specify/workspace.yml") -PathType Leaf)) {
            return $candidate
        }
    }
    return ""
}

function Get-WorkspaceScalar {
    param([string]$WorkspaceRoot, [string]$Key, [string]$Default = "")
    if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { return $Default }
    $path = Join-Path $WorkspaceRoot ".specify/workspace.yml"
    $match = Select-String -Path $path -Pattern ('^\s*' + [regex]::Escape($Key) + ':\s*(.+?)\s*$') | Select-Object -First 1
    if (-not $match) { return $Default }
    return (($match.Matches[0].Groups[1].Value -split '#', 2)[0]).Trim().Trim("'`"")
}

function Get-RecordedTargetBranch {
    param([string]$WorkspaceRoot, [string]$RepositoryName)
    if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { return "" }
    $path = Join-Path $WorkspaceRoot ".specify/feature.json"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return "" }
    $feature = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    $target = @($feature.completion_targets | Where-Object { [string]$_.repository -eq $RepositoryName } | Select-Object -First 1)
    if ($target.Count -gt 0) { return [string]$target[0].branch }
    return [string]$feature.entry_branch
}

$workspaceRoot = Find-WorkspaceRoot -RepositoryRoot $RepoRoot
$remoteKind = (Get-WorkspaceScalar -WorkspaceRoot $workspaceRoot -Key "remote_kind" -Default "generic").ToLowerInvariant()
$workflowPushMode = (Get-WorkspaceScalar -WorkspaceRoot $workspaceRoot -Key "workflow_push_allowed" -Default "true").ToLowerInvariant()
$workflowPushAllowed = $workflowPushMode -in @("true", "explicit-human-approval")
$gerritDelegatedPush = ($remoteKind -eq "gerrit" -and $workflowPushMode -eq "explicit-human-approval")
$gerritNoPush = ($remoteKind -eq "gerrit" -and $workflowPushMode -eq "false")
$gerritControlled = ($gerritNoPush -or $gerritDelegatedPush)

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
    remote_kind = $remoteKind
    workflow_push_allowed = $workflowPushAllowed
    workflow_push_forbidden = $gerritNoPush
    workflow_push_mode = $workflowPushMode
    human_push_approval_required = $gerritDelegatedPush
    human_push_approved = [bool]$ConfirmHumanPush
    target_branch = $TargetBranch
    remote_target_exists = $null
    merge_commits = @()
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
    if ([string]::IsNullOrWhiteSpace($TargetBranch) -and $gerritControlled) {
        $TargetBranch = Get-RecordedTargetBranch -WorkspaceRoot $workspaceRoot -RepositoryName (Split-Path -Leaf $RepoRoot)
    }
    $facts.target_branch = $TargetBranch
    if ($gerritControlled) {
        if ($gerritNoPush) {
            $blockers += "workflow_push_forbidden: Spec Kit never pushes in this Gerrit workspace; remote delivery is a manual action outside the workflow."
        } elseif (-not $ConfirmHumanPush) {
            $blockers += "human_push_approval_required: delegated Gerrit push requires an explicit human request for this operation."
        }
        if ([string]::IsNullOrWhiteSpace($TargetBranch)) {
            $blockers += "Recorded Gerrit entry branch is unavailable for push audit."
        } else {
            $remoteTarget = Git-Out @("ls-remote", "--exit-code", "--heads", $Remote, "refs/heads/$TargetBranch")
            $facts.remote_target_exists = ($remoteTarget.exit_code -eq 0 -and $remoteTarget.output.Count -gt 0)
            if (-not $facts.remote_target_exists) {
                $blockers += "Recorded Gerrit target 'refs/heads/$TargetBranch' does not exist; creating a remote branch is forbidden."
            } else {
                $fetchedTarget = Git-Out @("fetch", "--no-tags", $Remote, "+refs/heads/${TargetBranch}:refs/remotes/${Remote}/${TargetBranch}")
                if ($fetchedTarget.exit_code -ne 0) { $blockers += "Recorded Gerrit target '$TargetBranch' exists but could not be fetched for audit." }
            }
            $reference = ""
            foreach ($candidate in @("$Remote/$TargetBranch", $TargetBranch)) {
                $resolved = Git-Out @("rev-parse", "--verify", $candidate)
                if ($resolved.exit_code -eq 0) { $reference = $candidate; break }
            }
            if (-not [string]::IsNullOrWhiteSpace($reference)) {
                $merges = Git-Out @("rev-list", "--merges", "$reference..$Branch")
                if ($merges.exit_code -eq 0) { $facts.merge_commits = @($merges.output | Where-Object { $_ }) }
                if ($facts.merge_commits.Count -gt 0) {
                    $blockers += "Spec branch contains merge commit(s): $($facts.merge_commits -join ', ')"
                }
                $counts = Git-Out @("rev-list", "--left-right", "--count", "$reference...$Branch")
                if ($counts.exit_code -eq 0 -and $counts.output.Count -gt 0) {
                    $parts = ([string]$counts.output[0]) -split "\s+"
                    if ($parts.Count -ge 2) {
                        $facts.behind = [int]$parts[0]
                        $facts.ahead = [int]$parts[1]
                        if ($facts.behind -gt 0) {
                            $blockers += "Local Gerrit entry branch is behind '$reference' by $($facts.behind) commit(s)."
                        }
                    }
                }
                $changed = Git-Out @("diff", "--name-only", "$reference...$Branch")
                if ($changed.exit_code -eq 0) {
                    $facts.changed_files = @($changed.output | ForEach-Object { ([string]$_) -replace "\\", "/" })
                }
            }
            if ($gerritDelegatedPush -and $Branch -ne $TargetBranch) {
                $blockers += "Delegated Gerrit push must run from recorded entry branch '$TargetBranch', not '$Branch'."
            }
        }
    }
    $facts.branch = $Branch
    $facts.protected_branch = ($Branch -in @("main", "master", "trunk", "release"))
    if (-not $gerritControlled -and $facts.protected_branch -and -not $AllowProtectedBranch) {
        $blockers += "Direct push to protected branch '$Branch' is blocked; create a PR branch instead."
    }
    if ($gerritDelegatedPush -and $ForcePush) {
        $blockers += "Delegated Gerrit push never permits force push."
    } elseif ($ForcePush -and -not $AllowForce) {
        $blockers += "Force push requires explicit -AllowForce and should normally be replaced by a PR."
    }
    if (-not $gerritControlled -and -not $facts.readme_exists) {
        $blockers += "README.md is missing at repository root."
    }

    $remoteInfo = Git-Out @("remote", "get-url", $Remote)
    if ($remoteInfo.exit_code -ne 0) {
        $blockers += "Remote '$Remote' is not configured."
    }

    $upstream = Git-Out @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if (($upstream.exit_code -ne 0 -or $upstream.output.Count -eq 0) -and -not $gerritControlled) {
        $blockers += "Current branch has no upstream; push through a PR branch with explicit upstream setup."
    } elseif ($upstream.exit_code -eq 0 -and $upstream.output.Count -gt 0) {
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

    if ($facts.protected_branch -and -not $gerritControlled) {
        $hints += "Open-source default is PR-first. Direct protected-branch push should be an exceptional maintainer action."
    }
    if ($gerritNoPush) {
        $hints += "Audit only: do not create an upstream, remote Spec branch, or refs/heads target from Spec Kit."
    } elseif ($gerritDelegatedPush) {
        $hints += "Delegated Gerrit push may use only the existing workspace-configured, human-approved push mechanism; project-specific commands come from selected knowledge packs."
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
