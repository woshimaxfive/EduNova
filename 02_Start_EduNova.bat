@echo off
setlocal EnableExtensions
cd /d "%~dp0"

call "01_Check_Environment.bat"
if errorlevel 1 goto :failed

if not exist ".env" (
  echo.
  echo First run: creating a local .env from .env.example...
  copy /y ".env.example" ".env" >nul
  if errorlevel 1 goto :env_failed
)

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\initialize_env.ps1" -Path ".env"
if errorlevel 1 goto :env_failed
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sync_postgres_password.ps1" -Path ".env"
if errorlevel 1 goto :env_failed
echo Add your own AI provider credentials to .env to enable AI features.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare_local_runtime.ps1"
if errorlevel 1 goto :failed
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\migrate_local_retrieval_env.ps1" -Path ".env"
if errorlevel 1 goto :env_failed
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\migrate_local_search_env.ps1" -Path ".env"
if errorlevel 1 goto :env_failed

echo.
echo Building and starting EduNova. The first run downloads images, dependencies, and document models...
docker compose up -d --build
if errorlevel 1 goto :failed

echo Waiting for the health check...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(90); do { try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 5; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 goto :health_failed

start "" "http://127.0.0.1:8080"
echo.
echo EduNova is ready at http://127.0.0.1:8080
echo Run 03_Stop_EduNova.bat to stop the services.
exit /b 0

:env_failed
echo.
echo Could not create or initialize .env. Verify that the folder is writable and try again.
exit /b 1

:health_failed
echo.
echo The health check did not pass within 90 seconds. Run docker compose ps or docker compose logs --tail=100.
exit /b 1

:failed
echo.
echo EduNova could not be started. Review the message above.
exit /b 1
