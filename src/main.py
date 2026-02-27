"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import router, limiter, job_manager

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cancel running jobs on shutdown — closes CONS-014 / issue #60."""
    yield
    await job_manager.shutdown()


APP_VERSION = "0.9.6a"

app = FastAPI(title="Docrawl", version=APP_VERSION, lifespan=lifespan)

# ── Rate limiter state + error handler ───────────────────────────────────────
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc.detail)})


# ── CORS — closes CONS-034 / issue #80 ───────────────────────────────────────
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],  # empty = same-origin only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Api-Key"],
)


# ── Security headers — closes CONS-022 / issue #68 ───────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── API key auth — closes CONS-003 / issue #48 ───────────────────────────────
_API_KEY = os.environ.get("API_KEY", "").strip()

_AUTH_EXEMPT = {"/", "/api/health/ready"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth if no API_KEY is configured (dev-local mode)
        if not _API_KEY:
            return await call_next(request)
        # Skip auth for exempt paths
        if request.url.path in _AUTH_EXEMPT:
            return await call_next(request)
        key = request.headers.get("X-Api-Key", "")
        if key != _API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized — X-Api-Key required"},
            )
        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

app.include_router(router, prefix="/api")

UI_PATH = Path(__file__).parent / "ui"


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
