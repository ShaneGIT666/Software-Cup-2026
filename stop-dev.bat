@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "DOUBLE_CLICKED=0"
for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$filter='ProcessId=' + $PID; $process=Get-CimInstance Win32_Process -Filter $filter -ErrorAction SilentlyContinue; if ($process -and $process.ParentProcessId) { (Get-Process -Id $process.ParentProcessId -ErrorAction SilentlyContinue).ProcessName }" 2^>nul`) do set "PARENT_PROCESS=%%P"
if /I "%PARENT_PROCESS%"=="explorer" set "DOUBLE_CLICKED=1"

powershell.exe -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\dev.ps1" -Action stop
set "EXIT_CODE=%ERRORLEVEL%"

if "%DOUBLE_CLICKED%"=="1" (
    echo.
    if not "%EXIT_CODE%"=="0" echo Stop failed with exit code %EXIT_CODE%.
    echo Press any key to close this window.
    pause >nul
)

endlocal
exit /b %EXIT_CODE%
