#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$FeatureName = "",
    [switch]$Json,
    [switch]$AllowDirty,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Output "Usage: create-spec-branch.ps1 [-FeatureName <name>] [-Json] [-AllowDirty]"
    Write-Output "Creates or switches to one local spec branch across workspace repositories."
    exit 0
}

. "$PSScriptRoot/common.ps1"

function ConvertTo-Slug {
    param([string]$Value)
    $slug = $Value.ToLowerInvariant()
    $slug = $slug -replace '[^a-z0-9]+', '-'
    $slug = $slug.Trim('-')
    if ([string]::IsNullOrWhiteSpace($slug)) { return "spec-work" }
    if ($slug.Length -gt 48) { return $slug.Substring(0, 48).Trim('-') }
    return $slug
}

function Get-WorkspaceConfig {
    param([string]$RepoRoot)

    $configPath = Join-Path $RepoRoot ".specify/workspace.yml"
    $workspaceRoot = Split-Path -Parent $RepoRoot
    $baseBranch = "master"
    $repos = @(
        [PSCustomObject]@{ name = (Split-Path -Leaf $RepoRoot); path = (Split-Path -Leaf $RepoRoot); role = "primary"; required = $true }
    )

    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $rootText = Select-String -Path $configPath -Pattern '^\s*root:\s*"?([^"]+)"?\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($rootText -and $rootText.Matches[0].Groups[1].Value) {
            $rootValue = $rootText.Matches[0].Groups[1].Value.Trim("'`"")
            if ([System.IO.Path]::IsPathRooted($rootValue)) {
                $workspaceRoot = $rootValue
            } else {
                $workspaceRoot = Join-Path $RepoRoot $rootValue
            }
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
                $current = @{ name = $Matches[1].Trim("'`""); path = ""; role = ""; required = $false }
            } elseif ($current -and $line -match '^\s*path:\s*"?([^"]+)"?\s*$') {
                $current.path = $Matches[1].Trim("'`"")
            } elseif ($current -and $line -match '^\s*role:\s*"?([^"]+)"?\s*$') {
                $current.role = $Matches[1].Trim("'`"")
            } elseif ($current -and $line -match '^\s*required:\s*(true|false)\s*$') {
                $current.required = ($Matches[1] -eq "true")
            }
        }
        if ($current) { $parsedRepos += [PSCustomObject]$current }
        if ($parsedRepos.Count -gt 0) { $repos = $parsedRepos }
    }

    $workspaceRoot = (Resolve-Path -LiteralPath $workspaceRoot).Path
    $resolvedRepos = @()
    foreach ($repo in $repos) {
        $repoPath = if ([System.IO.Path]::IsPathRooted($repo.path)) { $repo.path } else { Join-Path $workspaceRoot $repo.path }
        $resolvedRepos += [PSCustomObject]@{
            name = $repo.name
            path = $repoPath
            role = if ([string]::IsNullOrWhiteSpace($repo.role)) { "unspecified" } else { $repo.role }
            required = [bool]$repo.required
        }
    }

    [PSCustomObject]@{
        workspace_root = $workspaceRoot
        default_base_branch = $baseBranch
        repositories = $resolvedRepos
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
    $status = @(git -C $Path status --porcelain)
    $blocking = @()
    foreach ($line in $status) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line.StartsWith("?? ")) {
            $candidate = $line.Substring(3).Trim()
            if (Test-GeneratedOrTempPath -Path $candidate) { continue }
        }
        $blocking += $line
    }
    return $blocking
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

function Get-NextSpecNumber {
    param([string]$RepoRoot, [array]$Repositories)
    $max = 0
    $specsDir = Join-Path $RepoRoot "specs"
    if (Test-Path -LiteralPath $specsDir -PathType Container) {
        foreach ($dir in Get-ChildItem -LiteralPath $specsDir -Directory) {
            if ($dir.Name -match '^(\d{3,})-') { $max = [Math]::Max($max, [int]$Matches[1]) }
        }
    }
    foreach ($repo in $Repositories) {
        if (Test-GitRepo $repo.path) {
            foreach ($branch in git -C $repo.path branch --format "%(refname:short)") {
                if ($branch -match '^(\d{3,})-') { $max = [Math]::Max($max, [int]$Matches[1]) }
            }
        }
    }
    return ($max + 1).ToString("000")
}

$repoRoot = Get-RepoRoot
$workspace = Get-WorkspaceConfig -RepoRoot $repoRoot
$repositoryMap = ".specify/memory/repository-map.md"

if ([string]::IsNullOrWhiteSpace($FeatureName)) {
    if ($env:SPECIFY_FEATURE) { $FeatureName = $env:SPECIFY_FEATURE }
    else { throw "FeatureName is required when SPECIFY_FEATURE is not set." }
}

$rawName = ConvertTo-Slug $FeatureName
if ($rawName -match '^\d{3,}-') {
    $branchName = $rawName
} else {
    $branchName = "$(Get-NextSpecNumber -RepoRoot $repoRoot -Repositories $workspace.repositories)-$rawName"
}

$preflight = @()
$errors = @()
foreach ($repo in $workspace.repositories) {
    if (-not (Test-Path -LiteralPath $repo.path -PathType Container)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "missing"; branch = $branchName; planned_action = "skip" }
        if ($repo.required) { $errors += "Required repository not found: $($repo.name) at $($repo.path)" }
        continue
    }
    if (-not (Test-GitRepo $repo.path)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "not-git"; branch = $branchName; planned_action = "error" }
        $errors += "Repository is not a git work tree: $($repo.name) at $($repo.path)"
        continue
    }
    if (-not $AllowDirty -and (Test-Dirty $repo.path)) {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "dirty"; branch = $branchName; planned_action = "error" }
        $errors += "Repository has uncommitted changes: $($repo.name). Commit/stash them, or rerun with -AllowDirty."
        continue
    }

    $exists = Test-BranchExists -Path $repo.path -BranchName $branchName
    if ($exists) {
        if (Test-BranchHasUpstream -Path $repo.path -BranchName $branchName) {
            $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "branch-has-upstream"; branch = $branchName; planned_action = "error" }
            $errors += "Spec branch '$branchName' in $($repo.name) has an upstream; Spec Kit branches must stay local-only."
            continue
        }
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "ready"; branch = $branchName; planned_action = "switch" }
    } else {
        $preflight += [PSCustomObject]@{ repository = $repo.name; path = $repo.path; role = $repo.role; required = [bool]$repo.required; status = "ready"; branch = $branchName; planned_action = "create" }
    }
}

