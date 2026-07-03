param(
    [string]$RepoRoot = "",
    [string]$WorkflowId = "",
    [string]$StageId = "",
    [ValidateSet("before", "after")]
    [string]$Phase = "after",
    [string]$RunId = "",
    [string]$ContextPath = "",
    [string]$ContextJson = "{}",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function New-WorkflowHookResult {
    [ordered]@{
        tool = "invoke-workflow-hooks"
        status = "ok"
        facts = [ordered]@{}
        blockers = @()
        unknowns = @()
        hints = @()
    }
}

function Set-WorkflowHookBlocked {
    param($Result, [string]$Message)
    $Result.status = "blocked"
    $Result.blockers += $Message
}

function Set-WorkflowHookWarning {
    param($Result, [string]$Message)
    if ($Result.status -eq "ok") {
        $Result.status = "warning"
    }
    $Result.hints += $Message
}

function Write-WorkflowHookJson {
    param($Result)
    $Result | ConvertTo-Json -Depth 18 -Compress
}

function Resolve-WorkflowHookRoot {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return (Get-Location).Path
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function ConvertTo-WorkflowHookSlug {
    param([string]$Value)
    $slug = ($Value.ToLowerInvariant() -replace "[^a-z0-9_.-]+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($slug)) { return "hook" }
    return $slug
}

function Get-YamlScalar {
    param([string]$Value)
    $clean = $Value.Trim()
    if ($clean -eq "[]") { return "" }
    if (
        ($clean.StartsWith('"') -and $clean.EndsWith('"')) -or
        ($clean.StartsWith("'") -and $clean.EndsWith("'"))
    ) {
        $inner = $clean.Substring(1, $clean.Length - 2)
        if ($clean.StartsWith('"')) {
            $inner = $inner.Replace('\"', '"').Replace('\\', '\')
        } else {
            $inner = $inner.Replace("''", "'")
        }
        return $inner
    }
    return $clean
}

function Get-YamlInlineList {
    param([string]$Value)
    $clean = $Value.Trim()
    if (-not ($clean.StartsWith("[") -and $clean.EndsWith("]"))) {
        return @()
    }
    $inner = $clean.Substring(1, $clean.Length - 2).Trim()
    if ([string]::IsNullOrWhiteSpace($inner)) {
        return @()
    }
    $items = @()
    foreach ($piece in ($inner -split ",")) {
        $item = Get-YamlScalar $piece
        if (-not [string]::IsNullOrWhiteSpace($item)) {
            $items += $item
        }
    }
    return $items
}

function Add-HookEntry {
    param([System.Collections.ArrayList]$Hooks, $Current)
    if ($null -ne $Current -and -not [string]::IsNullOrWhiteSpace($Current.id)) {
        [void]$Hooks.Add([PSCustomObject]$Current)
    }
}

function Read-WorkflowHookRegistry {
    param([string]$Path)
    $hooks = [System.Collections.ArrayList]::new()
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    $inHooks = $false
    $current = $null
    $activeListKey = ""
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        if (-not $inHooks) {
            if ($line -match "^\s*hooks:\s*$") {
                $inHooks = $true
            }
            continue
        }

        if ($line -match "^\s{2}-\s+id:\s*(.+?)\s*$") {
            Add-HookEntry -Hooks $hooks -Current $current
            $current = [ordered]@{
                id = Get-YamlScalar $Matches[1]
                events = @()
                tool_dependencies = @()
            }
            $activeListKey = ""
            continue
        }
        if ($null -eq $current) {
            continue
        }

        if ($line -match "^\s{4}([A-Za-z0-9_-]+):\s*(.*?)\s*$") {
            $key = $Matches[1].Trim()
            $value = $Matches[2]
            if ($key -in @("events", "tool_dependencies", "tools")) {
                $list = Get-YamlInlineList $value
                if ($list.Count -gt 0) {
                    $current[$key] = @($list)
                    $activeListKey = ""
                } else {
                    $current[$key] = @()
                    $activeListKey = $key
                }
            } else {
                $current[$key] = Get-YamlScalar $value
                $activeListKey = ""
            }
            continue
        }
        if ($activeListKey -and $line -match "^\s{6}-\s+(.+?)\s*$") {
            $current[$activeListKey] = @($current[$activeListKey]) + @((Get-YamlScalar $Matches[1]))
        }
    }
    Add-HookEntry -Hooks $hooks -Current $current
    return @($hooks)
}

function Read-WorkflowHookOverrides {
    param([string]$Path)
    $overrides = [ordered]@{
        enabled = $true
        disabled_events = @()
        disabled_hooks = @()
        disabled_packs = @()
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [PSCustomObject]$overrides
    }

    $activeListKey = ""
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($line -match "^\s{0,2}([A-Za-z0-9_-]+):\s*(.*?)\s*$") {
            $key = $Matches[1].Trim()
            $value = $Matches[2]
            if ($key -eq "enabled") {
                $overrides.enabled = ConvertTo-HookBool -Value (Get-YamlScalar $value) -Default $true
                $activeListKey = ""
                continue
            }
            if ($key -in @("disabled_events", "disabled_hooks", "disabled_packs")) {
                $list = Get-YamlInlineList $value
                if ($list.Count -gt 0) {
                    $overrides[$key] = @($list)
                    $activeListKey = ""
                } else {
                    $overrides[$key] = @()
                    $activeListKey = $key
                }
                continue
            }
            $activeListKey = ""
            continue
        }
        if ($activeListKey -and $line -match "^\s{2,4}-\s+(.+?)\s*$") {
            $overrides[$activeListKey] = @($overrides[$activeListKey]) + @((Get-YamlScalar $Matches[1]))
        }
    }
    return [PSCustomObject]$overrides
}

function Test-WorkflowHookDisabled {
    param(
        $Hook,
        [string]$Event,
        $Overrides
    )
    if ($null -eq $Overrides) { return "" }
    if (-not [bool]$Overrides.enabled) {
        return "workflow hooks disabled by .specify/workflow-hooks.local.yml"
    }
    $disabledEvents = ConvertTo-StringList $Overrides.disabled_events
    if ($disabledEvents -contains $Event) {
        return "event disabled by .specify/workflow-hooks.local.yml"
    }
    $hookId = [string](Get-ObjectValue -Object $Hook -Key "id")
    $packId = [string](Get-ObjectValue -Object $Hook -Key "pack_id")
    $disabledHooks = ConvertTo-StringList $Overrides.disabled_hooks
    if (-not [string]::IsNullOrWhiteSpace($hookId) -and $disabledHooks -contains $hookId) {
        return "hook disabled by .specify/workflow-hooks.local.yml"
    }
    $disabledPacks = ConvertTo-StringList $Overrides.disabled_packs
    if (-not [string]::IsNullOrWhiteSpace($packId) -and $disabledPacks -contains $packId) {
        return "pack disabled by .specify/workflow-hooks.local.yml"
    }
    return ""
}

function Get-ObjectValue {
    param($Object, [string]$Key)
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Key)) { return $Object[$Key] }
        return $null
    }
    if ($Object -is [System.Collections.DictionaryEntry]) {
        if ([string]$Object.Key -eq $Key) { return $Object.Value }
        return $null
    }
    if ($Object -is [System.Array]) {
        foreach ($entry in $Object) {
            if ($entry -is [System.Collections.DictionaryEntry] -and [string]$entry.Key -eq $Key) {
                return $entry.Value
            }
        }
    }
    if ($Object.PSObject.Properties.Name -contains $Key) {
        return $Object.$Key
    }
    return $null
}

