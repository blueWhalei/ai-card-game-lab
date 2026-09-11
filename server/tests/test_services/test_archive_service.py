"""Tests for ArchiveService."""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.database import connect_sqlite, init_db
from app.schemas.archive import ArchiveRequest, CleanupRequest
from app.services.archive_service import ArchiveService, _write_gzip_json


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
    async def test_get_archive_stats_with_archives(self, archive_service: ArchiveService) -> None:
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
    async def test_archive_with_no_old_games(self, archive_service: ArchiveService) -> None:
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
    async def test_cleanup_with_no_old_data(self, archive_service: ArchiveService) -> None:
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
    async def test_list_archives_with_files(self, archive_service: ArchiveService) -> None:
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
    async def test_delete_nonexistent_archive(self, archive_service: ArchiveService) -> None:
        """Test deleting a nonexistent archive."""
        deleted = await archive_service.delete_archive("nonexistent.jsonl.gz")
        assert deleted is False


async def seed_game(
    service: ArchiveService, game_id: str = "old", status: str = "finished", *, recent: bool = False
) -> Path:
    old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    finished = datetime.now(UTC).isoformat() if recent else old
    relative = f"games/2020-01-01/{game_id}.jsonl"
    path = service._data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"type":"game_end"}\n', encoding="utf-8")
    async with connect_sqlite(service._sqlite_path) as db:
        await db.execute(
            "INSERT INTO games (id, game_type, status, player_ids, data_file, created_at, finished_at) "
            "VALUES (?, 'doudizhu', ?, '[]', ?, ?, ?)",
            (game_id, status, relative, old, finished),
        )
        await db.execute(
            "INSERT INTO rounds (game_id, round_num, player_id, action_type, created_at) "
            "VALUES (?, 1, 'p1', 'PASS', ?)",
            (game_id, old),
        )
        await db.execute(
            "INSERT INTO traces (id, game_id, round_number, player_id, model, prompt_version, "
            "input_snapshot, output_data, metrics, created_at) "
            "VALUES (?, ?, 1, 'p1', 'baseline', 'v3', '{}', '{}', '{}', ?)",
            (f"trace_{game_id}", game_id, old),
        )
        await db.execute(
            "INSERT INTO spans (id, trace_id, span_type, start_time, status, data) "
            "VALUES (?, ?, 'tool', ?, 'completed', ?)",
            (f"span_{game_id}", f"trace_{game_id}", old, '{"result":42}'),
        )
        await db.execute(
            "INSERT INTO decision_points (id, game_id, round_number, player_id, hand_cards, "
            "game_phase, legal_actions, chosen_action, created_at) "
            "VALUES (?, ?, 1, 'p1', '[]', 'playing', '[]', '{}', ?)",
            (f"decision_{game_id}", game_id, old),
        )
        await db.commit()
    return path


async def table_counts(service: ArchiveService) -> dict[str, int]:
    counts = {}
    async with connect_sqlite(service._sqlite_path) as db:
        for table in ("games", "rounds", "traces", "spans", "decision_points"):
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            assert row is not None
            counts[table] = row[0]
    return counts


