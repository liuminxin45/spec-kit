param(
    [string]$RepoRoot = "",
    [string]$PackRoot = "",
    [string]$PackId = "",
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "install-hook-tools"

function ConvertTo-HookToolSlug {
    param([string]$Value)
    $slug = ($Value.ToLowerInvariant() -replace "[^a-z0-9_.-]+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($slug)) { return "hook-tool" }
    return $slug
}

function Get-HookToolSpecFingerprint {
    param($Dependency)
    $spec = [ordered]@{
        id = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "id")
        version = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "version")
        install_method = ([string](Get-KnowledgePackObjectValue -Object $Dependency -Key "install_method")).ToLowerInvariant()
        path = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "path")
        package = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "package")
        url = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "url")
        sha256 = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "sha256")
        command = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "command")
        resolved_command = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "resolved_command")
        verify_command = [string](Get-KnowledgePackObjectValue -Object $Dependency -Key "verify_command")
    }
    $json = $spec | ConvertTo-Json -Depth 8 -Compress
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
        return [ordered]@{
            spec = $spec
            hash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
        }
    } finally {
        $sha.Dispose()
    }
}

function Get-HookToolBool {
    param($Value, [bool]$Default = $true)
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [string]) {
        $lower = $Value.Trim().ToLowerInvariant()
        if ($lower -in @("true", "1", "yes")) { return $true }
        if ($lower -in @("false", "0", "no")) { return $false }
    }
    return $Default
}