function ConvertTo-StringList {
    param($Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($Value)) { return @() }
        return @($Value)
    }
    if ($Value -is [System.Array]) {
        return @($Value | ForEach-Object { [string]$_ })
    }
    return @([string]$Value)
}

function ConvertTo-HookBool {
    param($Value, [bool]$Default = $false)
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [string]) {
        $lower = $Value.Trim().ToLowerInvariant()
        if ($lower -in @("true", "1", "yes")) { return $true }
        if ($lower -in @("false", "0", "no")) { return $false }
    }
    return $Default
}

function Read-JsonObjectFromText {
    param([string]$Text)
    $stripped = $Text.Trim()
    if ([string]::IsNullOrWhiteSpace($stripped)) { return $null }
    $candidates = @($stripped)
    $candidates += @($stripped -split "\r?\n" | ForEach-Object { $_.Trim() } | Where-Object { $_.StartsWith("{") -and $_.EndsWith("}") })
    $first = $stripped.IndexOf("{")
    $last = $stripped.LastIndexOf("}")
    if ($first -ge 0 -and $last -gt $first) {
        $candidates += $stripped.Substring($first, $last - $first + 1)
    }
    foreach ($candidate in $candidates) {
        try {
            $parsed = $candidate | ConvertFrom-Json -NoEnumerate
            [PSCustomObject]@{ __spec_kit_json = $parsed }
            return
        } catch {
            continue
        }
    }
    return $null
}

