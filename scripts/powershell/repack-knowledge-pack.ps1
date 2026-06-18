param(
    [string]$RepoRoot = "",
    [string]$PackId = "",
    [string]$Title = "",
    [string]$Version = "0.1.0",
    [string]$OutputDir = "",
    [ValidateSet("full-snapshot", "delta-overlay", "promote-reviewed")]
    [string]$Mode = "full-snapshot",
    [ValidateSet("overlay-active-knowledge", "replace-active-knowledge")]
    [string]$ComposeStrategy = "overlay-active-knowledge",
    [bool]$IncludeCapabilities = $true,
    [switch]$IncludeProfiles,
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "repack-knowledge-pack"

function Resolve-FirstExistingCapabilityDir {
    param(
        [string]$Root,
        [string[]]$Candidates
    )
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $path = Join-Path $Root $candidate
        if (Test-Path -LiteralPath $path -PathType Container) {
            return $path
        }
    }
    return ""
}

try {
    $root = Resolve-KnowledgePackPath -Path $RepoRoot
    if ([string]::IsNullOrWhiteSpace($root)) { $root = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        Set-KnowledgePackBlocked $result "RepoRoot not found: $root"
    }

    if ([string]::IsNullOrWhiteSpace($PackId)) {
        $PackId = ConvertTo-KnowledgePackSlug -Value ((Split-Path -Leaf $root) + "-capability-pack")
    } else {
        $PackId = ConvertTo-KnowledgePackSlug -Value $PackId
    }
    if ([string]::IsNullOrWhiteSpace($Title)) { $Title = $PackId }
    if ([string]::IsNullOrWhiteSpace($OutputDir)) {
        $OutputDir = Join-Path $root ".specify\knowledge\exports\$PackId"
    }

    $activeKnowledge = Join-Path $root "ai\knowledge"
    if ($result.status -ne "blocked" -and -not (Test-Path -LiteralPath (Join-Path $activeKnowledge "index.yml") -PathType Leaf)) {
        Set-KnowledgePackBlocked $result "Active ai/knowledge/index.yml not found; apply or bootstrap knowledge before repack."
    }

    $workspaceFile = ""
    $repositoryMap = ""
    if ($IncludeProfiles) {
        $candidateWorkspace = Join-Path $root ".specify\workspace.yml"
        $candidateMap = Join-Path $root ".specify\memory\repository-map.md"
        if (Test-Path -LiteralPath $candidateWorkspace -PathType Leaf) { $workspaceFile = $candidateWorkspace }
        if (Test-Path -LiteralPath $candidateMap -PathType Leaf) { $repositoryMap = $candidateMap }
    }

    $capabilityArgs = @{}
    if ($IncludeCapabilities) {
        $capabilityArgs.SkillsDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\skills",
            ".agents\spec-kit\skills",
            ".specify\capabilities\materialized\skills"
        )
        $capabilityArgs.ToolsDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\tools",
            "ai\tools"
        )
        $capabilityArgs.ScriptsDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\scripts",
            ".specify\capabilities\materialized\scripts",
            ".specify\scripts\packs"
        )
        $capabilityArgs.CommandsDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\commands",
            ".specify\capabilities\materialized\commands",
            ".specify\capabilities\commands"
        )
        $capabilityArgs.PromptsDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\prompts",
            ".specify\capabilities\materialized\prompts",
            ".specify\capabilities\prompts"
        )
        $capabilityArgs.ResourcesDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\resources",
            ".specify\capabilities\materialized\resources",
            ".specify\capabilities\resources"
        )
        $capabilityArgs.TemplatesDir = Resolve-FirstExistingCapabilityDir -Root $root -Candidates @(
            ".specify\capabilities\overlays\local\templates",
            ".specify\capabilities\materialized\templates",
            ".specify\capabilities\templates"
        )
    }

    if ($result.status -ne "blocked") {
        $exportParams = @{
            SourceKnowledgeDir = $activeKnowledge
            PackId = $PackId
            Title = $Title
            Version = $Version
            OutputDir = (Resolve-KnowledgePackPath -Path $OutputDir)
            ComposeStrategy = $ComposeStrategy
            RepackMode = $Mode
            Json = $true
        }
        if ($Force) { $exportParams.Force = $true }
        if (-not [string]::IsNullOrWhiteSpace($workspaceFile)) { $exportParams.WorkspaceFile = $workspaceFile }
        if (-not [string]::IsNullOrWhiteSpace($repositoryMap)) { $exportParams.RepositoryMap = $repositoryMap }
        foreach ($key in @("SkillsDir", "ToolsDir", "ScriptsDir", "CommandsDir", "PromptsDir", "ResourcesDir", "TemplatesDir")) {
            if ($capabilityArgs.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($capabilityArgs[$key])) {
                $exportParams[$key] = $capabilityArgs[$key]
            }
        }
        $exportRaw = & "$PSScriptRoot\export-knowledge-pack.ps1" @exportParams
        $export = $exportRaw | ConvertFrom-Json
        if ($export.status -eq "blocked") {
            Set-KnowledgePackBlocked $result ("export failed: " + (($export.blockers) -join "; "))
        }

        $result.facts.repo_root = $root
        $result.facts.mode = $Mode
        $result.facts.pack_id = $PackId
        $result.facts.include_capabilities = $IncludeCapabilities
        $result.facts.capability_sources = $capabilityArgs
        $result.facts.export = $export
        if ($export.status -eq "ok") {
            $result.facts.pack_root = $export.facts.pack_root
            $result.hints += "Repacked capability pack is ready for validate-knowledge-pack.ps1 and apply-knowledge-pack.ps1."
        }
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
