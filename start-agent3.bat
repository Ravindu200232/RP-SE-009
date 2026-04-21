@echo off
setlocal

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

where npm >nul 2>&1
if errorlevel 1 (
  echo npm was not found in PATH.
  echo Please install Node.js and npm first.
  pause
  exit /b 1
)

echo Starting Agent 3...
echo Folder: %APP_DIR%
echo URL: http://localhost:3003

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":3003" ^| findstr "LISTENING"') do (
  echo Stopping existing Agent 3 process on port 3003: %%P
  taskkill /PID %%P /F >nul 2>&1
)

start "Agent 3 Dev Server" cmd /k "cd /d ""%APP_DIR%"" && npm run dev"

timeout /t 5 /nobreak >nul
start "" "http://localhost:3003"

exit /b 0
