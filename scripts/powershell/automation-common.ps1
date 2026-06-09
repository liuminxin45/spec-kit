param(
    [string]$Tool,
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [string]$Stage = "",
    [string]$DeliveryProfile = "",
    [string]$WorkflowState = "",
    [string]$CandidatesPath = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function New-Result {
    param([string]$Name)
    [ordered]@{
        tool = $Name
        status = "ok"
        facts = [ordered]@{}
        blockers = @()
        unknowns = @()
        hints = @()
    }
}

function Set-Blocked {
    param($Result, [string]$Message)
    $Result.status = "blocked"
    $Result.blockers += $Message
}

function Set-Warning {
    param($Result, [string]$Message)
    if ($Result.status -eq "ok") {
        $Result.status = "warning"
    }
    $Result.hints += $Message
}

function ConvertTo-JsonOutput {
    param($Result)
    $Result | ConvertTo-Json -Depth 10 -Compress
}

function Get-RepoChangedFiles {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) {
        return @()
    }

    $output = & git -C $Root status --porcelain=v1 -uall 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $output) {
        return @()
    }

    $files = @()
    foreach ($line in @($output)) {
        if ($line.Length -lt 4) { continue }
        $path = $line.Substring(3).Trim()
        if ($path.Contains(" -> ")) {
            $path = ($path -split " -> ")[-1]
        }
        $files += ($path -replace "\\", "/")
    }
    return $files
}

function Classify-Path {
    param([string]$Path)
    $p = ($Path -replace "\\", "/")

    if ($p.StartsWith("app-data/plugins/") -or $p.StartsWith("frontend/plugins/")) { return "runtime" }
    if ($p.StartsWith("dist/") -or $p.StartsWith("build/") -or $p.StartsWith("export/") -or $p.StartsWith("plugin-out/") -or $p.Contains("/dist/") -or $p.Contains("/build/")) { return "generated" }
    if ($p.StartsWith(".pytest_cache/") -or $p.Contains("/__pycache__/") -or $p.StartsWith(".mypy_cache/") -or $p.StartsWith(".ruff_cache/") -or $p.EndsWith(".log") -or $p.EndsWith(".tmp")) { return "temp" }
    if ($p.StartsWith("tests/") -or $p.StartsWith("test/") -or $p -match "(^|/)[^/]*(test|spec)[^/]*\.(py|js|ts|tsx|jsx|cpp|cs)$") { return "test" }
    if ($p.StartsWith("specs/") -or $p.StartsWith(".specify/") -or $p -eq "AGENTS.md" -or $p -eq "CLAUDE.md") { return "spec" }
    if ($p.StartsWith("src/") -or $p.StartsWith("source/") -or $p.StartsWith("lib/") -or $p.StartsWith("app/") -or $p.StartsWith("plugins/") -or $p.StartsWith("packages/") -or $p -match "\.(cpp|cc|c|h|hpp|ts|tsx|js|jsx|vue|cs|py)$") { return "source" }
    return "unknown"
}

function Get-LayerManifestPath {
    $candidates = @(
        (Join-Path $RepoRoot ".specify/templates/layer-manifest.yml"),
        (Join-Path $RepoRoot "tools/spec-kit/templates/layer-manifest.yml"),
        (Join-Path $RepoRoot "templates/layer-manifest.yml"),
        (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "templates/layer-manifest.yml")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return ""
}

function Get-YamlListForKey {
    param([string]$Path, [string]$Section, [string]$Key)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return @()
    }

    $lines = Get-Content -LiteralPath $Path
    $inSection = $false
    $inKey = $false
    $items = @()

    foreach ($line in $lines) {
        if ($line -match "^\S.*:\s*$") {
            $sectionName = ($line -replace ":\s*$", "").Trim()
            $inSection = ($sectionName -eq $Section)
            $inKey = $false
            continue
        }
        if (-not $inSection) { continue }

        if ($line -match "^\s{2}([^:#]+):\s*$") {
            $currentKey = $Matches[1].Trim().Trim('"')
            $inKey = ($currentKey -eq $Key)
            continue
        }

        if ($inKey -and $line -match "^\s{4}-\s+(.+?)\s*$") {
            $items += $Matches[1].Trim().Trim('"').Trim("'")
        } elseif ($inKey -and $line -match "^\s{0,2}\S") {
            $inKey = $false
        }
    }
    return $items
}

function Get-RequiredArtifacts {
    param([string]$ManifestPath)
    $stageKey = if ($Stage) { $Stage } else { "default" }
    $profileStageKey = if ($DeliveryProfile -and $Stage) { "$DeliveryProfile-$Stage" } else { "" }

    foreach ($key in @($profileStageKey, $stageKey) | Where-Object { $_ }) {
        $required = Get-YamlListForKey -Path $ManifestPath -Section "artifact_sets" -Key $key
        if ($required.Count -gt 0) {
            return @($required)
        }
    }

    if ($Stage -eq "commit") {
        return @(
            "spec.md",
            "plan.md",
            "validation.md",
            "acceptance.md",
            "workflow-state.json",
            "workflow-record.md",
            "improvement-candidates.md"
        )
    } elseif ($Stage -eq "implement") {
        return @("spec.md", "plan.md")
    } elseif ($Stage -eq "retrospective") {
        return @("acceptance.md", "workflow-record.md", "improvement-candidates.md")
    }
    return @("spec.md")
}

