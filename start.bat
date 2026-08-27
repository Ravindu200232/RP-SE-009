@echo off
setlocal
cd /d "%~dp0"
title AgentForge

rem AgentForge Desktop is the single owner of backend + Studio processes.
rem The Electron splash opens first, so a slow first npm install never looks
rem like the launcher crashed or froze in a console window.

where node >nul 2>&1
if errorlevel 1 (
  echo [AgentForge] Node.js 20+ is required.
  echo Install it from https://nodejs.org/ and run start.bat again.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [AgentForge] Python 3.11+ is required.
    echo Install it from https://www.python.org/downloads/ and run start.bat again.
    pause
    exit /b 1
  )
)

if not exist "desktop\node_modules\.bin\electron.cmd" (
  echo [AgentForge] Preparing the desktop shell for the first run...
  if exist "desktop\package-lock.json" (
    call npm --prefix desktop ci --no-audit --no-fund
  ) else (
    call npm --prefix desktop install --no-audit --no-fund
  )
  if errorlevel 1 (
    echo [AgentForge] Electron dependencies could not be installed.
    echo Run: npm --prefix desktop ci
    pause
    exit /b 1
  )
)

rem `start` returns this launcher immediately; Electron shows startup/install
rem progress and starts root server.py + studio/npm itself.
start "" /b cmd /c "npm --prefix desktop start"
exit /b 0
