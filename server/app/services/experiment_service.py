"""Experiment (run) service — one researcher session spanning collect → review."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.core.stats.proportion import wilson_interval
from app.database import open_db_connection
from app.repositories.experiment_repo import ExperimentRepository
from app.services.game_service import GameService
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()

_ACTIVE_STATUSES = frozenset({"created", "running", "paused", "pending"})


class ExperimentNotFoundError(AppError):
    def __init__(self, experiment_id: str) -> None:
        super().__init__(
            message=f"Experiment not found: {experiment_id}",
            code="EXPERIMENT_NOT_FOUND",
            status_code=404,
        )


class ExperimentValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="EXPERIMENT_VALIDATION_FAILED",
            status_code=400,
        )


def derive_experiment_status(
    *,
    target_games: int,
    total_games: int,
    active_games: int,
    finished_games: int,
) -> str:
    """Derive UI status from game rows (not persisted)."""
    if total_games == 0:
        return "pending_collect"
    if active_games > 0:
        return "collecting"
    if finished_games >= target_games:
        return "ready_review"
    return "ready_more"


class ExperimentService:
    """Manages experiment runs and collection against GameService."""

    def __init__(self, sqlite_path: str, game_service: GameService) -> None:
        self._sqlite_path = sqlite_path
        self._game_service = game_service

    async def _conn(self) -> aiosqlite.Connection:
        return await open_db_connection(self._sqlite_path)

    async def create_experiment(
        self,
        *,
        name: str,
        notes: str,
        game_type: str,
        player_ids: list[str],
        target_games: int,
    ) -> dict[str, Any]:
        min_players, max_players = self._game_service.player_slots(game_type)
        n_players = len(player_ids)
        if n_players < min_players or n_players > max_players:
            if min_players == max_players:
                raise ExperimentValidationError(
                    f"{game_type} 实验需要恰好 {min_players} 个选手配置"
                )
            raise ExperimentValidationError(
                f"{game_type} 实验需要 {min_players}-{max_players} 个选手配置"
            )
        if len(set(player_ids)) != n_players:
            raise ExperimentValidationError("选手配置不能重复")

        missing = [
            pid
            for pid in player_ids
            if self._game_service._experiment_config_service.get_config(pid) is None
        ]
        if missing:
            from app.utils.exceptions import InvalidPlayerIdsError

            raise InvalidPlayerIdsError(missing)

        experiment_id = generate_id("exp")
        now = datetime.now(tz=UTC).isoformat()
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            await repo.create(
                experiment_id=experiment_id,
                name=name.strip(),
                notes=notes.strip(),
                game_type=game_type,
                player_ids=player_ids,
                target_games=target_games,
                created_at=now,
                updated_at=now,
            )
        finally:
            await conn.close()
        logger.info("experiment_created", experiment_id=experiment_id)
        return await self.get_experiment(experiment_id, include_games=False)

    async def compare_experiments(self, experiment_ids: list[str]) -> dict[str, Any]:
        """Side-by-side metrics for 2–5 experiments, including Wilson CIs."""
        unique_ids = list(dict.fromkeys(experiment_ids))
        if len(unique_ids) < 2 or len(unique_ids) > 5:
            raise ExperimentValidationError("对比需要 2 到 5 个不重复的实验 ID")

        rows: list[dict[str, Any]] = []
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            for experiment_id in unique_ids:
                try:
                    row = await repo.get_by_id(experiment_id)
                except KeyError as exc:
                    raise ExperimentNotFoundError(experiment_id) from exc
                summary = await self._build_summary(repo, row)
                extras = await repo.compare_aggregates(experiment_id)
                rows.append(self._attach_compare_metrics(row, summary, extras))
        finally:
            await conn.close()
        return {"experiments": rows}

    async def list_experiments(self) -> list[dict[str, Any]]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            rows = await repo.list_all()
            results: list[dict[str, Any]] = []
            for row in rows:
                summary = await self._build_summary(repo, row)
                results.append({**row, "summary": summary})
            return results
        finally:
            await conn.close()

    async def get_experiment(
        self,
        experiment_id: str,
        *,
        include_games: bool = True,
    ) -> dict[str, Any]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            try:
                row = await repo.get_by_id(experiment_id)
            except KeyError as exc:
                raise ExperimentNotFoundError(experiment_id) from exc
            summary = await self._build_summary(repo, row)
            payload: dict[str, Any] = {**row, "summary": summary}
            if include_games:
                games = await repo.list_games(experiment_id)
                payload["games"] = [_normalize_game_row(g) for g in games]
            return payload
        finally:
            await conn.close()

    async def collect(
        self,
        experiment_id: str,
        *,
        count: int,
        db: aiosqlite.Connection,
    ) -> dict[str, Any]:
        experiment = await self.get_experiment(experiment_id, include_games=False)
        player_ids = list(experiment["player_ids"])
        game_type = str(experiment["game_type"])

        game_ids: list[str] = []
        for _ in range(count):
            game = await self._game_service.create_game(
                game_type=game_type,
                player_ids=player_ids,
                mode="batch",
                db=db,
                experiment_id=experiment_id,
            )
            await self._game_service.start_game(game["id"], db=db)
            game_ids.append(game["id"])

        now = datetime.now(tz=UTC).isoformat()
        conn = await self._conn()
        try:
            await ExperimentRepository(conn).touch_updated_at(experiment_id, now)
        finally:
            await conn.close()

        logger.info(
            "experiment_collect_started",
            experiment_id=experiment_id,
            count=len(game_ids),
        )
        return {"game_ids": game_ids, "count": len(game_ids)}

    async def _build_summary(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
    ) -> dict[str, Any]:
        experiment_id = str(experiment["id"])
        target = int(experiment["target_games"])
        games = await repo.list_games(experiment_id)

        active = 0
        finished = 0
        with_winner = 0
        rounds_sum = 0
        rounds_n = 0
        wins_by_config: dict[str, int] = {
            pid: 0 for pid in experiment.get("player_ids") or []
        }
        latest_game_id: str | None = None
        latest_created: str | None = None

        for g in games:
            status = str(g.get("status") or "")
            created = str(g.get("created_at") or "")
            if latest_created is None or created > latest_created:
                latest_created = created
                latest_game_id = str(g["id"])

            if status in _ACTIVE_STATUSES:
                active += 1
            else:
                finished += 1

            winner = g.get("winner_id")
            if winner:
                with_winner += 1
                wid = str(winner)
                if wid in wins_by_config:
                    wins_by_config[wid] += 1

            total_rounds = g.get("total_rounds")
            if isinstance(total_rounds, int) and total_rounds > 0:
                rounds_sum += total_rounds
                rounds_n += 1

        train_usable = await repo.count_train_usable_decisions(experiment_id)
        train_by_player = await repo.count_train_usable_by_player(experiment_id)
        response_by_player = await repo.avg_response_ms_by_player(experiment_id)
        avg_rounds = (rounds_sum / rounds_n) if rounds_n else 0.0
        status = derive_experiment_status(
            target_games=target,
            total_games=len(games),
            active_games=active,
            finished_games=finished,
        )
        player_ids: list[str] = list(experiment.get("player_ids") or [])
        player_stats: list[dict[str, Any]] = []
        for pid in player_ids:
            wins = wins_by_config.get(pid, 0)
            avg_ms, trace_count = response_by_player.get(pid, (0.0, 0))
            win_rate = (wins / with_winner) if with_winner > 0 else 0.0
            player_stats.append(
                {
                    "player_id": pid,
                    "wins": wins,
                    "win_rate": round(win_rate, 4),
                    "train_usable_decisions": train_by_player.get(pid, 0),
                    "avg_response_time_ms": avg_ms,
                    "trace_count": trace_count,
                }
            )
        return {
            "status": status,
            "target_games": target,
            "total_games": len(games),
            "active_games": active,
            "finished_games": finished,
            "games_with_winner": with_winner,
            "train_usable_decisions": train_usable,
            "avg_rounds": round(avg_rounds, 1),
            "wins_by_config": wins_by_config,
            "player_stats": player_stats,
            "latest_game_id": latest_game_id,
        }

    @staticmethod
    def _attach_compare_metrics(
        row: dict[str, Any],
        summary: dict[str, Any],
        extras: dict[str, Any],
    ) -> dict[str, Any]:
        with_winner = int(summary.get("games_with_winner") or 0)
        player_stats: list[dict[str, Any]] = []
        for stat in summary.get("player_stats") or []:
            wins = int(stat.get("wins") or 0)
            low, high = wilson_interval(wins, with_winner)
            player_stats.append(
                {
                    **stat,
                    "win_rate_ci": [round(low, 4), round(high, 4)],
                }
            )
        total_decisions = int(extras.get("decision_count") or 0)
        usable = int(summary.get("train_usable_decisions") or 0)
        train_rate = (usable / total_decisions) if total_decisions else 0.0
        parser_ok = int(extras.get("parser_ok") or 0)
        parser_n = int(extras.get("parser_n") or 0)
        parser_rate = (parser_ok / parser_n) if parser_n else 0.0
        return {
            "id": row["id"],
            "name": row["name"],
            "notes": row.get("notes") or "",
            "game_type": row["game_type"],
            "player_ids": row["player_ids"],
            "finished_games": summary["finished_games"],
            "games_with_winner": with_winner,
            "avg_rounds": summary["avg_rounds"],
            "avg_response_time_ms": extras.get("avg_response_time_ms", 0.0),
            "total_tokens": extras.get("total_tokens", 0),
            "avg_tokens_per_round": extras.get("avg_tokens_per_round", 0.0),
            "train_usable_rate": round(train_rate, 4),
            "train_usable_n": usable,
            "decision_count": total_decisions,
            "parser_success_rate": round(parser_rate, 4),
            "parser_n": parser_n,
            "player_stats": player_stats,
        }


def _normalize_game_row(row: dict[str, Any]) -> dict[str, Any]:
    import json

    out = dict(row)
    if isinstance(out.get("player_ids"), str):
        out["player_ids"] = json.loads(out["player_ids"])
    if isinstance(out.get("metadata"), str):
        out["metadata"] = json.loads(out["metadata"])
    return out
