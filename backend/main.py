"""FastAPI application entry point for manim-agent web backend."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import router, set_store
from .task_store import TaskStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = TaskStore()
    set_store(store)
    app.state.store = store
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
    allow_origins=["http://localhost:3000"],
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
