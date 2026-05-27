@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

powershell.exe -NoExit -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\configure-api.ps1"

endlocal
