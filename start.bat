@echo off
title Code Developer Agent
color 0A

echo.
echo  =====================================================
echo   CODE DEVELOPER AGENT — AI-Powered MERN Generator
echo   Ollama + DeepSeek + MongoDB
echo  =====================================================
echo.

:: ── Check Prerequisites ───────────────────────────────────────

echo [1/5] Checking prerequisites...

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] Node.js not found. Install from https://nodejs.org
  pause & exit /b 1
)
echo  [OK] Node.js found

:: Check MongoDB
sc query MongoDB >nul 2>&1
if errorlevel 1 (
  echo  [WARN] MongoDB service not found. Trying to start mongod...
  start "" mongod --dbpath C:\data\db >nul 2>&1
  timeout /t 2 >nul
) else (
  net start MongoDB >nul 2>&1
  echo  [OK] MongoDB started
)

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] Ollama not found. Install from https://ollama.ai
  pause & exit /b 1
)
echo  [OK] Ollama found

:: ── Start Ollama ──────────────────────────────────────────────

echo.
echo [2/5] Starting Ollama service...
start "Ollama" /min cmd /c "ollama serve"
timeout /t 3 >nul
echo  [OK] Ollama running at http://localhost:11434

:: Pull model if not available
echo  Checking DeepSeek model...
ollama list 2>nul | findstr "deepseek-v3.1" >nul
if errorlevel 1 (
  echo  [INFO] Pulling deepseek-v3.1:671b-cloud model (this may take a while)...
  ollama pull deepseek-v3.1:671b-cloud
)
echo  [OK] Model ready

:: ── Install Agent Service ─────────────────────────────────────

echo.
echo [3/5] Setting up Agent Service...
cd /d "%~dp0agent-service"
if not exist node_modules (
  echo  Installing dependencies...
  call npm install --silent
)
echo  [OK] Agent service ready

:: ── Install Frontend ──────────────────────────────────────────

echo.
echo [4/5] Setting up Frontend...
cd /d "%~dp0frontend"
if not exist node_modules (
  echo  Installing dependencies...
  call npm install --silent
)
if not exist .next (
  echo  Building Next.js...
  call npm run build
)
echo  [OK] Frontend ready

:: ── Start Services ────────────────────────────────────────────

echo.
echo [5/5] Starting services...

:: Start agent service
cd /d "%~dp0agent-service"
start "Agent Service :5000" cmd /k "title Agent Service && color 0B && npm start"
timeout /t 2 >nul

:: Start frontend
cd /d "%~dp0frontend"
start "Frontend :3000" cmd /k "title Frontend UI && color 09 && npm start"
timeout /t 3 >nul

echo.
echo  =====================================================
echo   ALL SERVICES RUNNING
echo  =====================================================
echo.
echo   UI:            http://localhost:3000
echo   Agent API:     http://localhost:5000
echo   Health Check:  http://localhost:5000/health
echo.
echo   Generated apps will run at:
echo   Gateway:       http://localhost:8080
echo.
echo  =====================================================
echo.

:: Open browser
timeout /t 2 >nul
start "" http://localhost:3000

echo  Press any key to STOP all services...
pause >nul

:: Kill all
echo  Stopping services...
taskkill /fi "WindowTitle eq Agent Service :5000*" /f >nul 2>&1
taskkill /fi "WindowTitle eq Frontend :3000*" /f >nul 2>&1
taskkill /fi "WindowTitle eq Ollama*" /f >nul 2>&1
echo  Done.
