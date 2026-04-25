@echo off
setlocal
set ROOT=%~dp0
set API_DIR=%ROOT%api
set FRONTEND_DIR=%ROOT%frontend

echo ============================================================
echo  Agent 2 Developer - starting API and Frontend
echo  API      : http://127.0.0.1:8102
echo  Frontend : http://127.0.0.1:3100/design-selector
echo  Model    : %AGENT2_MODEL%
echo ============================================================

if "%AGENT2_MODEL%"=="" set AGENT2_MODEL=qwen2.5:14b

start "Agent 2 API" cmd /k "cd /d %API_DIR% && set AGENT2_MODEL=%AGENT2_MODEL% && python -m uvicorn app.main:app --host 127.0.0.1 --port 8102 --reload"
start "Agent 2 Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

endlocal
