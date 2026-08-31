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

rem Electron shows startup/install progress and starts root server.py +
rem studio/npm itself, so this launcher only has to hand off and leave.
rem
rem It hands off through Start-Process rather than `start "" /b`. The /b form
rem means "no new window", which sounds right and is not: the child inherits
rem THIS console, so the black cmd window stayed on screen for the whole
rem session and closing it killed the app. Start-Process gives Electron its
rem own detached, hidden process instead, and the console closes on exit below.
rem The working directory is already this folder, from the cd /d above.
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath cmd.exe -ArgumentList '/c','npm --prefix desktop start' -WindowStyle Hidden"
exit /b 0
