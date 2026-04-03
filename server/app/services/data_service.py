"""Data statistics and dataset management service."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from app.repositories.dataset_repo import DatasetRepository
from app.repositories.stats_repo import StatsRepository
from app.schemas.data import CreateDatasetRequest
from app.utils.exceptions import DataExportError, DatasetNotFoundError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()


class DataService:
    """Handles data statistics, dataset creation, and export."""

    def __init__(self, sqlite_path: str, data_dir: str) -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = Path(data_dir)

    async def get_stats(self) -> dict[str, Any]:
        """Query aggregate statistics from games and rounds tables."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            stats = StatsRepository(db)

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
            result.append({
                "model": mname,
                "games": gcount,
                "wins": wins,
                "win_rate": round(wins / gcount, 4) if gcount > 0 else 0,
            })
        result.sort(key=lambda x: x["win_rate"], reverse=True)
        return result

    async def list_datasets(self) -> list[dict[str, Any]]:
        """Return all datasets."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DatasetRepository(db)
            return await repo.list_all()

    async def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Get a single dataset by ID."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DatasetRepository(db)
            try:
                return await repo.get_by_id(dataset_id)
            except KeyError:
                raise DatasetNotFoundError(dataset_id)

    async def create_dataset(self, request: CreateDatasetRequest) -> dict[str, Any]:
        """Scan JSONL game files, filter, and export a dataset."""
        dataset_id = generate_id("ds")
        games_dir = self._data_dir / "games"
        datasets_dir = self._data_dir / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)

        output_path = datasets_dir / f"{dataset_id}.jsonl"
        sample_count = await self._export_filtered_jsonl(
            games_dir, output_path, request
        )

        now = datetime.now(tz=timezone.utc).isoformat()
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DatasetRepository(db)
            return await repo.create({
                "id": dataset_id,
                "name": request.name,
                "game_type": request.game_type,
                "filters": request.filters.model_dump(),
                "sample_count": sample_count,
                "file_path": str(output_path.relative_to(self._data_dir)),
                "created_at": now,
            })

    async def _export_filtered_jsonl(
        self,
        games_dir: Path,
        output_path: Path,
        request: CreateDatasetRequest,
    ) -> int:
        """Filter JSONL files and write matching records. Returns sample count."""
        try:
            return await asyncio.to_thread(
                _write_filtered_jsonl, games_dir, output_path, request
            )
        except Exception as e:
            output_path.unlink(missing_ok=True)
            raise DataExportError(str(e))

    async def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset and its file."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DatasetRepository(db)
            try:
                ds = await repo.get_by_id(dataset_id)
            except KeyError:
                raise DatasetNotFoundError(dataset_id)

            file_path = self._data_dir / ds["file_path"]
            file_path.unlink(missing_ok=True)
            await repo.delete(dataset_id)

    @staticmethod
    def _matches_filters(record: dict[str, Any], request: CreateDatasetRequest) -> bool:
        """Check if a JSONL record matches the dataset filters."""
        filters = request.filters
        if record.get("game_type") and record["game_type"] != request.game_type:
            return False
        ts = record.get("timestamp", "")
        if filters.date_from and ts < filters.date_from:
            return False
        if filters.date_to and ts > filters.date_to:
            return False
        if filters.player_ids:
            record_player = record.get("player_id", "")
            record_players = record.get("players", [])
            if record_player and record_player not in filters.player_ids:
                return False
            if record_players and not any(p in filters.player_ids for p in record_players):
                return False
        return True


def _write_filtered_jsonl(
    games_dir: Path, output_path: Path, request: CreateDatasetRequest
) -> int:
    """Synchronous file I/O for dataset export (called via asyncio.to_thread)."""
    sample_count = 0
    with output_path.open("w", encoding="utf-8") as out:
        for jsonl_file in sorted(games_dir.rglob("*.jsonl")):
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if not DataService._matches_filters(record, request):
                    continue
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                sample_count += 1
    return sample_count
