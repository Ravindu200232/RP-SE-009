@echo off
setlocal
title Ollama via Tailscale HTTPS

echo Starting Ollama Tailscale HTTPS proxy on port 11434...
tailscale serve --bg --https=11434 http://127.0.0.1:11434
if errorlevel 1 (
  echo.
  echo Failed to start Tailscale HTTPS proxy.
  echo Try running this file as Administrator.
  pause
  exit /b 1
)

echo.
echo Ollama is now available inside your tailnet at:
echo   https://ravindu.tailae5f49.ts.net:11434
echo.
echo Use this on another PC:
echo   OLLAMA_BASE_URL=https://ravindu.tailae5f49.ts.net:11434
echo.
echo Current Tailscale serve status:
tailscale serve status
echo.
pause