function Add-UniqueItems {
    param([object[]]$Items, [object[]]$Extra)
    $output = @()
    foreach ($item in @($Items) + @($Extra)) {
        if (-not $item) { continue }
        if ($output -notcontains $item) {
            $output += $item
        }
    }
    return $output
}

function Read-FeatureRouting {
    param($Result)
    $routing = [ordered]@{
        profile = $DeliveryProfile
        risk_level = ""
        risk_flags = @()
        feature_json = Join-Path $RepoRoot ".specify/feature.json"
    }

    if (-not (Test-Path -LiteralPath $routing.feature_json)) {
        $Result.unknowns += ".specify/feature.json not found; using explicit DeliveryProfile only"
        return $routing
    }

    try {
        $feature = Get-Content -LiteralPath $routing.feature_json -Raw | ConvertFrom-Json
    } catch {
        Set-Blocked $Result ".specify/feature.json is not valid JSON"
        return $routing
    }

    if ((-not $routing.profile -or $routing.profile -eq "auto") -and $feature.PSObject.Properties.Name -contains "delivery_profile") {
        $routing.profile = [string]$feature.delivery_profile
    }
    if ($feature.PSObject.Properties.Name -contains "risk_level") {
        $routing.risk_level = [string]$feature.risk_level
    }
    if ($feature.PSObject.Properties.Name -contains "risk_flags") {
        $routing.risk_flags = @($feature.risk_flags | ForEach-Object { [string]$_ })
    }
    return $routing
}

function Get-StageGateRequiredArtifacts {
    param($Routing)
    if ($Stage -ne "implement") {
        return @()
    }

    $highRiskFlags = @("ui-parity", "host-embedded-ui", "cross-repo-validation", "public-api", "real-device")
    $hasHighRiskFlag = $false
    foreach ($flag in @($Routing.risk_flags)) {
        if ($highRiskFlags -contains $flag) {
            $hasHighRiskFlag = $true
            break
        }
    }

    if ($Routing.profile -eq "full-sdd") {
        return @("tasks.md", "analysis.md", "checklists/implementation-readiness.md")
    }
    if ($Routing.risk_level -in @("high", "blocked") -or $hasHighRiskFlag) {
        return @("analysis.md", "checklists/implementation-readiness.md")
    }
    return @()
}

