@echo off
set ROOT=%~dp0
set APPROOT=%ROOT%..

start "Agent 1 API" cmd /k "cd /d %APPROOT%\agent1-srs\api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8101 --reload"
start "Agent 2 API" cmd /k "cd /d %APPROOT%\agent2-developer\api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8102 --reload"
start "Agent 3 API" cmd /k "cd /d %APPROOT%\agent3-tester\api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8103 --reload"
start "Agent 4 API" cmd /k "cd /d %APPROOT%\agent4-deployment\api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8104 --reload"
start "Shared Demo UI" cmd /k "cd /d %ROOT% && npm run dev"
