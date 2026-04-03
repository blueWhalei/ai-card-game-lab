"""Trace service for AI decision observability."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import aiosqlite
import structlog

from app.repositories.trace_repo import TraceRepository
from app.utils.id_generator import generate_id

if TYPE_CHECKING:
    from app.websocket.manager import ConnectionManager

logger = structlog.get_logger()


class TraceService:
    """Service for recording and querying AI decision traces."""

    def __init__(
        self,
        sqlite_path: str,
        ws_manager: ConnectionManager | None = None,
    ) -> None:
        self._sqlite_path = sqlite_path
        self._ws_manager = ws_manager

    async def create_trace(
        self,
        game_id: str,
        round_number: int,
        player_id: str,
        model: str,
        prompt_version: str,
        input_snapshot: dict[str, Any],
        output_data: dict[str, Any],
        metrics: dict[str, Any],
    ) -> str:
        """Create a new trace record."""
        trace_id = generate_id("tr")
        now = datetime.now(tz=timezone.utc).isoformat()

        async with aiosqlite.connect(self._sqlite_path) as db:
            repo = TraceRepository(db)
            await repo.create_trace(
                trace_id=trace_id,
                game_id=game_id,
                round_number=round_number,
                player_id=player_id,
                model=model,
                prompt_version=prompt_version,
                input_snapshot=input_snapshot,
                output_data=output_data,
                metrics=metrics,
                created_at=now,
            )

        logger.info(
            "trace_created",
            trace_id=trace_id,
            game_id=game_id,
            round_number=round_number,
            player_id=player_id,
        )

        if self._ws_manager:
            trace_data = {
                "id": trace_id,
                "game_id": game_id,
                "round_number": round_number,
                "player_id": player_id,
                "model": model,
                "prompt_version": prompt_version,
                "metrics": metrics,
                "created_at": now,
            }
            await self._ws_manager.broadcast_trace_event(
                game_id=game_id,
                event_type="trace_created",
                trace_data=trace_data,
            )

        return trace_id

    async def create_span(
        self,
        trace_id: str,
        span_type: str,
        start_time: str,
        end_time: str | None = None,
        status: str = "completed",
        data: dict[str, Any] | None = None,
    ) -> str:
        """Create a new span record for a sub-operation."""
        span_id = generate_id("sp")

        async with aiosqlite.connect(self._sqlite_path) as db:
            repo = TraceRepository(db)
            await repo.create_span(
                span_id=span_id,
                trace_id=trace_id,
                span_type=span_type,
                start_time=start_time,
                end_time=end_time,
                status=status,
                data=data,
            )

        return span_id

    async def get_traces_by_game(self, game_id: str) -> list[dict[str, Any]]:
        """Get all traces for a game."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = TraceRepository(db)
            return await repo.get_by_game(game_id)

    async def get_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """Get a single trace by ID with its spans."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = TraceRepository(db)
            trace = await repo.get_by_id(trace_id)
            if not trace:
                return None
            trace["spans"] = await repo.get_spans(trace_id)
            return trace

    async def get_traces_by_player(
        self,
        player_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get traces for a specific player."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = TraceRepository(db)
            return await repo.get_by_player(player_id, limit, offset)

    async def get_metrics(
        self,
        game_id: str | None = None,
        model: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated metrics for traces."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = TraceRepository(db)
            return await repo.get_metrics(
                game_id=game_id,
                model=model,
                start_time=start_time,
                end_time=end_time,
            )

    async def compare_prompt_versions(
        self,
        version1: str,
        version2: str,
    ) -> dict[str, Any]:
        """Compare metrics between two prompt versions."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = TraceRepository(db)
            stats1 = await repo.get_version_stats(version1)
            stats2 = await repo.get_version_stats(version2)

        return {
            "version1": stats1,
            "version2": stats2,
            "response_time_diff": round(
                stats2["avg_response_time_ms"] - stats1["avg_response_time_ms"], 2
            ),
            "success_rate_diff": round(
                stats2["success_rate"] - stats1["success_rate"], 2
            ),
        }
