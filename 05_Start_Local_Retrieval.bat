@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "02_Start_EduNova.bat" local
exit /b %errorlevel%
