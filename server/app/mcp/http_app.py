"""Mount CardLab MCP tools on Streamable HTTP (same tools as stdio)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from app.dependencies import get_decision_service, get_experiment_service
from app.mcp.server import build_mcp_server
from app.services.decision_service import DecisionService
from app.services.experiment_service import ExperimentService

# Path on the MCP Starlette app when the parent mounts at ``/mcp``.
MCP_STREAMABLE_PATH = "/"


@dataclass(frozen=True)
class McpHttpMount:
    """Streamable HTTP ASGI app plus the MCPServer that owns its session manager."""

    server: MCPServer[Any]
    asgi: Starlette


def build_mcp_http_mount(
    experiment_service: ExperimentService | None = None,
    decision_service: DecisionService | None = None,
    *,
    host: str = "127.0.0.1",
    enforce_host_check: bool = True,
) -> McpHttpMount:
    """Build MCP Streamable HTTP mount (route ``/`` → parent should mount at ``/mcp``)."""
    mcp = build_mcp_server(
        experiment_service or get_experiment_service(),
        decision_service or get_decision_service(),
    )
    security: TransportSecuritySettings | None = None
    if not enforce_host_check:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    asgi = mcp.streamable_http_app(
        streamable_http_path=MCP_STREAMABLE_PATH,
        host=host,
        json_response=True,
        # One request = one session; fits local agent clients and simplifies tests.
        stateless_http=True,
        transport_security=security,
    )
    return McpHttpMount(server=mcp, asgi=asgi)
