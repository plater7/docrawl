"""FastAPI application entry point."""

import json
import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import router, limiter, job_manager


# ── Structured JSON logging — closes #109 ────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            ):
                log[key] = value
        if record.exc_info:
            log["exc_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else None
            )
        return json.dumps(log, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cancel running jobs on shutdown — closes CONS-014 / issue #60."""
    yield
    await job_manager.shutdown()


# ── App ───────────────────────────────────────────────────────────────────────

API_VERSION = "0.9.7"

app = FastAPI(title="Docrawl", version=API_VERSION, lifespan=lifespan)

UI_PATH = Path(__file__).parent / "ui"

# ── Rate limiter — closes CONS-007 / issue #53 ───────────────────────────────
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc.detail)})


# ── CORS — closes CONS-034 / issue #80 ───────────────────────────────────────
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],
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
        response.headers["X-API-Version"] = API_VERSION
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── API key auth — closes CONS-003 / issue #48 ───────────────────────────────
_API_KEY = os.environ.get("API_KEY", "").strip()

_AUTH_EXEMPT = {"/", "/api/health/ready"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _API_KEY:
            return await call_next(request)
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


# ── Global error sanitization — closes #113 ──────────────────────────────────
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a sanitized error response; never expose internal details."""
    logger.error(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exc_type": type(exc).__name__,
            "detail": traceback.format_exc(),
        },
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
