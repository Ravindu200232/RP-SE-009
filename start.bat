@echo off
setlocal
title AgentForge Studio Launcher
cd /d "%~dp0"

echo ===================================================
echo    AgentForge Studio - one click launcher
echo ===================================================
echo.

REM --- locate Python (python, then py) ---
set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
  set "PYTHON=py"
  where py >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.11+ from https://python.org
    echo.
    pause
    exit /b 1
  )
)

REM --- check Node / npm ---
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not found on PATH. Install Node.js 18+ from https://nodejs.org
  echo.
  pause
  exit /b 1
)

REM --- ensure .env exists ---
if not exist ".env" (
  echo [setup] Creating .env from .env.example
  copy /Y ".env.example" ".env" >nul
)

REM --- backend: create venv + install deps on first run ---
if not exist "apps\api\.venv\Scripts\python.exe" (
  echo [setup] Creating Python virtual environment ...
  %PYTHON% -m venv "apps\api\.venv"
  echo [setup] Installing backend dependencies ^(first run, may take a few minutes^) ...
  "apps\api\.venv\Scripts\python.exe" -m pip install --upgrade pip
  "apps\api\.venv\Scripts\python.exe" -m pip install -r "apps\api\requirements.txt"
  if errorlevel 1 (
    echo [ERROR] Backend dependency install failed. See messages above.
    pause
    exit /b 1
  )
)

REM --- frontend: install node_modules on first run ---
if not exist "node_modules" (
  echo [setup] Installing frontend dependencies ^(first run, may take a few minutes^) ...
  call npm install
  if errorlevel 1 (
    echo [ERROR] Frontend dependency install failed. See messages above.
    pause
    exit /b 1
  )
)

echo.
echo [start] Launching backend ^(http://localhost:8000^) and frontend ^(http://localhost:3000^) ...

REM Each server opens in its own window. /D sets the working directory so the
REM relative paths below resolve even though this folder name contains a space.
start "AgentForge API" /D "%~dp0apps\api" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "AgentForge Web" /D "%~dp0." cmd /k "npm run dev --workspace apps/web"

echo [start] Waiting for the dev servers to warm up ...
timeout /t 8 /nobreak >nul
start "" http://localhost:3000

echo.
echo   Web app  : http://localhost:3000
echo   API docs : http://localhost:8000/docs
echo.
echo   Two terminal windows were opened (API + Web).
echo   Close those windows to stop the servers.
echo   You can close THIS window now.
echo.
pause
endlocal
