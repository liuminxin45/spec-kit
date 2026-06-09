#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$Endpoint = "http://127.0.0.1:9222",
    [ValidateSet("host-app", "workbench")]
    [string]$TargetKind = "host-app",
    [string]$TargetsJson = "",
    [switch]$Json,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Output "Usage: ensure-desktop-shell-cdp-host.ps1 [-Endpoint http://127.0.0.1:9222] [-TargetKind host-app|workbench] [-TargetsJson <json>] [-Json]"
    Write-Output "Probes DesktopShell CDP readiness and reports recoverable host/port facts before UI validation."
    exit 0
}

function New-Result {
    param([string]$Status, [hashtable]$Facts, [array]$Blockers, [array]$Unknowns, [array]$Hints)
    [PSCustomObject]@{
        tool = "ensure-desktop-shell-cdp-host"
        status = $Status
        facts = [PSCustomObject]$Facts
        blockers = $Blockers
        unknowns = $Unknowns
        hints = $Hints
    }
}

function Write-Result {
    param($Payload)
    if ($Json) {
        $Payload | ConvertTo-Json -Depth 12 -Compress
    } else {
        Write-Output ("status: " + $Payload.status)
        if ($Payload.facts.selected_target) {
            Write-Output ("selected_target: " + $Payload.facts.selected_target.url)
        }
        foreach ($blocker in @($Payload.blockers)) {
            [Console]::Error.WriteLine(" - $blocker")
        }
    }
    if ($Payload.status -eq "blocked") { exit 1 }
}

function ConvertTo-TargetRecord {
    param($Target)
    [ordered]@{
        id = [string]$Target.id
        type = [string]$Target.type
        title = [string]$Target.title
        url = [string]$Target.url
        webSocketDebuggerUrl = [string]$Target.webSocketDebuggerUrl
    }
}

function Get-TargetReason {
    param([string]$Title, [string]$Url)
    if ($Title -match "DevTools" -or $Url -match "^devtools://") { return "devtools" }
    if ($Title -match "Plugin Workbench" -or $Url -match "plugin-workbench\.html") { return "workbench" }
    if ($Url -match "base-win\.html") { return "base-window" }
    if ($Url -match "about:blank|^$") { return "blank" }
    if ($Url -match "product-homepage|product-main-window|frontend/static/index\.html") { return "host-app" }
    return "unknown"
}

function Get-PortOwnerFacts {
    param([string]$EndpointUrl)
    $facts = @()
    try {
        $uri = [Uri]$EndpointUrl
        $port = $uri.Port
        if ($port -le 0) { return $facts }
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in @($connections)) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            $facts += [PSCustomObject][ordered]@{
                local_address = [string]$connection.LocalAddress
                local_port = $connection.LocalPort
                owning_process_id = $connection.OwningProcess
                process_name = if ($process) { $process.ProcessName } else { "" }
                process_path = if ($process) { $process.Path } else { "" }
            }
        }
    } catch {
        return $facts
    }
    return $facts
}

$blockers = @()
$unknowns = @()
$hints = @(
    "If a usable DesktopShell target is already running, reuse it instead of starting a second host.",
    "If CDP is unreachable and no process owns the port, start DesktopShell from <host-app-root> with npm run debug, then rerun this probe.",
    "If another process owns the CDP port, identify it before stopping; destructive process termination requires explicit human approval.",
    "Do not switch to human acceptance until this probe and the target inventory prove host/CDP is unavailable."
)
$facts = [ordered]@{
    endpoint = $Endpoint
    target_kind = $TargetKind
    endpoint_reachable = $false
    page_targets = @()
    rejected_targets = @()
    selected_target = $null
    port_owners = @()
}

try {
    if ([string]::IsNullOrWhiteSpace($TargetsJson)) {
        $listUrl = $Endpoint.TrimEnd("/") + "/json/list"
        $targets = Invoke-RestMethod -Uri $listUrl -Method Get -TimeoutSec 3
        $facts.endpoint_reachable = $true
    } else {
        $targets = $TargetsJson | ConvertFrom-Json
        $facts.endpoint_reachable = $true
    }
} catch {
    $facts.port_owners = @(Get-PortOwnerFacts -EndpointUrl $Endpoint)
    if (@($facts.port_owners).Count -gt 0) {
        $blockers += "CDP endpoint is unreachable, but the port is already owned by another process; inspect port_owners and resolve before manual acceptance."
    } else {
        $blockers += "CDP endpoint is unreachable and no listening process was identified; start DesktopShell with npm run debug, then rerun this probe."
    }
    Write-Result (New-Result -Status "blocked" -Facts $facts -Blockers $blockers -Unknowns $unknowns -Hints $hints)
}

foreach ($target in @($targets)) {
    if ([string]$target.type -ne "page") { continue }
    $record = ConvertTo-TargetRecord $target
    $reason = Get-TargetReason -Title $record.title -Url $record.url
    $record.reason = $reason
    $facts.page_targets += [PSCustomObject]$record
}

foreach ($target in @($facts.page_targets)) {
    if ($TargetKind -eq "host-app" -and $target.reason -eq "host-app") {
        $facts.selected_target = $target
        break
    }
    if ($TargetKind -eq "workbench" -and $target.reason -eq "workbench") {
        $facts.selected_target = $target
        break
    }
}

foreach ($target in @($facts.page_targets)) {
    if ($facts.selected_target -and $target.id -eq $facts.selected_target.id) { continue }
    if ($target.reason -in @("devtools", "workbench", "base-window", "blank")) {
        $facts.rejected_targets += $target
    }
}

if (-not $facts.selected_target) {
    $blockers += "CDP is reachable, but no matching DesktopShell target was found for TargetKind '$TargetKind'; navigate/reuse the host before manual acceptance."
}
if (@($facts.page_targets).Count -eq 0) {
    $unknowns += "No page targets were returned by CDP."
}

$status = if ($blockers.Count -eq 0) { "ok" } else { "blocked" }
Write-Result (New-Result -Status $status -Facts $facts -Blockers $blockers -Unknowns $unknowns -Hints $hints)
