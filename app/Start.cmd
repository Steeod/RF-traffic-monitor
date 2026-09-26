@echo off
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0server.py"
if errorlevel 1 pause
