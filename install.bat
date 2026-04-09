@echo off
echo ==========================================
echo  SRS Maker Agent - Installation
echo ==========================================
echo.
echo Make sure Ollama is running with:
echo   ollama pull minicpm-o
echo   ollama pull deepseek-v3.1:671b-cloud
echo.

echo [1/2] Backend...
cd agent-service && npm install && cd ..

echo [2/2] Frontend...
cd frontend && npm install && cd ..

echo.
echo ✓ Installation complete!
echo Run: start.bat to launch the app
echo ==========================================
pause
