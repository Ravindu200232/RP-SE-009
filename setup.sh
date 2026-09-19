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

echo "[4/5] Preparing runtime folders..."
mkdir -p production-ready logs

echo "[5/5] Registering Ollama models..."
# The models were only ever on the machine they were first pulled on, so a
# second machine came up with an empty `ollama list` and a model picker with
# nothing in it. These are cloud models: a pull fetches a manifest of a few
# hundred bytes and registers the name, so nothing here downloads weights or
# costs disk. It does cost about half a minute per model on the round trip,
# which is why each one is announced and why the ones already registered are
# skipped - a second run of setup should be quick.
if ! command -v ollama >/dev/null 2>&1; then
  echo "  - Ollama is not installed; skipping. Install it from https://ollama.com"
  echo "    and re-run setup to register the models."
elif [ ! -f ollama-models.txt ]; then
  echo "  - ollama-models.txt is missing; skipping."
else
  missed=""
  have="$(ollama list 2>/dev/null || true)"
  while IFS= read -r model || [ -n "$model" ]; do
    model="${model%%#*}"
    model="$(printf '%s' "$model" | tr -d '[:space:]')"
    [ -z "$model" ] && continue
    if printf '%s' "$have" | grep -qF "$model "; then
      echo "  - $model  already registered"
      continue
    fi
    echo "  - $model  ... registering"
    ollama pull "$model" >/dev/null 2>&1 || missed="$missed $model"
  done < ollama-models.txt
  if [ -n "$missed" ]; then
    echo
    echo "  Could not pull:$missed"
    echo "  Cloud models need an Ollama account on this machine - run 'ollama signin'"
    echo "  and then ./setup.sh again. Everything else is installed."
  fi
fi

echo "Setup complete. Start AgentForge with ./start.command (macOS/Linux) or start.bat (Windows)."
