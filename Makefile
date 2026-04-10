.PHONY: dev dev-backend dev-frontend build install clean lint test help

# ── Variables ──────────────────────────────────────────────
PYTHON  := uv run python
BE_HOST := 127.0.0.1
BE_PORT := 8471
FE_PORT := 3147

# ── Help ──────────────────────────────────────────────────
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Development ────────────────────────────────────────────
dev: ## Start both backend and frontend in development mode
	@echo "============================================="
	@echo "  Backend:  http://$(BE_HOST):$(BE_PORT)"
	@echo "  Frontend: http://localhost:$(FE_PORT)"
	@echo "============================================="
	@make dev-backend & make dev-frontend

dev-backend: ## Start FastAPI backend with hot-reload (uvicorn)
	$(PYTHON) -m uvicorn backend.main:app --host $(BE_HOST) --port $(BE_PORT) --reload

dev-frontend: ## Start Next.js frontend dev server
	cd frontend && npm run dev -- -p $(FE_PORT)

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
