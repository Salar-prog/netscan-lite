import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from netscan_lite.api import auth_router, router
from netscan_lite.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Initializing ns-lite database...")
    init_db()
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

    @app.get("/health", tags=["System"])
    def health_check():
        return {"status": "healthy", "service": "ns-lite"}

    return app


app = create_app()
