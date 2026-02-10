"""FastAPI application entry point."""

import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from src.api.routes import router

# Configure logging before anything else
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    force=True,
)
# Prevent uvicorn from overriding our config
logging.getLogger("uvicorn").handlers = []
logging.getLogger("uvicorn.access").handlers = []

logger = logging.getLogger(__name__)
logger.info(f"Logging configured at level {LOG_LEVEL}")

app = FastAPI(title="Docrawl", version="0.1.0")

app.include_router(router, prefix="/api")

UI_PATH = Path(__file__).parent / "ui"


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
