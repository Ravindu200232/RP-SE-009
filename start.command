#!/usr/bin/env bash
# Start the Electron shell. Electron owns the backend + Studio child processes.
set -euo pipefail
cd "$(dirname "$0")"

command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required."; exit 1; }

ELECTRON_BIN="desktop/node_modules/.bin/electron"
if [ ! -x "$ELECTRON_BIN" ]; then
  echo "[AgentForge] Preparing the desktop shell for the first run..."
  if [ -f desktop/package-lock.json ]; then
    npm --prefix desktop ci --no-audit --no-fund
  else
    npm --prefix desktop install --no-audit --no-fund
  fi
fi

exec npm --prefix desktop start
