#!/bin/bash
echo "Starting TaskFlow Manager..."

(cd "$(dirname "$0")/backend/api-gateway" && npm install --silent && node index.js) &
(cd "$(dirname "$0")/backend/tasks-service" && npm install --silent && node index.js) &
(cd "$(dirname "$0")/backend/board-service" && npm install --silent && node index.js) &
(cd "$(dirname "$0")/frontend" && npm install && npm run dev) &
sleep 8
command -v open &>/dev/null && open http://localhost:3000 || xdg-open http://localhost:3000 2>/dev/null || true