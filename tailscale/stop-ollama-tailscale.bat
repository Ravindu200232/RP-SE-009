@echo off
setlocal
title Stop Ollama Tailscale Share

echo Stopping Tailscale share for Ollama on port 11434...
tailscale serve --tcp=11434 off
tailscale serve --https=11434 off

echo.
echo Current Tailscale serve status:
tailscale serve status
echo.
pause
