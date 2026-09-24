@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "02_Start_EduNova.bat"
if errorlevel 1 exit /b 1
docker compose -f docker-compose.yml -f docker-compose.search.yml up -d --build --wait --wait-timeout 180
exit /b %errorlevel%
