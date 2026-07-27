[CmdletBinding()]
param(
    [switch]$OpenAfter
)

. "$PSScriptRoot\Common.ps1"

Write-ReserveActionResult `
    -Outcome "BLOCK" `
    -SafeSummary "The foreground processing action has not been mapped to a project-owned pipeline." `
    -ProjectState "UNCONFIGURED" `
    -NextAction "Replace this stub with a thin delegation to the project's existing processing script."

Write-Host "BLOCK: Process-HarnessInput.ps1 is a fail-closed template stub."
exit 20
