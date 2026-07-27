[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepositoryRoot,
    [switch]$SetUserHome,
    [switch]$CreateUserShim,
    [switch]$AddShimToUserPath,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$reserve = Join-Path $RepositoryRoot "reserve.ps1"
if (-not (Test-Path -LiteralPath $reserve -PathType Leaf)) {
    throw "BLOCK: reserve.ps1 was not found under $RepositoryRoot"
}

if (-not $SetUserHome -and -not $CreateUserShim -and -not $AddShimToUserPath) {
    Write-Host "No changes requested. Use -SetUserHome and optionally -CreateUserShim."
    Write-Host "Repository: $RepositoryRoot"
    exit 0
}

if ($SetUserHome -and $PSCmdlet.ShouldProcess("User environment", "Set HARNESS_RESERVE_HOME")) {
    [Environment]::SetEnvironmentVariable("HARNESS_RESERVE_HOME", $RepositoryRoot, "User")
    Write-Host "Set user HARNESS_RESERVE_HOME to $RepositoryRoot"
}

$shimDirectory = Join-Path $env:LOCALAPPDATA "HarnessReserve\bin"
$shimPath = Join-Path $shimDirectory "reserve.ps1"
if ($CreateUserShim) {
    if ((Test-Path -LiteralPath $shimPath) -and -not $Force) {
        throw "BLOCK: User shim already exists: $shimPath. Use -Force only after review."
    }
    if ($PSCmdlet.ShouldProcess($shimPath, "Create user-level Harness Reserve shim")) {
        New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null
        $escapedReserve = $reserve.Replace("'", "''")
        $content = @'
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$reserve = '__RESERVE_PS1__'
if (-not (Test-Path -LiteralPath $reserve -PathType Leaf)) {
    [Console]::Error.WriteLine("BLOCK: The configured Harness Reserve checkout was not found.")
    exit 20
}

& $reserve @Arguments
exit $LASTEXITCODE
'@.Replace("__RESERVE_PS1__", $escapedReserve)
        Set-Content -LiteralPath $shimPath -Value $content -Encoding utf8
        Write-Host "Created $shimPath"
    }
}

if ($AddShimToUserPath) {
    if (-not $CreateUserShim -and -not (Test-Path -LiteralPath $shimPath)) {
        throw "BLOCK: Create the user shim before adding its directory to PATH."
    }
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @($current -split ";" | Where-Object { $_ })
    if ($entries -notcontains $shimDirectory) {
        if ($PSCmdlet.ShouldProcess("User PATH", "Add $shimDirectory")) {
            $updated = (@($entries) + $shimDirectory) -join ";"
            [Environment]::SetEnvironmentVariable("Path", $updated, "User")
            Write-Host "Added $shimDirectory to the user PATH. Open a new terminal."
        }
    }
    else {
        Write-Host "$shimDirectory is already on the user PATH."
    }
}
