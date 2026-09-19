@echo off
setlocal
cd /d "%~dp0"
title AgentForge on the web

rem AgentForge as a web application: the Python backend, the Next studio, and
rem an HTTPS address that works from a phone or any other computer. No Electron
rem shell - the studio in a browser is the whole interface.
rem
rem Three windows open, one for each part. Closing a window stops that part.
rem The public address is printed in the "AgentForge link" window and is a new
rem one every time that window is started.

where node >nul 2>&1
if errorlevel 1 (
  echo [AgentForge] Node.js 20+ is required. Install it from https://nodejs.org/
  pause
  exit /b 1
)

set "PY=python"
where python >nul 2>&1 || set "PY=py -3"

if not exist "studio\node_modules" (
  echo [AgentForge] Installing the studio's packages for the first run...
  call npm --prefix studio install --no-audit --no-fund || goto :fail
)

rem The studio is served built, not compiled on demand: over a phone
rem connection the difference is a page that opens and one that times out.
rem Delete studio\.next after changing the studio to have it built again.
if not exist "studio\.next\BUILD_ID" (
  echo [AgentForge] Building the studio - this takes a minute...
  call npm --prefix studio run build || goto :fail
)

set "LINK=%USERPROFILE%\.agentforge\cloudflared.exe"

start "AgentForge backend" cmd /k %PY% server.py
start "AgentForge studio" cmd /k npm --prefix studio run start

if exist "%LINK%" (
  start "AgentForge link" cmd /k ""%LINK%" tunnel --no-autoupdate --url http://localhost:3000"
) else (
  echo [AgentForge] No public address: %LINK% was not found.
  echo              Download cloudflared-windows-amd64.exe from
  echo              https://github.com/cloudflare/cloudflared/releases and save
  echo              it there, or use this machine only.
)

echo.
echo   On this machine : http://localhost:3000/__agentforge
echo   Anywhere else   : the https://...trycloudflare.com address printed in
echo                     the "AgentForge link" window.
echo.
echo   Everyone who opens it signs in to their own account and sees only their
echo   own projects. Share the address only with people you want to let build
echo   on this machine.
echo.
exit /b 0

:fail
echo [AgentForge] The studio could not be prepared.
pause
exit /b 1
