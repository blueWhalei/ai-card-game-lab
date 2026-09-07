"""Schema migration behaviour: fresh databases, legacy ones, and downgrades."""

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
        assert {"train_usable_reason", "ev_loss", "evaluator_params"} <= await _columns(
            db, "decision_points"
        )


async def test_initialising_twice_changes_nothing(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "twice.db")

    await init_db(sqlite_path)
    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION


async def test_a_legacy_database_gains_columns_without_losing_rows(tmp_path: Path) -> None:
    """A database from before the migration table existed sits at version 0.

    Shaped like a real old database: the original columns are present and only the
    ones that used to arrive via best-effort ALTER statements are missing.
    Indexes in the base schema reference original columns, so those must exist.
    """
    sqlite_path = str(tmp_path / "legacy.db")
    async with connect_sqlite(sqlite_path) as db:
        await db.executescript(
            """
            CREATE TABLE decision_points (
                id            TEXT PRIMARY KEY,
                game_id       TEXT NOT NULL,
                round_number  INTEGER NOT NULL,
                player_id     TEXT NOT NULL,
                hand_cards    TEXT NOT NULL,
                game_phase    TEXT NOT NULL,
                legal_actions TEXT NOT NULL,
                chosen_action TEXT NOT NULL,
                thinking      TEXT,
                outcome       TEXT,
                quality_score REAL DEFAULT 0.5,
                created_at    TEXT NOT NULL
            );
            CREATE TABLE experiments (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                notes        TEXT NOT NULL DEFAULT '',
                game_type    TEXT NOT NULL,
                player_ids   TEXT NOT NULL,
                target_games INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            INSERT INTO decision_points VALUES
                ('d1', 'g1', 1, 'p1', '[]', 'playing', '[]', '{}', NULL, NULL, 0.8,
                 '2026-01-01');
            INSERT INTO experiments VALUES
                ('e1', 'old run', '', 'doudizhu', '[]', 5, '2026-01-01', '2026-01-01');
            """
        )
        await db.commit()
        assert await get_schema_version(db) == 0

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION
        decision_columns = await _columns(db, "decision_points")
        assert {
            "train_usable",
            "train_usable_reason",
            "ev_loss",
            "evaluator_params",
        } <= decision_columns
        assert {"protocol", "hypothesis", "conclusion", "tags"} <= await _columns(db, "experiments")

        kept = await (await db.execute("SELECT id FROM decision_points")).fetchall()
        assert [row[0] for row in kept] == ["d1"]
        row = await (
            await db.execute("SELECT train_usable, tags FROM decision_points, experiments")
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "[]"


async def test_retired_ai_players_table_is_folded_in(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "ai_players.db")
    async with connect_sqlite(sqlite_path) as db:
        await db.executescript(
            """
            CREATE TABLE ai_players (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT,
                model_config TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            INSERT INTO ai_players VALUES
                ('a1', 'old player', 'note', '{}', '2026-01-01', '2026-01-01');
            """
        )
        await db.commit()

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        moved = await (
            await db.execute("SELECT name, notes FROM experiment_configs WHERE id='a1'")
        ).fetchone()
        assert moved is not None
        assert moved[0] == "old player"
        assert moved[1] == "note"

        remaining = await (
            await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_players'"
            )
        ).fetchone()
        assert remaining is None


async def test_a_newer_database_is_refused(tmp_path: Path) -> None:
    """Reading a newer schema with an older build corrupts data quietly."""
    sqlite_path = str(tmp_path / "from_the_future.db")
    await init_db(sqlite_path)
    async with connect_sqlite(sqlite_path) as db:
        await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1:d}")
        await db.commit()

    with pytest.raises(SchemaVersionError):
        await init_db(sqlite_path)
