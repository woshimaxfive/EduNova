@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo WARNING: This deletes local EduNova database data, Redis cache, uploads, chat attachments, and exports.
echo Source code, .env, and Docker images will not be deleted. Learning data cannot be recovered.
choice /C YN /M "Delete local demo data"
if errorlevel 2 (
  echo Cancelled. No data was deleted.
  exit /b 0
)

docker compose down -v --remove-orphans
if errorlevel 1 (
  echo.
  echo Reset failed. Verify that Docker Desktop is running and review the message above.
  exit /b 1
)

echo.
echo Local EduNova demo data has been reset. Run 02_Start_EduNova.bat for a fresh environment.
exit /b 0
