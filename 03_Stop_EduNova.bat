@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Stop all project services, including local search; keep data volumes.
docker compose down --remove-orphans
if errorlevel 1 (
  echo.
  echo Stop failed. Verify that Docker Desktop is running and review the message above.
  exit /b 1
)

echo.
echo EduNova stopped. Local database and learning data were preserved.
exit /b 0
