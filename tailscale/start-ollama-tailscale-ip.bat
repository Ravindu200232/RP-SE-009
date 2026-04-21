@echo off
setlocal
title Ollama via Tailscale IP

echo Starting Ollama Tailscale TCP forward on port 11434...
tailscale serve --bg --tcp=11434 tcp://localhost:11434
if errorlevel 1 (
  echo.
  echo Failed to start Tailscale TCP forwarding.
  echo Try running this file as Administrator.
  pause
  exit /b 1
)

echo.
echo Ollama is now available inside your tailnet at:
echo   http://100.101.209.52:11434
echo.
echo Test from another PC with:
echo   curl http://100.101.209.52:11434/api/tags
echo.
echo Current Tailscale serve status:
tailscale serve status
echo.
pause