function Get-HookToolCommandForPath {
    param([string]$Path)
    $normalized = $Path.Replace('\', '/')
    $quoted = '"' + $normalized.Replace('"', '\"') + '"'
    switch ([System.IO.Path]::GetExtension($normalized).ToLowerInvariant()) {
        ".ps1" { return "pwsh -NoProfile -File $quoted" }
        ".sh" { return "bash $quoted" }
        ".cmd" { return "cmd /c $quoted" }
        ".bat" { return "cmd /c $quoted" }
        default { return $quoted }
    }
}

function Invoke-HookToolCommand {
    param([string]$Command, [string]$WorkingDirectory, [int]$TimeoutSeconds = 600)
    if ([string]::IsNullOrWhiteSpace($Command)) {
        return [PSCustomObject][ordered]@{ exit_code = 0; stdout = ""; stderr = ""; timed_out = $false }
    }
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "pwsh"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.WorkingDirectory = $WorkingDirectory
    [void]$psi.ArgumentList.Add("-NoProfile")
    [void]$psi.ArgumentList.Add("-ExecutionPolicy")
    [void]$psi.ArgumentList.Add("Bypass")
    [void]$psi.ArgumentList.Add("-Command")
    [void]$psi.ArgumentList.Add("& { $Command; if (`$null -ne `$global:LASTEXITCODE) { exit `$global:LASTEXITCODE } }")
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $finished = $process.WaitForExit([Math]::Max(1, $TimeoutSeconds) * 1000)
    if (-not $finished) {
        try { $process.Kill($true) } catch { }
        return [PSCustomObject][ordered]@{
            exit_code = -1
            stdout = $stdoutTask.GetAwaiter().GetResult()
            stderr = $stderrTask.GetAwaiter().GetResult()
            timed_out = $true
        }
    }
    return [PSCustomObject][ordered]@{
        exit_code = $process.ExitCode
        stdout = $stdoutTask.GetAwaiter().GetResult()
        stderr = $stderrTask.GetAwaiter().GetResult()
        timed_out = $false
    }
}

function Add-HookToolProblem {
    param($Result, [bool]$Required, [string]$Message)
    if ($Required) {
        Set-KnowledgePackBlocked $Result $Message
    } else {
        if ($Result.status -eq "ok") { $Result.status = "warning" }
        $Result.hints += $Message
    }
}

try {
    $root = Resolve-KnowledgePackPath -Path $RepoRoot
    if ([string]::IsNullOrWhiteSpace($root)) { $root = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        Set-KnowledgePackBlocked $result "RepoRoot not found: $root"
    }

    $packRootResolved = Resolve-KnowledgePackPath -Path $PackRoot
    if ([string]::IsNullOrWhiteSpace($packRootResolved)) {
        Set-KnowledgePackBlocked $result "PackRoot is required"
    } elseif (-not (Test-Path -LiteralPath $packRootResolved -PathType Container)) {
        Set-KnowledgePackBlocked $result "PackRoot not found: $packRootResolved"
    }

    if ($result.status -ne "blocked") {
        $info = Get-KnowledgePackInfo -PackRoot $packRootResolved
        $packSlug = if ([string]::IsNullOrWhiteSpace($PackId)) { ConvertTo-KnowledgePackSlug -Value $info.id } else { ConvertTo-KnowledgePackSlug -Value $PackId }
        $toolsRoot = Join-Path $root ".specify\tools"
        $recordsRoot = Join-Path $toolsRoot "records"

        $dependencies = @()
        foreach ($hook in @(Read-KnowledgePackHookIndex -PackRoot $packRootResolved)) {
            foreach ($dependency in @((Get-KnowledgePackObjectValue -Object $hook -Key "tool_dependencies"))) {
                if ($dependency -is [string]) { continue }
                $depId = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "id")
                $depVersion = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "version")
                $depMethod = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "install_method")
                if ([string]::IsNullOrWhiteSpace($depId) -or [string]::IsNullOrWhiteSpace($depVersion) -or [string]::IsNullOrWhiteSpace($depMethod)) {
                    continue
                }
                $key = "$(ConvertTo-HookToolSlug $depId)@$depVersion@$depMethod"
                if ($dependencies | Where-Object { $_.key -eq $key }) { continue }
                $dependencies += [PSCustomObject]@{
                    key = $key
                    spec = $dependency
                }
            }
        }

        $installed = @()
        if ($dependencies.Count -gt 0) {
            New-Item -ItemType Directory -Force -Path $recordsRoot | Out-Null
        }
        foreach ($entry in $dependencies) {
            $dependency = $entry.spec
            $depId = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "id")
            $depVersion = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "version")
            $depMethod = ([string](Get-KnowledgePackObjectValue -Object $dependency -Key "install_method")).ToLowerInvariant()
            $required = Get-HookToolBool -Value (Get-KnowledgePackObjectValue -Object $dependency -Key "required") -Default $true
            $depSlug = ConvertTo-HookToolSlug $depId
            $toolDir = Join-Path $toolsRoot "$depSlug\$depVersion"
            $resolvedCommand = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "resolved_command")
            $verifyCommand = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "verify_command")
            $status = "installed"
            $hashes = [ordered]@{}
            $fingerprint = Get-HookToolSpecFingerprint -Dependency $dependency
            $specHash = [string]$fingerprint.hash
            $spec = $fingerprint.spec
            $skipRecord = $false
            $toolBackupDir = ""
            $hadExistingTool = Test-Path -LiteralPath $toolDir

            try {
                $recordPath = Join-Path $recordsRoot "$depSlug-$depVersion.json"
                if (Test-Path -LiteralPath $recordPath -PathType Leaf) {
                    try {
                        $existingRecord = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
                        $existingHash = if ($existingRecord.PSObject.Properties.Name -contains "spec_hash") { [string]$existingRecord.spec_hash } else { "" }
                        $existingMethod = if ($existingRecord.PSObject.Properties.Name -contains "install_method") { [string]$existingRecord.install_method } else { "" }
                        if ((-not [string]::IsNullOrWhiteSpace($existingHash) -and $existingHash -ne $specHash) -or
                            ([string]::IsNullOrWhiteSpace($existingHash) -and -not [string]::IsNullOrWhiteSpace($existingMethod) -and $existingMethod -ne $depMethod)) {
                            throw "hook tool $depId version $depVersion conflicts with an existing install record; use a different version or identical install metadata"
                        }
                    } catch {
                        $skipRecord = $true
                        Add-HookToolProblem -Result $result -Required $true -Message $_.Exception.Message
                        continue
                    }
                }

                if ($hadExistingTool -and $Force) {
                    $toolBackupDir = Join-Path $toolsRoot (".backups\$depSlug\$depVersion-" + [guid]::NewGuid().ToString("N"))
                    Copy-KnowledgePackDirectory -Source $toolDir -Destination $toolBackupDir
                    Remove-KnowledgePackDirectorySafe -Root $toolsRoot -Path $toolDir
                }
                New-Item -ItemType Directory -Force -Path $toolDir | Out-Null

                switch ($depMethod) {
                    "pack-local-script" {
                        $sourceRelative = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "path")
                        if (-not (Test-KnowledgePackSafeRelativePath -RelativePath $sourceRelative)) {
                            throw "unsafe pack-local-script path: $sourceRelative"
                        }
                        $sourcePath = Join-Path (Join-Path $packRootResolved "hooks") ($sourceRelative -replace "/", "\")
                        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                            throw "pack-local-script source not found: $sourceRelative"
                        }
                        $destPath = Join-Path $toolDir (Split-Path -Leaf $sourcePath)
                        Copy-Item -LiteralPath $sourcePath -Destination $destPath -Force
                        $resolvedCommand = Get-HookToolCommandForPath ([System.IO.Path]::GetRelativePath($root, $destPath).Replace('\', '/'))
                        $hashes.source_sha256 = Get-KnowledgePackFileHash -Path $sourcePath
                        $hashes.installed_sha256 = Get-KnowledgePackFileHash -Path $destPath
                    }
                    "npm" {
                        $packageName = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "package")
                        if ([string]::IsNullOrWhiteSpace($packageName)) { $packageName = $depId }
                        $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
                        if ($null -eq $npmCommand) { throw "npm not found for hook tool $depId" }
                        $npmResult = & npm --prefix $toolDir install "$packageName@$depVersion" 2>&1
                        if ($LASTEXITCODE -ne 0) { throw "npm install failed for ${packageName}@${depVersion}: $npmResult" }
                        if ([string]::IsNullOrWhiteSpace($resolvedCommand)) {
                            $resolvedCommand = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "command")
                        }
                    }
                    "github-release" {
                        $url = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "url")
                        if ([string]::IsNullOrWhiteSpace($url)) { throw "github-release install requires url for $depId" }
                        $assetName = Split-Path -Leaf ([Uri]$url).AbsolutePath
                        if ([string]::IsNullOrWhiteSpace($assetName)) { $assetName = "$depSlug-$depVersion" }
                        $assetPath = Join-Path $toolDir $assetName
                        Invoke-WebRequest -Uri $url -OutFile $assetPath
                        $hashes.asset_sha256 = Get-KnowledgePackFileHash -Path $assetPath
                        $expectedHash = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "sha256")
                        if (-not [string]::IsNullOrWhiteSpace($expectedHash) -and $hashes.asset_sha256 -ne $expectedHash.ToLowerInvariant()) {
                            throw "github-release asset hash mismatch for $depId"
                        }
                        if ([string]::IsNullOrWhiteSpace($resolvedCommand)) {
                            $resolvedCommand = Get-HookToolCommandForPath ([System.IO.Path]::GetRelativePath($root, $assetPath).Replace('\', '/'))
                        }
                    }
                    "manual" {
                        if ([string]::IsNullOrWhiteSpace($verifyCommand)) {
                            throw "manual hook tool $depId requires verify_command"
                        }
                        if ([string]::IsNullOrWhiteSpace($resolvedCommand)) {
                            $resolvedCommand = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "command")
                        }
                    }
                    default {
                        throw "unsupported hook tool install_method: $depMethod"
                    }
                }

                if (-not [string]::IsNullOrWhiteSpace($verifyCommand)) {
                    $verifyTimeoutSeconds = 600
                    $verifyTimeoutRaw = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "verify_timeout_seconds")
                    if ([string]::IsNullOrWhiteSpace($verifyTimeoutRaw)) {
                        $verifyTimeoutRaw = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "timeout_seconds")
                    }
                    if (-not [string]::IsNullOrWhiteSpace($verifyTimeoutRaw)) {
                        try { $verifyTimeoutSeconds = [Math]::Max(1, [int]$verifyTimeoutRaw) } catch { $verifyTimeoutSeconds = 600 }
                    }
                    $verify = Invoke-HookToolCommand -Command $verifyCommand -WorkingDirectory $root -TimeoutSeconds $verifyTimeoutSeconds
                    if ($verify.timed_out) {
                        throw "verify_command timed out for $depId after $verifyTimeoutSeconds seconds"
                    }
                    if ($verify.exit_code -ne 0) {
                        throw "verify_command failed for $depId with exit code $($verify.exit_code)"
                    }
                }
            } catch {
                $status = if ($required) { "blocked" } else { "warning" }
                if ($required) {
                    $skipRecord = $true
                    if (Test-Path -LiteralPath $toolDir) {
                        Remove-KnowledgePackDirectorySafe -Root $toolsRoot -Path $toolDir
                    }
                    if (-not [string]::IsNullOrWhiteSpace($toolBackupDir) -and (Test-Path -LiteralPath $toolBackupDir -PathType Container)) {
                        Copy-KnowledgePackDirectory -Source $toolBackupDir -Destination $toolDir
                    }
                }
                Add-HookToolProblem -Result $result -Required $required -Message $_.Exception.Message
            } finally {
                if (-not [string]::IsNullOrWhiteSpace($toolBackupDir) -and (Test-Path -LiteralPath $toolBackupDir -PathType Container)) {
                    Remove-KnowledgePackDirectorySafe -Root $toolsRoot -Path $toolBackupDir
                }
            }

            if ($skipRecord) {
                continue
            }

            $relativeToolDir = try { [System.IO.Path]::GetRelativePath($root, $toolDir).Replace('\', '/') } catch { $toolDir }
            $record = [ordered]@{
                schema_version = "1.0"
                generated_by = "install-hook-tools"
                installed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
                pack_id = $packSlug
                id = $depId
                slug = $depSlug
                version = $depVersion
                install_method = $depMethod
                required = $required
                status = $status
                install_dir = $relativeToolDir
                resolved_command = $resolvedCommand
                verify_command = $verifyCommand
                spec_hash = $specHash
                dependency_spec = $spec
                hashes = $hashes
            }
            $recordPath = Join-Path $recordsRoot "$depSlug-$depVersion.json"
            $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $recordPath -Encoding utf8
            $relativeRecordPath = try { [System.IO.Path]::GetRelativePath($root, $recordPath).Replace('\', '/') } catch { $recordPath }
            $record.record_path = $relativeRecordPath
            $installed += $record
        }

        $lock = Write-KnowledgeHookToolsLock -RepoRoot $root

        $result.facts.repo_root = $root
        $result.facts.pack_id = $packSlug
        $result.facts.pack_root = $packRootResolved
        $result.facts.tool_count = $installed.Count
        $result.facts.tools = $installed
        $result.facts.lock = $lock.path
        $result.facts.total_locked_tool_count = $lock.tool_count
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
