#!/bin/bash
set -e

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/backend/output /app/backend/logs /home/appuser
  chown -R appuser:appuser /app/backend/output /app/backend/logs /home/appuser
  export HOME=/home/appuser
  exec gosu appuser "$0" "$@"
fi

echo "=== Manim Agent Starting ==="
APP_PORT="${PORT:-8000}"
NEXT_PORT_VALUE="${NEXT_PORT:-3000}"
NEXT_HOST_VALUE="${NEXTJS_HOST:-127.0.0.1}"

echo "PORT (Railway): ${APP_PORT}"
echo "Next.js host:   ${NEXT_HOST_VALUE}"
echo "Next.js port:   ${NEXT_PORT_VALUE}"

# Start Next.js in background
HOSTNAME="${NEXT_HOST_VALUE}" PORT="${NEXT_PORT_VALUE}" node /app/server.js &
NEXT_PID=$!
echo "Next.js started (PID: $NEXT_PID) on ${NEXT_HOST_VALUE}:${NEXT_PORT_VALUE}"

# Start FastAPI (foreground, receives Railway signals)
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${APP_PORT}"
