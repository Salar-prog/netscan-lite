import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from netscan_lite.api import auth_router, router, ws_router
from netscan_lite.config import settings
from netscan_lite.db import init_db

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
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
    )

    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(ws_router)
    app.add_middleware(SecurityHeadersMiddleware)

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

    # Mount dashboard static files (built React app)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="dashboard")

    return app


app = create_app()