function Get-KnowledgeIndexPath {
    $templateRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $candidates = @(
        (Join-Path $RepoRoot "ai/knowledge/index.yml"),
        (Join-Path $RepoRoot "tools/spec-kit/templates/ai/knowledge/index.yml"),
        (Join-Path $templateRoot "templates/ai/knowledge/index.yml")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return ""
}

function Get-KnowledgeGuideRoot {
    param([string]$IndexPath)
    $indexFile = Get-Item -LiteralPath $IndexPath
    $knowledgeDir = $indexFile.Directory
    if ($knowledgeDir.Name -eq "knowledge" -and $knowledgeDir.Parent -and $knowledgeDir.Parent.Name -eq "ai") {
        return $knowledgeDir.Parent.Parent.FullName
    }
    return $RepoRoot
}

function Resolve-KnowledgeGuidePath {
    param([string]$IndexPath, [string]$Guide)
    if ([System.IO.Path]::IsPathRooted($Guide)) {
        return $Guide
    }
    if (($Guide -replace "\\", "/").StartsWith("ai/knowledge/")) {
        return Join-Path (Get-KnowledgeGuideRoot -IndexPath $IndexPath) $Guide
    }
    return Join-Path (Split-Path $IndexPath -Parent) $Guide
}

function Get-KnowledgeDisplayPath {
    param([string]$Guide)
    $normalized = $Guide -replace "\\", "/"
    if ($normalized.StartsWith("ai/knowledge/")) {
        return $normalized
    }
    return "ai/knowledge/$normalized"
}

function Get-KnowledgeMaxSelected {
    param([string]$IndexPath)
    $text = Get-Content -LiteralPath $IndexPath -Raw
    $match = [regex]::Match($text, "(?m)^\s*max_selected_guides:\s*(\d+)\s*$")
    if ($match.Success) {
        return [int]$match.Groups[1].Value
    }
    return 3
}

function Get-KnowledgeEntries {
    param([string]$IndexPath)
    if (-not $IndexPath -or -not (Test-Path -LiteralPath $IndexPath)) {
        return @()
    }

    $entrySections = @("workspace", "repositories", "domains", "build")
    $entries = @()
    $section = ""
    $current = $null

    foreach ($line in Get-Content -LiteralPath $IndexPath) {
        if ($line -match "^([A-Za-z0-9_-]+):\s*$") {
            if ($current) {
                $entries += $current
                $current = $null
            }
            $section = $Matches[1]
            continue
        }

        if ($entrySections -contains $section -and $line -match "^\s{2}([A-Za-z0-9_-]+):\s*$") {
            if ($current) {
                $entries += $current
            }
            $current = [ordered]@{
                category = $section
                key = $Matches[1]
                guide = ""
                tags = @()
            }
            continue
        }

        if (-not $current) { continue }

        if ($line -match "^\s{4}guide:\s*['""]?(.+?)['""]?\s*$") {
            $current.guide = $Matches[1].Trim().Trim('"').Trim("'")
            continue
        }
        if ($line -match "^\s{4}tags:\s*\[(.*?)\]\s*$") {
            $tags = @()
            foreach ($tag in ($Matches[1] -split ",")) {
                $clean = $tag.Trim().Trim('"').Trim("'")
                if ($clean) { $tags += $clean.ToLowerInvariant() }
            }
            $current.tags = $tags
            continue
        }
    }

    if ($current) {
        $entries += $current
    }
    return $entries
}

function Normalize-KnowledgeToken {
    param([string]$Value)
    return (($Value.ToLowerInvariant()) -replace "[^a-z0-9]+", "")
}

function Add-KnowledgeTerm {
    param([System.Collections.ArrayList]$Terms, [string]$Value)
    if (-not $Value) { return }
    $lower = $Value.ToLowerInvariant()
    if (-not $Terms.Contains($lower)) {
        [void]$Terms.Add($lower)
    }
    foreach ($piece in ($lower -split "[^a-z0-9]+")) {
        if ($piece -and -not $Terms.Contains($piece)) {
            [void]$Terms.Add($piece)
        }
    }
}

function Get-KnowledgeRoutingContext {
    $terms = [System.Collections.ArrayList]@()
    $affected = @()
    $riskFlags = @()
    $capabilityTags = @()
    $summary = ""
    $featureJson = Join-Path $RepoRoot ".specify/feature.json"

    foreach ($value in @($Stage, $DeliveryProfile)) {
        Add-KnowledgeTerm -Terms $terms -Value $value
    }

    if (Test-Path -LiteralPath $featureJson) {
        try {
            $feature = Get-Content -LiteralPath $featureJson -Raw | ConvertFrom-Json
            if ($feature.PSObject.Properties.Name -contains "affected_repositories") {
                $affected = @($feature.affected_repositories | ForEach-Object { [string]$_ })
            }
            if ($feature.PSObject.Properties.Name -contains "risk_flags") {
                $riskFlags = @($feature.risk_flags | ForEach-Object { [string]$_ })
            }
            if ($feature.PSObject.Properties.Name -contains "capability_tags") {
                $capabilityTags = @($feature.capability_tags | ForEach-Object { [string]$_ })
            }
            if ($feature.PSObject.Properties.Name -contains "request_summary") {
                $summary = [string]$feature.request_summary
            }
        } catch {
            # The validation tool reports malformed feature state; selection stays best-effort.
        }
    }

    foreach ($value in @($affected + $riskFlags + $capabilityTags + @($summary))) {
        Add-KnowledgeTerm -Terms $terms -Value $value
    }

    return [ordered]@{
        terms = @($terms)
        affected_repositories = $affected
        risk_flags = $riskFlags
        capability_tags = $capabilityTags
        request_summary = $summary
        feature_json = $featureJson
    }
}

function Get-KnowledgeRepositoryNames {
    $names = @()
    $workspaceFile = Join-Path $RepoRoot ".specify/workspace.yml"
    if (Test-Path -LiteralPath $workspaceFile) {
        foreach ($match in [regex]::Matches((Get-Content -LiteralPath $workspaceFile -Raw), "(?m)^\s*-\s*name:\s*(.+?)\s*$")) {
            $names += $match.Groups[1].Value.Trim().Trim('"').Trim("'")
        }
    }
    return $names
}

function Invoke-SelectKnowledge {
    $result = New-Result "select-knowledge"
    $indexPath = Get-KnowledgeIndexPath
    if (-not $indexPath) {
        Set-Blocked $result "ai/knowledge/index.yml not found"
        return $result
    }

    $entries = Get-KnowledgeEntries -IndexPath $indexPath
    $routing = Get-KnowledgeRoutingContext
    $terms = @($routing.terms)
    $normalizedAffected = @($routing.affected_repositories | ForEach-Object { Normalize-KnowledgeToken $_ })
    $maxSelected = [Math]::Max(1, (Get-KnowledgeMaxSelected -IndexPath $indexPath))
    $ranked = @()

    foreach ($entry in $entries) {
        if (-not $entry.guide) { continue }
        $score = 0
        $reasons = @()
        $matchedTags = @()
        $normalizedKey = Normalize-KnowledgeToken $entry.key

        if ($normalizedAffected -contains $normalizedKey) {
            $score += 8
            $reasons += "affected repository"
        }

        foreach ($tag in @($entry.tags)) {
            if ($terms -contains $tag) {
                $score += 3
                $matchedTags += $tag
            }
        }

        if ($Stage -eq "validation" -and $entry.key -eq "validation-matrix") {
            $score += 4
            $reasons += "validation stage"
        }
        if ($Stage -eq "plan" -and $entry.category -eq "workspace") {
            $score += 1
            $reasons += "planning context"
        }
        if (($terms -contains "cross") -or ($terms -contains "cross-repo")) {
            if ($entry.key -eq "cross-repo-routing") {
                $score += 4
                $reasons += "cross-repo routing"
            }
        }

        if ($matchedTags.Count -gt 0) {
            $reasons += ("matched tags: " + (($matchedTags | Select-Object -Unique) -join ", "))
        }

        if ($score -gt 0) {
            $ranked += [ordered]@{
                score = $score
                path = Get-KnowledgeDisplayPath -Guide $entry.guide
                category = $entry.category
                key = $entry.key
                reason = (($reasons | Select-Object -Unique) -join "; ")
                matched_tags = @($matchedTags | Select-Object -Unique)
            }
        }
    }

    $selected = @($ranked | Sort-Object -Property @{ Expression = "score"; Descending = $true }, @{ Expression = "path"; Descending = $false } | Select-Object -First $maxSelected)
    $result.facts.index = $indexPath
    $result.facts.max_selected_guides = $maxSelected
    $result.facts.terms = $terms
    $result.facts.affected_repositories = $routing.affected_repositories
    $result.facts.risk_flags = $routing.risk_flags
    $result.facts.capability_tags = $routing.capability_tags
    $result.facts.selected = @($selected | ForEach-Object {
        [ordered]@{
            path = $_.path
            category = $_.category
            key = $_.key
            reason = $_.reason
            matched_tags = $_.matched_tags
        }
    })
    if ($selected.Count -eq 0) {
        $result.hints += "no knowledge guide matched deterministic routing fields; keep default context only"
    }
    return $result
}

function Invoke-ValidateKnowledgeIndex {
    $result = New-Result "validate-knowledge-index"
    $indexPath = Get-KnowledgeIndexPath
    if (-not $indexPath) {
        Set-Blocked $result "ai/knowledge/index.yml not found"
        return $result
    }

    $indexText = Get-Content -LiteralPath $indexPath -Raw
    $requiredPhrases = @("repository_map_authority", "no_full_text_search_required", "max_selected_guides")
    foreach ($phrase in $requiredPhrases) {
        if ($indexText -notmatch [regex]::Escape($phrase)) {
            Set-Blocked $result "knowledge index missing required phrase: $phrase"
        }
    }

    $entries = Get-KnowledgeEntries -IndexPath $indexPath
    $missingGuides = @()
    $absolutePathOffenders = @()
    $oversizedGuides = @()
    $repoNames = @(Get-KnowledgeRepositoryNames | ForEach-Object { Normalize-KnowledgeToken $_ })
    $unknownRepos = @()
    $forbiddenPatterns = @(
        "[A-Za-z]:\\Internal\\",
        "[A-Za-z]:\\Private\\",
        "/Users/example/",
        "/home/example/",
        "AppData",
        "private-user"
    )

    foreach ($entry in $entries) {
        if (-not $entry.guide) {
            $missingGuides += "$($entry.category).$($entry.key) has no guide"
            continue
        }

        $guidePath = Resolve-KnowledgeGuidePath -IndexPath $indexPath -Guide $entry.guide
        if (-not (Test-Path -LiteralPath $guidePath)) {
            $missingGuides += (Get-KnowledgeDisplayPath -Guide $entry.guide)
            continue
        }

        $text = Get-Content -LiteralPath $guidePath -Raw
        foreach ($pattern in $forbiddenPatterns) {
            if ($text -match $pattern) {
                $absolutePathOffenders += "$(Get-KnowledgeDisplayPath -Guide $entry.guide) contains machine-specific path pattern: $pattern"
            }
        }

        $lineCount = @((Get-Content -LiteralPath $guidePath)).Count
        if ($lineCount -gt 220) {
            $oversizedGuides += "$(Get-KnowledgeDisplayPath -Guide $entry.guide) has $lineCount lines"
        }

        if ($entry.category -eq "repositories" -and $repoNames.Count -gt 0) {
            $normalizedKey = Normalize-KnowledgeToken $entry.key
            if ($repoNames -notcontains $normalizedKey) {
                $unknownRepos += $entry.key
            }
        }
    }

    if ($missingGuides.Count -gt 0) {
        Set-Blocked $result ("missing knowledge guides: " + (($missingGuides | Select-Object -Unique) -join ", "))
    }
    if ($absolutePathOffenders.Count -gt 0) {
        Set-Blocked $result ("machine-specific knowledge paths found: " + (($absolutePathOffenders | Select-Object -Unique) -join "; "))
    }
    if ($oversizedGuides.Count -gt 0) {
        Set-Blocked $result ("knowledge guides exceed 220 lines: " + (($oversizedGuides | Select-Object -Unique) -join "; "))
    }
    if ($unknownRepos.Count -gt 0) {
        Set-Blocked $result ("knowledge index references repositories missing from workspace.yml: " + (($unknownRepos | Select-Object -Unique) -join ", "))
    }

    $result.facts.index = $indexPath
    $result.facts.guide_count = @($entries | Where-Object { $_.guide }).Count
    $result.facts.missing_guides = @($missingGuides | Select-Object -Unique)
    $result.facts.absolute_path_offenders = @($absolutePathOffenders | Select-Object -Unique)
    $result.facts.oversized_guides = @($oversizedGuides | Select-Object -Unique)
    $result.facts.unknown_repositories = @($unknownRepos | Select-Object -Unique)
    $result.facts.max_selected_guides = Get-KnowledgeMaxSelected -IndexPath $indexPath
    return $result
}

function Invoke-ValidateFeatureArtifacts {
    $result = New-Result "validate-feature-artifacts"
    $manifestPath = Get-LayerManifestPath
    $required = Get-RequiredArtifacts -ManifestPath $manifestPath
    $routing = Read-FeatureRouting -Result $result
    $stageGateRequired = Get-StageGateRequiredArtifacts -Routing $routing
    $required = Add-UniqueItems -Items $required -Extra $stageGateRequired
    $requiredSource = if ($manifestPath) { "layer-manifest.yml" } else { "fallback" }

    $missing = @()
    foreach ($file in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $FeatureDir $file))) {
            $missing += $file
        }
    }
    if ($missing.Count -gt 0) {
        Set-Blocked $result ("missing required artifacts: " + ($missing -join ", "))
    }

    $missingSections = @()
    if ($manifestPath -and (Test-Path -LiteralPath $FeatureDir)) {
        foreach ($file in $required) {
            $path = Join-Path $FeatureDir $file
            if (-not (Test-Path -LiteralPath $path)) { continue }
            $requiredSections = Get-YamlListForKey -Path $manifestPath -Section "artifact_sections" -Key $file
            if ($requiredSections.Count -eq 0) { continue }
            $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
            $missingForFile = @($requiredSections | Where-Object { $text -notmatch [regex]::Escape($_) })
            if ($missingForFile.Count -gt 0) {
                $missingSections += [ordered]@{ file = $file; missing = $missingForFile }
                Set-Blocked $result ("$file missing required sections: " + ($missingForFile -join ", "))
            }
        }
    }

    $todos = @()
    if (Test-Path -LiteralPath $FeatureDir) {
        foreach ($file in Get-ChildItem -LiteralPath $FeatureDir -Filter "*.md" -File -ErrorAction SilentlyContinue) {
            $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($text -match "(?i)\b(TBD|TODO)\b") {
                $todos += $file.Name
            }
        }
    }
    if ($todos.Count -gt 0) {
        Set-Blocked $result ("unfinished placeholders in: " + ($todos -join ", "))
    }

    $result.facts.feature_dir = $FeatureDir
    $result.facts.stage = $Stage
    $result.facts.delivery_profile = $DeliveryProfile
    $result.facts.effective_delivery_profile = $routing.profile
    $result.facts.risk_level = $routing.risk_level
    $result.facts.risk_flags = $routing.risk_flags
    $result.facts.stage_gate_required = $stageGateRequired
    $result.facts.feature_json = $routing.feature_json
    $result.facts.required = $required
    $result.facts.required_source = $requiredSource
    $result.facts.layer_manifest = $manifestPath
    $result.facts.missing_sections = $missingSections
    return $result
}

