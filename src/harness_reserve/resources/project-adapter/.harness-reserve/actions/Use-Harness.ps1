[CmdletBinding()]
param()

. "$PSScriptRoot\Common.ps1"

Write-ReserveActionResult `
    -Outcome "BLOCK" `
    -SafeSummary "The ordinary local-use action has not been mapped to a project-owned launcher." `
    -ProjectState "UNCONFIGURED" `
    -NextAction "Replace this stub with a thin delegation to the project's existing local launcher."

Write-Host "BLOCK: Use-Harness.ps1 is a fail-closed template stub."
exit 20
