@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem Compatibility alias: local retrieval is now the default.
echo Local retrieval is included in 02_Start_EduNova.bat. Forwarding to the standard startup...
call "02_Start_EduNova.bat"
exit /b %errorlevel%
