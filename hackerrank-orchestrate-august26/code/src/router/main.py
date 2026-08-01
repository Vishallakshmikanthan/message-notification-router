"""FastAPI Application Main Entry Point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from router.core.config.settings import get_settings
from router.core.logging.logger import configure_logger, get_logger

settings = get_settings()
configure_logger(log_level=settings.log_level, is_dev=(settings.app_env == "development"))
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle event manager."""
    logger.info("Initializing system foundation...", app_env=settings.app_env)
    yield
    logger.info("Shutting down system foundation...")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("router.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
