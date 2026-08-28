"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import Settings
from app.database import init_db, open_db_connection
from app.core.ai.prompts.registry import get_registry
from app.dependencies import get_experiment_config_service
from app.utils.exceptions import AppError
from app.utils.logger import setup_logging

logger = structlog.get_logger()

try:
    _APP_VERSION = pkg_version("ai-card-game-lab")
except Exception:
    _APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    settings: Settings = app.state.settings
    setup_logging(debug=settings.app_debug)
    logger.info("application_starting", name=settings.app_name)

    await init_db(settings.sqlite_path)
    db = await open_db_connection(settings.sqlite_path)
    try:
        seeded = await get_registry().seed_defaults(db)
        if seeded:
            logger.info("prompt_templates_seeded", count=seeded)
    finally:
        await db.close()

    await get_experiment_config_service().initialize()

    # Wire env A/B settings into the in-process prompt registry
    registry = get_registry()
    registry._default_version = settings.prompt_version
    registry._ab_test_enabled = settings.prompt_ab_test_enabled
    registry._ab_test_ratio = settings.prompt_ab_test_ratio

    yield

    logger.info("application_shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application instance."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title=settings.app_name,
        version=_APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.settings = settings

    # ── CORS ──────────────────────────────────────────
    cors_origins = settings.cors_origins
    allow_credentials = len(cors_origins) > 0 and "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
            },
        )

    # ── Routes ────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()
