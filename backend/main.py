"""FastAPI application entry point for manim-agent web backend."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import router, set_store
from .task_store import TaskStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = TaskStore()
    set_store(store)
    app.state.store = store
    # 启动横幅：让用户在终端中一眼识别后端就绪状态
    print()
    print("=" * 56)
    print("  Manim Agent Backend Ready")
    print(f"  Tasks in store: {len(store._tasks)}")
    print(f"  Output dir:   {Path('backend/output').resolve()}")
    print("=" * 56)
    print()
    yield
    await store.save()


app = FastAPI(
    title="Manim Agent API",
    description="Web API for AI-driven Manim math animation generation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3147"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve generated videos as static files
output_dir = Path("backend/output")
if output_dir.exists():
    app.mount("/videos", StaticFiles(directory=str(output_dir)), name="videos")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
