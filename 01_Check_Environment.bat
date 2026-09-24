@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo [1/3] Checking Docker CLI...
docker --version >nul 2>&1
if errorlevel 1 goto :docker_missing

echo [2/3] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 goto :docker_not_running

echo [3/3] Checking Compose configuration...
rem Syntax check only: first-run .env secrets are initialized later by 02.
rem setlocal keeps this placeholder out of the actual runtime environment.
set "SEARXNG_SECRET=compose-validation-only-not-for-runtime"
docker compose config --quiet
if errorlevel 1 goto :compose_invalid

echo.
echo Environment check passed. Run 02_Start_EduNova.bat next.
exit /b 0

:docker_missing
echo.
echo Docker was not found. Install Docker Desktop and try again.
exit /b 1

:docker_not_running
echo.
echo Docker Desktop is not running or not ready. Start it and wait for Running.
exit /b 1

:compose_invalid
echo.
echo Docker Compose configuration check failed. Review the message above and verify .env.
exit /b 1