function Invoke-ValidateGeneratedContext {
    $result = New-Result "validate-generated-context"
    $contextFile = "AGENTS.md"
    $canonicalContextFile = "AGENTS.md"
    $initOptionsPath = Join-Path $RepoRoot ".specify/init-options.json"
    if (Test-Path -LiteralPath $initOptionsPath) {
        try {
            $initOptions = Get-Content -LiteralPath $initOptionsPath -Raw | ConvertFrom-Json
            if ($initOptions.context_file -and [string]$initOptions.context_file -ne "") {
                $contextFile = [string]$initOptions.context_file
            }
            if ($initOptions.canonical_context_file -and [string]$initOptions.canonical_context_file -ne "") {
                $canonicalContextFile = [string]$initOptions.canonical_context_file
            }
        }
        catch {
            Set-Blocked $result "failed to parse .specify/init-options.json"
        }
    }
    if ($contextFile -eq "CLAUDE.md" -and $canonicalContextFile -eq $contextFile) {
        $canonicalContextFile = "AGENTS.md"
    }
    $skillsDir = ".agents/skills"
    if ($contextFile -eq "CLAUDE.md") {
        $skillsDir = ".claude/skills"
    }
    $workflowPath = "tools/spec-kit/workflows/speckit/workflow.yml"
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $workflowPath)) -and
        (Test-Path -LiteralPath (Join-Path $RepoRoot ".specify/workflows/speckit/workflow.yml"))) {
        $workflowPath = ".specify/workflows/speckit/workflow.yml"
    }
    $checks = @()
    if ($contextFile -eq "CLAUDE.md") {
        $checks += [ordered]@{
            path = $contextFile
            phrases = @("@AGENTS.md", ".claude/skills", "/speckit-specify", "/speckit-plan", "/speckit-tasks", "/speckit-implement")
        }
    }
    $checks += @(
        [ordered]@{
            path = $canonicalContextFile
            phrases = @("Project Path Categories", "source-to-runtime copy", "best-effort self-validation", "direct runtime replacement", "DesktopShell CDP validation", "stale/current-feature hint", "read the current plan only", "select-knowledge", "validate-knowledge-index")
        },
        [ordered]@{
            path = ".specify/memory/repository-map.md"
            phrases = @("Project Path Categories", "<workspace-root>/ProductUIPlugin/<plugin-id>/", "CDP target inventory", "Do not write machine-specific absolute paths here")
        },
        [ordered]@{
            path = ".specify/templates/layer-manifest.yml"
            phrases = @("stage_gates:", "read_strategies:", "Knowledge", "validate-knowledge-index", "checklists/implementation-readiness.md")
        },
        [ordered]@{
            path = "ai/workflows/task-routing.md"
            phrases = @("tasks -> analyze -> checklist", "validate-generated-context", "validate-knowledge-index", "select-knowledge", "artifact_sections", "Stage Continuation", "inspect-desktop-shell-cdp-target", "do not apply stale feature risk flags")
        },
        [ordered]@{
            path = "ai/rules/ai-coding-rules.md"
            phrases = @("Generated Context Drift", "analysis.md", "validate-generated-context", "validate-knowledge-index", "Stage Continuation Contract", "Host Frontend Delivery Chain", "Retrospective/留痕 is mandatory before commit")
        },
        [ordered]@{
            path = $workflowPath
            phrases = @("id: retrospective", "id: commit", "Require workflow-record.md and improvement-candidates.md before commit", "automatic_stage_continuation", "inspect-desktop-shell-cdp-target", "validate-knowledge-index", "current-feature state only")
        },
        [ordered]@{
            path = "tools/spec-kit/TEAM-README.md"
            optional = $true
            phrases = @("retrospective/留痕 -> commit", "commit 前强制 retrospective", "source edit -> frontend build -> direct runtime replacement -> real host CDP verification", "select-knowledge", "full-text/BM25 search")
        },
        [ordered]@{
            path = "$skillsDir/speckit-commit/SKILL.md"
            phrases = @("Confirm acceptance, quick acceptance, and retrospective are passed", "workflow-record.md", "improvement-candidates.md")
        },
        [ordered]@{
            path = "$skillsDir/speckit-tasks/SKILL.md"
            phrases = @("Run mandatory", "speckit.retrospective", "after quick acceptance and before", "optional test-hardening, retrospective/留痕")
        }
    )

    $details = @()
    foreach ($check in $checks) {
        $path = Join-Path $RepoRoot $check.path
        if (-not (Test-Path -LiteralPath $path)) {
            $details += [ordered]@{ path = $check.path; exists = $false; missing_phrases = $check.phrases }
            if (-not $check.optional) {
                Set-Blocked $result ("generated context missing: " + $check.path)
            }
            continue
        }

        $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
        $missingPhrases = @($check.phrases | Where-Object { $text -notlike ("*" + $_ + "*") })
        $details += [ordered]@{ path = $check.path; exists = $true; missing_phrases = $missingPhrases }
        if ($missingPhrases.Count -gt 0) {
            Set-Blocked $result ($check.path + " missing required generated-context phrases: " + ($missingPhrases -join ", "))
        }
    }

    $result.facts.repo_root = $RepoRoot
    $result.facts.checked = $details
    return $result
}

