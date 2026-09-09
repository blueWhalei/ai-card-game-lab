"""HTTP MCP mount: same tools as stdio, Streamable HTTP at /mcp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.mcp.http_app import build_mcp_http_mount
from app.mcp.server import build_mcp_server


def test_build_mcp_server_registers_tools() -> None:
    mcp = build_mcp_server(MagicMock(), MagicMock())
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert {
        "list_experiments",
        "get_experiment",
        "list_decision_points",
        "get_decision_stats",
        "start_collect",
        "cancel_collect",
    } <= names


def test_build_mcp_http_mount_path() -> None:
    mount = build_mcp_http_mount(
        experiment_service=MagicMock(),
        decision_service=MagicMock(),
    )
    paths = [getattr(r, "path", None) for r in mount.asgi.routes]
    assert "/" in paths


@pytest.mark.asyncio
async def test_mcp_http_initialize(tmp_path: Path) -> None:
    settings = Settings(
        sqlite_path=str(tmp_path / "app.db"),
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
        mcp_http_enabled=True,
        mcp_http_enforce_host=False,
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        async with app.router.lifespan_context(app):
            resp = await client.post(
                "/mcp/",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                },
            )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("result", {}).get("serverInfo", {}).get("name") == "cardlab"
