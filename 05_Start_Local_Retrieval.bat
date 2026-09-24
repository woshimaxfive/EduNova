@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem Compatibility alias: local retrieval is now the default.
call "02_Start_EduNova.bat"
exit /b %errorlevel%
