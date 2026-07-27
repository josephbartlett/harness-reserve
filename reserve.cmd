@echo off
setlocal EnableExtensions DisableDelayedExpansion
echo BLOCK: reserve.cmd does not forward arguments because Windows batch parsing cannot preserve the closed argument contract. 1>&2
echo Use PowerShell 7 instead: pwsh -NoLogo -NoProfile -File "%~dp0reserve.ps1" ^<arguments^> 1>&2
exit /b 20
