function Get-SpecKitWorktrees {
    param([string]$Path)
    $lines = @(git -C $Path -c core.quotepath=false worktree list --porcelain)
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect worktrees in $Path" }
    $item = $null
    foreach ($line in $lines) {
        if ($line.StartsWith('worktree ')) {
            if ($item) { [pscustomobject]$item }
            $item = @{path=$line.Substring(9); branch=''; head=''}
        } elseif ($item -and $line.StartsWith('branch refs/heads/')) { $item.branch=$line.Substring(18) }
        elseif ($item -and $line.StartsWith('HEAD ')) { $item.head=$line.Substring(5) }
    }
    if ($item) { [pscustomobject]$item }
}

function Test-SpecKitSamePath {
    param([string]$Left, [string]$Right)
    $a = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($Left))
    $b = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($Right))
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    return [string]::Equals($a, $b, $comparison)
}

function Move-SpecKitEntryForward {
    param([string]$Path, [string]$Branch, [string]$Reference)
    git -C $Path merge-base --is-ancestor $Branch $Reference
    if ($LASTEXITCODE -ne 0) { throw "Entry '$Branch' is not a strict fast-forward candidate." }
    $current = git -C $Path branch --show-current
    if ($current -eq $Branch) {
        git -C $Path switch --detach | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Cannot detach entry before fast-forward.' }
    }
    try {
        git -C $Path branch -f $Branch $Reference | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Cannot fast-forward '$Branch'." }
    } finally {
        if ($current -eq $Branch) {
            git -C $Path switch $Branch | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Cannot restore entry '$Branch'." }
        }
    }
}
