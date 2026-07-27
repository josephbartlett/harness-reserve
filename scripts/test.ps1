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

    $pythonCandidates = [System.Collections.Generic.List[object]]::new()
    $seenExecutables = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($commandName in @("python.exe", "python")) {
        $commands = @(
            Get-Command $commandName -CommandType Application -All -ErrorAction SilentlyContinue
        )
        foreach ($command in $commands) {
            if ($seenExecutables.Add($command.Source)) {
                $pythonCandidates.Add(
                    [pscustomobject]@{
                        Executable = $command.Source
                        Arguments = @()
                    }
                )
            }
        }
    }
    $launchers = @(
        Get-Command py.exe -CommandType Application -All -ErrorAction SilentlyContinue
    )
    foreach ($launcher in $launchers) {
        if ($seenExecutables.Add($launcher.Source)) {
            $pythonCandidates.Add(
                [pscustomobject]@{
                    Executable = $launcher.Source
                    Arguments = @("-3")
                }
            )
        }
    }

    if ($pythonCandidates.Count -eq 0) {
        [Console]::Error.WriteLine("BLOCK: Python 3.11 or later was not found.")
        $exitCode = 20
    }
    else {
        $python = $null
        $PSNativeCommandUseErrorActionPreference = $false
        foreach ($candidate in $pythonCandidates) {
            $exe = $candidate.Executable
            $prefix = @($candidate.Arguments)
            & $exe @prefix -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 20)"
            if ($LASTEXITCODE -eq 0) {
                $python = $candidate
                break
            }
        }

        if (-not $python) {
            [Console]::Error.WriteLine("BLOCK: Python 3.11 or later is required.")
            $exitCode = 20
        }
        else {
            $exe = $python.Executable
            $prefix = @($python.Arguments)
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
