@echo off
echo ==========================================
echo  SRS Maker Agent - Starting...
echo ==========================================
echo.

echo [1/3] Installing backend dependencies...
cd agent-service
call npm install
echo.

echo [2/3] Installing frontend dependencies...
cd ..\frontend
call npm install
echo.

echo [3/3] Starting services...
cd ..\agent-service
start cmd /k "title SRS Backend :3200 && npm start"
cd ..\frontend
start cmd /k "title SRS Frontend :5200 && npm run dev"

echo.
echo ==========================================
echo  Services starting:
echo  Backend:  http://localhost:3200
echo  Frontend: http://localhost:5200
echo ==========================================
echo.
timeout /t 3
start http://localhost:5200
