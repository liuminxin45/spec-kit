param(
    [string]$RepoRoot = "",
    [string[]]$PackId = @(),
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "compose-knowledge-packs"

try {
    $root = Resolve-KnowledgePackPath -Path $RepoRoot
    if ([string]::IsNullOrWhiteSpace($root)) { $root = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        Set-KnowledgePackBlocked $result "RepoRoot not found: $root"
    }

    if ($result.status -ne "blocked") {
        $knowledgeRoot = Join-Path $root ".specify\knowledge"
        $packsRoot = Join-Path $knowledgeRoot "packs"
        if (-not (Test-Path -LiteralPath $packsRoot -PathType Container)) {
            Set-KnowledgePackBlocked $result "No installed knowledge packs found under .specify/knowledge/packs"
        } else {
            if ($PackId.Count -eq 0) {
                $PackId = @(Get-ChildItem -LiteralPath $packsRoot -Directory | Where-Object {
                    Test-Path -LiteralPath (Join-Path $_.FullName "knowledge-pack.yml") -PathType Leaf
                } | ForEach-Object { $_.Name })
            }
            if ($PackId.Count -eq 0) {
                Set-KnowledgePackBlocked $result "No PackId supplied and no installed packs discovered"
            }
        }
    }

    if ($result.status -ne "blocked") {
        $baseRoot = Join-Path $root ".specify\knowledge\base\ai\knowledge"
        $activeKnowledge = Join-Path $root "ai\knowledge"
        if (-not (Test-Path -LiteralPath $baseRoot -PathType Container) -and (Test-Path -LiteralPath $activeKnowledge -PathType Container)) {
            Copy-KnowledgePackDirectory -Source $activeKnowledge -Destination $baseRoot
        }

        $materialized = Join-Path $root ".specify\knowledge\materialized\ai\knowledge"
        Remove-KnowledgePackDirectorySafe -Root (Join-Path $root ".specify\knowledge") -Path $materialized
        New-Item -ItemType Directory -Force -Path $materialized | Out-Null
        $materializedInitialized = $false
        $baseKnowledgeIncluded = $false

        $applied = @()
        $aliases = [ordered]@{}
        foreach ($id in $PackId) {
            $slug = ConvertTo-KnowledgePackSlug -Value $id
            $packRoot = Join-Path $root ".specify\knowledge\packs\$slug"
            if (-not (Test-Path -LiteralPath (Join-Path $packRoot "knowledge-pack.yml") -PathType Leaf)) {
                Set-KnowledgePackBlocked $result "Installed pack not found: $slug"
                continue
            }
            $info = Get-KnowledgePackInfo -PackRoot $packRoot
            $packKnowledge = Join-Path $packRoot "ai\knowledge"
            if (-not (Test-Path -LiteralPath $packKnowledge -PathType Container)) {
                Set-KnowledgePackBlocked $result "Installed pack has no ai/knowledge directory: $slug"
                continue
            }
            $strategy = Get-KnowledgePackComposeStrategy -PackRoot $packRoot
            if ($strategy -eq "replace-active-knowledge") {
                Remove-KnowledgePackDirectorySafe -Root (Join-Path $root ".specify\knowledge") -Path $materialized
                New-Item -ItemType Directory -Force -Path $materialized | Out-Null
                $materializedInitialized = $true
                $baseKnowledgeIncluded = $false
            } elseif ($strategy -ne "overlay-active-knowledge") {
                Set-KnowledgePackBlocked $result "Unsupported compose.strategy '$strategy' in pack: $slug"
                continue
            } elseif (-not $materializedInitialized) {
                if (Test-Path -LiteralPath $baseRoot -PathType Container) {
                    Copy-KnowledgePackDirectory -Source $baseRoot -Destination $materialized
                    $baseKnowledgeIncluded = $true
                }
                $materializedInitialized = $true
            }
            Copy-KnowledgePackDirectory -Source $packKnowledge -Destination $materialized
            $packAliases = Read-KnowledgeToolAliases -PackRoot $packRoot
            foreach ($key in $packAliases.Keys) { $aliases[$key] = $packAliases[$key] }
            $applied += [ordered]@{
                id = $info.id
                version = $info.version
                compose_strategy = $strategy
                installed_path = ".specify/knowledge/packs/$($info.id)"
            }
        }

        if ($result.status -ne "blocked") {
            $aliasChanged = Apply-KnowledgeToolAliases -Root $materialized -Aliases $aliases
            $backupRoot = Join-Path $root (".specify\knowledge\backups\" + (Get-Date -Format "yyyyMMdd-HHmmss") + "\ai\knowledge")
            if (Test-Path -LiteralPath $activeKnowledge -PathType Container) {
                Copy-KnowledgePackDirectory -Source $activeKnowledge -Destination $backupRoot
                Remove-KnowledgePackDirectorySafe -Root (Join-Path $root "ai") -Path $activeKnowledge
            }
            Copy-KnowledgePackDirectory -Source $materialized -Destination $activeKnowledge

            $lockPath = Join-Path $root ".specify\knowledge\lock.yml"
            $lock = @(
                'schema_version: "1.0"',
                'generated_by: "compose-knowledge-packs"',
                'materialized: "ai/knowledge"',
                'base: ".specify/knowledge/base/ai/knowledge"',
                "packs:"
            )
            foreach ($pack in $applied) {
                $lock += "  - id: `"$($pack.id)`""
                $lock += "    version: `"$($pack.version)`""
                $lock += "    compose_strategy: `"$($pack.compose_strategy)`""
                $lock += "    installed_path: `"$($pack.installed_path)`""
            }
            $lock += "aliases_applied:"
            if ($aliases.Count -eq 0) {
                $lock += "  {}"
            } else {
                foreach ($key in $aliases.Keys) {
                    $lock += "  ${key}: $($aliases[$key])"
                }
            }
            $lock | Set-Content -LiteralPath $lockPath -Encoding utf8

            $result.facts.repo_root = $root
            $result.facts.materialized_knowledge_dir = $activeKnowledge
            $result.facts.staging_dir = $materialized
            $result.facts.backup_dir = $backupRoot
            $result.facts.lock = $lockPath
            $result.facts.applied_packs = $applied
            $result.facts.base_knowledge_included = $baseKnowledgeIncluded
            $result.facts.aliases_applied = $aliases
            $result.facts.alias_changed_files = @($aliasChanged | ForEach-Object {
                try {
                    [System.IO.Path]::GetRelativePath($root, $_).Replace('\', '/')
                } catch {
                    $_
                }
            })
        }
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
