"""Schema migration behaviour: fresh databases and downgrades."""

from pathlib import Path

import aiosqlite
import pytest

from app.database import connect_sqlite, init_db
from app.migrations import SCHEMA_VERSION, get_schema_version
from app.utils.exceptions import SchemaVersionError


async def _columns(db: aiosqlite.Connection, table: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in await cursor.fetchall()}


async def test_a_fresh_database_is_stamped_at_the_current_version(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "fresh.db")

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION
        assert "all_hands" in await _columns(db, "rounds")
        decision_columns = await _columns(db, "decision_points")
        assert {
            "train_usable_reason",
            "ev_loss",
            "evaluator_params",
            "action_id",
            "prompt_messages",
            "parse_fallback",
        } <= decision_columns


async def test_initialising_twice_changes_nothing(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "twice.db")

    await init_db(sqlite_path)
    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION


async def test_a_newer_database_is_refused(tmp_path: Path) -> None:
    """Reading a newer schema with an older build would corrupt data quietly."""
    sqlite_path = str(tmp_path / "from_the_future.db")
    await init_db(sqlite_path)
    async with connect_sqlite(sqlite_path) as db:
        await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1:d}")
        await db.commit()

    with pytest.raises(SchemaVersionError):
        await init_db(sqlite_path)
