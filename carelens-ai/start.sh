#!/usr/bin/env bash
# Starts the backend (127.0.0.1:5000) and the web app (http://localhost:5173).
# The sample family (known password) is NOT created automatically. For a demo run:  CARELENS_SEED_DEMO=1 ./start.sh
set -e
cd "$(dirname "$0")"
[ -f backend/.env ] || cp backend/.env.example backend/.env
(cd backend && python3 -m pip install -r requirements.txt)
if [ "$CARELENS_SEED_DEMO" = "1" ] && [ ! -f backend/instance/family.db ]; then (cd backend && python3 seed_demo.py); fi
(cd backend && exec python3 app.py) &
BACK=$!
(cd frontend && { [ -d node_modules ] || npm install; } && exec npm run dev) &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
echo "Open http://localhost:5173  and choose Register to create your family."
[ "$CARELENS_SEED_DEMO" = "1" ] && echo "Demo login: meena / sample-pass-1  (sample data only: don't store real information in it)"
wait
