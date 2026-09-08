"""Data statistics and dataset management service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.database import connect_sqlite
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.stats_repo import StatsRepository
from app.schemas.data import CreateDatasetFromDecisionsRequest
from app.services.decision_service import DecisionService
from app.utils.exceptions import DatasetNotFoundError, NoExportableDataError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()


class DataService:
    """Handles data statistics, dataset creation, and export."""

    def __init__(self, sqlite_path: str, data_dir: str) -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = Path(data_dir)
        self._decision_service = DecisionService(sqlite_path=sqlite_path, data_dir=data_dir)

    async def get_stats(self, experiment_id: str | None = None) -> dict[str, Any]:
        """Query aggregate statistics from games and rounds tables."""
        async with connect_sqlite(self._sqlite_path) as db:
            stats = StatsRepository(db, experiment_id=experiment_id)

            # --- 基础统计 ---
            total_games = await stats.total_games()
            total_rounds = await stats.total_rounds()
            avg_ms = await stats.avg_response_time_ms()
            games_by_type = await stats.games_by_type()
            models_usage = await stats.models_usage()

            # --- Token 用量统计 ---
            total_tokens = await stats.total_tokens()
            total_prompt_tokens = await stats.total_prompt_tokens()
            total_completion_tokens = await stats.total_completion_tokens()
            tokens_by_model = await stats.tokens_by_model()

            # --- 对局质量分析 ---
            avg_game_rounds = await stats.avg_game_rounds()
            games_with_winner = await stats.games_with_winner()
            wins_by_role = await stats.wins_by_role()

            # --- AI 表现对比（各模型胜率）---
            model_win_rates = await self._compute_model_win_rates(stats)

            # --- 响应时间分析 ---
            p50_ms, p95_ms = await stats.response_time_percentiles()
            response_time_by_model = await stats.response_time_by_model()

        return {
            "total_games": total_games,
            "total_rounds": total_rounds,
            "games_by_type": games_by_type,
            "models_usage": models_usage,
            "avg_response_time_ms": round(avg_ms, 1) if avg_ms else 0,
            # Token 用量
            "total_tokens": total_tokens or 0,
            "total_prompt_tokens": total_prompt_tokens or 0,
            "total_completion_tokens": total_completion_tokens or 0,
            "tokens_by_model": tokens_by_model,
            # 对局质量
            "avg_game_rounds": round(avg_game_rounds, 1) if avg_game_rounds else 0,
            "games_with_winner": games_with_winner,
            "wins_by_role": wins_by_role,
            # AI 表现
            "ai_win_rates": model_win_rates,
            # 响应时间
            "p50_response_ms": p50_ms,
            "p95_response_ms": p95_ms,
            "response_time_by_model": response_time_by_model,
        }

    async def _compute_model_win_rates(self, stats: StatsRepository) -> list[dict[str, Any]]:
        """Compute per-model win rates from game and round data."""
        model_game_counts = await stats.model_game_counts()
        winner_rows = await stats.game_winner_rows()
        game_model_players = await stats.model_player_mapping()

        model_wins: dict[str, int] = {}
        for gid, wid, _player_ids in winner_rows:
            pmap = game_model_players.get(gid, {})
            mname = pmap.get(wid)
            if mname:
                model_wins[mname] = model_wins.get(mname, 0) + 1

        result: list[dict[str, Any]] = []
        for mname, gcount in model_game_counts.items():
            wins = model_wins.get(mname, 0)
            result.append(
                {
                    "model": mname,
                    "games": gcount,
                    "wins": wins,
                    "win_rate": round(wins / gcount, 4) if gcount > 0 else 0,
                }
            )
        result.sort(key=lambda x: x["win_rate"], reverse=True)
        return result

    async def list_datasets(self) -> list[dict[str, Any]]:
        """Return all datasets."""
        async with connect_sqlite(self._sqlite_path) as db:
            repo = DatasetRepository(db)
            return await repo.list_all()

    async def create_dataset_from_decisions(
        self,
        request: CreateDatasetFromDecisionsRequest,
    ) -> dict[str, Any]:
        """Export decision points to ChatML and register as a training dataset."""
        dataset_id = generate_id("ds")
        datasets_dir = self._data_dir / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)
        output_path = datasets_dir / f"{dataset_id}_chatml.jsonl"

        filepath, sample_count, split_meta = await self._decision_service.export_chatml(
            game_id=request.game_id,
            experiment_id=request.experiment_id,
            player_id=request.player_id,
            min_quality=request.min_quality,
            outcome=request.outcome,
            game_phase=request.game_phase,
            train_usable=request.train_usable,
            train_usable_only=request.train_usable_only,
            max_ev_loss=request.max_ev_loss,
            include_thinking=request.include_thinking,
            output_path=str(output_path),
            eval_ratio=request.eval_ratio,
        )
        if not filepath or sample_count == 0:
            output_path.unlink(missing_ok=True)
            raise NoExportableDataError("No decision points to export into a dataset")

        now = datetime.now(tz=UTC).isoformat()
        filters: dict[str, Any] = {
            "source": "decisions",
            "format": "chatml",
            "train_usable": request.train_usable,
            "train_usable_only": request.train_usable_only,
            "max_ev_loss": request.max_ev_loss,
            "include_thinking": request.include_thinking,
            "game_id": request.game_id,
            "experiment_id": request.experiment_id,
            "player_id": request.player_id,
            "min_quality": request.min_quality,
            "outcome": request.outcome,
            "game_phase": request.game_phase,
            "eval_ratio": request.eval_ratio,
            "eval_sample_count": split_meta.get("eval_sample_count", 0),
            "eval_game_ids": split_meta.get("eval_game_ids") or [],
        }
        eval_file = split_meta.get("eval_file_path")
        if eval_file:
            try:
                filters["eval_file_path"] = str(Path(eval_file).relative_to(self._data_dir))
            except ValueError:
                filters["eval_file_path"] = eval_file
        async with connect_sqlite(self._sqlite_path) as db:
            repo = DatasetRepository(db)
            return await repo.create(
                {
                    "id": dataset_id,
                    "name": request.name,
                    "game_type": request.game_type,
                    "filters": filters,
                    "sample_count": sample_count,
                    "file_path": str(output_path.relative_to(self._data_dir)),
                    "created_at": now,
                }
            )

    async def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset and its file."""
        async with connect_sqlite(self._sqlite_path) as db:
            repo = DatasetRepository(db)
            try:
                ds = await repo.get_by_id(dataset_id)
            except KeyError:
                raise DatasetNotFoundError(dataset_id) from None

            file_path = self._data_dir / ds["file_path"]
            file_path.unlink(missing_ok=True)
            await repo.delete(dataset_id)
