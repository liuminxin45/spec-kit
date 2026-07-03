param(
    [string]$RepoRoot = "",
    [string]$PackPath = "",
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\knowledge-pack-common.ps1"

$result = New-KnowledgePackResult "install-knowledge-pack"

try {
    $root = Resolve-KnowledgePackPath -Path $RepoRoot
    if ([string]::IsNullOrWhiteSpace($root)) { $root = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        Set-KnowledgePackBlocked $result "RepoRoot not found: $root"
    }

    $packRoot = Resolve-KnowledgePackPath -Path $PackPath
    if ([string]::IsNullOrWhiteSpace($packRoot)) {
        Set-KnowledgePackBlocked $result "PackPath is required"
    } elseif (-not (Test-Path -LiteralPath $packRoot -PathType Container)) {
        Set-KnowledgePackBlocked $result "PackPath not found: $packRoot"
    }

    if ($result.status -ne "blocked") {
        $validationRaw = & "$PSScriptRoot\validate-knowledge-pack.ps1" -PackRoot $packRoot -Json
        $validation = $validationRaw | ConvertFrom-Json
        if ($validation.status -eq "blocked") {
            Set-KnowledgePackBlocked $result ("pack validation failed: " + (($validation.blockers) -join "; "))
        } else {
            $info = Get-KnowledgePackInfo -PackRoot $packRoot
            $packSlug = ConvertTo-KnowledgePackSlug -Value $info.id
            $knowledgeRoot = Join-Path $root ".specify\knowledge"
            $packsRoot = Join-Path $knowledgeRoot "packs"
            $baseRoot = Join-Path $knowledgeRoot "base\ai\knowledge"
            New-Item -ItemType Directory -Force -Path $packsRoot | Out-Null

            $activeKnowledge = Join-Path $root "ai\knowledge"
            if (-not (Test-Path -LiteralPath $baseRoot -PathType Container) -and (Test-Path -LiteralPath $activeKnowledge -PathType Container)) {
                Copy-KnowledgePackDirectory -Source $activeKnowledge -Destination $baseRoot
            }

            $destination = Join-Path $packsRoot $packSlug
            if ((Test-Path -LiteralPath $destination) -and -not $Force) {
                Set-KnowledgePackBlocked $result "Pack is already installed; pass -Force to replace: $packSlug"
            } else {
                $destinationBackup = ""
                $failedHookToolRefs = @()
                if (Test-Path -LiteralPath $destination) {
                    $destinationBackup = Join-Path $knowledgeRoot (".backups\install-" + (Get-Date -Format "yyyyMMdd-HHmmss") + "\packs\$packSlug")
                    Copy-KnowledgePackDirectory -Source $destination -Destination $destinationBackup
                    Remove-KnowledgePackDirectorySafe -Root $packsRoot -Path $destination
                }
                Copy-KnowledgePackDirectory -Source $packRoot -Destination $destination
                $failedHookToolRefs = @(Get-KnowledgePackHookToolReferences -PackRoot $destination)
                $hookTools = [ordered]@{
                    tool = "install-hook-tools"
                    status = "ok"
                    facts = [ordered]@{
                        repo_root = $root
                        pack_id = $packSlug
                        pack_root = $destination
                        tool_count = 0
                        tools = @()
                    }
                    blockers = @()
                    unknowns = @()
                    hints = @()
                }
                if (Test-Path -LiteralPath (Join-Path $destination "hooks\index.yml") -PathType Leaf) {
                    $hookToolsRaw = & "$PSScriptRoot\install-hook-tools.ps1" -RepoRoot $root -PackRoot $destination -PackId $packSlug -Force:$Force -Json
                    $hookTools = $hookToolsRaw | ConvertFrom-Json
                    if ($hookTools.status -eq "blocked") {
                        Set-KnowledgePackBlocked $result ("hook tool installation failed: " + (($hookTools.blockers) -join "; "))
                    }
                }
                if ($result.status -eq "blocked") {
                    if (Test-Path -LiteralPath $destination) {
                        Remove-KnowledgePackDirectorySafe -Root $packsRoot -Path $destination
                    }
                    if (-not [string]::IsNullOrWhiteSpace($destinationBackup) -and (Test-Path -LiteralPath $destinationBackup -PathType Container)) {
                        Copy-KnowledgePackDirectory -Source $destinationBackup -Destination $destination
                    }
                    $activeHookToolRefs = @()
                    if (Test-Path -LiteralPath $packsRoot -PathType Container) {
                        foreach ($installedPack in Get-ChildItem -LiteralPath $packsRoot -Directory -Force) {
                            $activeHookToolRefs += @(Get-KnowledgePackHookToolReferences -PackRoot $installedPack.FullName)
                        }
                    }
                    $hookToolPrune = Remove-UnusedKnowledgeHookTools -RepoRoot $root -CandidateRefs $failedHookToolRefs -ActiveRefs $activeHookToolRefs
                    $installRecord = $null
                } else {
                    $installRecord = Write-KnowledgePackInstallRecord -RepoRoot $root -PackRoot $destination -InstalledPath $destination -Info $info -Validation $validation -SourcePath $packRoot -HookTools $hookTools
                    $hookToolPrune = $null
                }
                if (-not [string]::IsNullOrWhiteSpace($destinationBackup) -and (Test-Path -LiteralPath $destinationBackup -PathType Container)) {
                    Remove-KnowledgePackDirectorySafe -Root $knowledgeRoot -Path $destinationBackup
                }
                $result.facts.repo_root = $root
                $result.facts.pack_id = $info.id
                $result.facts.pack_slug = $packSlug
                $result.facts.version = $info.version
                $result.facts.installed_path = $destination
                $result.facts.install_record = if ($null -ne $installRecord) { $installRecord.path } else { "" }
                $result.facts.install_record_index = if ($null -ne $installRecord) { $installRecord.index } else { "" }
                $result.facts.tree_sha256 = if ($null -ne $installRecord) { $installRecord.tree_sha256 } else { "" }
                $result.facts.file_count = if ($null -ne $installRecord) { $installRecord.file_count } else { 0 }
                $result.facts.base_knowledge = $baseRoot
                $result.facts.validation = $validation
                $result.facts.hook_tools = $hookTools
                $result.facts.rollback_backup = $destinationBackup
                $result.facts.hook_tool_prune = $hookToolPrune
                if ($result.status -ne "blocked") {
                    $result.hints += "Run apply-knowledge-pack.ps1 to materialize installed pack knowledge into ai/knowledge."
                }
            }
        }
    }
} catch {
    Set-KnowledgePackBlocked $result $_.Exception.Message
}

if ($Json) { Write-KnowledgePackJson $result } else { $result }
