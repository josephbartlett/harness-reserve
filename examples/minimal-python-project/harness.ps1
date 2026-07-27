[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$reserve = Join-Path (Split-Path -Parent (Split-Path -Parent $projectRoot)) "reserve.ps1"
if (-not (Test-Path -LiteralPath $reserve -PathType Leaf)) {
    [Console]::Error.WriteLine("BLOCK: The example could not find the repository reserve.ps1 launcher.")
    exit 20
}

$reserveArguments = @("--project-root", $projectRoot, "run") + @($Arguments)
& $reserve @reserveArguments
exit $LASTEXITCODE
