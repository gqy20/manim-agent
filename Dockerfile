# ── Stage 1: Build Next.js (standalone output) ────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python runtime with Manim system dependencies ─────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NEXT_PORT=3000 \
    NODE_ENV=production

# ── System dependencies for Manim, Cairo, FFmpeg, LaTeX ──────
# NOTE: texlive-full is ~5-7 GB but required by Manim's MathTex/Tex mobjects
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libcairo2-dev libpango1.0-dev pangocairo-dev \
    ffmpeg \
    texlive-full \
    latexmk \
    curl git \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies (uv for fast, reproducible installs) ──
COPY pyproject.toml uv.lock ./
RUN pip install uv && \
    uv pip install --system --frozen .

# ── Application source code ───────────────────────────────────
COPY src/ ./src/
COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY migrations/ ./migrations/

# ── Next.js standalone output ─────────────────────────────────
COPY --from=frontend-builder /app/frontend/.next/standalone/ ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

# ── Create required directories ────────────────────────────────
RUN mkdir -p /app/backend/output /app/backend/logs

# ── Start script: run both Next.js and FastAPI ─────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
