@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "02_Start_EduNova.bat"
if errorlevel 1 exit /b 1
exit /b 0