function Read-JsonObjectFromFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        $parsed = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -NoEnumerate
        [PSCustomObject]@{ __spec_kit_json = $parsed }
        return
    } catch {
        $failure = [ordered]@{
            status = "failed"
            action = "fail"
            auto_continue = $false
            summary = "Invalid hook result JSON: $($_.Exception.Message)"
            artifact_paths = @()
        }
        [PSCustomObject]@{ __spec_kit_json = [PSCustomObject]$failure }
        return
    }
}

function Unwrap-JsonObject {
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value.PSObject.Properties.Name -contains "__spec_kit_json") {
        return $Value.__spec_kit_json
    }
    return $Value
}

function Invoke-HookCommand {
    param(
        [string]$Command,
        [hashtable]$Environment,
        [int]$TimeoutSeconds,
        [string]$WorkingDirectory = ""
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "pwsh"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $psi.WorkingDirectory = $WorkingDirectory
    }
    [void]$psi.ArgumentList.Add("-NoProfile")
    [void]$psi.ArgumentList.Add("-ExecutionPolicy")
    [void]$psi.ArgumentList.Add("Bypass")
    [void]$psi.ArgumentList.Add("-Command")
    [void]$psi.ArgumentList.Add("& { $Command; if (`$null -ne `$global:LASTEXITCODE) { exit `$global:LASTEXITCODE } }")
    foreach ($key in $Environment.Keys) {
        $psi.Environment[$key] = [string]$Environment[$key]
    }

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
            timed_out = $true
            stdout = $stdoutTask.GetAwaiter().GetResult()
            stderr = $stderrTask.GetAwaiter().GetResult()
        }
    }
    return [PSCustomObject][ordered]@{
        exit_code = $process.ExitCode
        timed_out = $false
        stdout = $stdoutTask.GetAwaiter().GetResult()
        stderr = $stderrTask.GetAwaiter().GetResult()
    }
}

function Get-NormalizedHookStatus {
    param([string]$Status)
    $raw = $Status.Trim().ToLowerInvariant()
    $map = @{
        ok = "passed"
        success = "passed"
        succeeded = "passed"
        completed = "passed"
        complete = "passed"
        pass = "passed"
        passed = "passed"
        warn = "warning"
        warning = "warning"
        warnings = "warning"
        skip = "skipped"
        skipped = "skipped"
        blocked = "blocked"
        block = "blocked"
        failed = "failed"
        failure = "failed"
        error = "failed"
        requires_rework = "requires_rework"
        rework = "requires_rework"
    }
    if ($map.ContainsKey($raw)) { return $map[$raw] }
    return "failed"
}

