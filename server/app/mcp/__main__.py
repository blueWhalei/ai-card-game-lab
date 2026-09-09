"""Run CardLab MCP: ``poetry run python -m app.mcp`` from ``server/``.

Transports:
  stdio (default) — Cursor / Claude Desktop
  streamable-http — standalone HTTP on --host/--port (API already mounts /mcp when
  MCP_HTTP_ENABLED=true)
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="CardLab MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    parser.add_argument("--port", type=int, default=8001, help="HTTP bind port")
    args = parser.parse_args()

    configure_mcp_logging()
    asyncio.run(_prepare())
    server = build_mcp_server(get_experiment_service(), get_decision_service())
    if args.transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
