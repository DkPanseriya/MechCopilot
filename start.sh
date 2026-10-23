#!/usr/bin/env bash
# MechPartner launcher for macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "  MechPartner - mechanical design copilot"
echo "  ---------------------------------------"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Node.js 20+ is required: https://nodejs.org/"; exit 1; }

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo
  echo "  Paste your Replicate API token (starts with r8_) and press Enter."
  echo "  Get one at https://replicate.com/account/api-tokens"
  echo "  Or just press Enter to run in offline mode (calculators only)."
  printf "  Token: "
  read -r TOKEN || TOKEN=""
  if [ -n "${TOKEN// /}" ]; then
    "$PY" - "$TOKEN" <<'PY'
import pathlib, re, sys
env = pathlib.Path("backend/.env")
token = sys.argv[1].strip()
env.write_text(re.sub(r"^REPLICATE_API_TOKEN=.*$", f"REPLICATE_API_TOKEN={token}", env.read_text(), flags=re.M))
print("  Saved to backend/.env")
PY
  fi
fi

[ -d .venv ] || { echo "Creating Python environment..."; "$PY" -m venv .venv; }
echo "Checking Python packages..."
.venv/bin/python -m pip install -q --disable-pip-version-check -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend packages (first run only)..."
  (cd frontend && npm install)
fi

# Production frontend by default (fast page loads). "./start.sh dev" runs the hot-reload dev server.
MODE=prod
[ "${1:-}" = "dev" ] && MODE=dev
if [ "$MODE" = prod ]; then
  if [ ! -f frontend/.next/BUILD_ID ] || [ -n "$(find frontend/app frontend/components frontend/lib frontend/types \
        frontend/package.json frontend/next.config.ts -type f -newer frontend/.next/BUILD_ID 2>/dev/null | head -1)" ]; then
    echo "Building the frontend (first run or code changed, about a minute)..."
    (cd frontend && npm run build)
  fi
fi

echo "Starting backend on http://127.0.0.1:8001 and frontend on http://localhost:3000 ..."
(cd backend && ../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM

( sleep 8; (command -v open >/dev/null && open http://localhost:3000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true ) &
cd frontend
if [ "$MODE" = prod ]; then npm start; else npm run dev; fi
