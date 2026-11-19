@echo off
rem Double-click this file on Windows to start Maple Hollow.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py start.py) else (python start.py)
pause
