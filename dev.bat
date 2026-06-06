@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=status"

powershell.exe -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\dev.ps1" -Action "%ACTION%" %2 %3 %4 %5 %6 %7 %8 %9

endlocal
