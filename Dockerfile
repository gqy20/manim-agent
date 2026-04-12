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
    HOME=/home/appuser \
    NEXT_PORT=3000 \
    NODE_ENV=production

# ── System dependencies ────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    build-essential gcc g++ \
    # Cairo/Pango (Manim rendering backend)
    libcairo2-dev libpango1.0-dev \
    # FFmpeg (video muxing)
    ffmpeg \
    # Node.js runtime for Next.js standalone server
    curl git wget nodejs gosu \
    # TeX/LaTeX for Manim MathTex (~500MB vs texlive-full ~6GB)
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-science \
    latexmk \
    dvisvgm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ─────────────────────────────────────────
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN pip install uv && \
    uv pip install --system .

# ── Application source code ───────────────────────────────────
COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY migrations/ ./migrations/

# ── Next.js standalone output ─────────────────────────────────
COPY --from=frontend-builder /app/frontend/.next/standalone/ ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

RUN groupadd --system --gid 10001 appuser && \
    useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/appuser appuser

# ── Create required directories ────────────────────────────────
RUN mkdir -p /app/backend/output /app/backend/logs && \
    chown -R appuser:appuser /app /home/appuser

# ── Start script: run both Next.js and FastAPI ─────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
