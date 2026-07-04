param(
    [string]$PackRoot = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "validate-knowledge-pack"

try {
    $packRootResolved = Resolve-KnowledgePackPath -Path $PackRoot
    if ([string]::IsNullOrWhiteSpace($packRootResolved)) {
        Set-KnowledgePackBlocked $result "PackRoot is required"
    } elseif (-not (Test-Path -LiteralPath $packRootResolved -PathType Container)) {
        Set-KnowledgePackBlocked $result "PackRoot not found: $packRootResolved"
    }

    if ($result.status -ne "blocked") {
        $info = Get-KnowledgePackInfo -PackRoot $packRootResolved
        if (-not (Test-Path -LiteralPath $info.manifest -PathType Leaf)) {
            Set-KnowledgePackBlocked $result "pack manifest not found: knowledge-pack.yml or pack.yml"
        }
        if ([string]::IsNullOrWhiteSpace($info.id)) {
            Set-KnowledgePackBlocked $result "pack manifest missing id"
        }
        if ([string]::IsNullOrWhiteSpace($info.version)) {
            Set-KnowledgePackBlocked $result "pack manifest missing version"
        }
        $strategy = Get-KnowledgePackComposeStrategy -PackRoot $packRootResolved
        if (@("overlay-active-knowledge", "replace-active-knowledge") -notcontains $strategy) {
            Set-KnowledgePackBlocked $result "pack manifest has unsupported compose.strategy: $strategy"
        }

        $indexPath = Join-Path $packRootResolved "ai\knowledge\index.yml"
        if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
            Set-KnowledgePackBlocked $result "ai/knowledge/index.yml not found"
        }

        $missingGuides = @()
        $absolutePathOffenders = @()
        $oversizedGuides = @()
        $invalidAuthorities = @()
        $validAuthorities = @("generated", "reviewed", "authoritative", "")

        if (Test-Path -LiteralPath $indexPath -PathType Leaf) {
            $indexText = Get-Content -LiteralPath $indexPath -Raw
            foreach ($phrase in @("repository_map_authority", "no_full_text_search_required", "max_selected_guides")) {
                if ($indexText -notmatch [regex]::Escape($phrase)) {
                    Set-KnowledgePackBlocked $result "knowledge index missing required phrase: $phrase"
                }
            }

            foreach ($entry in Get-KnowledgePackIndexEntries -IndexPath $indexPath) {
                $authority = if ($entry.authority) { $entry.authority.ToString().Trim().ToLowerInvariant() } else { "" }
                if ($validAuthorities -notcontains $authority) {
                    $invalidAuthorities += "$($entry.category).$($entry.key): $authority"
                }
                if (-not $entry.guide) {
                    $missingGuides += "$($entry.category).$($entry.key) has no guide"
                    continue
                }

                $guidePath = Resolve-KnowledgePackGuidePath -IndexPath $indexPath -Guide $entry.guide
                if (-not (Test-Path -LiteralPath $guidePath -PathType Leaf)) {
                    $missingGuides += (Get-KnowledgePackDisplayPath -Guide $entry.guide)
                    continue
                }

                $text = Get-Content -LiteralPath $guidePath -Raw
                foreach ($pattern in @("[A-Za-z]:\\", "(^|[\\/])Users[\\/][^\\/]+")) {
                    if ($text -match $pattern) {
                        $absolutePathOffenders += "$(Get-KnowledgePackDisplayPath -Guide $entry.guide) contains machine-specific path pattern: $pattern"
                    }
                }
                $lineCount = @((Get-Content -LiteralPath $guidePath)).Count
                if ($lineCount -gt 220) {
                    $oversizedGuides += "$(Get-KnowledgePackDisplayPath -Guide $entry.guide) has $lineCount lines"
                }
            }
        }

        if ($missingGuides.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("missing knowledge guides: " + (($missingGuides | Select-Object -Unique) -join ", "))
        }
        if ($absolutePathOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("machine-specific knowledge paths found: " + (($absolutePathOffenders | Select-Object -Unique) -join "; "))
        }
        if ($oversizedGuides.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("knowledge guides exceed 220 lines: " + (($oversizedGuides | Select-Object -Unique) -join "; "))
        }
        if ($invalidAuthorities.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("knowledge index entries use invalid authority values: " + (($invalidAuthorities | Select-Object -Unique) -join ", "))
        }

        $capabilityLayers = Get-KnowledgePackCapabilityLayers -PackRoot $packRootResolved
        $capabilityLayerFacts = [ordered]@{}
        $capabilityPathOffenders = @()
        $capabilityMachinePathOffenders = @()
        $skillManifestOffenders = @()
        $scriptExtensionOffenders = @()
        $hookExtensionOffenders = @()
        $hookSchemaOffenders = @()
        $hookToolDependencyOffenders = @()
        $scriptHashes = @()
        $hookHashes = @()
        $workflowHookCount = 0
        $legacyHookCount = 0
        $extraCapabilityLayerPresent = $false
        foreach ($layerName in $capabilityLayers.Keys) {
            $layer = $capabilityLayers[$layerName]
            $capabilityLayerFacts[$layerName] = [ordered]@{
                present = [bool]$layer.present
                file_count = 0
            }
            if (-not $layer.present) { continue }
            $extraCapabilityLayerPresent = $true
            $files = @(Get-ChildItem -LiteralPath $layer.path -Recurse -File -Force)
            $capabilityLayerFacts[$layerName]["file_count"] = $files.Count
            foreach ($file in $files) {
                $relative = [System.IO.Path]::GetRelativePath($packRootResolved, $file.FullName).Replace('\', '/')
                if (-not (Test-KnowledgePackSafeRelativePath -RelativePath $relative)) {
                    $capabilityPathOffenders += $relative
                }
                if ($layerName -eq "scripts") {
                    if (@(".ps1", ".psm1", ".psd1", ".sh", ".cmd", ".bat") -notcontains $file.Extension.ToLowerInvariant()) {
                        $scriptExtensionOffenders += $relative
                    }
                    $scriptHashes += [ordered]@{
                        path = $relative
                        sha256 = Get-KnowledgePackFileHash -Path $file.FullName
                    }
                }
                if ($layerName -eq "hooks") {
                    if (@(".ps1", ".psm1", ".psd1", ".sh", ".cmd", ".bat", ".md", ".yml", ".yaml", ".json", ".txt") -notcontains $file.Extension.ToLowerInvariant()) {
                        $hookExtensionOffenders += $relative
                    }
                    $hookHashes += [ordered]@{
                        path = $relative
                        sha256 = Get-KnowledgePackFileHash -Path $file.FullName
                    }
                }
                if (@(".md", ".yml", ".yaml", ".json", ".ps1", ".psm1", ".psd1", ".txt") -contains $file.Extension.ToLowerInvariant()) {
                    $text = Get-Content -LiteralPath $file.FullName -Raw
                    foreach ($pattern in @("[A-Za-z]:\\", "(^|[\\/])Users[\\/][^\\/]+")) {
                        if ($text -match $pattern) {
                            $capabilityMachinePathOffenders += "$relative contains machine-specific path pattern: $pattern"
                        }
                    }
                }
            }
        }

        if ($capabilityLayers["skills"].present) {
            foreach ($skillDir in Get-ChildItem -LiteralPath $capabilityLayers["skills"].path -Directory -Force) {
                if (-not (Test-Path -LiteralPath (Join-Path $skillDir.FullName "SKILL.md") -PathType Leaf)) {
                    $relative = [System.IO.Path]::GetRelativePath($packRootResolved, $skillDir.FullName).Replace('\', '/')
                    $skillManifestOffenders += "$relative missing SKILL.md"
                }
            }
        }
        if ($capabilityLayers["hooks"].present) {
            $hookIndexPath = Join-Path $capabilityLayers["hooks"].path "index.yml"
            if (-not (Test-Path -LiteralPath $hookIndexPath -PathType Leaf)) {
                $hookSchemaOffenders += "hooks/index.yml not found"
            }
            $validInstallMethods = @("pack-local-script", "npm", "github-release", "manual")
            $validFailurePolicies = @("block", "warn", "warning", "advisory")
            $validHookTypes = @("workflow-shell", "workflow-agent-chain")
            foreach ($hook in @(Read-KnowledgePackHookIndex -PackRoot $packRootResolved)) {
                $hookId = [string](Get-KnowledgePackObjectValue -Object $hook -Key "id")
                $hookType = [string](Get-KnowledgePackObjectValue -Object $hook -Key "type")
                $events = @((Get-KnowledgePackObjectValue -Object $hook -Key "events") | ForEach-Object { [string]$_ } | Where-Object { $_ })
                $runner = [string](Get-KnowledgePackObjectValue -Object $hook -Key "runner")
                $command = [string](Get-KnowledgePackObjectValue -Object $hook -Key "command")
                $chainManifest = [string](Get-KnowledgePackObjectValue -Object $hook -Key "chain_manifest")
                $timeout = [string](Get-KnowledgePackObjectValue -Object $hook -Key "timeout_seconds")
                $failurePolicy = [string](Get-KnowledgePackObjectValue -Object $hook -Key "failure_policy")
                if ([string]::IsNullOrWhiteSpace($hookId)) {
                    $hookSchemaOffenders += "hook missing id"
                } elseif ($hookId -notmatch "^[A-Za-z0-9][A-Za-z0-9_.-]*$") {
                    $hookSchemaOffenders += "hook id has unsupported characters: $hookId"
                }
                if ($validHookTypes -notcontains $hookType) {
                    $legacyHookCount += 1
                    continue
                }
                $workflowHookCount += 1
                if ($events.Count -eq 0) {
                    $hookSchemaOffenders += "hook $hookId has no events"
                }
                foreach ($event in $events) {
                    if ($event -notmatch "^workflow\.[a-z0-9][a-z0-9-]*\.[A-Za-z0-9_.-]+\.(before|after)$") {
                        $hookSchemaOffenders += "hook $hookId has invalid event: $event"
                    }
                }
                if ($hookType -eq "workflow-shell") {
                    if ([string]::IsNullOrWhiteSpace($runner) -and [string]::IsNullOrWhiteSpace($command)) {
                        $hookSchemaOffenders += "hook $hookId must declare runner or command"
                    }
                    foreach ($candidateRunner in @($runner, $command) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) {
                        $normalizedRunner = $candidateRunner.Replace('\', '/')
                        if ([System.IO.Path]::IsPathRooted($normalizedRunner) -or $normalizedRunner -match '(^|/)\.\.($|/)' -or $normalizedRunner -match '^[A-Za-z]:') {
                            $hookSchemaOffenders += "hook $hookId uses unsafe runner path: $candidateRunner"
                        }
                        if ((Test-KnowledgePackSafeRelativePath -RelativePath $normalizedRunner) -and $normalizedRunner -match "\.(ps1|sh|cmd|bat)$") {
                            $runnerPath = Join-Path $capabilityLayers["hooks"].path ($normalizedRunner -replace "/", "\")
                            if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
                                $hookSchemaOffenders += "hook $hookId runner file not found: $normalizedRunner"
                            }
                        }
                    }
                }
                if ($hookType -eq "workflow-agent-chain") {
                    if ([string]::IsNullOrWhiteSpace($chainManifest)) {
                        $hookSchemaOffenders += "hook $hookId must declare chain_manifest"
                    } elseif (-not (Test-KnowledgePackSafeRelativePath -RelativePath $chainManifest)) {
                        $hookSchemaOffenders += "hook $hookId has unsafe chain_manifest: $chainManifest"
                    } elseif (@(".yml", ".yaml", ".json") -notcontains [System.IO.Path]::GetExtension($chainManifest).ToLowerInvariant()) {
                        $hookSchemaOffenders += "hook $hookId chain_manifest must be .yml, .yaml, or .json: $chainManifest"
                    } else {
                        $chainManifestPath = Join-Path $capabilityLayers["hooks"].path ($chainManifest -replace "/", "\")
                        if (-not (Test-Path -LiteralPath $chainManifestPath -PathType Leaf)) {
                            $hookSchemaOffenders += "hook $hookId chain_manifest file not found: $chainManifest"
                        } else {
                            $chainText = Get-Content -LiteralPath $chainManifestPath -Raw
                            if ($chainText -notmatch "(?m)^\s*steps\s*:") {
                                $hookSchemaOffenders += "hook $hookId chain_manifest missing steps: $chainManifest"
                            }
                            if ($chainText -notmatch "(?m)^\s*skill\s*:") {
                                $hookSchemaOffenders += "hook $hookId chain_manifest missing skill entries: $chainManifest"
                            }
                        }
                    }
                }
                if (-not [string]::IsNullOrWhiteSpace($timeout)) {
                    try {
                        if ([int]$timeout -lt 1) { $hookSchemaOffenders += "hook $hookId timeout_seconds must be positive" }
                    } catch {
                        $hookSchemaOffenders += "hook $hookId timeout_seconds must be an integer"
                    }
                }
                if (-not [string]::IsNullOrWhiteSpace($failurePolicy) -and $validFailurePolicies -notcontains $failurePolicy.ToLowerInvariant()) {
                    $hookSchemaOffenders += "hook $hookId has unsupported failure_policy: $failurePolicy"
                }
                foreach ($dependency in @((Get-KnowledgePackObjectValue -Object $hook -Key "tool_dependencies"))) {
                    if ($dependency -is [string]) {
                        $hookToolDependencyOffenders += "hook $hookId tool dependency '$dependency' must declare id, version, and install_method"
                        continue
                    }
                    $depId = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "id")
                    $depVersion = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "version")
                    $depInstallMethod = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "install_method")
                    $depPath = [string](Get-KnowledgePackObjectValue -Object $dependency -Key "path")
                    if ([string]::IsNullOrWhiteSpace($depId)) {
                        $hookToolDependencyOffenders += "hook $hookId tool dependency missing id"
                    }
                    if ([string]::IsNullOrWhiteSpace($depVersion)) {
                        $hookToolDependencyOffenders += "hook $hookId tool dependency $depId missing version"
                    }
                    if ([string]::IsNullOrWhiteSpace($depInstallMethod) -or $validInstallMethods -notcontains $depInstallMethod) {
                        $hookToolDependencyOffenders += "hook $hookId tool dependency $depId has unsupported install_method: $depInstallMethod"
                    }
                    if ($depInstallMethod -eq "pack-local-script") {
                        if (-not (Test-KnowledgePackSafeRelativePath -RelativePath $depPath)) {
                            $hookToolDependencyOffenders += "hook $hookId tool dependency $depId has unsafe path: $depPath"
                        } else {
                            $depFullPath = Join-Path $capabilityLayers["hooks"].path ($depPath -replace "/", "\")
                            if (-not (Test-Path -LiteralPath $depFullPath -PathType Leaf)) {
                                $hookToolDependencyOffenders += "hook $hookId tool dependency $depId path not found: $depPath"
                            }
                        }
                    }
                }
            }
        }

        $capabilityIndexPath = Join-Path $packRootResolved "capabilities\index.yml"
        if ($extraCapabilityLayerPresent -and -not (Test-Path -LiteralPath $capabilityIndexPath -PathType Leaf)) {
            Set-KnowledgePackBlocked $result "capability pack layers require capabilities/index.yml"
        }
        if ($capabilityPathOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("unsafe capability paths found: " + (($capabilityPathOffenders | Select-Object -Unique) -join ", "))
        }
        if ($capabilityMachinePathOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("machine-specific capability paths found: " + (($capabilityMachinePathOffenders | Select-Object -Unique) -join "; "))
        }
        if ($skillManifestOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("invalid skill layer entries: " + (($skillManifestOffenders | Select-Object -Unique) -join "; "))
        }
        if ($scriptExtensionOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("unsupported script files in capability pack: " + (($scriptExtensionOffenders | Select-Object -Unique) -join ", "))
        }
        if ($hookExtensionOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("unsupported hook files in capability pack: " + (($hookExtensionOffenders | Select-Object -Unique) -join ", "))
        }
        if ($hookSchemaOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("invalid workflow hooks: " + (($hookSchemaOffenders | Select-Object -Unique) -join "; "))
        }
        if ($hookToolDependencyOffenders.Count -gt 0) {
            Set-KnowledgePackBlocked $result ("invalid hook tool dependencies: " + (($hookToolDependencyOffenders | Select-Object -Unique) -join "; "))
        }

        $aliases = Read-KnowledgeToolAliases -PackRoot $packRootResolved
        $scenarios = @(Get-KnowledgePackEvaluationScenarios -PackRoot $packRootResolved)
        $fileManifest = @(Get-KnowledgePackFileManifest -PackRoot $packRootResolved)
        $treeSha256 = Get-KnowledgePackTreeHash -PackRoot $packRootResolved -FileManifest $fileManifest
        $result.facts.pack_root = $packRootResolved
        $result.facts.pack_id = $info.id
        $result.facts.version = $info.version
        $result.facts.kind = $info.kind
        $result.facts.manifest = $info.manifest
        $result.facts.compose_strategy = $strategy
        $result.facts.index = $indexPath
        $result.facts.guide_count = @(Get-KnowledgePackIndexEntries -IndexPath $indexPath | Where-Object { $_.guide }).Count
        $result.facts.missing_guides = @($missingGuides | Select-Object -Unique)
        $result.facts.absolute_path_offenders = @($absolutePathOffenders | Select-Object -Unique)
        $result.facts.oversized_guides = @($oversizedGuides | Select-Object -Unique)
        $result.facts.invalid_authorities = @($invalidAuthorities | Select-Object -Unique)
        $result.facts.tool_aliases = $aliases
        $result.facts.evaluation_scenario_count = $scenarios.Count
        $result.facts.capability_index = $capabilityIndexPath
        $result.facts.capability_layers = $capabilityLayerFacts
        $result.facts.script_hashes = $scriptHashes
        $result.facts.hook_hashes = $hookHashes
        $result.facts.workflow_hook_count = $workflowHookCount
        $result.facts.legacy_hook_count = $legacyHookCount
        $result.facts.hook_schema_offenders = @($hookSchemaOffenders | Select-Object -Unique)
        $result.facts.hook_tool_dependency_offenders = @($hookToolDependencyOffenders | Select-Object -Unique)
        $result.facts.hash_algorithm = "sha256"
        $result.facts.tree_sha256 = $treeSha256
        $result.facts.file_count = $fileManifest.Count
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
