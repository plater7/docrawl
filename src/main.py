"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

from src.api.routes import router, job_manager

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cancel running jobs on shutdown — closes CONS-014 / issue #60."""
    yield
    await job_manager.shutdown()


app = FastAPI(title="Docrawl", version="0.9.1", lifespan=lifespan)

app.include_router(router, prefix="/api")

UI_PATH = Path(__file__).parent / "ui"


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
