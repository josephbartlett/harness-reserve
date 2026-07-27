[CmdletBinding()]
param()

. "$PSScriptRoot\Common.ps1"

Write-ReserveActionResult `
    -Outcome "DEGRADED" `
    -SafeSummary "The Harness Reserve adapter exists but project-specific status logic is not configured." `
    -ProjectState "UNCONFIGURED" `
    -NextAction "Implement Get-HarnessStatus.ps1 by delegating to the project's existing status evidence."

Write-Host "DEGRADED: Project status adapter is not configured."
exit 10
