@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem Compatibility alias: keyless search is now the default.
echo Keyless search is included in 02_Start_EduNova.bat. Forwarding to the standard startup...
call "02_Start_EduNova.bat"
if errorlevel 1 exit /b 1
exit /b 0
