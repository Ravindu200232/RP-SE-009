@echo off
title AI Designer Launcher
color 0b
echo ==========================================================
echo        ___   ___   ___  ___  ___  _  _  ___  ___ 
echo       ^|_ _^| / __^| / __^|^|_ _^|/ __^|^|_^|^|_^|^|_ _^|^|_ _^|
echo        ^| ^|  \__ \ \__ \ ^| ^| \__ \ \  /   ^| ^|  ^| ^| 
echo       ^|___^| ^|___/ ^|___/^|___^|^|___/  \/   ^|___^| ^|___^|
echo.
echo           AI DESIGNER DEPLOYMENT SERVER SYSTEM
echo ==========================================================
echo.

:: Check if port 8000 is occupied and kill the blocking process
echo [*] Checking for processes occupying Port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [!] Found active process with PID %%a on Port 8000. Terminating...
    taskkill /f /pid %%a >nul 2>&1
)

:: Detect virtual environments
set "VENV_PATH="
if exist "%~dp0backend\.venv\Scripts\activate.bat" (
    set "VENV_PATH=%~dp0backend\.venv\Scripts\activate.bat"
) else if exist "%~dp0backend\venv\Scripts\activate.bat" (
    set "VENV_PATH=%~dp0backend\venv\Scripts\activate.bat"
)

:: Start Backend
echo [*] Starting Backend (FastAPI on http://localhost:8000)...
if defined VENV_PATH (
    start "AI Designer Backend (VirtualEnv)" cmd /k "cd /d "%~dp0backend" && call "%VENV_PATH%" && python run.py"
) else (
    start "AI Designer Backend" cmd /k "cd /d "%~dp0backend" && python run.py"
)

:: Start Frontend
echo [*] Starting Frontend (Vite)...
start "AI Designer Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ==========================================================
echo [SUCCESS] Both servers are starting up in separate windows!
echo - Backend API: http://localhost:8000
echo - Frontend App: Check the Vite terminal (usually http://localhost:5173)
echo ==========================================================
echo.
pause
