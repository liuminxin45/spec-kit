param(
    [string]$Tool,
    [string]$RepoRoot = (Get-Location).Path,
    [string]$FeatureDir = "",
    [string]$Stage = "",
    [string]$DeliveryProfile = "",
    [string]$WorkflowState = "",
    [string]$CandidatesPath = "",
    [string]$PackagePath = "",
    [string]$RubricPath = "",
    [string]$PackId = "",
    [switch]$Repack,
    [switch]$Force,
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

function Get-SpecKitSourceRoot {
    $candidates = @(
        (Join-Path $RepoRoot "spec-kit"),
        (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate "pyproject.toml") -PathType Leaf) {
            return $candidate
        }
    }
    return ""
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
    if ($p.StartsWith("specs/") -or $p.StartsWith(".specify/") -or $p -eq "AGENTS.md") { return "spec" }
    if ($p.StartsWith("src/") -or $p.StartsWith("source/") -or $p.StartsWith("lib/") -or $p.StartsWith("app/") -or $p.StartsWith("plugins/") -or $p.StartsWith("packages/") -or $p -match "\.(cpp|cc|c|h|hpp|ts|tsx|js|jsx|vue|cs|py)$") { return "source" }
    return "unknown"
}

function Get-LayerManifestPath {
    $sourceRoot = Get-SpecKitSourceRoot
    $candidates = @(
        (Join-Path $RepoRoot ".specify/templates/layer-manifest.yml"),
        (Join-Path $RepoRoot "spec-kit/templates/layer-manifest.yml"),
        (Join-Path $RepoRoot "templates/layer-manifest.yml")
    )
    if (-not [string]::IsNullOrWhiteSpace($sourceRoot)) {
        $candidates += (Join-Path $sourceRoot "templates/layer-manifest.yml")
    }
    $candidates += (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "templates/layer-manifest.yml")
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
    } elseif ($Stage -eq "converge") {
        return @("spec.md", "plan.md", "progress.md", "validation.md")
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

function Resolve-FeatureDirPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $RepoRoot $Path
}

function Get-RelativeDisplayPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    try {
        $root = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).Path
        $full = if (Test-Path -LiteralPath $Path) {
            (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
        } else {
            [System.IO.Path]::GetFullPath($Path)
        }
        $relative = [System.IO.Path]::GetRelativePath($root, $full)
        return ($relative -replace "\\", "/")
    } catch {
        return ($Path -replace "\\", "/")
    }
}

