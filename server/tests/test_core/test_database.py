"""SQLite connection pragmas for concurrent game writes."""

from pathlib import Path

from app.database import bind_game_connection, connect_or_reuse, init_db, open_db_connection


async def test_open_db_enables_wal_busy_timeout_and_foreign_keys(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "app.db")
    await init_db(sqlite_path)
    db = await open_db_connection(sqlite_path)
    try:
        journal = await (await db.execute("PRAGMA journal_mode")).fetchone()
        timeout = await (await db.execute("PRAGMA busy_timeout")).fetchone()
        fks = await (await db.execute("PRAGMA foreign_keys")).fetchone()
        assert journal is not None
        assert str(journal[0]).lower() == "wal"
        assert timeout is not None
        assert int(timeout[0]) >= 5000
        assert fks is not None
        assert int(fks[0]) == 1
    finally:
        await db.close()


async def test_bind_game_connection_reuses_same_object(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "reuse.db")
    await init_db(sqlite_path)
    from app.database import connect_sqlite

    async with connect_sqlite(sqlite_path) as db:
        async with bind_game_connection(db):
            async with connect_or_reuse(sqlite_path) as inner:
                assert inner is db


async def test_connect_or_reuse_opens_when_unbound(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "unbound.db")
    await init_db(sqlite_path)
    async with connect_or_reuse(sqlite_path) as db:
        journal = await (await db.execute("PRAGMA journal_mode")).fetchone()
        assert journal is not None
        assert str(journal[0]).lower() == "wal"