function Get-DefaultHookAction {
    param([string]$Status)
    if ($Status -eq "requires_rework") { return "rework" }
    if ($Status -eq "failed") { return "fail" }
    if ($Status -eq "blocked") { return "pause" }
    return "continue"
}

function Normalize-HookCommandResult {
    param(
        $Hook,
        [string]$Event,
        [string]$ResultPath,
        $CommandResult,
        $RawResult
    )
    $exitCode = [int]$CommandResult.exit_code
    $statusValue = Get-ObjectValue -Object $RawResult -Key "status"
    if ([string]::IsNullOrWhiteSpace([string]$statusValue)) {
        $status = if ($exitCode -eq 0) { "passed" } else { "failed" }
    } else {
        $status = Get-NormalizedHookStatus ([string]$statusValue)
    }
    if ($CommandResult.timed_out) {
        $status = "failed"
    }

    $failurePolicy = ([string](Get-ObjectValue -Object $Hook -Key "failure_policy")).Trim().ToLowerInvariant()
    $isAdvisory = $failurePolicy -in @("warn", "warning", "advisory")
    $summary = [string](Get-ObjectValue -Object $RawResult -Key "summary")
    if ([string]::IsNullOrWhiteSpace($summary)) {
        if ($CommandResult.timed_out) {
            $summary = "hook timed out"
        } elseif ($exitCode -eq 0) {
            $summary = "hook passed"
        } else {
            $summary = "hook failed with exit code $exitCode"
        }
    }
    if ($isAdvisory -and $status -in @("failed", "blocked")) {
        $status = "warning"
        $summary = "advisory hook warning: $summary"
    }

    $action = [string](Get-ObjectValue -Object $RawResult -Key "action")
    if ([string]::IsNullOrWhiteSpace($action)) {
        $action = Get-DefaultHookAction $status
    }
    $autoContinue = ConvertTo-HookBool -Value (Get-ObjectValue -Object $RawResult -Key "auto_continue") -Default:($status -in @("passed", "warning", "skipped") -and $action -eq "continue")
    if ($status -in @("blocked", "failed", "requires_rework")) {
        $autoContinue = $false
    }

    $artifacts = ConvertTo-StringList (Get-ObjectValue -Object $RawResult -Key "artifact_paths")
    $hookId = [string](Get-ObjectValue -Object $Hook -Key "id")
    $packId = [string](Get-ObjectValue -Object $Hook -Key "pack_id")
    $command = [string](Get-ObjectValue -Object $Hook -Key "resolved_command")
    if ([string]::IsNullOrWhiteSpace($command)) {
        $command = [string](Get-ObjectValue -Object $Hook -Key "command")
    }
    if ([string]::IsNullOrWhiteSpace($command)) {
        $command = [string](Get-ObjectValue -Object $Hook -Key "runner")
    }

    return [ordered]@{
        schema_version = "1.0"
        id = $hookId
        pack_id = $packId
        event = $Event
        status = $status
        action = $action
        auto_continue = $autoContinue
        summary = $summary
        artifact_paths = @($artifacts)
        result_path = $ResultPath
        exit_code = $exitCode
        timed_out = [bool]$CommandResult.timed_out
        command = $command
    }
}

function Get-AggregateStatus {
    param([object[]]$Results)
    $statuses = @($Results | ForEach-Object { [string]$_.status })
    if ($statuses.Count -eq 0) { return "skipped" }
    if ($statuses -contains "requires_rework") { return "requires_rework" }
    if ($statuses -contains "blocked") { return "blocked" }
    if ($statuses -contains "failed") { return "failed" }
    if ($statuses -contains "warning") { return "warning" }
    if (($statuses | Where-Object { $_ -ne "skipped" }).Count -eq 0) { return "skipped" }
    return "passed"
}

$result = New-WorkflowHookResult

