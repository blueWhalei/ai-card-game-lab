"""Game service - coordinates game creation and basic operations."""

from __future__ import annotations

import json as json_mod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.database import open_db_connection
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.utils.exceptions import GameAlreadyStartedError, GameNotFoundError
from app.utils.id_generator import generate_id

if TYPE_CHECKING:
    import aiosqlite

    from app.core.collector.jsonl_writer import JsonlWriter
    from app.core.engine.base import GameState
    from app.core.engine.registry import GameEngineRegistry
    from app.services.game_orchestration_service import GameOrchestrationService
    from app.services.game_replay_service import GameReplayService

logger = structlog.get_logger()


class GameService:
    """Coordinates game creation, listing, and basic operations.

    This service acts as a facade that:
    - Handles game creation and listing
    - Delegates execution to GameOrchestrationService
    - Delegates replay to GameReplayService
    """

    def __init__(
        self,
        engine_registry: GameEngineRegistry,
        collector: JsonlWriter,
        sqlite_path: str,
        orchestration_service: GameOrchestrationService,
        replay_service: GameReplayService,
    ) -> None:
        self._engine_registry = engine_registry
        self._collector = collector
        self._sqlite_path = sqlite_path
        self._orchestration_service = orchestration_service
        self._replay_service = replay_service

    async def _get_bg_db(self) -> aiosqlite.Connection:
        """Open a fresh DB connection for background tasks."""
        return await open_db_connection(self._sqlite_path)

    async def list_games(
        self,
        *,
        game_type: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        db: aiosqlite.Connection | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List games with optional filters and pagination."""
        conn = db or await self._get_bg_db()
        try:
            repo = GameRepository(conn)
            return await repo.list_games(
                game_type=game_type,
                status=status,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        finally:
            if db is None:
                await conn.close()

    async def get_game(
        self,
        game_id: str,
        db: aiosqlite.Connection | None = None,
    ) -> dict[str, Any]:
        """Get a single game by ID."""
        conn = db or await self._get_bg_db()
        try:
            repo = GameRepository(conn)
            try:
                return await repo.get_by_id(game_id)
            except KeyError:
                raise GameNotFoundError(game_id) from None
        finally:
            if db is None:
                await conn.close()

    async def create_game(
        self,
        game_type: str,
        player_ids: list[str],
        mode: str = "realtime",
        db: aiosqlite.Connection | None = None,
    ) -> dict[str, Any]:
        """Create a new game.

        Args:
            game_type: The type of game to create
            player_ids: List of player identifiers
            mode: Game mode (realtime or batch)
            db: Optional database connection

        Returns:
            The created game record
        """
        game_id = generate_id("game")
        now = datetime.now(tz=UTC).isoformat()

        self._engine_registry.get(game_type)

        data_file = self._collector.start_game(game_id, game_type, player_ids)

        conn = db or await self._get_bg_db()
        try:
            game_repo = GameRepository(conn)
            game = await game_repo.create(
                game_id=game_id,
                game_type=game_type,
                player_ids=player_ids,
                data_file=data_file,
                created_at=now,
                status="created",
                metadata={"mode": mode},
            )
        finally:
            if db is None:
                await conn.close()
        logger.info("game_created", game_id=game_id, game_type=game_type)
        return game

    async def start_game(
        self,
        game_id: str,
        db: aiosqlite.Connection | None = None,
    ) -> dict[str, Any]:
        """Start a created game.

        Args:
            game_id: The game identifier
            db: Optional database connection

        Returns:
            The updated game record

        Raises:
            GameNotFoundError: If the game doesn't exist
            GameAlreadyStartedError: If the game has already started
        """
        conn = db or await self._get_bg_db()
        try:
            game_repo = GameRepository(conn)
            try:
                game = await game_repo.get_by_id(game_id)
            except KeyError:
                raise GameNotFoundError(game_id) from None

            if game["status"] not in ("created",):
                raise GameAlreadyStartedError(game_id)

            player_ids_raw = game["player_ids"]
            player_ids = (
                json_mod.loads(player_ids_raw)
                if isinstance(player_ids_raw, str)
                else player_ids_raw
            )

            await conn.execute(
                "UPDATE games SET status = 'running' WHERE id = ?", (game_id,)
            )
            await conn.commit()

            await self._orchestration_service.start_game_execution(
                game_id=game_id,
                game_type=game["game_type"],
                player_ids=player_ids,
            )

            logger.info("game_started", game_id=game_id)

            result = await game_repo.get_by_id(game_id)
        finally:
            if db is None:
                await conn.close()
        return result

    async def pause_game(self, game_id: str) -> None:
        """Pause an active game.

        Args:
            game_id: The game identifier
        """
        await self._orchestration_service.pause_game(game_id)

    async def resume_game(self, game_id: str) -> None:
        """Resume a paused game.

        Args:
            game_id: The game identifier
        """
        await self._orchestration_service.resume_game(game_id)

    def get_game_state(self, game_id: str) -> GameState | None:
        """Get the current state of an active game.

        Args:
            game_id: The game identifier

        Returns:
            The game state if active, None otherwise
        """
        return self._orchestration_service.get_game_state(game_id)

    async def get_replay_data(self, game_id: str) -> dict[str, Any]:
        """Get replay data for a finished game.

        Args:
            game_id: The game identifier

        Returns:
            Dictionary containing game info, rounds, and thinking data
        """
        return await self._replay_service.get_replay_data(game_id)

    async def get_game_rounds(
        self,
        game_id: str,
        db: aiosqlite.Connection,
    ) -> list[dict[str, Any]]:
        """Return all rounds for a game (running or finished)."""
        round_repo = RoundRepository(db)
        return await round_repo.list_by_game(game_id)
