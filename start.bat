@echo off
setlocal
cd /d "%~dp0"
title AgentForge

rem AgentForge Desktop is the single owner of backend + Studio processes.
rem The Electron splash opens first, so a slow first npm install never looks
rem like the launcher crashed or froze in a console window.
rem
rem Launched from AgentForge.vbs there is no console at all. That launcher sets
rem AGENTFORGE_QUIET, because a `pause` in a hidden window waits forever for a
rem keypress nobody can give it.

where node >nul 2>&1
if errorlevel 1 (
  echo [AgentForge] Node.js 20+ is required.
  echo Install it from https://nodejs.org/ and run start.bat again.
  if not defined AGENTFORGE_QUIET pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [AgentForge] Python 3.11+ is required.
    echo Install it from https://www.python.org/downloads/ and run start.bat again.
    if not defined AGENTFORGE_QUIET pause
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
    if not defined AGENTFORGE_QUIET pause
    exit /b 1
  )
)

rem Electron is started as its own process, not with `start /b`.
rem
rem `/b` means "no new window", which sounds like the quiet option and is the
rem opposite: the child shares this batch file's console, and a console is only
rem destroyed once every process attached to it has exited. So `cmd /c npm
rem start` held the window open for as long as the application ran, and closing
rem it took the application with it.
rem
rem `start ""` without `/b` gives Electron its own process. electron.exe is a
rem GUI binary and opens no console of its own, so this batch file exits, its
rem console closes, and the app keeps running.
set "ELECTRON=desktop\node_modules\electron\dist\electron.exe"
if exist "%ELECTRON%" (
  start "" "%ELECTRON%" "%CD%\desktop"
) else (
  rem An unusual install with no binary where it is expected. npm knows where
  rem it is; the console lingers, which is better than not starting.
  start "" /b cmd /c "npm --prefix desktop start"
)
exit /b 0
