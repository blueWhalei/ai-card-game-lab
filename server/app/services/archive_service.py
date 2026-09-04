"""Data archiving and cleanup service.

Provides functionality to:
1. Archive finished games past a day threshold into compressed files
2. Remove those rows from the database
3. Manage storage lifecycle
"""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from app.database import connect_sqlite
from app.repositories.archive_repo import ArchiveRepository
from app.schemas.archive import ArchiveRequest, ArchiveResult, CleanupRequest, CleanupResult

logger = structlog.get_logger()


class ArchiveService:
    """Handles data archiving and cleanup operations."""

    def __init__(self, sqlite_path: str, data_dir: str) -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = Path(data_dir)
        self._archive_dir = self._data_dir / "archives"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    async def get_archive_stats(self) -> dict[str, Any]:
        """Get statistics about archivable data."""
        async with connect_sqlite(self._sqlite_path) as db:
            repo = ArchiveRepository(db)

            total_games = await repo.count_games()
            total_rounds = await repo.count_rounds()
            total_traces = await repo.count_traces()
            total_decisions = await repo.count_decisions()

            old_30d = await repo.count_old_games(30)
            old_90d = await repo.count_old_games(90)
            old_180d = await repo.count_old_games(180)

        archive_files = list(self._archive_dir.glob("*.jsonl.gz"))
        archive_size = sum(f.stat().st_size for f in archive_files)

        return {
            "total_games": total_games,
            "total_rounds": total_rounds,
            "total_traces": total_traces,
            "total_decisions": total_decisions,
            "games_older_than_30d": old_30d,
            "games_older_than_90d": old_90d,
            "games_older_than_180d": old_180d,
            "archive_files": len(archive_files),
            "archive_size_bytes": archive_size,
        }

    async def archive_old_games(self, request: ArchiveRequest) -> ArchiveResult:
        """Archive games older than specified days to compressed files."""
        cutoff = datetime.now(UTC) - timedelta(days=request.days_old)
        cutoff_str = cutoff.isoformat()

        async with connect_sqlite(self._sqlite_path) as db:
            repo = ArchiveRepository(db)

            games = await repo.fetch_old_games(cutoff_str, request.game_type)
            if not games:
                return ArchiveResult(
                    archived_games=0,
                    archived_rounds=0,
                    archived_traces=0,
                    archived_decisions=0,
                    archive_file=None,
                    freed_bytes=0,
                )

            game_ids = [g["id"] for g in games]
            rounds = await repo.fetch_rounds_for_games(game_ids)
            traces = await repo.fetch_traces_for_games(game_ids)
            decisions = await repo.fetch_decisions_for_games(game_ids)

            if request.dry_run:
                return ArchiveResult(
                    archived_games=len(games),
                    archived_rounds=len(rounds),
                    archived_traces=len(traces),
                    archived_decisions=len(decisions),
                    archive_file=None,
                    freed_bytes=0,
                )

            archive_file = await self._write_archive(
                games, rounds, traces, decisions, cutoff_str
            )

            db_size_before = Path(self._sqlite_path).stat().st_size

            await repo.delete_by_game_ids(game_ids)
            await db.execute("VACUUM")

            db_size_after = Path(self._sqlite_path).stat().st_size
            freed_bytes = db_size_before - db_size_after

            logger.info(
                "games_archived",
                count=len(games),
                archive_file=str(archive_file),
                freed_bytes=freed_bytes,
            )

            return ArchiveResult(
                archived_games=len(games),
                archived_rounds=len(rounds),
                archived_traces=len(traces),
                archived_decisions=len(decisions),
                archive_file=str(archive_file),
                freed_bytes=freed_bytes,
            )

    async def cleanup_old_data(self, request: CleanupRequest) -> CleanupResult:
        """Permanently delete old data (use with caution)."""
        cutoff = datetime.now(UTC) - timedelta(days=request.days_old)
        cutoff_str = cutoff.isoformat()

        async with connect_sqlite(self._sqlite_path) as db:
            repo = ArchiveRepository(db)

            old_games = await repo.fetch_old_games(cutoff_str, request.game_type)
            game_ids = [g["id"] for g in old_games]

            if not game_ids:
                return CleanupResult(
                    deleted_games=0,
                    deleted_rounds=0,
                    deleted_traces=0,
                    deleted_decisions=0,
                    deleted_jsonl_files=0,
                    freed_bytes=0,
                )

            rounds_count = await repo.count_rounds_for_games(game_ids)
            traces_count = await repo.count_traces_for_games(game_ids)
            decisions_count = await repo.count_decisions_for_games(game_ids)

            if request.dry_run:
                return CleanupResult(
                    deleted_games=len(game_ids),
                    deleted_rounds=rounds_count,
                    deleted_traces=traces_count,
                    deleted_decisions=decisions_count,
                    deleted_jsonl_files=0,
                    freed_bytes=0,
                )

            db_size_before = Path(self._sqlite_path).stat().st_size

            await repo.delete_by_game_ids(game_ids)
            await db.execute("VACUUM")

            db_size_after = Path(self._sqlite_path).stat().st_size
            freed_bytes = db_size_before - db_size_after

            jsonl_deleted = await self._cleanup_jsonl_files(game_ids)

            logger.info(
                "data_cleaned_up",
                games=len(game_ids),
                rounds=rounds_count,
                freed_bytes=freed_bytes,
            )

            return CleanupResult(
                deleted_games=len(game_ids),
                deleted_rounds=rounds_count,
                deleted_traces=traces_count,
                deleted_decisions=decisions_count,
                deleted_jsonl_files=jsonl_deleted,
                freed_bytes=freed_bytes,
            )

    async def list_archives(self) -> list[dict[str, Any]]:
        """List all archive files with metadata."""
        archives = []
        for f in sorted(self._archive_dir.glob("*.jsonl.gz"), reverse=True):
            archives.append(
                {
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "created_at": datetime.fromtimestamp(f.stat().st_ctime, UTC).isoformat(),
                }
            )
        return archives

    async def delete_archive(self, filename: str) -> bool:
        """Delete an archive file."""
        archive_path = self._archive_dir / filename
        if not archive_path.exists() or not archive_path.is_relative_to(self._archive_dir):
            return False
        archive_path.unlink()
        logger.info("archive_deleted", filename=filename)
        return True

    async def _write_archive(
        self,
        games: list[dict[str, Any]],
        rounds: list[dict[str, Any]],
        traces: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        cutoff: str,
    ) -> Path:
        """Write archive data to a compressed JSONL file."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        archive_file = self._archive_dir / f"archive_{timestamp}.jsonl.gz"

        archive_data = {
            "metadata": {
                "created_at": datetime.now(UTC).isoformat(),
                "cutoff_date": cutoff,
                "games_count": len(games),
                "rounds_count": len(rounds),
                "traces_count": len(traces),
                "decisions_count": len(decisions),
            },
            "games": games,
            "rounds": rounds,
            "traces": traces,
            "decisions": decisions,
        }

        await asyncio.to_thread(
            _write_gzip_json, archive_file, archive_data
        )

        return archive_file

    async def _cleanup_jsonl_files(self, game_ids: list[str]) -> int:
        """Remove JSONL files for archived game IDs."""
        games_dir = self._data_dir / "games"
        if not games_dir.exists():
            return 0

        deleted = 0
        for game_id in game_ids:
            jsonl_file = games_dir / f"{game_id}.jsonl"
            if jsonl_file.exists():
                jsonl_file.unlink()
                deleted += 1

        return deleted


def _write_gzip_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON data to a gzip file (called via asyncio.to_thread)."""
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