try {
    $root = Resolve-WorkflowHookRoot -Path $RepoRoot
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        Set-WorkflowHookBlocked $result "RepoRoot not found: $root"
    }
    if ([string]::IsNullOrWhiteSpace($WorkflowId)) {
        Set-WorkflowHookBlocked $result "WorkflowId is required"
    }
    if ([string]::IsNullOrWhiteSpace($StageId)) {
        Set-WorkflowHookBlocked $result "StageId is required"
    }
    if ([string]::IsNullOrWhiteSpace($RunId)) {
        $RunId = "manual"
    }

    $event = "workflow.$WorkflowId.$StageId.$Phase"
    $registryPath = Join-Path $root ".specify\workflow-hooks.yml"
    $overridesPath = Join-Path $root ".specify\workflow-hooks.local.yml"
    $contextPathResolved = ""
    if (-not [string]::IsNullOrWhiteSpace($ContextPath)) {
        $contextPathResolved = if ([System.IO.Path]::IsPathRooted($ContextPath)) {
            [System.IO.Path]::GetFullPath($ContextPath)
        } else {
            [System.IO.Path]::GetFullPath((Join-Path $root $ContextPath))
        }
    }
    $overrides = Read-WorkflowHookOverrides -Path $overridesPath
    $hookResults = @()
    $ignoredHooks = @()
    $disabledHooks = @()

    if ($result.status -ne "blocked") {
        $allHooks = @(Read-WorkflowHookRegistry -Path $registryPath)
        foreach ($hook in $allHooks) {
            $events = ConvertTo-StringList (Get-ObjectValue -Object $hook -Key "events")
            if ($events -notcontains $event) { continue }
            $disabledReason = Test-WorkflowHookDisabled -Hook $hook -Event $event -Overrides $overrides
            if (-not [string]::IsNullOrWhiteSpace($disabledReason)) {
                $disabledHooks += [ordered]@{
                    id = Get-ObjectValue -Object $hook -Key "id"
                    pack_id = Get-ObjectValue -Object $hook -Key "pack_id"
                    reason = $disabledReason
                }
                continue
            }
            $type = ([string](Get-ObjectValue -Object $hook -Key "type")).Trim()
            if ($type -ne "workflow-shell") {
                $ignoredHooks += [ordered]@{
                    id = Get-ObjectValue -Object $hook -Key "id"
                    type = $type
                    reason = "only type workflow-shell participates in blocking workflow hooks"
                }
                continue
            }

            $command = ""
            $commandWindows = [string](Get-ObjectValue -Object $hook -Key "command_windows")
            if ($IsWindows -and -not [string]::IsNullOrWhiteSpace($commandWindows)) {
                $command = $commandWindows
            }
            if ([string]::IsNullOrWhiteSpace($command)) {
                $command = [string](Get-ObjectValue -Object $hook -Key "runner")
            }
            if ([string]::IsNullOrWhiteSpace($command)) {
                $command = [string](Get-ObjectValue -Object $hook -Key "command")
            }

            $hookId = [string](Get-ObjectValue -Object $hook -Key "id")
            $eventSlug = ConvertTo-WorkflowHookSlug $event
            $hookSlug = ConvertTo-WorkflowHookSlug $hookId
            $resultDir = Join-Path $root ".specify\workflows\runs\$RunId\hooks\$eventSlug"
            New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
            $resultPath = Join-Path $resultDir "$hookSlug.json"
            if (Test-Path -LiteralPath $resultPath -PathType Leaf) {
                Remove-Item -LiteralPath $resultPath -Force
            }

            $timeoutSeconds = 600
            $timeoutRaw = [string](Get-ObjectValue -Object $hook -Key "timeout_seconds")
            if (-not [string]::IsNullOrWhiteSpace($timeoutRaw)) {
                try { $timeoutSeconds = [Math]::Max(1, [int]$timeoutRaw) } catch { $timeoutSeconds = 600 }
            }

            if ([string]::IsNullOrWhiteSpace($command)) {
                $hookResults += Normalize-HookCommandResult -Hook $hook -Event $event -ResultPath $resultPath -CommandResult ([ordered]@{
                    exit_code = 1
                    timed_out = $false
                    stdout = ""
                    stderr = ""
                }) -RawResult ([ordered]@{
                    status = "failed"
                    action = "fail"
                    auto_continue = $false
                    summary = "workflow hook has no command or runner"
                    artifact_paths = @()
                })
                continue
            }

            if ($hook -is [System.Collections.IDictionary]) {
                $hook["resolved_command"] = $command
            } else {
                $hook | Add-Member -NotePropertyName "resolved_command" -NotePropertyValue $command -Force
            }
            $envMap = @{
                SPEC_KIT_HOOK_EVENT = $event
                SPEC_KIT_WORKFLOW_ID = $WorkflowId
                SPEC_KIT_STAGE_ID = $StageId
                SPEC_KIT_PHASE = $Phase
                SPEC_KIT_RUN_ID = $RunId
                SPEC_KIT_RESULT_PATH = $resultPath
                SPEC_KIT_CONTEXT_PATH = $contextPathResolved
                SPEC_KIT_CONTEXT_JSON = $ContextJson
            }
            $commandResult = Invoke-HookCommand -Command $command -Environment $envMap -TimeoutSeconds $timeoutSeconds -WorkingDirectory $root
            $rawResult = Unwrap-JsonObject (Read-JsonObjectFromFile -Path $resultPath)
            if ($null -eq $rawResult) {
                $rawResult = Unwrap-JsonObject (Read-JsonObjectFromText -Text ([string]$commandResult.stdout))
            }
            $hookResults += Normalize-HookCommandResult -Hook $hook -Event $event -ResultPath $resultPath -CommandResult $commandResult -RawResult $rawResult
        }

        $aggregateStatus = Get-AggregateStatus $hookResults
        $autoContinue = $aggregateStatus -in @("passed", "warning", "skipped")
        $action = Get-DefaultHookAction $aggregateStatus
        $summaryItems = @($hookResults | ForEach-Object { [string]$_.summary } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        $summary = if ($summaryItems.Count -gt 0) { ($summaryItems -join "; ") } else { "no matching workflow hooks" }
        $artifactPaths = @()
        foreach ($item in $hookResults) {
            $artifactPaths += @($item.artifact_paths)
            if (-not [string]::IsNullOrWhiteSpace($item.result_path)) {
                $artifactPaths += $item.result_path
            }
        }

        $result.facts.event = $event
        $result.facts.workflow_id = $WorkflowId
        $result.facts.stage_id = $StageId
        $result.facts.phase = $Phase
        $result.facts.run_id = $RunId
        $result.facts.registry = $registryPath
        $result.facts.local_overrides = $overridesPath
        $result.facts.context_path = $contextPathResolved
        $result.facts.hook_count = @($hookResults).Count
        $result.facts.ignored_hook_count = @($ignoredHooks).Count
        $result.facts.ignored_hooks = $ignoredHooks
        $result.facts.disabled_hook_count = @($disabledHooks).Count
        $result.facts.disabled_hooks = $disabledHooks
        $result.facts.aggregate_status = $aggregateStatus
        $result.facts.status = $aggregateStatus
        $result.facts.action = $action
        $result.facts.auto_continue = $autoContinue
        $result.facts.summary = $summary
        $result.facts.artifact_paths = @($artifactPaths | Select-Object -Unique)
        $result.facts.results = $hookResults

        if ($aggregateStatus -eq "warning") {
            Set-WorkflowHookWarning $result $summary
        } elseif ($aggregateStatus -in @("blocked", "failed", "requires_rework")) {
            Set-WorkflowHookBlocked $result $summary
        }
    }
} catch {
    Set-WorkflowHookBlocked $result $_.Exception.Message
}

if ($Json) { Write-WorkflowHookJson $result } else { $result }
