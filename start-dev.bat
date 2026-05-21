@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

echo Starting Software Cup development services...
echo Backend window and frontend window will open separately.
echo Frontend URL: http://localhost:5173
echo Backend URL:  http://127.0.0.1:8000
echo.

start "Software Cup Backend" powershell.exe -NoExit -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\start-backend.ps1"
start "Software Cup Frontend" powershell.exe -NoExit -ExecutionPolicy Bypass -File "%REPO_ROOT%\scripts\start-frontend.ps1"

echo Startup commands have been sent.
echo If the page does not open immediately, wait a few seconds for Vite and FastAPI to finish booting.
echo To stop both services later, run:
echo   stop-dev.bat

endlocal