function Invoke-SuggestValidation {
    $result = New-Result "suggest-validation"
    $hints = @()
    $result.facts.validation_artifacts = @("validation.md", "acceptance.md")
    $result.facts.optional_evidence_artifacts = @("evidence.md", "fact-pack.md")
    $result.facts.validation_template = "ai/templates/validation-template.md"
    $result.facts.evidence_template = "ai/templates/evidence-template.md"
    $result.facts.evidence_required = "complex_or_runtime_or_tool_heavy"
    if ($FeatureDir) {
        $result.facts.feature_dir = $FeatureDir
        $result.facts.validation_path = Join-Path $FeatureDir "validation.md"
        $result.facts.acceptance_path = Join-Path $FeatureDir "acceptance.md"
        $result.facts.evidence_path = Join-Path $FeatureDir "evidence.md"
    }
    $packagePath = Join-Path $RepoRoot "package.json"
    if (Test-Path -LiteralPath $packagePath) {
        try {
            $package = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
            $scripts = $package.scripts
            if ($scripts) {
                if ($scripts.PSObject.Properties.Name -contains "test") {
                    $hints += [ordered]@{ command = "npm test"; confidence = "exact"; source = "package.json scripts.test" }
                }
                if ($scripts.PSObject.Properties.Name -contains "build") {
                    $hints += [ordered]@{ command = "npm run build"; confidence = "exact"; source = "package.json scripts.build" }
                }
                if ($scripts.PSObject.Properties.Name -contains "lint") {
                    $hints += [ordered]@{ command = "npm run lint"; confidence = "exact"; source = "package.json scripts.lint" }
                }
            }
        } catch {
            $result.unknowns += "package.json could not be parsed"
        }
    }

    if ((Test-Path -LiteralPath (Join-Path $RepoRoot "pytest.ini")) -or (Test-Path -LiteralPath (Join-Path $RepoRoot "conftest.py")) -or (Test-Path -LiteralPath (Join-Path $RepoRoot "pyproject.toml"))) {
        $hints += [ordered]@{ command = "pytest"; confidence = "likely"; source = "pytest marker" }
    }
    if (Test-Path -LiteralPath (Join-Path $RepoRoot "CMakeLists.txt")) {
        $hints += [ordered]@{ command = "cmake --build <build-dir>"; confidence = "likely"; source = "CMakeLists.txt" }
    }

    $result.hints = $hints
    $result.facts.repo_root = $RepoRoot
    $result.facts.candidate_count = $hints.Count
    if ($hints.Count -eq 0) {
        $result.unknowns += "no validation command candidates discovered from package.json, pytest, or CMake markers"
    }
    return $result
}

