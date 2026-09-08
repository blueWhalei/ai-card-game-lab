"""Build the CardLab stdio MCP server (read-only tools)."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from mcp.server.mcpserver import MCPServer

from app.mcp import tools as tool_impl
from app.services.decision_service import DecisionService
from app.services.experiment_service import ExperimentService


def configure_mcp_logging() -> None:
    """Keep stdout clean for JSON-RPC; send human logs to stderr."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def build_mcp_server(
    experiment_service: ExperimentService,
    decision_service: DecisionService,
) -> MCPServer[Any]:
    """Register the four read-only tools against injected services."""
    mcp = MCPServer(
        name="cardlab",
        instructions=(
            "CardLab local research tools: list/read experiments and decision points. "
            "Read-only; use the HTTP API or UI for collect/train."
        ),
    )

    @mcp.tool(name="list_experiments", description="List experiments with next_step and slim delta")
    async def list_experiments() -> dict[str, Any]:
        return await tool_impl.list_experiments(experiment_service)

    @mcp.tool(
        name="get_experiment",
        description="Get one experiment (next_step, delta, validation). Games off by default.",
    )
    async def get_experiment(
        experiment_id: str,
        include_games: bool = False,
    ) -> dict[str, Any]:
        return await tool_impl.get_experiment(
            experiment_service,
            experiment_id,
            include_games=include_games,
        )

    @mcp.tool(
        name="list_decision_points",
        description="List decision points (experiment_id/game_id filters; limit default 20, max 100)",
    )
    async def list_decision_points(
        experiment_id: str | None = None,
        game_id: str | None = None,
        train_usable: bool | None = None,
        max_ev_loss: float | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await tool_impl.list_decision_points(
            decision_service,
            experiment_id=experiment_id,
            game_id=game_id,
            train_usable=train_usable,
            max_ev_loss=max_ev_loss,
            limit=limit,
        )

    @mcp.tool(
        name="get_decision_stats",
        description="Aggregate decision-point stats (optional experiment_id)",
    )
    async def get_decision_stats(experiment_id: str | None = None) -> dict[str, Any]:
        return await tool_impl.get_decision_stats(
            decision_service,
            experiment_id=experiment_id,
        )

    return mcp