if ($errors.Count -gt 0) {
    throw ("Preflight failed before creating or switching spec branches:`n - " + ($errors -join "`n - "))
}

$results = @()
foreach ($item in $preflight) {
    if ($item.status -eq "missing") {
        $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; role = $item.role; required = [bool]$item.required; status = "missing"; branch = $branchName }
        continue
    }
    if ($item.planned_action -eq "switch") {
        git -C $item.path switch $branchName | Out-Null
        $status = "switched"
    } elseif ($item.planned_action -eq "create") {
        git -C $item.path switch -c $branchName | Out-Null
        $status = "created"
    } else {
        throw "Unexpected preflight action '$($item.planned_action)' for $($item.repository)."
    }
    $results += [PSCustomObject]@{ repository = $item.repository; path = $item.path; role = $item.role; required = [bool]$item.required; status = $status; branch = $branchName }
}

$featureDir = Join-Path $repoRoot "specs/$branchName"
New-Item -ItemType Directory -Path $featureDir -Force | Out-Null

$featureJson = Join-Path $repoRoot ".specify/feature.json"
$featureConfig = [ordered]@{}
if (Test-Path -LiteralPath $featureJson -PathType Leaf) {
    try {
        $existing = Get-Content -LiteralPath $featureJson -Raw | ConvertFrom-Json
        foreach ($prop in $existing.PSObject.Properties) { $featureConfig[$prop.Name] = $prop.Value }
    } catch {
        throw "Failed to parse .specify/feature.json: $_"
    }
}
$featureConfig["feature_directory"] = "specs/$branchName"
$featureConfig["spec_branch"] = $branchName
$featureConfig["branch_local_only"] = $true
$featureConfig["workspace_root"] = $workspace.workspace_root
$featureConfig["default_base_branch"] = $workspace.default_base_branch
$featureConfig["repository_map"] = $repositoryMap
$featureConfig["workspace_repositories"] = @($workspace.repositories | ForEach-Object {
    [ordered]@{
        name = $_.name
        path = $_.path
        role = $_.role
        required = [bool]$_.required
    }
})
$featureConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $featureJson -Encoding UTF8

$payload = [PSCustomObject]@{
    branch = $branchName
    feature_dir = $featureDir
    local_only = $true
    workspace_root = $workspace.workspace_root
    default_base_branch = $workspace.default_base_branch
    repository_map = $repositoryMap
    preflight = $preflight
    repositories = $results
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 8 -Compress
} else {
    Write-Output "SPEC_BRANCH: $branchName"
    Write-Output "FEATURE_DIR: $featureDir"
    Write-Output "LOCAL_ONLY: true"
    Write-Output "WORKSPACE_ROOT: $($workspace.workspace_root)"
    Write-Output "DEFAULT_BASE_BRANCH: $($workspace.default_base_branch)"
    Write-Output "REPOSITORY_MAP: $repositoryMap"
    Write-Output "PREFLIGHT: passed"
    foreach ($result in $results) {
        Write-Output "$($result.repository) [$($result.role)]: $($result.status) -> $($result.branch)"
    }
}
