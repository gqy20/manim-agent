#!/bin/bash
set -e

echo "=== Manim Agent Starting ==="
echo "PORT (Railway): ${PORT:-8000}"
echo "Next.js port:   ${NEXT_PORT:-3000}"

# Start Next.js in background
node /app/server.js --port "${NEXT_PORT:-3000}" &
NEXT_PID=$!
echo "Next.js started (PID: $NEXT_PID) on port ${NEXT_PORT:-3000}"

# Start FastAPI (foreground, receives Railway signals)
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
