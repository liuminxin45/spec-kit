param(
    [string]$PackId = "",
    [string]$HookId = "",
    [string]$Event = "",
    [ValidateSet("open-code-review", "generic")]
    [string]$Adapter = "generic",
    [string]$ToolId = "",
    [string]$ToolVersion = "",
    [ValidateSet("pack-local-script", "npm", "github-release", "manual")]
    [string]$InstallMethod = "manual",
    [string]$Package = "",
    [string]$Url = "",
    [string]$Sha256 = "",
    [string]$Command = "",
    [string]$VerifyCommand = "",
    [int]$VerifyTimeoutSeconds = 60,
    [int]$TimeoutSeconds = 1800,
    [ValidateSet("block", "warn", "warning", "advisory")]
    [string]$FailurePolicy = "block",
    [string]$OutputDir = "",
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "new-workflow-hook-pack"

function Format-HookPackYamlValue {
    param([string]$Value)
    return '"' + (($Value -replace '\\', '/') -replace '"', '\"') + '"'
}

function New-OpenCodeReviewRunner {
    param(
        [string]$ToolId,
        [string]$ToolVersion,
        [string]$DefaultCommand,
        [int]$TimeoutSeconds
    )
    $toolIdLiteral = $ToolId.Replace("'", "''")
    $toolVersionLiteral = $ToolVersion.Replace("'", "''")
    $defaultCommandLiteral = $DefaultCommand.Replace("'", "''")
    return @"
`$ErrorActionPreference = "Stop"

`$ToolId = '$toolIdLiteral'
`$ToolVersion = '$toolVersionLiteral'
`$DefaultCommand = '$defaultCommandLiteral'
`$TimeoutSeconds = $TimeoutSeconds

function ConvertTo-ToolSlug {
    param([string]`$Value)
    `$slug = (`$Value.ToLowerInvariant() -replace "[^a-z0-9_.-]+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace(`$slug)) { return "hook-tool" }
    return `$slug
}

function New-HookPayload {
    param(
        [string]`$Status,
        [string]`$Action,
        [bool]`$AutoContinue,
        [string]`$Summary,
        [string[]]`$ArtifactPaths = @()
    )
    [ordered]@{
        schema_version = "1.0"
        status = `$Status
        action = `$Action
        auto_continue = `$AutoContinue
        summary = `$Summary
        artifact_paths = @(`$ArtifactPaths)
    }
}

function Write-HookPayload {
    param(`$Payload)
    `$Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath `$env:SPEC_KIT_RESULT_PATH -Encoding utf8
}

function Get-JsonObjectFromText {
    param([string]`$Text)
    if ([string]::IsNullOrWhiteSpace(`$Text)) { return `$null }
    `$start = `$Text.IndexOf("{")
    if (`$start -lt 0) { return `$null }
    try {
        return (`$Text.Substring(`$start) | ConvertFrom-Json)
    } catch {
        return `$null
    }
}

function Get-ArrayProperty {
    param(`$Object, [string[]]`$Names)
    if (`$null -eq `$Object) { return @() }
    foreach (`$name in `$Names) {
        if (`$Object.PSObject.Properties.Name -contains `$name) {
            `$value = `$Object.`$name
            if (`$null -ne `$value) { return @(`$value) }
        }
    }
    return @()
}