async def test_archive_preserves_all_related_records(archive_service: ArchiveService) -> None:
    path = await seed_game(archive_service)
    dry = await archive_service.archive_old_games(ArchiveRequest(dry_run=True))
    assert dry.archived_games == 1
    assert set((await table_counts(archive_service)).values()) == {1}
    assert list(archive_service._archive_dir.iterdir()) == []
    result = await archive_service.archive_old_games(ArchiveRequest(dry_run=False))
    assert result.archive_file is not None
    with gzip.open(result.archive_file, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    for name in ("games", "rounds", "traces", "spans", "decisions"):
        assert len(data[name]) == 1
    assert data["spans"][0]["trace_id"] == data["traces"][0]["id"]
    assert json.loads(data["spans"][0]["data"]) == {"result": 42}
    assert data["metadata"]["spans_count"] == 1
    assert set((await table_counts(archive_service)).values()) == {0}
    assert path.exists()  # Archiving retains original game JSONL; cleanup is explicit.


async def test_cleanup_uses_persisted_dated_path(archive_service: ArchiveService) -> None:
    old_path = await seed_game(archive_service)
    active_path = await seed_game(archive_service, "active", "running")
    dry = await archive_service.cleanup_old_data(CleanupRequest(dry_run=True))
    assert dry.deleted_games == 1
    assert old_path.exists()
    result = await archive_service.cleanup_old_data(CleanupRequest(dry_run=False))
    assert result.deleted_jsonl_files == 1
    assert not old_path.exists()
    assert active_path.exists()
    assert set((await table_counts(archive_service)).values()) == {1}


@pytest.mark.parametrize("status", ["created", "running", "paused"])
async def test_active_games_are_excluded(archive_service: ArchiveService, status: str) -> None:
    await seed_game(archive_service, status=status)
    stats = await archive_service.get_archive_stats()
    assert stats["games_older_than_30d"] == 0
    result = await archive_service.archive_old_games(ArchiveRequest(dry_run=False))
    assert result.archived_games == 0
    assert set((await table_counts(archive_service)).values()) == {1}


@pytest.mark.parametrize("status", ["finished", "failed", "cancelled"])
async def test_retention_uses_completion_time(archive_service: ArchiveService, status: str) -> None:
    await seed_game(archive_service, status=status, recent=True)
    result = await archive_service.cleanup_old_data(CleanupRequest(dry_run=False))
    assert result.deleted_games == 0


@pytest.mark.parametrize("days", [0, -1, 36501])
def test_retention_validation(days: int) -> None:
    for schema in (ArchiveRequest, CleanupRequest):
        with pytest.raises(ValidationError):
            schema(days_old=days)


@pytest.mark.parametrize(
    "filename", ["../victim.jsonl.gz", "..\\victim.jsonl.gz", "x:stream.jsonl.gz", "x.db"]
)
async def test_archive_delete_rejects_unsafe_names(
    archive_service: ArchiveService, filename: str
) -> None:
    victim = archive_service._data_dir / "victim.jsonl.gz"
    victim.write_text("keep", encoding="utf-8")
    assert not await archive_service.delete_archive(filename)
    assert victim.read_text(encoding="utf-8") == "keep"


async def test_archive_delete_rejects_symlink(archive_service: ArchiveService) -> None:
    victim = archive_service._data_dir / "victim.jsonl.gz"
    victim.write_text("keep", encoding="utf-8")
    link = archive_service._archive_dir / "link.jsonl.gz"
    try:
        link.symlink_to(victim)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    assert not await archive_service.delete_archive(link.name)
    assert victim.exists()


async def test_cleanup_rejects_paths_outside_games(archive_service: ArchiveService) -> None:
    await seed_game(archive_service)
    victim = archive_service._data_dir / "victim.jsonl"
    victim.write_text("keep", encoding="utf-8")
    async with connect_sqlite(archive_service._sqlite_path) as db:
        await db.execute("UPDATE games SET data_file = 'games/../victim.jsonl'")
        await db.commit()
    result = await archive_service.cleanup_old_data(CleanupRequest(dry_run=False))
    assert result.deleted_jsonl_files == 0
    assert victim.exists()


async def test_archive_publication_failure_keeps_database(
    archive_service: ArchiveService, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_game(archive_service)

    def fail_link(source: Path, target: Path) -> None:
        raise OSError("publication failed")

    monkeypatch.setattr("app.services.archive_service.os.link", fail_link)
    with pytest.raises(OSError, match="publication failed"):
        await archive_service.archive_old_games(ArchiveRequest(dry_run=False))
    assert set((await table_counts(archive_service)).values()) == {1}
    assert list(archive_service._archive_dir.iterdir()) == []


def test_archive_publication_never_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "existing.jsonl.gz"
    _write_gzip_json(target, {"original": True})
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        _write_gzip_json(target, {"replacement": True})
    assert target.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


async def test_archive_names_are_unique(archive_service: ArchiveService) -> None:
    paths = await asyncio.gather(
        *(archive_service._write_archive([], [], [], [], [], "cutoff") for _ in range(8))
    )
    assert len(set(paths)) == 8
    assert all(path.is_file() for path in paths)


async def test_concurrent_archives_only_delete_once(archive_service: ArchiveService) -> None:
    await seed_game(archive_service)
    results = await asyncio.gather(
        *(archive_service.archive_old_games(ArchiveRequest(dry_run=False)) for _ in range(2))
    )
    assert sorted(result.archived_games for result in results) == [0, 1]
    assert len(list(archive_service._archive_dir.glob("*.jsonl.gz"))) == 1
