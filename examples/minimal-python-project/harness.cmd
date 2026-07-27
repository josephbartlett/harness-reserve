@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
set "ACTION_ROOT=%PROJECT_ROOT%\.harness-reserve\cmd-actions"

where pwsh.exe >nul 2>&1
if errorlevel 1 (
    echo BLOCK: PowerShell 7 ^(pwsh^) is required. 1>&2
    exit /b 20
)

pushd "%ACTION_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo BLOCK: The tracked CMD action markers are missing. Use harness.ps1. 1>&2
    exit /b 20
)

set "ACTION_DRIVE=%~d1"
set "EXTRA_DRIVE=%~d2"
if "%ACTION_DRIVE%"=="\\" goto unsafe_action_metadata
if "%EXTRA_DRIVE%"=="\\" goto extra_argument_metadata
if not "%EXTRA_DRIVE%"=="" goto extra_argument_metadata
if "%ACTION_DRIVE%"=="" goto default_action_metadata

set "ACTION_SIZE=%~z1"
for %%I in (use) do set "USE_SIZE=%%~zI"
for %%I in (status) do set "STATUS_SIZE=%%~zI"
for %%I in (process) do set "PROCESS_SIZE=%%~zI"
for %%I in (verify) do set "VERIFY_SIZE=%%~zI"

if "%ACTION_SIZE%"=="%USE_SIZE%" goto maybe_use
if "%ACTION_SIZE%"=="%STATUS_SIZE%" goto maybe_status
if "%ACTION_SIZE%"=="%PROCESS_SIZE%" goto maybe_process
if "%ACTION_SIZE%"=="%VERIFY_SIZE%" goto maybe_verify
goto unknown_metadata

:unsafe_action_metadata
goto unknown_metadata

:extra_argument_metadata
popd
goto extra_arguments

:default_action_metadata
popd
goto default_action

:maybe_use
if /i "%~f1"=="%ACTION_ROOT%\use" (
    popd
    goto use_action
)
goto unknown_metadata

:maybe_status
if /i "%~f1"=="%ACTION_ROOT%\status" (
    popd
    goto status_action
)
goto unknown_metadata

:maybe_process
if /i "%~f1"=="%ACTION_ROOT%\process" (
    popd
    goto process_action
)
goto unknown_metadata

:maybe_verify
if /i "%~f1"=="%ACTION_ROOT%\verify" (
    popd
    goto verify_action
)
goto unknown_metadata

:unknown_metadata
popd
goto unknown_action

:default_action
pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%PROJECT_ROOT%\harness.ps1"
exit /b %ERRORLEVEL%

:use_action
pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%PROJECT_ROOT%\harness.ps1" use
exit /b %ERRORLEVEL%

:status_action
pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%PROJECT_ROOT%\harness.ps1" status
exit /b %ERRORLEVEL%

:process_action
pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%PROJECT_ROOT%\harness.ps1" process
exit /b %ERRORLEVEL%

:verify_action
pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%PROJECT_ROOT%\harness.ps1" verify
exit /b %ERRORLEVEL%

:extra_arguments
echo BLOCK: harness.cmd accepts no parameters after the fixed action name. Use harness.ps1 for typed parameters. 1>&2
exit /b 20

:unknown_action
echo BLOCK: harness.cmd accepts only use, status, process, or verify. Use harness.ps1 for other declared actions. 1>&2
exit /b 20
