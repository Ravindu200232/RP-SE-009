#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  ====================================================="
echo "   CODE DEVELOPER AGENT — AI-Powered MERN Generator"
echo "  ====================================================="
echo ""

# ── Check prerequisites ────────────────────────────────────────
command -v node >/dev/null 2>&1 || { echo "[ERROR] Node.js not found"; exit 1; }
command -v mongod >/dev/null 2>&1 || { echo "[ERROR] MongoDB not found"; exit 1; }
command -v ollama >/dev/null 2>&1 || { echo "[ERROR] Ollama not found. Install from https://ollama.ai"; exit 1; }

echo "[1/5] Prerequisites OK"

# ── Start MongoDB ──────────────────────────────────────────────
echo "[2/5] Starting MongoDB..."
mongod --dbpath /data/db --fork --logpath /tmp/mongod.log >/dev/null 2>&1 || true
sleep 1

# ── Start Ollama ───────────────────────────────────────────────
echo "[3/5] Starting Ollama..."
ollama serve >/dev/null 2>&1 &
OLLAMA_PID=$!
sleep 3

# Pull model if needed
if ! ollama list 2>/dev/null | grep -q "deepseek-v3.1"; then
  echo "  Pulling deepseek-v3.1:671b-cloud model..."
  ollama pull deepseek-v3.1:671b-cloud
fi

# ── Install & setup agent service ─────────────────────────────
echo "[4/5] Setting up services..."
cd "$ROOT/agent-service"
[ ! -d node_modules ] && npm install --silent

cd "$ROOT/frontend"
[ ! -d node_modules ] && npm install --silent
[ ! -d .next ] && npm run build

# ── Start agent service ───────────────────────────────────────
echo "[5/5] Starting all services..."
cd "$ROOT/agent-service"
npm start &
AGENT_PID=$!
sleep 2

# ── Start frontend ────────────────────────────────────────────
cd "$ROOT/frontend"
npm start &
FRONTEND_PID=$!
sleep 2

echo ""
echo "  ====================================================="
echo "   ALL SERVICES RUNNING"
echo "  ====================================================="
echo ""
echo "   UI:           http://localhost:3000"
echo "   Agent API:    http://localhost:5000"
echo "   (Generated app gateway will run at :8080)"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Open browser on Mac/Linux
(sleep 2 && (open "http://localhost:3000" || xdg-open "http://localhost:3000")) >/dev/null 2>&1 &

# Wait and cleanup on exit
trap "echo 'Stopping...'; kill $AGENT_PID $FRONTEND_PID $OLLAMA_PID 2>/dev/null; exit 0" INT TERM
wait