function Invoke-InspectCommitScope {
    $result = New-Result "inspect-commit-scope"
    $classified = [ordered]@{
        source = @()
        test = @()
        spec = @()
        generated = @()
        runtime = @()
        temp = @()
        unknown = @()
    }
    $files = Get-RepoChangedFiles $RepoRoot
    foreach ($file in $files) {
        $kind = Classify-Path $file
        $classified[$kind] += $file
        if ($kind -eq "unknown") {
            $result.unknowns += $file
        }
    }
    $result.facts.repo_root = $RepoRoot
    $result.facts.changed_files = $files
    $result.facts.classified = $classified
    if ($result.unknowns.Count -gt 0) {
        $result.status = "warning"
    }
    return $result
}

function Invoke-ValidateFactLayerGate {
    $result = New-Result "validate-fact-layer-gate"
    if (-not (Test-Path -LiteralPath $WorkflowState)) {
        Set-Blocked $result "missing workflow-state.json; LLM must create structured state before this gate"
        return $result
    }

    try {
        $state = Get-Content -LiteralPath $WorkflowState -Raw | ConvertFrom-Json
    } catch {
        Set-Blocked $result "workflow-state.json is not valid JSON"
        return $result
    }

    if ($null -eq $state.attempts) {
        Set-Blocked $result "workflow-state.json missing attempts[]"
        return $result
    }

    foreach ($attempt in @($state.attempts)) {
        if ($attempt.result -eq "failed" -and $attempt.symptom_changed -eq $false -and $attempt.fact_layer_after_failure -ne $true) {
            $attemptId = if ($attempt.id) { $attempt.id } else { "<missing-id>" }
            Set-Blocked $result "failed unchanged attempt requires fact-layer evidence: $attemptId"
        }
    }
    $result.facts.workflow_state = $WorkflowState
    $result.facts.attempt_count = @($state.attempts).Count
    return $result
}

