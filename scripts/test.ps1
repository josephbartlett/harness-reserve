[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$hadPythonPath = Test-Path Env:PYTHONPATH
$previousPythonPath = $env:PYTHONPATH
$hadNoBytecode = Test-Path Env:PYTHONDONTWRITEBYTECODE
$previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
$exitCode = 20

try {
    Push-Location $root
    $env:PYTHONPATH = "$root\src;$root\tests" + $(if ($previousPythonPath) { ";$previousPythonPath" } else { "" })
    $env:PYTHONDONTWRITEBYTECODE = "1"

    $python = $null
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $python = @("py.exe", "-3")
    }
    elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $python = @("python.exe")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = @("python")
    }
    if (-not $python) {
        [Console]::Error.WriteLine("BLOCK: Python 3.11 or later was not found.")
        $exitCode = 20
    }
    else {
        $exe = $python[0]
        $prefix = @()
        if ($python.Count -gt 1) {
            $prefix = $python[1..($python.Count - 1)]
        }
        $PSNativeCommandUseErrorActionPreference = $false
        & $exe @prefix -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 20)"
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine("BLOCK: Python 3.11 or later is required.")
            $exitCode = 20
        }
        else {
            & $exe @prefix scripts\validate_scaffold.py
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                & $exe @prefix -m unittest discover -s tests -v
                $exitCode = $LASTEXITCODE
            }
        }
    }
}
finally {
    Pop-Location
    if ($hadPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    }
    else {
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $null, "Process")
    }
    if ($hadNoBytecode) {
        $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode
    }
    else {
        [Environment]::SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", $null, "Process")
    }
}

exit $exitCode
