@echo off
title AI Website Builder - Stop All
color 0C

echo.
echo  ============================================
echo    AI Website Builder - Stopping Services
echo  ============================================
echo.

:: Kill Next.js (node on port 3000)
echo  Stopping Next.js (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo  [OK] Next.js stopped

:: Kill Express backend (node on port 5000)
echo  Stopping Express Backend (port 5000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo  [OK] Backend stopped

:: Close named terminal windows
taskkill /FI "WINDOWTITLE eq AI Builder - Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI Builder - Frontend" /F >nul 2>&1

echo.
echo  [NOTE] MongoDB and Ollama are left running.
echo         Run 'net stop MongoDB' to stop MongoDB manually.
echo.
echo  Done! Press any key to close.
pause >nul