function Invoke-InspectSourceArtifactConsistency {
    $scope = Invoke-InspectCommitScope
    $result = New-Result "inspect-source-artifact-consistency"
    $classified = $scope.facts.classified
    $artifactCount = @($classified.runtime).Count + @($classified.generated).Count
    $sourceCount = @($classified.source).Count + @($classified.test).Count + @($classified.spec).Count
    $result.facts.classified = $classified
    if ($artifactCount -gt 0 -and $sourceCount -eq 0) {
        Set-Blocked $result "runtime/generated artifacts changed without repository source changes"
    }
    return $result
}

function Invoke-ParsePromotionCandidates {
    $result = New-Result "parse-promotion-candidates"
    $counts = [ordered]@{ approved = 0; pending = 0; rejected = 0 }
    if (-not (Test-Path -LiteralPath $CandidatesPath)) {
        Set-Blocked $result "missing improvement-candidates.md"
        $result.facts.counts = $counts
        return $result
    }

    $text = Get-Content -LiteralPath $CandidatesPath -Raw
    foreach ($state in @("approved", "pending", "rejected")) {
        $matches = [regex]::Matches($text, "(?im)人工审核结论\s*:\s*$state\b")
        $counts[$state] = $matches.Count
    }
    $result.facts.candidates_path = $CandidatesPath
    $result.facts.counts = $counts
    return $result
}

function Invoke-InspectAffectedRepos {
    $result = New-Result "inspect-affected-repos"
    $workspaceFile = Join-Path $RepoRoot ".specify/workspace.yml"
    $repos = @()
    if (Test-Path -LiteralPath $workspaceFile) {
        $text = Get-Content -LiteralPath $workspaceFile -Raw
        foreach ($match in [regex]::Matches($text, "(?m)^\s*-\s*name:\s*(.+?)\s*$")) {
            $repos += $match.Groups[1].Value.Trim()
        }
    } else {
        $result.unknowns += ".specify/workspace.yml not found"
    }
    $result.facts.workspace_file = $workspaceFile
    $result.facts.repositories = $repos
    return $result
}

function Invoke-InspectDeliveryFacts {
    $result = New-Result "inspect-delivery-facts"
    $featureJson = Join-Path $RepoRoot ".specify/feature.json"
    if (Test-Path -LiteralPath $featureJson) {
        try {
            $feature = Get-Content -LiteralPath $featureJson -Raw | ConvertFrom-Json
            $result.facts.feature_json = $featureJson
            $result.facts.delivery_profile = $feature.delivery_profile
            $result.facts.risk_level = $feature.risk_level
            $result.facts.task_type = $feature.task_type
        } catch {
            Set-Blocked $result ".specify/feature.json is not valid JSON"
        }
    } else {
        $result.unknowns += ".specify/feature.json not found"
    }
    return $result
}

function Invoke-ValidateChecklistRules {
    $result = New-Result "validate-checklist-rules"
    $rulesDir = Join-Path $RepoRoot "tools/spec-kit/checklist-rules"
    if (-not (Test-Path -LiteralPath $rulesDir)) {
        $rulesDir = Join-Path $RepoRoot "checklist-rules"
    }
    if (-not (Test-Path -LiteralPath $rulesDir)) {
        Set-Blocked $result "checklist-rules directory not found"
        return $result
    }
    $files = @(Get-ChildItem -LiteralPath $rulesDir -Filter "*.yml" -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) {
        Set-Blocked $result "no checklist rule files found"
    }
    $result.facts.rules_dir = $rulesDir
    $result.facts.rule_files = @($files | ForEach-Object { $_.Name })
    return $result
}

function Invoke-ValidateRootCauseStructure {
    $result = New-Result "validate-root-cause-structure"
    $planPath = Join-Path $FeatureDir "plan.md"
    $required = @("Root Cause Evidence", "Symptom", "Call Path", "Evidence", "Excluded Alternatives", "Counterexample", "Blast Radius", "Validation Mapping", "Confidence")
    if (-not (Test-Path -LiteralPath $planPath)) {
        Set-Blocked $result "plan.md not found"
        $result.facts.required = $required
        return $result
    }
    $text = Get-Content -LiteralPath $planPath -Raw
    $missing = @($required | Where-Object { $text -notmatch [regex]::Escape($_) })
    if ($missing.Count -gt 0) {
        Set-Blocked $result ("missing root-cause structure fields: " + ($missing -join ", "))
    }
    $result.facts.plan = $planPath
    $result.facts.required = $required
    return $result
}

function Invoke-ValidateImplementationSlices {
    $result = New-Result "validate-implementation-slices"
    $tasksPath = Join-Path $FeatureDir "tasks.md"
    $required = @("Implementation Slices", "允许写入范围", "禁止范围", "停止条件")
    if (-not (Test-Path -LiteralPath $tasksPath)) {
        Set-Blocked $result "tasks.md not found"
        $result.facts.required = $required
        return $result
    }
    $text = Get-Content -LiteralPath $tasksPath -Raw
    $missing = @($required | Where-Object { $text -notmatch [regex]::Escape($_) })
    if ($missing.Count -gt 0) {
        Set-Blocked $result ("missing implementation-slice structure fields: " + ($missing -join ", "))
    }
    $result.facts.tasks = $tasksPath
    $result.facts.required = $required
    return $result
}

