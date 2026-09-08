"""Run CardLab MCP over stdio: ``poetry run python -m app.mcp`` from ``server/``."""

from __future__ import annotations

import asyncio

from app.database import init_db
from app.dependencies import get_decision_service, get_experiment_service, get_settings
from app.mcp.server import build_mcp_server, configure_mcp_logging
from app.utils.runtime_dirs import ensure_runtime_dirs


async def _prepare() -> None:
    settings = get_settings()
    ensure_runtime_dirs(settings)
    await init_db(settings.sqlite_path)


def main() -> None:
    configure_mcp_logging()
    asyncio.run(_prepare())
    server = build_mcp_server(get_experiment_service(), get_decision_service())
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
