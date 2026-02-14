"""FastAPI application entry point."""

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from src.api.routes import router

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(title="Docrawl", version="0.1.0")

app.include_router(router, prefix="/api")

UI_PATH = Path(__file__).parent / "ui"


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
