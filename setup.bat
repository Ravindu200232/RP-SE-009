@echo off
setlocal
cd /d "%~dp0"
title AgentForge Setup

where node >nul 2>&1 || (
  echo [AgentForge] Node.js 20+ is required.
  exit /b 1
)
where npm >nul 2>&1 || (
  echo [AgentForge] npm is required.
  exit /b 1
)

set "PY=python"
where python >nul 2>&1 || (
  where py >nul 2>&1 || (
    echo [AgentForge] Python 3.11+ is required.
    exit /b 1
  )
  set "PY=py -3"
)

echo [1/4] Installing Python dependencies...
%PY% -m pip install -r requirements.txt -r srs-agent\requirements.txt -r deployment-agent\requirements.txt
if errorlevel 1 exit /b 1

echo [2/4] Installing Electron dependencies...
if exist desktop\package-lock.json (
  call npm --prefix desktop ci --no-audit --no-fund
) else (
  call npm --prefix desktop install --no-audit --no-fund
)
if errorlevel 1 exit /b 1

echo [3/4] Installing Studio dependencies...
if exist studio\package-lock.json (
  call npm --prefix studio ci --no-audit --no-fund
) else (
  call npm --prefix studio install --no-audit --no-fund
)
if errorlevel 1 exit /b 1

echo [4/4] Preparing runtime folders...
if not exist production-ready mkdir production-ready
if not exist logs mkdir logs

echo AgentForge setup complete. Run start.bat.
exit /b 0
