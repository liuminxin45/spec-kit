# Shared read contract: stage_statuses is canonical; legacy nodes remain readable.
function Get-SpecKitStageStatus {
    param($State, [string]$Name)
    if ($null -eq $State) { return "" }
    $stageName = $Name.Replace('_', '-')
    $stages = $State.stage_statuses
    if ($stages -and $stages.PSObject.Properties.Name -contains $stageName -and $stages.$stageName) {
        return ([string]$stages.$stageName).ToLowerInvariant()
    }
    $nodeName = $stageName.Replace('-', '_')
    if ($State.PSObject.Properties.Name -contains $nodeName) {
        return ([string]$State.$nodeName.status).ToLowerInvariant()
    }
    return ""
}

function Get-SpecKitStateConflicts {
    param($State)
    if ($null -eq $State -or $null -eq $State.stage_statuses) { return }
    foreach ($stage in $State.stage_statuses.PSObject.Properties) {
        $node = $stage.Name.Replace('-', '_')
        if ($State.PSObject.Properties.Name -notcontains $node -or -not $State.$node.status) { continue }
        $a = ([string]$stage.Value).ToLowerInvariant()
        $b = ([string]$State.$node.status).ToLowerInvariant()
        $success = @('completed', 'complete', 'passed', 'ok', 'done')
        if ($a -ne $b -and -not ($a -in $success -and $b -in $success)) {
            [pscustomobject]@{stage=$stage.Name; canonical=$a; legacy=$b; repair='update-workflow-state.ps1 with explicit status and evidence'}
        }
    }
}
