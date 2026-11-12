@echo off
REM Sina OS — Windows
cd /d "%~dp0"
where py >nul 2>nul && (py -3 sina.py %*) || (python sina.py %*)
pause
