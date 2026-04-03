"""Tests for ArchiveService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.database import init_db
from app.schemas.archive import ArchiveRequest, CleanupRequest
from app.services.archive_service import ArchiveService


@pytest.fixture
async def archive_service(tmp_path: Path) -> ArchiveService:
    """Create an ArchiveService instance for testing."""
    db_path = str(tmp_path / "test.db")
    data_dir = str(tmp_path / "data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    await init_db(db_path)
    return ArchiveService(sqlite_path=db_path, data_dir=data_dir)


class TestArchiveServiceStats:
    """Test archive statistics."""

    @pytest.mark.asyncio
    async def test_get_archive_stats_empty(self, archive_service: ArchiveService) -> None:
        """Test stats when no data exists."""
        stats = await archive_service.get_archive_stats()
        assert stats["total_games"] == 0
        assert stats["total_rounds"] == 0
        assert stats["archive_files"] == 0

    @pytest.mark.asyncio
    async def test_get_archive_stats_with_archives(
        self, archive_service: ArchiveService
    ) -> None:
        """Test stats with existing archive files."""
        archive_dir = Path(archive_service._archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "test_archive.jsonl.gz").write_bytes(b"test")

        stats = await archive_service.get_archive_stats()
        assert stats["archive_files"] == 1
        assert stats["archive_size_bytes"] > 0


class TestArchiveServiceArchive:
    """Test game archiving."""

    @pytest.mark.asyncio
    async def test_archive_dry_run(self, archive_service: ArchiveService) -> None:
        """Test archive dry run doesn't modify data."""
        request = ArchiveRequest(days_old=30, dry_run=True)
        result = await archive_service.archive_old_games(request)
        assert result.archived_games == 0
        assert result.archive_file is None

    @pytest.mark.asyncio
    async def test_archive_with_no_old_games(
        self, archive_service: ArchiveService
    ) -> None:
        """Test archive when no old games exist."""
        request = ArchiveRequest(days_old=30, dry_run=False)
        result = await archive_service.archive_old_games(request)
        assert result.archived_games == 0


class TestArchiveServiceCleanup:
    """Test data cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_dry_run(self, archive_service: ArchiveService) -> None:
        """Test cleanup dry run doesn't modify data."""
        request = CleanupRequest(days_old=90, dry_run=True)
        result = await archive_service.cleanup_old_data(request)
        assert result.deleted_games == 0
        assert result.freed_bytes == 0

    @pytest.mark.asyncio
    async def test_cleanup_with_no_old_data(
        self, archive_service: ArchiveService
    ) -> None:
        """Test cleanup when no old data exists."""
        request = CleanupRequest(days_old=90, dry_run=False)
        result = await archive_service.cleanup_old_data(request)
        assert result.deleted_games == 0


class TestArchiveServiceArchives:
    """Test archive file management."""

    @pytest.mark.asyncio
    async def test_list_archives_empty(self, archive_service: ArchiveService) -> None:
        """Test listing archives when none exist."""
        archives = await archive_service.list_archives()
        assert archives == []

    @pytest.mark.asyncio
    async def test_list_archives_with_files(
        self, archive_service: ArchiveService
    ) -> None:
        """Test listing archives with files."""
        archive_dir = Path(archive_service._archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "archive_20240101_120000.jsonl.gz").write_bytes(b"test")

        archives = await archive_service.list_archives()
        assert len(archives) == 1
        assert archives[0]["filename"] == "archive_20240101_120000.jsonl.gz"

    @pytest.mark.asyncio
    async def test_delete_archive(self, archive_service: ArchiveService) -> None:
        """Test deleting an archive file."""
        archive_dir = Path(archive_service._archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / "archive_test.jsonl.gz"
        archive_file.write_bytes(b"test")

        deleted = await archive_service.delete_archive("archive_test.jsonl.gz")
        assert deleted is True
        assert not archive_file.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_archive(
        self, archive_service: ArchiveService
    ) -> None:
        """Test deleting a nonexistent archive."""
        deleted = await archive_service.delete_archive("nonexistent.jsonl.gz")
        assert deleted is False
