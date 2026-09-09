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
from app.core.ai.prompts.registry import get_registry
from app.database import init_db, open_db_connection
from app.dependencies import get_experiment_config_service
from app.mcp.http_app import McpHttpMount, build_mcp_http_mount
from app.services.startup_recovery import recover_orphaned_runtime
from app.utils.exceptions import AppError
from app.utils.logger import setup_logging
from app.utils.runtime_dirs import ensure_runtime_dirs

logger = structlog.get_logger()

try:
    _APP_VERSION = pkg_version("ai-card-game-lab")
except Exception:
    _APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application instance."""
    if settings is None:
        settings = Settings()

    mcp_mount: McpHttpMount | None = None
    if settings.mcp_http_enabled:
        mcp_mount = build_mcp_http_mount(
            host="127.0.0.1",
            enforce_host_check=settings.mcp_http_enforce_host,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Startup / shutdown; MCP session manager runs alongside when enabled."""
        cfg: Settings = app.state.settings
        setup_logging(debug=cfg.app_debug)
        logger.info("application_starting", name=cfg.app_name)

        ensure_runtime_dirs(cfg)
        await init_db(cfg.sqlite_path)
        recovered = await recover_orphaned_runtime(cfg.sqlite_path)
        if recovered["games"] or recovered["training_tasks"]:
            logger.warning("startup_orphans_closed", **recovered)
        db = await open_db_connection(cfg.sqlite_path)
        try:
            seeded = await get_registry().seed_defaults(db)
            if seeded:
                logger.info("prompt_templates_seeded", count=seeded)
        finally:
            await db.close()

        await get_experiment_config_service().initialize()

        mount: McpHttpMount | None = getattr(app.state, "mcp_http_mount", None)
        if mount is not None:
            async with mount.server.session_manager.run():
                logger.info("mcp_http_ready", path="/mcp")
                yield
        else:
            yield

        logger.info("application_shutdown")

    app = FastAPI(
        title=settings.app_name,
        version=_APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.settings = settings
    app.state.mcp_http_mount = mcp_mount

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

    if mcp_mount is not None:
        app.mount("/mcp", mcp_mount.asgi)

    return app


app = create_app()
