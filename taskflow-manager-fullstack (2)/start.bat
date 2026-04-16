@echo off
title taskflow-manager Launcher
echo.
echo  =========== Starting TaskFlow Manager ===========
echo.
echo  [1/4] Starting backend: api-gateway
start "api-gateway" cmd /k "cd /d "%~dp0backend\api-gateway" && (if not exist node_modules npm install) && node index.js"
timeout /t 2 /nobreak >nul
echo  [2/4] Starting backend: tasks-service
start "tasks-service" cmd /k "cd /d "%~dp0backend\tasks-service" && (if not exist node_modules npm install) && node index.js"
timeout /t 2 /nobreak >nul
echo  [3/4] Starting backend: board-service
start "board-service" cmd /k "cd /d "%~dp0backend\board-service" && (if not exist node_modules npm install) && node index.js"
timeout /t 2 /nobreak >nul
echo  [4/4] Starting Frontend
start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm install && npm run dev"
timeout /t 10 /nobreak >nul
start "" "http://localhost:3000"
echo.
echo  ========================================
echo    Gateway  : http://localhost:3005
echo    Frontend : http://localhost:3000
echo  ========================================
pause