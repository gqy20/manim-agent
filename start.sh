#!/bin/bash
set -e

echo "=== Manim Agent Starting ==="
APP_PORT="${PORT:-8000}"
NEXT_PORT_VALUE="${NEXT_PORT:-3000}"

echo "PORT (Railway): ${APP_PORT}"
echo "Next.js port:   ${NEXT_PORT_VALUE}"

# Start Next.js in background
PORT="${NEXT_PORT_VALUE}" node /app/server.js &
NEXT_PID=$!
echo "Next.js started (PID: $NEXT_PID) on port ${NEXT_PORT_VALUE}"

# Start FastAPI (foreground, receives Railway signals)
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${APP_PORT}"