function Invoke-CollectWorkflowFacts {
    $result = New-Result "collect-workflow-facts"
    $result.facts.repo_root = $RepoRoot
    $result.facts.changed_files = Get-RepoChangedFiles $RepoRoot
    $result.facts.feature_json_exists = Test-Path -LiteralPath (Join-Path $RepoRoot ".specify/feature.json")
    $result.facts.workflow_state_exists = if ($WorkflowState) { Test-Path -LiteralPath $WorkflowState } else { $false }
    return $result
}

function Invoke-InspectPackageSync {
    $result = New-Result "inspect-package-sync"
    $corePack = Join-Path $RepoRoot "tools/spec-kit/.venv/Lib/site-packages/specify_cli/core_pack"
    if (-not (Test-Path -LiteralPath $corePack)) {
        $corePack = Join-Path $RepoRoot ".venv/Lib/site-packages/specify_cli/core_pack"
    }
    $result.facts.core_pack = $corePack
    $result.facts.core_pack_exists = Test-Path -LiteralPath $corePack
    if (-not $result.facts.core_pack_exists) {
        $result.unknowns += "core_pack package copy not found"
    }
    return $result
}

function Invoke-NormalizeWorkflowState {
    $result = New-Result "normalize-workflow-state"
    if (-not $WorkflowState -or -not (Test-Path -LiteralPath $WorkflowState)) {
        Set-Blocked $result "workflow-state.json missing; create from templates/workflow-state-template.json before normalization"
        return $result
    }
    try {
        $state = Get-Content -LiteralPath $WorkflowState -Raw | ConvertFrom-Json
        foreach ($field in @("attempts", "validations", "fact_layer", "acceptance", "retrospective", "promotion")) {
            if ($null -eq $state.$field) {
                Set-Blocked $result "workflow-state.json missing field: $field"
            }
        }
        $result.facts.workflow_state = $WorkflowState
    } catch {
        Set-Blocked $result "workflow-state.json is not valid JSON"
    }
    return $result
}

function Invoke-InspectUntrackedNoise {
    $result = New-Result "inspect-untracked-noise"
    $files = Get-RepoChangedFiles $RepoRoot
    $untracked = @($files | Where-Object {
        $raw = & git -C $RepoRoot status --porcelain=v1 -uall -- $_ 2>$null
        $raw -match "^\?\?"
    })
    $noise = @()
    $unknown = @()
    foreach ($file in $untracked) {
        $kind = Classify-Path $file
        if ($kind -in @("generated", "runtime", "temp")) { $noise += $file } else { $unknown += $file }
    }
    $result.facts.untracked_noise = $noise
    $result.facts.untracked_unknown = $unknown
    $result.unknowns = $unknown
    if ($unknown.Count -gt 0) { $result.status = "warning" }
    return $result
}

function Invoke-GenerateAcceptanceSkeleton {
    $result = New-Result "generate-acceptance-skeleton"
    $result.facts.feature_dir = $FeatureDir
    $result.hints += [ordered]@{ file = "acceptance.md"; purpose = "user-facing acceptance steps" }
    $result.hints += [ordered]@{ file = "acceptance-checklist.md"; purpose = "human-facing acceptance checklist" }
    return $result
}

function Invoke-GenericInspector {
    param([string]$Name)
    $result = New-Result $Name
    $result.facts.repo_root = $RepoRoot
    $result.hints += "hard facts collected only; LLM owns semantic routing, risk, and sufficiency decisions"
    return $result
}

switch ($Tool) {
    "validate-feature-artifacts" { $result = Invoke-ValidateFeatureArtifacts }
    "validate-generated-context" { $result = Invoke-ValidateGeneratedContext }
    "select-knowledge" { $result = Invoke-SelectKnowledge }
    "validate-knowledge-index" { $result = Invoke-ValidateKnowledgeIndex }
    "suggest-validation" { $result = Invoke-SuggestValidation }
    "inspect-commit-scope" { $result = Invoke-InspectCommitScope }
    "validate-fact-layer-gate" { $result = Invoke-ValidateFactLayerGate }
    "inspect-affected-repos" { $result = Invoke-InspectAffectedRepos }
    "inspect-delivery-facts" { $result = Invoke-InspectDeliveryFacts }
    "validate-checklist-rules" { $result = Invoke-ValidateChecklistRules }
    "validate-root-cause-structure" { $result = Invoke-ValidateRootCauseStructure }
    "validate-implementation-slices" { $result = Invoke-ValidateImplementationSlices }
    "inspect-source-artifact-consistency" { $result = Invoke-InspectSourceArtifactConsistency }
    "collect-workflow-facts" { $result = Invoke-CollectWorkflowFacts }
    "parse-promotion-candidates" { $result = Invoke-ParsePromotionCandidates }
    "inspect-package-sync" { $result = Invoke-InspectPackageSync }
    "normalize-workflow-state" { $result = Invoke-NormalizeWorkflowState }
    "inspect-untracked-noise" { $result = Invoke-InspectUntrackedNoise }
    "generate-acceptance-skeleton" { $result = Invoke-GenerateAcceptanceSkeleton }
    default { $result = Invoke-GenericInspector $Tool }
}

ConvertTo-JsonOutput $result
