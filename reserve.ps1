[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourcePath = Join-Path $root "src"
$hadPythonPath = Test-Path Env:PYTHONPATH
$previousPythonPath = $env:PYTHONPATH
$exitCode = 20

try {
    if ([string]::IsNullOrEmpty($previousPythonPath)) {
        $env:PYTHONPATH = $sourcePath
    }
    else {
        $env:PYTHONPATH = $sourcePath + [IO.Path]::PathSeparator + $previousPythonPath
    }

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

        # Keep caller profiles from turning expected 10/20 outcomes into terminating errors.
        $PSNativeCommandUseErrorActionPreference = $false
        $argumentJson = ConvertTo-Json -InputObject @($Arguments) -Compress
        # Isolated mode prevents an adopting project or caller directory from shadowing the
        # shared harness_reserve package. Insert only this checkout's inspected source root.
        $bridgeCode = "import runpy,sys; sys.path.insert(0,sys.argv[1]); runpy.run_module('harness_reserve.ps_bridge',run_name='__main__')"
        $argumentJson | & $exe @prefix -X utf8 -I -B -c $bridgeCode $sourcePath
        $exitCode = $LASTEXITCODE
    }
}
finally {
    if ($hadPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    }
    else {
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $null, "Process")
    }
}

exit $exitCode
