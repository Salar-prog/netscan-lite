import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from netscan_lite.api import auth_router, router, ws_router
from netscan_lite.config import settings
from netscan_lite.db import init_db
from netscan_lite.logging_config import request_id_var, setup_logging

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        )
        if settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=0"
        else:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    # ponytail: in-memory per-worker rate limiter. With WORKERS > 1,
    # effective limit is max_requests × workers. Use reverse proxy
    # rate limiting (nginx limit_req) for global limits in production.
    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()
        self._cleanup_interval: float = 300  # every 5 minutes

    def _cleanup_stale(self, now: float):
        """Remove IPs with no recent requests to prevent memory leak."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_threshold = now - self.window * 2
        stale_ips = [ip for ip, times in self._requests.items() if not times or times[-1] < stale_threshold]
        for ip in stale_ips:
            del self._requests[ip]

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window

        # Prune old entries for this IP
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window_start]

        if len(self._requests[client_ip]) >= self.max_requests:
            return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json")

        self._requests[client_ip].append(now)

        # Periodic cleanup of stale IPs
        self._cleanup_stale(now)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging(log_level="debug" if settings.DEBUG else "info")
    logger.info("Initializing ns-lite database...")
    init_db()
    if not settings.LDAP_ENABLED and settings.DEV_AUTH_ENABLED:
        if settings.DEBUG:
            logger.warning("DEV_AUTH_ENABLED is true — any token is accepted. Do not use in production.")
        else:
            logger.error("DEV_AUTH_ENABLED=true but DEBUG=false — dev auth will be rejected.")
    warnings = settings.validate_production_config()
    for w in warnings:
        logger.warning("Config warning: %s", w)
    logger.info("ns-lite ready")
    yield
    logger.info("ns-lite shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from importlib.metadata import version

    try:
        app_version = version("netscan-lite")
    except Exception:
        app_version = "0.1.0"

    app = FastAPI(
        title="ns-lite API",
        description="Lightweight IP discovery with quarantine logic",
        version=app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(ws_router)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.ENABLE_METRICS:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator().instrument(app).expose(app)
        except ImportError:
            logger.warning("prometheus-fastapi-instrumentator not installed — metrics disabled")

    @app.get("/health", tags=["System"])
    def health_check():
        from sqlalchemy import text

        from netscan_lite.db import engine

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "healthy", "service": "ns-lite"}
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return Response(
                content='{"status":"unhealthy","service":"ns-lite"}',
                status_code=503,
                media_type="application/json",
            )

    @app.get("/health/ready", tags=["System"])
    def readiness_check():
        import shutil

        from sqlalchemy import text

        from netscan_lite.db import engine

        checks = {}
        ok = True

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"
            ok = False

        nmap = shutil.which("nmap")
        checks["nmap"] = "ok" if nmap else "not found"
        if not nmap:
            ok = False

        return Response(
            content='{"status":"%s","checks":%s}' % ("ready" if ok else "not_ready", __import__("json").dumps(checks)),
            status_code=200 if ok else 503,
            media_type="application/json",
        )

    # Mount dashboard static files (built React app).
    # WARNING: This catch-all must be added LAST — any routes added after this will be swallowed.
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="dashboard")

    return app


app = create_app()