function Resolve-OcrCommand {
    param([string]`$RepoRoot)
    `$envCommand = [string]`$env:OPEN_CODE_REVIEW_COMMAND
    if (-not [string]::IsNullOrWhiteSpace(`$envCommand)) { return `$envCommand }

    `$slug = ConvertTo-ToolSlug `$ToolId
    `$recordPath = Join-Path `$RepoRoot ".specify/tools/records/`$slug-`$ToolVersion.json"
    if (Test-Path -LiteralPath `$recordPath -PathType Leaf) {
        try {
            `$record = Get-Content -LiteralPath `$recordPath -Raw | ConvertFrom-Json
            `$installDir = if (`$record.install_dir) { Join-Path `$RepoRoot ([string]`$record.install_dir) } else { "" }
            if (`$record.install_method -eq "npm" -and -not [string]::IsNullOrWhiteSpace(`$installDir)) {
                `$binBase = Join-Path `$installDir "node_modules/.bin/ocr"
                foreach (`$candidate in @("`$binBase.cmd", `$binBase)) {
                    if (Test-Path -LiteralPath `$candidate -PathType Leaf) {
                        return '"' + `$candidate.Replace('"', '\"') + '"'
                    }
                }
            }
            if (`$record.resolved_command) { return [string]`$record.resolved_command }
        } catch {
        }
    }
    return `$DefaultCommand
}

function Invoke-OcrReview {
    param(
        [string]`$Command,
        [string]`$RepoRoot,
        [string]`$ArtifactsDir
    )
    `$stdoutPath = Join-Path `$ArtifactsDir "open-code-review.stdout.json"
    `$stderrPath = Join-Path `$ArtifactsDir "open-code-review.stderr.txt"
    `$argsExpression = [string]`$env:SPEC_KIT_OPEN_CODE_REVIEW_ARGS
    if ([string]::IsNullOrWhiteSpace(`$argsExpression)) {
        `$argsExpression = "review --audience agent --format json"
    }
    `$script = "& { `$Command `$argsExpression; if (`$null -ne `$global:LASTEXITCODE) { exit `$global:LASTEXITCODE } }"

    `$psi = [System.Diagnostics.ProcessStartInfo]::new()
    `$psi.FileName = "pwsh"
    `$psi.UseShellExecute = `$false
    `$psi.RedirectStandardOutput = `$true
    `$psi.RedirectStandardError = `$true
    `$psi.WorkingDirectory = `$RepoRoot
    [void]`$psi.ArgumentList.Add("-NoProfile")
    [void]`$psi.ArgumentList.Add("-ExecutionPolicy")
    [void]`$psi.ArgumentList.Add("Bypass")
    [void]`$psi.ArgumentList.Add("-Command")
    [void]`$psi.ArgumentList.Add(`$script)

    `$process = [System.Diagnostics.Process]::new()
    `$process.StartInfo = `$psi
    [void]`$process.Start()
    `$stdoutTask = `$process.StandardOutput.ReadToEndAsync()
    `$stderrTask = `$process.StandardError.ReadToEndAsync()
    `$finished = `$process.WaitForExit([Math]::Max(1, `$TimeoutSeconds) * 1000)
    if (-not `$finished) {
        try { `$process.Kill(`$true) } catch { }
    }
    `$stdout = `$stdoutTask.GetAwaiter().GetResult()
    `$stderr = `$stderrTask.GetAwaiter().GetResult()
    `$stdout | Set-Content -LiteralPath `$stdoutPath -Encoding utf8
    `$stderr | Set-Content -LiteralPath `$stderrPath -Encoding utf8
    return [PSCustomObject][ordered]@{
        exit_code = if (`$finished) { `$process.ExitCode } else { -1 }
        timed_out = -not `$finished
        stdout = `$stdout
        stderr = `$stderr
        artifacts = @(`$stdoutPath, `$stderrPath)
    }
}

try {
    `$context = `$null
    if (-not [string]::IsNullOrWhiteSpace(`$env:SPEC_KIT_CONTEXT_PATH) -and (Test-Path -LiteralPath `$env:SPEC_KIT_CONTEXT_PATH -PathType Leaf)) {
        `$context = Get-Content -LiteralPath `$env:SPEC_KIT_CONTEXT_PATH -Raw | ConvertFrom-Json
    }
    `$repoRoot = if (`$context -and `$context.project_root) { [string]`$context.project_root } else { (Get-Location).Path }
    `$artifactsDir = if (-not [string]::IsNullOrWhiteSpace(`$env:SPEC_KIT_CONTEXT_PATH)) {
        Split-Path -Parent `$env:SPEC_KIT_CONTEXT_PATH
    } else {
        Join-Path `$repoRoot ".specify/workflows/runs/unknown/hooks/open-code-review"
    }
    New-Item -ItemType Directory -Force -Path `$artifactsDir | Out-Null

    `$ocrCommand = Resolve-OcrCommand -RepoRoot `$repoRoot
    `$review = Invoke-OcrReview -Command `$ocrCommand -RepoRoot `$repoRoot -ArtifactsDir `$artifactsDir
    `$json = Get-JsonObjectFromText -Text `$review.stdout
    `$relativeArtifacts = @(`$review.artifacts | ForEach-Object {
        try { [System.IO.Path]::GetRelativePath(`$repoRoot, `$_).Replace('\', '/') } catch { `$_ }
    })

    if (`$review.timed_out) {
        Write-HookPayload (New-HookPayload -Status "failed" -Action "pause" -AutoContinue `$false -Summary "open-code-review timed out" -ArtifactPaths `$relativeArtifacts)
        exit 0
    }
    if (`$review.exit_code -ne 0) {
        `$summary = if (`$review.stderr) { "open-code-review failed: " + (`$review.stderr.Trim() -replace "\s+", " ") } else { "open-code-review failed with exit code `$(`$review.exit_code)" }
        Write-HookPayload (New-HookPayload -Status "failed" -Action "pause" -AutoContinue `$false -Summary `$summary -ArtifactPaths `$relativeArtifacts)
        exit 0
    }

    if (`$json -and (`$json.PSObject.Properties.Name -contains "status")) {
        `$status = [string]`$json.status
        if (`$status -in @("passed", "warning", "blocked", "failed", "requires_rework", "skipped")) {
            `$auto = `$status -in @("passed", "warning", "skipped")
            `$action = if (`$auto) { "continue" } else { "pause" }
            `$summary = if (`$json.PSObject.Properties.Name -contains "summary" -and `$json.summary) { [string]`$json.summary } else { "open-code-review returned `$status" }
            Write-HookPayload (New-HookPayload -Status `$status -Action `$action -AutoContinue `$auto -Summary `$summary -ArtifactPaths `$relativeArtifacts)
            exit 0
        }
    }

    `$findings = @()
    `$findings += Get-ArrayProperty -Object `$json -Names @("issues", "findings", "comments", "violations", "problems")
    `$blocking = @(`$findings | Where-Object {
        `$severity = ""
        if (`$_.PSObject.Properties.Name -contains "severity") { `$severity = [string]`$_.severity }
        elseif (`$_.PSObject.Properties.Name -contains "level") { `$severity = [string]`$_.level }
        `$severity.ToLowerInvariant() -in @("blocker", "critical", "error", "high")
    })

    if (`$blocking.Count -gt 0) {
        Write-HookPayload (New-HookPayload -Status "requires_rework" -Action "pause" -AutoContinue `$false -Summary "open-code-review found `$(`$blocking.Count) blocking finding(s)" -ArtifactPaths `$relativeArtifacts)
    } elseif (`$findings.Count -gt 0) {
        Write-HookPayload (New-HookPayload -Status "warning" -Action "continue" -AutoContinue `$true -Summary "open-code-review found `$(`$findings.Count) advisory finding(s)" -ArtifactPaths `$relativeArtifacts)
    } else {
        Write-HookPayload (New-HookPayload -Status "passed" -Action "continue" -AutoContinue `$true -Summary "open-code-review passed" -ArtifactPaths `$relativeArtifacts)
    }
} catch {
    Write-HookPayload (New-HookPayload -Status "failed" -Action "pause" -AutoContinue `$false -Summary ("open-code-review hook failed: " + `$_.Exception.Message) -ArtifactPaths @())
}
"@
}

function New-GenericRunner {
    param([string]$Command)
    $commandLiteral = $Command.Replace("'", "''")
    return @"
`$ErrorActionPreference = "Stop"
`$Command = '$commandLiteral'
`$payload = [ordered]@{
    schema_version = "1.0"
    status = "passed"
    action = "continue"
    auto_continue = `$true
    summary = "hook command passed"
    artifact_paths = @()
}
try {
    if (-not [string]::IsNullOrWhiteSpace(`$Command)) {
        & pwsh -NoProfile -ExecutionPolicy Bypass -Command "& { `$Command; if (`$null -ne `$global:LASTEXITCODE) { exit `$global:LASTEXITCODE } }"
        if (`$LASTEXITCODE -ne 0) {
            `$payload.status = "failed"
            `$payload.action = "pause"
            `$payload.auto_continue = `$false
            `$payload.summary = "hook command failed with exit code `$LASTEXITCODE"
        }
    }
} catch {
    `$payload.status = "failed"
    `$payload.action = "pause"
    `$payload.auto_continue = `$false
    `$payload.summary = "hook command failed: " + `$_.Exception.Message
}
`$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath `$env:SPEC_KIT_RESULT_PATH -Encoding utf8
"@
}

try {
    if ([string]::IsNullOrWhiteSpace($PackId)) { Set-KnowledgePackBlocked $result "PackId is required" }
    if ([string]::IsNullOrWhiteSpace($Event)) { Set-KnowledgePackBlocked $result "Event is required" }
    if (-not [string]::IsNullOrWhiteSpace($Event) -and $Event -notmatch "^workflow\.[a-z0-9][a-z0-9-]*\.[A-Za-z0-9_.-]+\.(before|after)$") {
        Set-KnowledgePackBlocked $result "Event must match workflow.<workflow-id>.<stage-id>.<before|after>: $Event"
    }
    if ([string]::IsNullOrWhiteSpace($ToolId)) {
        $ToolId = if ($Adapter -eq "open-code-review") { "open-code-review" } else { $PackId }
    }
    if ([string]::IsNullOrWhiteSpace($ToolVersion)) { Set-KnowledgePackBlocked $result "ToolVersion is required" }
    $packSlug = ConvertTo-KnowledgePackSlug -Value $PackId
    if ([string]::IsNullOrWhiteSpace($HookId)) {
        $stage = ($Event -replace "^workflow\.[^.]+\.","") -replace "\.(before|after)$",""
        $HookId = "$packSlug-$stage-hook"
    }
    if ([string]::IsNullOrWhiteSpace($Command)) {
        $Command = if ($Adapter -eq "open-code-review") { "ocr" } else { "" }
    }
    if ([string]::IsNullOrWhiteSpace($VerifyCommand) -and $InstallMethod -eq "manual") {
        $VerifyCommand = "$Command version"
    }
    if ([string]::IsNullOrWhiteSpace($Package) -and $Adapter -eq "open-code-review" -and $InstallMethod -eq "npm") {
        $Package = "@alibaba-group/open-code-review"
    }
    if ([string]::IsNullOrWhiteSpace($OutputDir)) {
        $OutputDir = Join-Path (Get-Location).Path "$packSlug-pack"
    }
    $out = Resolve-KnowledgePackPath -Path $OutputDir

    if ($result.status -ne "blocked") {
        if ((Test-Path -LiteralPath $out) -and -not $Force) {
            Set-KnowledgePackBlocked $result "OutputDir already exists; pass -Force to replace: $out"
        } else {
            if (Test-Path -LiteralPath $out) {
                Remove-KnowledgePackDirectorySafe -Root (Split-Path -Parent $out) -Path $out
            }
            New-Item -ItemType Directory -Force -Path $out | Out-Null

            $knowledgeDir = Join-Path $out "ai\knowledge"
            $guideDir = Join-Path $knowledgeDir "tools"
            New-Item -ItemType Directory -Force -Path $guideDir | Out-Null
            @(
                'schema_version: "1.1"',
                'purpose: "Generated hook pack knowledge index."',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 1",
                "workspace:",
                "  workflow-hook:",
                '    guide: "tools/workflow-hook.md"',
                '    authority: "generated"',
                '    confidence: "medium"',
                '    tags: ["workflow-hook", "tool"]',
                ""
            ) | Set-Content -LiteralPath (Join-Path $knowledgeDir "index.yml") -Encoding utf8
            @(
                "---",
                "authority: generated",
                "confidence: medium",
                "---",
                "# Workflow Hook Tool",
                "",
                "This pack installs a workflow-shell hook for event `$Event`.",
                "The external tool is declared by id, pinned version, install method, and verify command.",
                "Machine-local secrets and LLM credentials are intentionally not packaged."
            ) | Set-Content -LiteralPath (Join-Path $guideDir "workflow-hook.md") -Encoding utf8

            $hooksRoot = Join-Path $out "hooks"
            $hookDirName = ConvertTo-KnowledgePackSlug -Value $HookId
            $hookDir = Join-Path $hooksRoot $hookDirName
            New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
            $runnerName = if ($Adapter -eq "open-code-review") { "review-after-commit.ps1" } else { "run-hook.ps1" }
            $runnerPath = Join-Path $hookDir $runnerName
            if ($Adapter -eq "open-code-review") {
                New-OpenCodeReviewRunner -ToolId $ToolId -ToolVersion $ToolVersion -DefaultCommand $Command -TimeoutSeconds $TimeoutSeconds |
                    Set-Content -LiteralPath $runnerPath -Encoding utf8
            } else {
                New-GenericRunner -Command $Command | Set-Content -LiteralPath $runnerPath -Encoding utf8
            }

            $hookIndex = @(
                'schema_version: "1.0"',
                "hooks:",
                "  - id: $(Format-HookPackYamlValue $HookId)",
                '    type: "workflow-shell"',
                "    events:",
                "      - $(Format-HookPackYamlValue $Event)",
                "    runner: $(Format-HookPackYamlValue "$hookDirName/$runnerName")",
                "    timeout_seconds: $TimeoutSeconds",
                "    failure_policy: $(Format-HookPackYamlValue $FailurePolicy)",
                "    tool_dependencies:",
                "      - id: $(Format-HookPackYamlValue $ToolId)",
                "        version: $(Format-HookPackYamlValue $ToolVersion)",
                "        install_method: $(Format-HookPackYamlValue $InstallMethod)",
                "        required: true"
            )
            if (-not [string]::IsNullOrWhiteSpace($Package)) { $hookIndex += "        package: $(Format-HookPackYamlValue $Package)" }
            if (-not [string]::IsNullOrWhiteSpace($Url)) { $hookIndex += "        url: $(Format-HookPackYamlValue $Url)" }
            if (-not [string]::IsNullOrWhiteSpace($Sha256)) { $hookIndex += "        sha256: $(Format-HookPackYamlValue $Sha256)" }
            if (-not [string]::IsNullOrWhiteSpace($Command)) { $hookIndex += "        command: $(Format-HookPackYamlValue $Command)" }
            if (-not [string]::IsNullOrWhiteSpace($VerifyCommand)) { $hookIndex += "        verify_command: $(Format-HookPackYamlValue $VerifyCommand)" }
            if ($VerifyTimeoutSeconds -gt 0) { $hookIndex += "        verify_timeout_seconds: $VerifyTimeoutSeconds" }
            $hookIndex | Set-Content -LiteralPath (Join-Path $hooksRoot "index.yml") -Encoding utf8

            $resourcesDir = Join-Path $out "resources"
            New-Item -ItemType Directory -Force -Path $resourcesDir | Out-Null
            @(
                "# $PackId",
                "",
                "Generated workflow hook pack.",
                "",
                "- Hook event: $Event",
                "- Tool id: $ToolId",
                "- Tool version: $ToolVersion",
                "- Install method: $InstallMethod",
                "",
                "Configure external credentials outside this pack. For open-code-review, run the tool's LLM setup and verify it before relying on the hook."
            ) | Set-Content -LiteralPath (Join-Path $resourcesDir "README.md") -Encoding utf8

            $layers = [ordered]@{
                knowledge = $true
                skills = $false
                tools = $false
                scripts = $false
                commands = $false
                prompts = $false
                resources = $true
                templates = $false
                hooks = $true
            }
            $manifest = @(
                'schema_version: "1.0"',
                "id: $(Format-HookPackYamlValue $packSlug)",
                "title: $(Format-HookPackYamlValue $PackId)",
                'version: "0.1.0"',
                'kind: "capability-pack"',
                'description: "Portable Spec Kit workflow hook capability pack."',
                "provides:",
                "  knowledge: true",
                "  skills: false",
                "  tools: false",
                "  scripts: false",
                "  commands: false",
                "  prompts: false",
                "  resources: true",
                "  templates: false",
                "  hooks: true",
                "  workspace_profile: false",
                "  repository_map_profile: false",
                "  command_aliases: false",
                "  evaluation_scenarios: false",
                "activation:",
                '  mode: "overlay"',
                "  progressive_disclosure: true",
                "  auto_run_scripts: false",
                '  skills: "namespaced"',
                '  tools: "namespaced-overlay"',
                '  scripts: "namespaced-bin"',
                "authority:",
                '  default: "generated"',
                "  source_refs_required: false",
                "trust:",
                '  level: "local"',
                '  source: "scaffolded-hook-pack"',
                "  verified: false",
                "integrity:",
                '  algorithm: "sha256"',
                '  tree_hash_recorded_in: "install-record"',
                "ancestry:",
                '  repack_mode: "hook-scaffold"',
                "  base_packs: []",
                "compose:",
                '  strategy: "overlay-active-knowledge"',
                "  apply_tool_aliases: true"
            )
            $manifestPath = Join-Path $out "knowledge-pack.yml"
            $manifest | Set-Content -LiteralPath $manifestPath -Encoding utf8
            Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $out "pack.yml") -Force
            Write-KnowledgePackCapabilityIndex -PackRoot $out -Layers $layers -PackId $packSlug -Version "0.1.0" -RepackMode "hook-scaffold"

            $validationRaw = & "$PSScriptRoot\validate-knowledge-pack.ps1" -PackRoot $out -Json
            $validation = $validationRaw | ConvertFrom-Json
            if ($validation.status -eq "blocked") {
                Set-KnowledgePackBlocked $result ("scaffolded pack failed validation: " + (($validation.blockers) -join "; "))
            }

            $result.facts.pack_root = $out
            $result.facts.pack_id = $packSlug
            $result.facts.hook_id = $HookId
            $result.facts.event = $Event
            $result.facts.adapter = $Adapter
            $result.facts.tool = [ordered]@{
                id = $ToolId
                version = $ToolVersion
                install_method = $InstallMethod
                package = $Package
                url = $Url
                command = $Command
                verify_command = $VerifyCommand
            }
            $result.facts.hooks_dir = $hooksRoot
            $result.facts.validation = $validation
            $result.hints += "Apply this pack with apply-knowledge-pack.ps1 or 'specify knowledge apply-pack'."
        }
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
