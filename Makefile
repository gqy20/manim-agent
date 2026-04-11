.PHONY: dev dev-backend dev-frontend build install clean lint test help

# ── Variables ──────────────────────────────────────────────
PYTHON ?= uv run python
BE_HOST ?= 127.0.0.1
BE_PORT ?= 8471
FE_PORT ?= 3147

# ── Help ──────────────────────────────────────────────────
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Port helpers ──────────────────────────────────────────
# Kill any process listening on $1 (port number). Works on Windows (git-bash / WSL).
define kill-port
	$(shell netstat -ano | grep ':$(1)[^0-9].*LISTENING' | awk '{print $$5}' | grep -E '^[0-9]+$$' | sort -u | while read pid; do taskkill //F //PID "$$pid" >/dev/null 2>&1 || true; done)
endef

# ── Development ────────────────────────────────────────────
dev: ## Start both backend and frontend in development mode (auto-kills old processes)
	@echo "============================================="
	@echo "  Backend:  http://$(BE_HOST):$(BE_PORT)"
	@echo "  Frontend: http://localhost:$(FE_PORT)"
	@echo "============================================="
	@$(call kill-port,$(BE_PORT))
	@$(call kill-port,$(FE_PORT))
	@make dev-backend & make dev-frontend

dev-backend: ## Start FastAPI backend with hot-reload (uvicorn, excludes output dirs)
	@$(call kill-port,$(BE_PORT))
	$(PYTHON) backend/_dev.py

dev-frontend: ## Start Next.js frontend dev server
	@$(call kill-port,$(FE_PORT))
	cd frontend && API_URL=http://$(BE_HOST):$(BE_PORT) npm run dev -- --port $(FE_PORT)

# ── Build & Production ─────────────────────────────────────
build: ## Build frontend for production
	cd frontend && npm run build

install: ## Install all dependencies (Python + Node)
	uv sync
	cd frontend && npm install

clean: ## Remove build artifacts, cache, and generated files
	rm -rf backend/output/
	rm -rf backend/data/
	rm -rf frontend/.next/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

lint: ## Run linters on Python code
	uv run ruff check src/ backend/
	uv run ruff format --check src/ backend/

test: ## Run all tests
	uv run pytest tests/ backend/tests/ -v

test-cov: ## Run tests with coverage report
	uv run pytest tests/ backend/tests/ -v --cov=src --cov=backend --cov-report=term-missing
