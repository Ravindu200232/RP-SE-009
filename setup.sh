#!/usr/bin/env bash
# Install the full AgentForge runtime, SRS/deployment agents, desktop shell and Studio.
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required."; exit 1; }

echo "[1/4] Installing Python dependencies..."
# One file at a time, so a wheel that will not build on this machine names
# itself rather than failing all three lists with one unattributable message.
for list in requirements.txt srs-agent/requirements.txt deployment-agent/requirements.txt; do
  echo "  - $list"
  python3 -m pip install -r "$list" || {
    echo "[AgentForge] Could not install $list - see the pip output above."
    exit 1
  }
done

echo "[2/4] Installing Electron dependencies..."
if [ -f desktop/package-lock.json ]; then
  npm --prefix desktop ci --no-audit --no-fund
else
  npm --prefix desktop install --no-audit --no-fund
fi

echo "[3/4] Installing Studio dependencies..."
if [ -f studio/package-lock.json ]; then
  npm --prefix studio ci --no-audit --no-fund
else
  npm --prefix studio install --no-audit --no-fund
fi

echo "[4/4] Preparing runtime folders..."
mkdir -p production-ready logs

echo "Setup complete. Start AgentForge with ./start.command (macOS/Linux) or start.bat (Windows)."
