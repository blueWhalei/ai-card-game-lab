"""Collect / cancel-collect for ExperimentService."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_errors import ExperimentValidationError
from app.services.experiment_protocol import (
    clamp_benchmark_collect_count,
    pick_collect_seed,
    protocol_collect_mode,
    protocol_deal_seeds,
    protocol_pair_deals,
    protocol_players,
    set_protocol_deal_seeds,
    set_protocol_pair_deals,
    validate_protocol,
)
from app.services.game_service import GameService
from app.utils.exceptions import ProviderNotConfiguredError
from app.utils.providers import unconfigured_providers_from_players

logger = structlog.get_logger()

ACTIVE_GAME_STATUSES = frozenset({"created", "running", "paused", "pending"})


class ExperimentCollectMixin:
    """Start and stop experiment game collection.

    Host attrs/methods are provided by ``ExperimentService``; stubs below exist
    only so mypy can type-check the mixin in isolation.
    """

    _game_service: GameService

    async def _conn(self) -> aiosqlite.Connection:
        raise NotImplementedError

    async def get_experiment(
        self,
        experiment_id: str,
        *,
        include_games: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def collect(
        self,
        experiment_id: str,
        *,
        count: int,
        db: aiosqlite.Connection,
    ) -> dict[str, Any]:
        experiment = await self.get_experiment(experiment_id, include_games=True)
        player_ids = list(experiment["player_ids"])
        game_type = str(experiment["game_type"])
        existing_games = list(experiment.get("games") or [])
        start_index = len(existing_games)

        now = datetime.now(tz=UTC).isoformat()
        try:
            protocol = validate_protocol(experiment.get("protocol"))
        except ValueError as exc:
            raise ExperimentValidationError(str(exc)) from exc
        protocol = deepcopy(protocol)

        from app.config import Settings

        settings = getattr(self._game_service, "_settings", None)
        frozen_players = protocol_players(protocol)
        if isinstance(settings, Settings):
            missing = unconfigured_providers_from_players(settings, frozen_players)
            if missing:
                raise ProviderNotConfiguredError(missing)

        deal_seeds = protocol_deal_seeds(protocol)
        pair_deals = protocol_pair_deals(protocol)
        collect_mode = protocol_collect_mode(protocol)

        if collect_mode == "benchmark" and not pair_deals:
            try:
                count = clamp_benchmark_collect_count(
                    deal_seeds=deal_seeds,
                    start_index=start_index,
                    count=count,
                )
            except ValueError as exc:
                raise ExperimentValidationError(str(exc)) from exc

        game_ids: list[str] = []
        for offset in range(count):
            index = start_index + offset
            seed, paired = pick_collect_seed(
                index=index,
                deal_seeds=deal_seeds,
                pair_deals=pair_deals,
                collect_mode=collect_mode,
            )

            game = await self._game_service.create_game(
                game_type=game_type,
                player_ids=player_ids,
                mode="batch",
                db=db,
                experiment_id=experiment_id,
                deal_seed=seed,
                paired=paired,
                frozen_players=frozen_players,
            )
            await self._game_service.start_game(game["id"], db=db)
            game_ids.append(game["id"])

        set_protocol_deal_seeds(protocol, deal_seeds)
        set_protocol_pair_deals(protocol, pair_deals)
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            await repo.update_protocol(experiment_id, protocol, updated_at=now)
        finally:
            await conn.close()

        logger.info(
            "experiment_collect_started",
            experiment_id=experiment_id,
            count=len(game_ids),
            deal_seed_count=len(deal_seeds),
        )
        return {"game_ids": game_ids, "count": len(game_ids)}

    async def cancel_collect(self, experiment_id: str) -> dict[str, Any]:
        """Cancel all active games for an experiment (stop an in-flight collect)."""
        experiment = await self.get_experiment(experiment_id, include_games=True)
        cancelled: list[str] = []
        needs_db: list[str] = []
        for game in experiment.get("games") or []:
            status = str(game.get("status") or "")
            if status not in ACTIVE_GAME_STATUSES:
                continue
            game_id = str(game["id"])
            if await self._game_service.cancel_game(game_id):
                cancelled.append(game_id)
            else:
                needs_db.append(game_id)

        if needs_db:
            from app.repositories.game_repo import GameRepository

            conn = await self._conn()
            try:
                repo = GameRepository(conn)
                for game_id in needs_db:
                    await repo.update_status(game_id, "cancelled")
                    cancelled.append(game_id)
            finally:
                await conn.close()

        logger.info(
            "experiment_collect_cancelled",
            experiment_id=experiment_id,
            cancelled_count=len(cancelled),
        )
        return {"cancelled_game_ids": cancelled, "count": len(cancelled)}
