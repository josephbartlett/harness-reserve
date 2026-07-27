Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-ReserveActionResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("PASS", "DEGRADED", "BLOCK", "ERROR")]
        [string]$Outcome,

        [Parameter(Mandatory = $true)]
        [string]$SafeSummary,

        [ValidateSet("READY", "DEGRADED", "BLOCKED", "STALE", "UNCONFIGURED", "UNKNOWN")]
        [string]$ProjectState = "UNKNOWN",

        [string[]]$Warnings = @(),
        [string]$NextAction
    )

    $resultPath = $env:HARNESS_RESERVE_RESULT_PATH
    if ([string]::IsNullOrWhiteSpace($resultPath)) {
        throw "HARNESS_RESERVE_RESULT_PATH was not provided by the shared runtime."
    }

    $payload = [ordered]@{
        contract_version = 1
        outcome = $Outcome
        safe_summary = $SafeSummary
        project_state = $ProjectState
        warnings = @($Warnings)
        evidence = @()
        next_action = $NextAction
    }
    $directory = Split-Path -Parent $resultPath
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding utf8
}
