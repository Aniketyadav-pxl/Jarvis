@echo off
cd /d D:\jarvis

:: Check if port 8765 is already active
netstat -ano | findstr ":8765 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    start "" pythonw agent\main.py
    timeout /t 2 /nobreak >nul
)

:: Launch Brave in standalone desktop app mode
start "" brave --app=http://localhost:8765
