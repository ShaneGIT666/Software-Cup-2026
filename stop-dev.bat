@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

powershell.exe -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\dev.ps1" -Action stop

endlocal
