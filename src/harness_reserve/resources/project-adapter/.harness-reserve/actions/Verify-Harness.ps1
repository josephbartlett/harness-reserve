[CmdletBinding()]
param()

. "$PSScriptRoot\Common.ps1"

Write-ReserveActionResult `
    -Outcome "BLOCK" `
    -SafeSummary "The verification action has not been mapped to the project's ordinary validation gate." `
    -ProjectState "UNCONFIGURED" `
    -NextAction "Replace this stub with a thin delegation to existing non-destructive tests or validation."

Write-Host "BLOCK: Verify-Harness.ps1 is a fail-closed template stub."
exit 20