function Read-JsonObject {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-ObjectPropertyValue {
    param($Object, [string]$PropertyName)
    if ($null -eq $Object) {
        return $null
    }
    if ($Object.PSObject.Properties.Name -contains $PropertyName) {
        return $Object.$PropertyName
    }
    return $null
}

function Get-WorkflowStateStatus {
    param($State, [string]$NodeName)
    $node = Get-ObjectPropertyValue -Object $State -PropertyName $NodeName
    if ($null -eq $node) {
        return ""
    }
    $status = Get-ObjectPropertyValue -Object $node -PropertyName "status"
    if ($null -eq $status) {
        return ""
    }
    return [string]$status
}

function Test-TextAcceptancePassed {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    return ($text -match "(?i)acceptance\s*(status|result)?\s*[:：]\s*passed|human\s+acceptance\s*[:：]\s*passed|验收通过|人工验收通过")
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
    $sourceRoot = Get-SpecKitSourceRoot
    $templateRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $candidates = @(
        (Join-Path $RepoRoot "ai/knowledge/index.yml"),
        (Join-Path $RepoRoot "spec-kit/templates/ai/knowledge/index.yml")
    )
    if (-not [string]::IsNullOrWhiteSpace($sourceRoot)) {
        $candidates += (Join-Path $sourceRoot "templates/ai/knowledge/index.yml")
    }
    $candidates += (Join-Path $templateRoot "templates/ai/knowledge/index.yml")
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

    $entrySections = @("workspace", "repositories", "domains", "build", "promoted")
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
                authority = ""
                confidence = ""
                tags = @()
            }
            continue
        }

        if (-not $current) { continue }

        if ($line -match "^\s{4}guide:\s*['""]?(.+?)['""]?\s*$") {
            $current.guide = $Matches[1].Trim().Trim('"').Trim("'")
            continue
        }
        if ($line -match "^\s{4}authority:\s*['""]?(.+?)['""]?\s*$") {
            $current.authority = $Matches[1].Trim().Trim('"').Trim("'")
            continue
        }
        if ($line -match "^\s{4}confidence:\s*['""]?(.+?)['""]?\s*$") {
            $current.confidence = $Matches[1].Trim().Trim('"').Trim("'")
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
    $stageName = $Stage.ToLowerInvariant()
    $termText = " " + (($terms | ForEach-Object { "$_" }) -join " ") + " "
    $isTestPlanningStage = (($stageName -match '^(plan|clarify)$') -or ($termText -match '\s(plan|clarify)\s'))
    $hasTestPlanningTerms = ($termText -match '\s(api|e2e|test)\s')
    $normalizedAffected = @($routing.affected_repositories | ForEach-Object { Normalize-KnowledgeToken $_ })
    $maxSelected = [Math]::Max(1, (Get-KnowledgeMaxSelected -IndexPath $indexPath))
    $ranked = @()

    foreach ($entry in $entries) {
        if (-not $entry.guide) { continue }
        $score = 0
        $reasons = @()
        $matchedTags = @()
        $normalizedKey = Normalize-KnowledgeToken $entry.key
        $authority = if ($entry.authority) { $entry.authority.ToString().Trim().ToLowerInvariant() } else { "generated" }
        $confidence = if ($entry.confidence) { $entry.confidence.ToString().Trim().ToLowerInvariant() } else { "" }

        switch ($authority) {
            "authoritative" {
                $score += 2
                $reasons += "authoritative guide"
            }
            "reviewed" {
                $score += 1
                $reasons += "reviewed guide"
            }
            "generated" {
                $reasons += "generated draft; verify before treating as source of truth"
            }
            default {
                $reasons += "unknown authority '$authority'; validate before use"
            }
        }

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

        $isValidationCapabilities = ($entry.key -eq "validation-capabilities" -or $entry.guide -eq "build/validation-capabilities.yml")

        if ($stageName -eq "validation" -and $entry.key -eq "validation-matrix") {
            $score += 4
            $reasons += "validation stage"
        }
        if ($isTestPlanningStage -and $isValidationCapabilities) {
            $score += 5
            $reasons += "test planning capability matrix"
        }
        if ($hasTestPlanningTerms) {
            if ($isValidationCapabilities) {
                $score += 4
                $reasons += "API/E2E test planning"
            }
        }
        if ($stageName -eq "plan" -and $entry.category -eq "workspace") {
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
            $ranked += [PSCustomObject][ordered]@{
                score = $score
                path = Get-KnowledgeDisplayPath -Guide $entry.guide
                category = $entry.category
                key = $entry.key
                authority = $authority
                confidence = $confidence
                reason = (($reasons | Select-Object -Unique) -join "; ")
                matched_tags = @($matchedTags | Select-Object -Unique)
            }
        }
    }

    if ($isTestPlanningStage) {
        $capabilityEntry = @($entries | Where-Object { $_.guide -eq "build/validation-capabilities.yml" -or $_.key -eq "validation-capabilities" } | Select-Object -First 1)
        if ($capabilityEntry.Count -gt 0) {
            $capabilityPath = Get-KnowledgeDisplayPath -Guide $capabilityEntry[0].guide
            if (-not @($ranked | Where-Object { $_.path -eq $capabilityPath })) {
                $ranked += [PSCustomObject][ordered]@{
                    score = 9
                    path = $capabilityPath
                    category = $capabilityEntry[0].category
                    key = $capabilityEntry[0].key
                    authority = if ($capabilityEntry[0].authority) { $capabilityEntry[0].authority.ToString().Trim().ToLowerInvariant() } else { "generated" }
                    confidence = if ($capabilityEntry[0].confidence) { $capabilityEntry[0].confidence.ToString().Trim().ToLowerInvariant() } else { "" }
                    reason = "test planning capability matrix"
                    matched_tags = @()
                }
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
            authority = $_.authority
            confidence = $_.confidence
            reason = $_.reason
            matched_tags = $_.matched_tags
        }
    })
    if ($selected.Count -eq 0) {
        $result.hints += "no knowledge guide matched deterministic routing fields; keep default context only"
    }
    if (@($selected | Where-Object { $_.authority -eq "generated" }).Count -gt 0) {
        $result.hints += "Generated guides are bootstrap material; keep final judgments grounded in source evidence or reviewed guides."
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
    $invalidAuthorities = @()
    $generatedGuides = @()
    $validAuthorities = @("generated", "reviewed", "authoritative")
    $forbiddenPatterns = @(
        "[A-Za-z]:\\",
        "(^|[\\/])Users[\\/][^\\/]+"
    )

    foreach ($entry in $entries) {
        $authority = if ($entry.authority) { $entry.authority.ToString().Trim().ToLowerInvariant() } else { "generated" }
        if ($validAuthorities -notcontains $authority) {
            $invalidAuthorities += "$($entry.category).$($entry.key): $authority"
        }

        if (-not $entry.guide) {
            $missingGuides += "$($entry.category).$($entry.key) has no guide"
            continue
        }
        if ($authority -eq "generated") {
            $generatedGuides += "$($entry.category).$($entry.key): $($entry.guide)"
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
    if ($invalidAuthorities.Count -gt 0) {
        Set-Blocked $result ("knowledge index entries use invalid authority values: " + (($invalidAuthorities | Select-Object -Unique) -join ", "))
    }

    $result.facts.index = $indexPath
    $result.facts.guide_count = @($entries | Where-Object { $_.guide }).Count
    $result.facts.missing_guides = @($missingGuides | Select-Object -Unique)
    $result.facts.absolute_path_offenders = @($absolutePathOffenders | Select-Object -Unique)
    $result.facts.oversized_guides = @($oversizedGuides | Select-Object -Unique)
    $result.facts.unknown_repositories = @($unknownRepos | Select-Object -Unique)
    $result.facts.invalid_authorities = @($invalidAuthorities | Select-Object -Unique)
    $result.facts.generated_guides = @($generatedGuides | Select-Object -Unique)
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

    $retrospectiveGate = [ordered]@{
        checked = $false
        gate_status = "not_checked"
        status = ""
        workflow_record = ""
        improvement_candidates = ""
        knowledge_candidates = ""
        workflow_observation = ""
    }
    if ($Stage -eq "commit") {
        $retrospectiveGate.checked = $true
        $retrospectiveGate.gate_status = "ok"
        $workflowStatePath = Join-Path $FeatureDir "workflow-state.json"
        if (-not (Test-Path -LiteralPath $workflowStatePath)) {
            $retrospectiveGate.gate_status = "blocked"
            Set-Blocked $result "workflow-state.json missing; commit requires completed retrospective state"
        } else {
            try {
                $workflowState = Get-Content -LiteralPath $workflowStatePath -Raw | ConvertFrom-Json
                $retroState = $workflowState.retrospective
                if ($null -eq $retroState) {
                    $retrospectiveGate.gate_status = "blocked"
                    Set-Blocked $result "workflow-state.json missing retrospective state"
                } else {
                    $retrospectiveGate.status = [string]$retroState.status
                    $retrospectiveGate.workflow_record = [string]$retroState.workflow_record
                    $retrospectiveGate.improvement_candidates = [string]$retroState.improvement_candidates
                    $retrospectiveGate.knowledge_candidates = [string](Get-ObjectPropertyValue -Object $retroState -PropertyName "knowledge_candidates")
                    $retrospectiveGate.workflow_observation = [string](Get-ObjectPropertyValue -Object $retroState -PropertyName "workflow_observation")
                    if ($retrospectiveGate.status -ne "completed") {
                        $retrospectiveGate.gate_status = "blocked"
                        Set-Blocked $result "retrospective.status must be completed before commit"
                    }
                    if ([string]::IsNullOrWhiteSpace($retrospectiveGate.workflow_record)) {
                        $retrospectiveGate.gate_status = "blocked"
                        Set-Blocked $result "retrospective.workflow_record must reference workflow-record.md before commit"
                    }
                    if ([string]::IsNullOrWhiteSpace($retrospectiveGate.improvement_candidates)) {
                        $retrospectiveGate.gate_status = "blocked"
                        Set-Blocked $result "retrospective.improvement_candidates must reference improvement-candidates.md before commit"
                    }
                    if ([string]::IsNullOrWhiteSpace($retrospectiveGate.knowledge_candidates)) {
                        $retrospectiveGate.gate_status = "blocked"
                        Set-Blocked $result "retrospective.knowledge_candidates must reference knowledge-candidates.md before commit"
                    }
                }
            }
            catch {
                $retrospectiveGate.gate_status = "blocked"
                Set-Blocked $result "workflow-state.json is not valid JSON"
            }
        }

        $testPlanGate = Invoke-ValidateTestPlan
        $result.facts.test_plan_gate = $testPlanGate.facts
        if ($testPlanGate.status -eq "blocked") {
            foreach ($blocker in @($testPlanGate.blockers)) {
                Set-Blocked $result $blocker
            }
        }

        $aiAcceptanceGate = Invoke-ValidateAiSelfAcceptance
        $result.facts.ai_self_acceptance_gate = $aiAcceptanceGate.facts
        if ($aiAcceptanceGate.status -eq "blocked") {
            foreach ($blocker in @($aiAcceptanceGate.blockers)) {
                Set-Blocked $result $blocker
            }
        }
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
    $result.facts.retrospective_gate = $retrospectiveGate
    return $result
}

function Invoke-ValidateGeneratedContext {
    $result = New-Result "validate-generated-context"
    $canonicalContextFile = "AGENTS.md"
    $internalSkillsDir = ".agents/spec-kit/skills"
    $workflowPath = "spec-kit/workflows/speckit/workflow.yml"
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $workflowPath)) -and
        (Test-Path -LiteralPath (Join-Path $RepoRoot ".specify/workflows/speckit/workflow.yml"))) {
        $workflowPath = ".specify/workflows/speckit/workflow.yml"
    }
    $knowledgeLockPath = Join-Path $RepoRoot ".specify/knowledge/lock.yml"
    $repositoryMapPhrases = @("Project Path Categories", "CDP target inventory", "Do not write machine-specific absolute paths here")
    if (-not (Test-Path -LiteralPath $knowledgeLockPath -PathType Leaf)) {
        $repositoryMapPhrases += "<workspace-root>/FrontendPlugin/<plugin-id>/"
    }
    $checks = @()
    $checks += @(
        [ordered]@{
            path = $canonicalContextFile
            phrases = @("Project Path Categories", "source-to-runtime copy", "best-effort self-validation", "direct runtime replacement", "host CDP validation", "ensure-host-cdp", "stale/current-feature hint", "read the current plan only", "select-knowledge", "select-gates", "validate-knowledge-index", "validate-context-budget", "inspect-validation-capabilities", "inspect-workflow-closure", "knowledge-candidates.md")
        },
        [ordered]@{
            path = ".specify/memory/repository-map.md"
            phrases = $repositoryMapPhrases
        },
        [ordered]@{
            path = ".specify/templates/layer-manifest.yml"
            phrases = @("stage_gates:", "read_strategies:", "Knowledge", "gate_routing", "select-gates", "validate-context-budget", "validate-knowledge-index", "checklists/implementation-readiness.md")
        },
        [ordered]@{
            path = "ai/workflows/task-routing.md"
            phrases = @("tasks -> analyze -> checklist", "skill-routing.yml", "validate-generated-context", "validate-knowledge-index", "validate-context-budget", "select-knowledge", "select-gates", "artifact_sections", "Stage Continuation", "Final Response Guard", "inspect-workflow-closure", "workflow-observer", "promote-candidates", "inspect-host-cdp-target", "ensure-host-cdp", "capture-cdp-screenshot", "do not apply stale feature risk flags")
        },
        [ordered]@{
            path = "ai/workflows/skill-routing.yml"
            phrases = @("internal_skill_root", ".agents/spec-kit/skills", "load_only_selected_skill", "speckit-fact-layer", "speckit-test-plan", "speckit-quality-vision", "speckit-acceptance-rubric", "speckit-ai-self-acceptance", "speckit-workflow-observer", "speckit-promote-knowledge", "commit-message")
        },
        [ordered]@{
            path = "ai/rules/ai-coding-rules.md"
            phrases = @("Generated Context Drift", "analysis.md", "validate-generated-context", "validate-knowledge-index", "Stage Continuation Contract", "Host Frontend Delivery Chain", "ensure-host-cdp", "Retrospective", "inspect-workflow-closure", "knowledge-candidates.md")
        },
        [ordered]@{
            path = $workflowPath
            phrases = @("id: retrospective", "id: workflow-observer", "id: commit", "Require workflow-record.md", "knowledge-candidates.md", "workflow-observation.md", "automatic_stage_continuation", "post_human_acceptance_closure", "promote_knowledge_candidates", "inspect-host-cdp-target", "ensure-host-cdp", "capture-cdp-screenshot", "validate-knowledge-index", "validate-context-budget", "select-gates", "current-feature state only")
        },
        [ordered]@{
            path = "spec-kit/TEAM-README.md"
            optional = $true
            phrases = @("source edit -> frontend build -> direct runtime replacement -> real host CDP verification", "select-knowledge", "select-gates", "validate-context-budget", "full-text/BM25 search")
        }
    )
    if (Test-Path -LiteralPath $knowledgeLockPath -PathType Leaf) {
        $checks += [ordered]@{
            path = ".specify/knowledge/lock.yml"
            phrases = @("generated_by: `"compose-knowledge-packs`"", "materialized: `"ai/knowledge`"", "packs:", "aliases_applied:")
        }
    }
    $checks += [ordered]@{
        path = ".agents/skills/speckit-specify/SKILL.md"
        phrases = @("Internal Stage Loading", ".agents/spec-kit/skills/speckit-<stage>/SKILL.md", "Do not pre-load")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-commit/SKILL.md"
        phrases = @("validate-feature-artifacts", "Stage commit", "workflow-record.md", "improvement-candidates.md", "retrospective.status")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-implement/SKILL.md"
        phrases = @("ensure-host-cdp", "CDP host recovery ladder", "manual acceptance", "select-gates")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-retrospective/SKILL.md"
        phrases = @("Existing Constraint Audit", "AI workflow self-check", "Team knowledge candidates", "knowledge-candidates.md", "workflow-observer-packet.json", "retrospective.status")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-tasks/SKILL.md"
        phrases = @("Run mandatory", "speckit.retrospective", "after quick acceptance and before", "optional test-hardening")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-test-plan/SKILL.md"
        phrases = @("API/E2E", "select-knowledge", "approved-by-ai-obvious", "needs-human-review")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-quality-vision/SKILL.md"
        phrases = @("quality-vision.md", "UI Baseline", "needs-human-baseline", "owner-approved-n/a")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-acceptance-rubric/SKILL.md"
        phrases = @("acceptance-rubric.md", "Essential", "Pitfall", "L1", "L4")
    }
    $checks += [ordered]@{
        path = "$internalSkillsDir/speckit-ai-self-acceptance/SKILL.md"
        phrases = @("AI Self-Acceptance", "PASS", "FAIL", "BLOCKED", "CDP", "console", "logs", "cdp-screenshots")
    }
    $checks += [ordered]@{
        path = ".specify/templates/acceptance-rubric-template.md"
        source_path = "spec-kit/templates/acceptance-rubric-template.md"
        phrases = @("Layer weights for actual workflow scoring", "workflow_score", "Actual Workflow Rubric Audit", "AI acceptance decision", "Human acceptance readiness")
    }
    $checks += [ordered]@{
        path = ".specify/templates/checklist-template.md"
        source_path = "spec-kit/templates/checklist-template.md"
        phrases = @("next_required_human_action", "CHK010N", "runtime 替换目录")
    }

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
        $sourcePath = $null
        $sourceHash = $null
        $actualHash = $null
        if ($check.Contains("source_path")) {
            $sourcePath = Join-Path $RepoRoot $check.source_path
            if (Test-Path -LiteralPath $sourcePath) {
                $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
                $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($sourceHash -ne $actualHash) {
                    Set-Blocked $result ($check.path + " differs from source template " + $check.source_path)
                }
            } else {
                $result.hints += "source template missing; skipped exact generated-template drift check: $($check.source_path)"
            }
        }
        $details += [ordered]@{
            path = $check.path
            exists = $true
            missing_phrases = $missingPhrases
            source_path = $check.source_path
            source_hash = $sourceHash
            actual_hash = $actualHash
            source_equal = if ($null -eq $sourceHash) { $null } else { $sourceHash -eq $actualHash }
        }
        if ($missingPhrases.Count -gt 0) {
            Set-Blocked $result ($check.path + " missing required generated-context phrases: " + ($missingPhrases -join ", "))
        }
    }

    $requiredRuntimeScripts = @(
        "select-gates.ps1",
        "inspect-workspace-repositories.ps1",
        "validate-test-plan.ps1",
        "validate-ai-self-acceptance.ps1",
        "inspect-plugin-build-plan.ps1",
        "validate-plugin-package.ps1",
        "post-commit-self-check.ps1",
        "validate-rubric-score.ps1",
        "inspect-workflow-closure.ps1",
        "collect-workflow-observer-packet.ps1",
        "promote-knowledge-candidates.ps1",
        "cleanup-host-cdp.ps1",
        "capture-cdp-screenshot.ps1",
        "cdp-common.ps1",
        "validate-context-budget.ps1",
        "sync-native-runtime-artifacts.ps1",
        "validate-rpc-proto-bundle.ps1"
    )
    $runtimeScriptDetails = @()
    foreach ($scriptName in $requiredRuntimeScripts) {
        $rel = ".specify/scripts/powershell/$scriptName"
        $path = Join-Path $RepoRoot $rel
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        $runtimeScriptDetails += [ordered]@{ path = $rel; exists = $exists }
        if (-not $exists) {
            Set-Blocked $result ("runtime script missing: " + $rel)
        }
    }

    $result.facts.repo_root = $RepoRoot
    $result.facts.checked = $details
    $result.facts.runtime_scripts = $runtimeScriptDetails
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
        $matches = [regex]::Matches($text, "(?im)^\s*[^:\r\n]+:\s*$state\b")
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
    $rulesDir = Join-Path $RepoRoot "spec-kit/checklist-rules"
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
    $required = @("Implementation Slices", "write scope", "forbidden scope", "stop conditions")
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
    $corePack = Join-Path $RepoRoot "spec-kit/.venv/Lib/site-packages/specify_cli/core_pack"
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
        foreach ($field in @("attempts", "validations", "fact_layer", "acceptance", "retrospective", "promotion", "commit", "post_commit_self_check", "rubric_score")) {
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

function Get-WorkspaceRepositoryEntries {
    $workspaceFile = Join-Path $RepoRoot ".specify/workspace.yml"
    if (-not (Test-Path -LiteralPath $workspaceFile -PathType Leaf)) {
        return @()
    }

    $workspaceRoot = $RepoRoot
    $text = Get-Content -LiteralPath $workspaceFile -Raw
    $rootMatch = [regex]::Match($text, "(?m)^\s*root:\s*['""]?(.+?)['""]?\s*$")
    if ($rootMatch.Success) {
        $rootValue = $rootMatch.Groups[1].Value.Trim().Trim('"').Trim("'")
        $workspaceRoot = if ([System.IO.Path]::IsPathRooted($rootValue)) { $rootValue } else { Join-Path $RepoRoot $rootValue }
        if (Test-Path -LiteralPath $workspaceRoot) {
            $workspaceRoot = (Resolve-Path -LiteralPath $workspaceRoot).Path
        }
    }

    $repos = @()
    $current = $null
    foreach ($line in Get-Content -LiteralPath $workspaceFile) {
        if ($line -match '^\s*-\s*name:\s*"?([^"]+)"?\s*$') {
            if ($current) { $repos += [PSCustomObject]$current }
            $current = @{ name = $Matches[1].Trim("'`""); path = ""; role = ""; required = $false; participates_in_spec_branches = $true }
        } elseif ($current -and $line -match '^\s*path:\s*"?([^"]+)"?\s*$') {
            $current.path = $Matches[1].Trim("'`"")
        } elseif ($current -and $line -match '^\s*role:\s*"?([^"]+)"?\s*$') {
            $current.role = $Matches[1].Trim("'`"")
        } elseif ($current -and $line -match '^\s*required:\s*(true|false)\s*$') {
            $current.required = ($Matches[1] -eq "true")
        } elseif ($current -and $line -match '^\s*participates_in_spec_branches:\s*(true|false)\s*$') {
            $current.participates_in_spec_branches = ($Matches[1] -eq "true")
        }
    }
    if ($current) { $repos += [PSCustomObject]$current }

    return @($repos | ForEach-Object {
        $repoPath = if ([System.IO.Path]::IsPathRooted($_.path)) { $_.path } else { Join-Path $workspaceRoot $_.path }
        [PSCustomObject]@{
            name = $_.name
            path = $repoPath
            role = $_.role
            required = [bool]$_.required
            participates_in_spec_branches = [bool]$_.participates_in_spec_branches
        }
    })
}

function Invoke-InspectWorkspaceRepositories {
    $result = New-Result "inspect-workspace-repositories"
    $workspaceFile = Join-Path $RepoRoot ".specify/workspace.yml"
    if (-not (Test-Path -LiteralPath $workspaceFile -PathType Leaf)) {
        Set-Blocked $result ".specify/workspace.yml not found"
        return $result
    }

    $repos = @(Get-WorkspaceRepositoryEntries)
    $details = @()
    foreach ($repo in $repos) {
        $exists = Test-Path -LiteralPath $repo.path -PathType Container
        $isGit = $false
        if ($exists) {
            $null = git -C $repo.path rev-parse --is-inside-work-tree 2>$null
            $isGit = ($LASTEXITCODE -eq 0)
        }
        $details += [ordered]@{
            name = $repo.name
            path = $repo.path
            role = $repo.role
            required = [bool]$repo.required
            exists = $exists
            is_git = $isGit
            participates_in_spec_branches = [bool]$repo.participates_in_spec_branches
        }
        if ($repo.required -and -not $exists) {
            Set-Blocked $result ("Required repository missing from workspace map: " + $repo.name)
        } elseif ($repo.required -and -not $isGit) {
            Set-Blocked $result ("Required repository is not a git work tree: " + $repo.name)
        }
    }

    $result.facts.workspace_file = $workspaceFile
    $result.facts.repositories = $details
    $result.facts.required_missing = @($details | Where-Object { $_.required -and -not $_.exists } | ForEach-Object { $_.name })
    $result.facts.required_not_git = @($details | Where-Object { $_.required -and $_.exists -and -not $_.is_git } | ForEach-Object { $_.name })
    if ($result.status -eq "blocked") {
        $result.hints += "Do not scan other repositories to guess missing implementation ownership; fix workspace checkout/map first."
    }
    return $result
}

function Invoke-ValidateTestPlan {
    $result = New-Result "validate-test-plan"
    $planPath = Join-Path $FeatureDir "plan.md"
    if (-not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
        Set-Blocked $result "plan.md not found"
        return $result
    }

    $text = Get-Content -LiteralPath $planPath -Raw
    $hasTestPlanSection = ($text -match "(?im)^##\s+测试用例计划\b")
    $hasApiPlan = ($text -match "(?i)\bAPI\b|接口|interface|contract")
    $hasE2ePlanOrNa = ($text -match "(?i)\bE2E\b|端到端|interface\s+flow|N/A|不适用|unsupported|未支持")
    $hasReviewStatus = ($text -match "(?i)approved-by-ai-obvious|needs-human-review|human-reviewed|review\s*status|评审状态|reviewed|已确认|N/A")

    if (-not $hasTestPlanSection) { Set-Blocked $result "plan.md missing ## 测试用例计划 section" }
    if (-not $hasApiPlan) { Set-Blocked $result "API/interface test plan row or explicit API validation plan is required" }
    if (-not $hasE2ePlanOrNa) { Set-Blocked $result "E2E/interface-flow plan or explicit N/A reason is required" }
    if (-not $hasReviewStatus) { Set-Blocked $result "test plan review status is required: approved-by-ai-obvious, needs-human-review, human-reviewed, or N/A with reason" }

    $result.facts.plan = $planPath
    $result.facts.has_test_plan_section = $hasTestPlanSection
    $result.facts.has_api_plan = $hasApiPlan
    $result.facts.has_e2e_plan_or_na = $hasE2ePlanOrNa
    $result.facts.has_review_status = $hasReviewStatus
    return $result
}

function Invoke-ValidateAiSelfAcceptance {
    $result = New-Result "validate-ai-self-acceptance"
    $validationPath = Join-Path $FeatureDir "validation.md"
    if (-not (Test-Path -LiteralPath $validationPath -PathType Leaf)) {
        Set-Blocked $result "validation.md not found"
        return $result
    }

    $text = Get-Content -LiteralPath $validationPath -Raw
    $hasSection = ($text -match "(?i)AI\s+Self-Acceptance|AI\s+Acceptance\s+Result|AI\s+自验|AI\s+验收")
    $isPass = ($text -match "(?i)AI\s+(Self-)?Acceptance[^#\r\n]*(PASS)|AI\s+Self-Acceptance\s*[:：]\s*PASS|AI\s+Acceptance\s+Result\s*[:：]\s*PASS")
    if (-not $hasSection) {
        Set-Blocked $result "validation.md missing AI Self-Acceptance result"
    } elseif (-not $isPass) {
        Set-Blocked $result "AI Self-Acceptance must be PASS before human acceptance or commit"
    }

    $result.facts.validation = $validationPath
    $result.facts.has_ai_self_acceptance = $hasSection
    $result.facts.pass = $isPass
    return $result
}

function Invoke-InspectPluginBuildPlan {
    $result = New-Result "inspect-plugin-build-plan"
    $candidates = @()
    $packageFiles = @(
        (Join-Path $RepoRoot "package.json"),
        (Join-Path $RepoRoot "HostApplication/HostApplication/package.json")
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }

    foreach ($packageFile in $packageFiles) {
        try {
            $package = Get-Content -LiteralPath $packageFile -Raw | ConvertFrom-Json
        } catch {
            $result.unknowns += "package.json could not be parsed: $packageFile"
            continue
        }
        if (-not $package.scripts) { continue }
        foreach ($property in @($package.scripts.PSObject.Properties)) {
            $scriptText = [string]$property.Value
            if ($property.Name -match "(?i)plugin|package" -or $scriptText -match "(?i)\.plugin|plugin-out|build-builtin-plugins|plugin") {
                $commandRoot = Split-Path -Parent $packageFile
                $candidates += [ordered]@{
                    package_json = $packageFile
                    command_root = $commandRoot
                    script = $property.Name
                    command = "npm run $($property.Name)"
                    value = $scriptText
                }
            }
        }
    }

    $result.facts.candidates = $candidates
    $result.facts.policy = "All plugin types require final .plugin build/package evidence; source build/export is only a prerequisite or fallback."
    if ($candidates.Count -eq 0) {
        Set-Warning $result "No deterministic plugin package script found; use repository-map Project Path Categories and host packaging docs before manual search."
    }
    return $result
}

function Invoke-ValidatePluginPackage {
    $result = New-Result "validate-plugin-package"
    if (-not $PackagePath) {
        Set-Blocked $result "PackagePath is required and must point to a .plugin artifact"
        return $result
    }

    $resolvedPackage = if ([System.IO.Path]::IsPathRooted($PackagePath)) { $PackagePath } else { Join-Path $RepoRoot $PackagePath }
    $exists = Test-Path -LiteralPath $resolvedPackage -PathType Leaf
    $isPlugin = ([System.IO.Path]::GetExtension($resolvedPackage) -eq ".plugin")
    if (-not $exists) { Set-Blocked $result "plugin package artifact not found: $resolvedPackage" }
    if (-not $isPlugin) { Set-Blocked $result "plugin package artifact must use .plugin extension: $resolvedPackage" }

    $result.facts.package_path = $resolvedPackage
    $result.facts.exists = $exists
    $result.facts.extension = [System.IO.Path]::GetExtension($resolvedPackage)
    if ($exists) {
        $item = Get-Item -LiteralPath $resolvedPackage
        $result.facts.bytes = $item.Length
        $result.facts.sha256 = (Get-FileHash -LiteralPath $resolvedPackage -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $result.facts.policy = "All frontend/native/JS/plugin integration changes require .plugin package validation evidence before complete-branch."
    return $result
}

function Invoke-PostCommitSelfCheck {
    $result = New-Result "post-commit-self-check"
    if (-not (Test-Path -LiteralPath $FeatureDir -PathType Container)) {
        Set-Blocked $result "FeatureDir not found"
        return $result
    }

    $requiredFiles = @("validation.md", "acceptance.md", "workflow-record.md", "improvement-candidates.md", "knowledge-candidates.md", "workflow-observation.md", "workflow-state.json")
    $missing = @()
    foreach ($fileName in $requiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $FeatureDir $fileName) -PathType Leaf)) {
            $missing += $fileName
        }
    }
    foreach ($fileName in $missing) {
        Set-Blocked $result "post-commit self-check missing required artifact: $fileName"
    }

    $statePath = Join-Path $FeatureDir "workflow-state.json"
    $retrospectiveStatus = ""
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            if ($state.retrospective -and ($state.retrospective.PSObject.Properties.Name -contains "status")) {
                $retrospectiveStatus = [string]$state.retrospective.status
            }
        } catch {
            Set-Blocked $result "workflow-state.json is not valid JSON"
        }
    }
    if ($retrospectiveStatus -ne "completed") {
        Set-Blocked $result "retrospective.status must be completed before post-commit self-check"
    }

    $result.facts.feature_dir = $FeatureDir
    $result.facts.required_files = $requiredFiles
    $result.facts.missing = $missing
    $result.facts.retrospective_status = $retrospectiveStatus
    $result.facts.single_pass = $true
    $result.facts.amend_required = $false
    $result.hints += "If this single self-check makes deterministic fixes, amend the commit once, then score rubric without running another self-check."
    return $result
}

function Get-RubricScore {
    param([string]$Text, [string]$Key)
    foreach ($line in ($Text -split "\r?\n")) {
        if ($line -notmatch "(?i)^\s*\|?\s*$Key\b") { continue }
        $candidateScores = @()
        foreach ($cell in ($line -split "\|")) {
            $trimmed = $cell.Trim()
            if ($trimmed -match "^\d{1,3}(?:\.\d+)?$") {
                $value = [double]$trimmed
                if ($value -eq 0 -or $value -gt 1) {
                    $candidateScores += [int][Math]::Round($value)
                }
            }
        }
        if ($candidateScores.Count -gt 0) {
            return [int]$candidateScores[-1]
        }
    }

    $patterns = @(
        "(?im)^\s*\|\s*$Key\b[^|]*\|\s*(\d{1,3})\s*\|",
        "(?im)^\s*$Key\b[^0-9\r\n]*(\d{1,3})\b"
    )
    foreach ($pattern in $patterns) {
        $match = [regex]::Match($Text, $pattern)
        if ($match.Success) { return [int]$match.Groups[1].Value }
    }
    return $null
}

function Invoke-ValidateRubricScore {
    $result = New-Result "validate-rubric-score"
    $path = $RubricPath
    if (-not $path) {
        $path = Join-Path $FeatureDir "rubric-score.md"
    }
    $resolvedPath = if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $RepoRoot $path }
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        Set-Blocked $result "rubric-score.md not found; final rubric must be generated after post-commit self-check"
        $result.facts.rubric_path = $resolvedPath
        return $result
    }

    $text = Get-Content -LiteralPath $resolvedPath -Raw
    $scores = [ordered]@{}
    foreach ($key in @("L1", "L2", "L3", "L4", "L5")) {
        $score = Get-RubricScore -Text $text -Key $key
        $scores[$key] = $score
        if ($null -eq $score) {
            Set-Blocked $result "rubric missing dimension score: $key"
        } elseif ($score -lt 80 -and $text -notmatch "(?i)$key[\s\S]{0,240}(accepted gap|owner accepted|user accepted|用户.*接受|owner.*接受)") {
            Set-Blocked $result "rubric dimension $key is below 80 without accepted-gap owner evidence"
        }
    }

    $overall = $null
    $overallMatch = [regex]::Match($text, "(?im)(Overall\s+Weighted\s+Score|总分|weighted_total|workflow_score)[^0-9\r\n]*(\d{1,3}(?:\.\d+)?)")
    if ($overallMatch.Success) {
        $overall = [double]$overallMatch.Groups[2].Value
    } elseif ($scores.Values -notcontains $null) {
        $overall = [Math]::Round(
            ([double]$scores["L1"] * 0.30) +
            ([double]$scores["L2"] * 0.25) +
            ([double]$scores["L3"] * 0.25) +
            ([double]$scores["L4"] * 0.10) +
            ([double]$scores["L5"] * 0.10),
            2
        )
    }

    if ($null -eq $overall) {
        Set-Blocked $result "rubric missing Overall Weighted Score / 总分"
    } elseif ($overall -lt 90) {
        Set-Blocked $result "rubric total score is below 90"
    }

    $hardGateFailed = ($text -match "(?i)hard\s*gate[^#\r\n]*(fail|failed|blocked)|硬门禁[^#\r\n]*(失败|未通过|blocked|FAIL)")
    $hardGatePassed = ($text -match "(?i)hard\s*gate[^#\r\n]*(pass|passed)|硬门禁[^#\r\n]*(通过|PASS)")
    if ($hardGateFailed) {
        Set-Blocked $result "rubric hard gate conclusion failed"
    }
    if (-not $hardGatePassed) {
        Set-Blocked $result "rubric must include hard gate PASS conclusion"
    }

    foreach ($phrase in @("evidence", "证据", "扣分", "complete-branch")) {
        if ($text -notmatch [regex]::Escape($phrase)) {
            Set-Blocked $result "rubric output missing required content: $phrase"
        }
    }

    $result.facts.rubric_path = $resolvedPath
    $result.facts.scores = $scores
    $result.facts.overall_weighted_score = $overall
    $result.facts.hard_gate_passed = ($hardGatePassed -and -not $hardGateFailed)
    $result.facts.complete_branch_allowed = ($result.status -eq "ok")
    return $result
}

function Get-WorkflowPolicyFacts {
    $workspacePath = Join-Path $RepoRoot ".specify/workspace.yml"
    $policy = [ordered]@{
        workspace_file = $workspacePath
        local_only = $null
        push_remote = $null
        complete_by_cherry_picking_to_base = $null
        closure_exemption = $false
        rule = "local branch and push policy never exempts retrospective, post-commit self-check, or rubric-score"
    }
    if (-not (Test-Path -LiteralPath $workspacePath -PathType Leaf)) {
        return $policy
    }
    $text = Get-Content -LiteralPath $workspacePath -Raw
    foreach ($key in @("local_only", "push_remote", "complete_by_cherry_picking_to_base")) {
        $match = [regex]::Match($text, "(?m)^\s*$key\s*:\s*(true|false)\s*$")
        if ($match.Success) {
            $policy[$key] = ($match.Groups[1].Value -eq "true")
        }
    }
    return $policy
}

function Invoke-InspectWorkflowClosure {
    $result = New-Result "inspect-workflow-closure"
    $resolvedFeatureDir = Resolve-FeatureDirPath $FeatureDir
    $result.facts.repo_root = $RepoRoot
    $result.facts.feature_dir = $resolvedFeatureDir
    $result.facts.stage = if ($Stage) { $Stage } else { "final-response" }
    $result.facts.branch_policy = Get-WorkflowPolicyFacts

    if (-not (Test-Path -LiteralPath $resolvedFeatureDir -PathType Container)) {
        Set-Blocked $result "FeatureDir not found"
        $result.facts.next_required_stage = "speckit.specify"
        $result.facts.missing_artifacts = @("feature directory")
        return $result
    }

    $statePath = Join-Path $resolvedFeatureDir "workflow-state.json"
    $state = Read-JsonObject $statePath
    if ((Test-Path -LiteralPath $statePath -PathType Leaf) -and $null -eq $state) {
        Set-Blocked $result "workflow-state.json is not valid JSON"
    }

    $deliveryProfile = $DeliveryProfile
    if (-not $deliveryProfile -and $state) {
        $workflowModel = Get-ObjectPropertyValue -Object $state -PropertyName "workflow_model"
        if ($workflowModel) {
            $deliveryProfile = [string](Get-ObjectPropertyValue -Object $workflowModel -PropertyName "delivery_profile")
        }
    }

    $artifacts = [ordered]@{}
    foreach ($name in @(
        "validation.md",
        "acceptance.md",
        "workflow-record.md",
        "improvement-candidates.md",
        "knowledge-candidates.md",
        "workflow-observation.md",
        "post-commit-self-check.md",
        "rubric-score.md",
        "workflow-state.json",
        "investigation.md",
        "fact-pack.md",
        "commit-record.md",
        "commit.md"
    )) {
        $artifacts[$name] = Test-Path -LiteralPath (Join-Path $resolvedFeatureDir $name) -PathType Leaf
    }

    $acceptanceStatus = Get-WorkflowStateStatus -State $state -NodeName "acceptance"
    if (-not $acceptanceStatus) {
        if (Test-TextAcceptancePassed -Path (Join-Path $resolvedFeatureDir "acceptance.md")) {
            $acceptanceStatus = "passed"
        } elseif ($artifacts["acceptance.md"]) {
            $acceptanceStatus = "artifact-present"
        } else {
            $acceptanceStatus = "missing"
        }
    }

    $retrospectiveStatus = Get-WorkflowStateStatus -State $state -NodeName "retrospective"
    if (-not $retrospectiveStatus) {
        $retrospectiveStatus = if ($artifacts["workflow-record.md"] -or $artifacts["improvement-candidates.md"]) { "artifact-present" } else { "missing" }
    }

    $postCommitStatus = Get-WorkflowStateStatus -State $state -NodeName "post_commit_self_check"
    if (-not $postCommitStatus) {
        $postCommitStatus = if ($artifacts["post-commit-self-check.md"]) { "completed" } else { "missing" }
    }

    $commitStatus = Get-WorkflowStateStatus -State $state -NodeName "commit"
    $commitNode = Get-ObjectPropertyValue -Object $state -PropertyName "commit"
    $commitHash = ""
    if ($commitNode) {
        $commitHash = [string](Get-ObjectPropertyValue -Object $commitNode -PropertyName "commit_hash")
    }
    $commitDetected = (
        $commitStatus -eq "completed" -or
        -not [string]::IsNullOrWhiteSpace($commitHash) -or
        $artifacts["commit-record.md"] -or
        $artifacts["commit.md"] -or
        $artifacts["post-commit-self-check.md"] -or
        $artifacts["rubric-score.md"]
    )
    if (-not $commitStatus) {
        $commitStatus = if ($commitDetected) { "completed" } else { "missing" }
    }

    $rubricStatus = Get-WorkflowStateStatus -State $state -NodeName "rubric_score"
    $rubricValidation = $null
    if ($artifacts["rubric-score.md"]) {
        $oldRubricPath = $RubricPath
        $script:RubricPath = Join-Path $resolvedFeatureDir "rubric-score.md"
        $rubricValidation = Invoke-ValidateRubricScore
        $script:RubricPath = $oldRubricPath
        $rubricStatus = if ($rubricValidation.status -eq "ok") { "completed" } else { "blocked" }
    } elseif (-not $rubricStatus) {
        $rubricStatus = "missing"
    }

    $missingArtifacts = @()
    foreach ($entry in $artifacts.GetEnumerator()) {
        if (-not $entry.Value -and $entry.Key -in @(
            "workflow-record.md",
            "improvement-candidates.md",
            "knowledge-candidates.md",
            "workflow-observation.md",
            "post-commit-self-check.md",
            "rubric-score.md"
        )) {
            $missingArtifacts += $entry.Key
        }
    }

    $workflowRecordExists = [bool]$artifacts["workflow-record.md"]
    $improvementCandidatesExists = [bool]$artifacts["improvement-candidates.md"]
    $knowledgeCandidatesExists = [bool]$artifacts["knowledge-candidates.md"]
    $workflowObservationExists = [bool]$artifacts["workflow-observation.md"]
    $retrospectiveCompleted = (
        $retrospectiveStatus -eq "completed" -and
        $workflowRecordExists -and
        $improvementCandidatesExists -and
        $knowledgeCandidatesExists
    )
    $postCommitCompleted = ($postCommitStatus -eq "completed")
    $closureRequired = (
        $acceptanceStatus -eq "passed" -or
        $commitDetected -or
        $postCommitCompleted -or
        $artifacts["rubric-score.md"]
    )

    $result.facts.delivery_profile = $deliveryProfile
    $result.facts.acceptance_status = $acceptanceStatus
    $result.facts.retrospective_status = if ($retrospectiveCompleted) { "completed" } else { $retrospectiveStatus }
    $result.facts.workflow_observer_status = if ($workflowObservationExists) { "completed" } else { "missing" }
    $result.facts.commit_status = $commitStatus
    $result.facts.commit_detected = [bool]$commitDetected
    $result.facts.post_commit_self_check_status = $postCommitStatus
    $result.facts.rubric_score_status = $rubricStatus
    $result.facts.missing_artifacts = @($missingArtifacts | Select-Object -Unique)
    $result.facts.artifacts = $artifacts
    if ($rubricValidation) {
        $result.facts.rubric_validation = $rubricValidation
    }

    if ($deliveryProfile -eq "validation-only") {
        if (-not $artifacts["validation.md"]) {
            Set-Blocked $result "validation-only closure requires validation.md"
            $result.facts.next_required_stage = "speckit.validation"
        } else {
            $result.facts.next_required_stage = ""
        }
        return $result
    }
    if ($deliveryProfile -eq "blocked-investigation") {
        $hasBlockerRecord = $artifacts["investigation.md"] -or $artifacts["fact-pack.md"]
        if (-not $hasBlockerRecord) {
            Set-Blocked $result "blocked-investigation closure requires investigation.md or fact-pack.md"
            $result.facts.next_required_stage = "speckit.fact-layer"
        } else {
            $result.facts.next_required_stage = ""
        }
        return $result
    }

    $nextRequiredStage = ""
    if ($closureRequired) {
        if (-not $retrospectiveCompleted) {
            $nextRequiredStage = "speckit.retrospective"
            Set-Blocked $result "acceptance or commit detected but retrospective is not completed"
        } elseif (-not $workflowObservationExists) {
            $nextRequiredStage = "speckit.workflow-observer"
            Set-Blocked $result "retrospective completed but workflow-observation.md is missing"
        } elseif (-not $commitDetected) {
            $nextRequiredStage = "speckit.commit"
            Set-Blocked $result "acceptance closure requires commit after retrospective and workflow observer"
        } elseif (-not $postCommitCompleted) {
            $nextRequiredStage = "speckit.post-commit-self-check"
            Set-Blocked $result "commit detected but post-commit self-check is missing"
        } elseif ($rubricStatus -ne "completed") {
            $nextRequiredStage = "speckit.rubric-score"
            if ($rubricStatus -eq "blocked" -and $rubricValidation) {
                foreach ($blocker in @($rubricValidation.blockers)) {
                    Set-Blocked $result $blocker
                }
            } else {
                Set-Blocked $result "post-commit self-check completed but rubric-score.md is missing or invalid"
            }
        }
    }

    $result.facts.next_required_stage = $nextRequiredStage
    if ($result.status -eq "ok") {
        $result.hints += "workflow closure is complete for the inspected stage"
    }
    return $result
}

function Get-WorkflowStageIds {
    $workflowPath = Join-Path $RepoRoot "workflows/speckit/workflow.yml"
    if (-not (Test-Path -LiteralPath $workflowPath -PathType Leaf)) {
        $workflowPath = Join-Path $RepoRoot ".specify/workflows/speckit/workflow.yml"
    }
    if (-not (Test-Path -LiteralPath $workflowPath -PathType Leaf)) {
        return @()
    }
    $ids = @()
    foreach ($line in Get-Content -LiteralPath $workflowPath) {
        if ($line -match "^\s*-\s+id:\s*['""]?([^'""]+)['""]?\s*$") {
            $ids += $Matches[1]
        }
    }
    return $ids
}

function Invoke-CollectWorkflowObserverPacket {
    $result = New-Result "collect-workflow-observer-packet"
    $resolvedFeatureDir = Resolve-FeatureDirPath $FeatureDir
    if (-not (Test-Path -LiteralPath $resolvedFeatureDir -PathType Container)) {
        Set-Blocked $result "FeatureDir not found"
        return $result
    }

    $statePath = Join-Path $resolvedFeatureDir "workflow-state.json"
    $state = Read-JsonObject $statePath
    $stateSummary = [ordered]@{
        exists = Test-Path -LiteralPath $statePath -PathType Leaf
        parseable = $null -ne $state
        acceptance_status = Get-WorkflowStateStatus -State $state -NodeName "acceptance"
        retrospective_status = Get-WorkflowStateStatus -State $state -NodeName "retrospective"
        commit_status = Get-WorkflowStateStatus -State $state -NodeName "commit"
        post_commit_self_check_status = Get-WorkflowStateStatus -State $state -NodeName "post_commit_self_check"
        rubric_score_status = Get-WorkflowStateStatus -State $state -NodeName "rubric_score"
    }

    $artifactNames = @(
        "intake.md",
        "spec.md",
        "plan.md",
        "tasks.md",
        "progress.md",
        "validation.md",
        "evidence.md",
        "fact-pack.md",
        "acceptance.md",
        "acceptance-checklist.md",
        "workflow-record.md",
        "improvement-candidates.md",
        "knowledge-candidates.md",
        "workflow-observation.md",
        "post-commit-self-check.md",
        "rubric-score.md",
        "workflow-state.json"
    )
    $artifacts = [ordered]@{}
    foreach ($name in $artifactNames) {
        $artifacts[$name] = Test-Path -LiteralPath (Join-Path $resolvedFeatureDir $name) -PathType Leaf
    }

    $closure = Invoke-InspectWorkflowClosure
    $changedFiles = @(Get-RepoChangedFiles $RepoRoot)
    $dirty = [ordered]@{
        changed_file_count = $changedFiles.Count
        classified = [ordered]@{
            source = @()
            test = @()
            spec = @()
            generated = @()
            runtime = @()
            temp = @()
            unknown = @()
        }
    }
    foreach ($file in $changedFiles) {
        $kind = Classify-Path $file
        $dirty.classified[$kind] += $file
    }

    $packet = [ordered]@{
        schema_version = "1.0"
        generated_by = "collect-workflow-observer-packet"
        repo_root = $RepoRoot
        feature_dir = Get-RelativeDisplayPath $resolvedFeatureDir
        expected_stage_sequence = Get-WorkflowStageIds
        workflow_state = $stateSummary
        artifacts = $artifacts
        closure_gate = $closure
        dirty_state = $dirty
        context_policy = [ordered]@{
            default_context_only = $true
            does_not_include_source_text = $true
            allowed_reads = @("workflow-observer-packet.json", "workflow.yml", "task-routing.md", "missing feature artifact only when packet points to a gap")
        }
    }

    $packetPath = Join-Path $resolvedFeatureDir "workflow-observer-packet.json"
    $packet | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $packetPath -Encoding UTF8

    $result.facts.packet_path = $packetPath
    $result.facts.feature_dir = $resolvedFeatureDir
    $result.facts.context_bounded = $true
    $result.facts.does_not_include_source_text = $true
    $result.facts.artifacts = $artifacts
    $result.facts.closure_status = $closure.status
    $result.facts.next_required_stage = $closure.facts.next_required_stage
    if ($closure.status -eq "blocked") {
        $result.status = "warning"
        $result.hints += "observer packet collected a blocked closure state; run the reported next_required_stage"
    }
    return $result
}

function Get-MarkdownField {
    param([string]$Block, [string[]]$Names)
    foreach ($name in $Names) {
        $pattern = "(?im)^\s*-\s*" + [regex]::Escape($name) + "\s*[:：]\s*(.*?)\s*$"
        $match = [regex]::Match($Block, $pattern)
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }
    return ""
}

function Get-SafeKnowledgeGuide {
    param([string]$Guide)
    $rawGuide = if ($null -eq $Guide) { "" } else { $Guide }
    $candidate = $rawGuide.Trim().Trim('"').Trim("'") -replace "\\", "/"
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = "workspace/promoted-knowledge.md"
    }
    if ($candidate.StartsWith("ai/knowledge/")) {
        $candidate = $candidate.Substring("ai/knowledge/".Length)
    }
    if ([System.IO.Path]::IsPathRooted($candidate) -or $candidate.StartsWith("/") -or $candidate.Contains("..")) {
        throw "unsafe knowledge guide path: $Guide"
    }
    if (-not $candidate.EndsWith(".md")) {
        $candidate = "$candidate.md"
    }
    return $candidate
}

function Get-PromotionSlug {
    param([string]$Value)
    $slug = ($Value.ToLowerInvariant() -replace "[^a-z0-9]+", "-").Trim("-")
    if (-not $slug) { return "promoted-knowledge" }
    return $slug
}

function Update-KnowledgeIndexForGuide {
    param([string]$IndexPath, [string]$Guide, [string]$Confidence)
    if (-not (Test-Path -LiteralPath $IndexPath -PathType Leaf)) {
        $indexDir = Split-Path $IndexPath -Parent
        New-Item -ItemType Directory -Force -Path $indexDir | Out-Null
        @"
schema_version: "1.1"
purpose: "Project knowledge index."
policy:
  default_context: false
  no_full_text_search_required: true
  repository_map_authority: ".specify/memory/repository-map.md"
  max_selected_guides: 3
promoted:
"@ | Set-Content -LiteralPath $IndexPath -Encoding UTF8
    }

    $indexText = Get-Content -LiteralPath $IndexPath -Raw
    if ($indexText -match [regex]::Escape("guide: `"$Guide`"") -or $indexText -match [regex]::Escape("guide: '$Guide'")) {
        return
    }
    if ($indexText -notmatch "(?m)^promoted:\s*$") {
        Add-Content -LiteralPath $IndexPath -Encoding UTF8 -Value "`npromoted:"
    }
    $key = Get-PromotionSlug ([System.IO.Path]::GetFileNameWithoutExtension($Guide))
    $existing = Get-KnowledgeEntries -IndexPath $IndexPath | Where-Object { $_.key -eq $key }
    if ($existing) {
        $key = "$key-$([Math]::Abs($Guide.GetHashCode()))"
    }
    $entry = @"
  ${key}:
    guide: "$Guide"
    authority: "reviewed"
    confidence: "$Confidence"
    tags: ["promoted-knowledge", "retrospective"]
"@
    Add-Content -LiteralPath $IndexPath -Encoding UTF8 -Value $entry
}

function Invoke-PromoteKnowledgeCandidates {
    $result = New-Result "promote-knowledge-candidates"
    $resolvedFeatureDir = Resolve-FeatureDirPath $FeatureDir
    if (-not (Test-Path -LiteralPath $resolvedFeatureDir -PathType Container)) {
        Set-Blocked $result "FeatureDir not found"
        return $result
    }

    $candidatePath = if ($CandidatesPath) { $CandidatesPath } else { Join-Path $resolvedFeatureDir "knowledge-candidates.md" }
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
        Set-Blocked $result "knowledge-candidates.md not found"
        return $result
    }

    $knowledgeRoot = Join-Path $RepoRoot "ai/knowledge"
    $indexPath = Join-Path $knowledgeRoot "index.yml"
    New-Item -ItemType Directory -Force -Path $knowledgeRoot | Out-Null

    $text = Get-Content -LiteralPath $candidatePath -Raw
    $blocks = @()
    foreach ($piece in [regex]::Split($text, "(?m)^##\s+")) {
        if ([string]::IsNullOrWhiteSpace($piece)) { continue }
        if ($piece -notmatch "(?im)^\s*-\s*(人工审核结论|review_status|审核状态)\s*[:：]") { continue }
        $blocks += $piece
    }

    $promoted = @()
    $skipped = @()
    $candidateNumber = 0
    foreach ($block in $blocks) {
        $candidateNumber += 1
        $review = (Get-MarkdownField -Block $block -Names @("人工审核结论", "review_status", "审核状态")).ToLowerInvariant()
        $titleLine = (($block -split "\r?\n") | Select-Object -First 1).Trim()
        if ($review -ne "approved") {
            $skipped += [ordered]@{
                candidate = $candidateNumber
                title = $titleLine
                review_status = if ($review) { $review } else { "missing" }
                reason = "only approved knowledge candidates can be promoted"
            }
            continue
        }

        $experience = Get-MarkdownField -Block $block -Names @("经验", "lesson")
        $applies = Get-MarkdownField -Block $block -Names @("适用条件", "applies_when")
        $notApplies = Get-MarkdownField -Block $block -Names @("不适用条件", "does_not_apply_when")
        $layer = Get-MarkdownField -Block $block -Names @("推荐知识层", "recommended_layer")
        $guide = Get-MarkdownField -Block $block -Names @("推荐 guide", "recommended_guide", "guide")
        $sourceRefs = Get-MarkdownField -Block $block -Names @("source_refs", "来源证据")
        $confidence = (Get-MarkdownField -Block $block -Names @("置信度", "confidence")).ToLowerInvariant()
        if ($confidence -notin @("low", "medium", "high")) {
            $confidence = "medium"
        }
        $risk = Get-MarkdownField -Block $block -Names @("污染风险", "pollution_risk")

        try {
            $safeGuide = Get-SafeKnowledgeGuide -Guide $guide
        } catch {
            Set-Blocked $result ([string]$_)
            continue
        }
        $guidePath = Join-Path $knowledgeRoot $safeGuide
        $guideDir = Split-Path $guidePath -Parent
        New-Item -ItemType Directory -Force -Path $guideDir | Out-Null

        if (-not (Test-Path -LiteralPath $guidePath -PathType Leaf)) {
            @"
---
authority: reviewed
confidence: $confidence
source_refs:
  - $sourceRefs
---
# Promoted Knowledge

"@ | Set-Content -LiteralPath $guidePath -Encoding UTF8
        }

        $sectionTitle = if ($titleLine) { $titleLine } else { "Candidate $candidateNumber" }
        $entry = @"

## Promoted Knowledge - $sectionTitle
- Type: project-knowledge
- Recommended layer: $layer
- Experience: $experience
- Applies when: $applies
- Does not apply when: $notApplies
- Source refs: $sourceRefs
- Confidence: $confidence
- Pollution risk: $risk
- Review status: approved
"@
        Add-Content -LiteralPath $guidePath -Encoding UTF8 -Value $entry
        Update-KnowledgeIndexForGuide -IndexPath $indexPath -Guide $safeGuide -Confidence $confidence
        $promoted += [ordered]@{
            candidate = $candidateNumber
            title = $sectionTitle
            guide = Get-KnowledgeDisplayPath -Guide $safeGuide
            confidence = $confidence
        }
    }

    $validation = Invoke-ValidateKnowledgeIndex
    if ($validation.status -eq "blocked") {
        foreach ($blocker in @($validation.blockers)) {
            Set-Blocked $result $blocker
        }
    }

    $repackResult = $null
    if ($Repack) {
        if ([string]::IsNullOrWhiteSpace($PackId)) {
            Set-Blocked $result "--repack requires --pack-id"
        } elseif ($result.status -ne "blocked") {
            $scriptPath = Join-Path $PSScriptRoot "repack-knowledge-pack.ps1"
            if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
                Set-Blocked $result "repack-knowledge-pack.ps1 not found"
            } else {
                $repackParams = @{
                    RepoRoot = $RepoRoot
                    PackId = $PackId
                    Mode = "delta-overlay"
                    Json = $true
                }
                if ($Force) { $repackParams.Force = $true }
                $raw = & $scriptPath @repackParams
                try {
                    $repackResult = $raw | ConvertFrom-Json
                    if ($repackResult.status -eq "blocked") {
                        Set-Blocked $result ("repack failed: " + (($repackResult.blockers | ForEach-Object { [string]$_ }) -join "; "))
                    }
                } catch {
                    Set-Blocked $result "repack did not return JSON"
                }
            }
        }
    }

    $reportPath = Join-Path $resolvedFeatureDir "knowledge-promotion-report.md"
    $reportLines = @(
        "# Knowledge Promotion Report",
        "",
        "- Candidate file: $(Get-RelativeDisplayPath $candidatePath)",
        "- Promoted count: $(@($promoted).Count)",
        "- Skipped count: $(@($skipped).Count)",
        "- Validation status: $($validation.status)"
    )
    if ($Repack) {
        $reportLines += "- Repack requested: true"
        $reportLines += "- Pack id: $PackId"
        if ($repackResult) {
            $reportLines += "- Repack status: $($repackResult.status)"
        }
    }
    $reportLines += ""
    $reportLines += "## Promoted"
    foreach ($item in @($promoted)) {
        $reportLines += "- Candidate $($item.candidate): $($item.guide) ($($item.confidence))"
    }
    $reportLines += ""
    $reportLines += "## Skipped"
    foreach ($item in @($skipped)) {
        $reportLines += "- Candidate $($item.candidate): $($item.review_status) - $($item.reason)"
    }
    $reportLines | Set-Content -LiteralPath $reportPath -Encoding UTF8

    $result.facts.candidates_path = $candidatePath
    $result.facts.promoted = $promoted
    $result.facts.skipped = $skipped
    $result.facts.knowledge_index = $indexPath
    $result.facts.validation = $validation
    $result.facts.report_path = $reportPath
    if ($repackResult) {
        $result.facts.repack = $repackResult
    }
    if (@($promoted).Count -eq 0) {
        $result.hints += "no approved candidates promoted; pending and rejected candidates were left untouched"
    }
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
    "inspect-workspace-repositories" { $result = Invoke-InspectWorkspaceRepositories }
    "validate-test-plan" { $result = Invoke-ValidateTestPlan }
    "validate-ai-self-acceptance" { $result = Invoke-ValidateAiSelfAcceptance }
    "inspect-plugin-build-plan" { $result = Invoke-InspectPluginBuildPlan }
    "validate-plugin-package" { $result = Invoke-ValidatePluginPackage }
    "post-commit-self-check" { $result = Invoke-PostCommitSelfCheck }
    "validate-rubric-score" { $result = Invoke-ValidateRubricScore }
    "inspect-workflow-closure" { $result = Invoke-InspectWorkflowClosure }
    "collect-workflow-observer-packet" { $result = Invoke-CollectWorkflowObserverPacket }
    "promote-knowledge-candidates" { $result = Invoke-PromoteKnowledgeCandidates }
    default { $result = Invoke-GenericInspector $Tool }
}

ConvertTo-JsonOutput $result
