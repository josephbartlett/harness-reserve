[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @()
if ($env:HARNESS_RESERVE_HOME) {
    $candidates += Join-Path $env:HARNESS_RESERVE_HOME "reserve.ps1"
}
$candidates += Join-Path $projectRoot ".tools\harness-reserve\reserve.ps1"
$candidates += Join-Path (Split-Path -Parent $projectRoot) "harness-reserve\reserve.ps1"

$reserve = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
$installed = Get-Command `
    -Name @("harness-reserve.exe", "harness-reserve") `
    -CommandType Application `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $reserve -and -not $installed) {
    [Console]::Error.WriteLine("BLOCK: Harness Reserve was not found. Install its console command, set HARNESS_RESERVE_HOME, or add a supported checkout.")
    exit 20
}

$reserveArguments = @("--project-root", $projectRoot, "run") + @($Arguments)
if ($reserve) {
    & $reserve @reserveArguments
}
else {
    & $installed.Path @reserveArguments
}
exit $LASTEXITCODE
