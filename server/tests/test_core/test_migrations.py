"""Schema migration behaviour: fresh databases and downgrades."""

from pathlib import Path

import aiosqlite
import pytest

from app.database import connect_sqlite, init_db
from app.migrations import SCHEMA_VERSION, get_schema_version, migrate
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
            "policy_kind",
            "tool_calls",
            "annotation",
        } <= decision_columns
        assert "policy_kind" in await _columns(db, "experiment_configs")


async def test_initialising_twice_changes_nothing(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "twice.db")

    await init_db(sqlite_path)
    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION


async def test_v5_database_gains_collection_reservations(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "legacy_collect.db")
    await init_db(sqlite_path)
    async with connect_sqlite(sqlite_path) as db:
        await db.execute("DROP TABLE experiment_collect_requests")
        await db.execute("PRAGMA user_version = 5")
        await db.commit()
        await migrate(db)
        assert await get_schema_version(db) == 6
        assert {"experiment_id", "request_key", "requested_count", "start_index", "game_ids"} <= (
            await _columns(db, "experiment_collect_requests")
        )


async def test_a_newer_database_is_refused(tmp_path: Path) -> None:
    """Reading a newer schema with an older build would corrupt data quietly."""
    sqlite_path = str(tmp_path / "from_the_future.db")
    await init_db(sqlite_path)
    async with connect_sqlite(sqlite_path) as db:
        await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1:d}")
        await db.commit()

    with pytest.raises(SchemaVersionError):
        await init_db(sqlite_path)


async def test_migration_1_adds_policy_kind_to_legacy_decision_points(
    tmp_path: Path,
) -> None:
    """A pre-policy_kind database gains the column when migrate runs."""
    sqlite_path = str(tmp_path / "legacy.db")
    async with aiosqlite.connect(sqlite_path) as db:
        await db.execute(
            """
            CREATE TABLE decision_points (
                id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                hand_cards TEXT NOT NULL,
                opponent_hands TEXT,
                last_action TEXT,
                game_phase TEXT NOT NULL,
                legal_actions TEXT NOT NULL,
                chosen_action TEXT NOT NULL,
                action_id TEXT NOT NULL DEFAULT '',
                prompt_messages TEXT,
                thinking TEXT,
                outcome TEXT,
                quality_score REAL DEFAULT 0.5,
                train_usable INTEGER NOT NULL DEFAULT 1,
                train_usable_reason TEXT NOT NULL DEFAULT '',
                parse_fallback INTEGER NOT NULL DEFAULT 0,
                ev_loss REAL,
                evaluator_params TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute("PRAGMA user_version = 0")
        await db.commit()

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION
        assert SCHEMA_VERSION == 6
        assert "policy_kind" in await _columns(db, "decision_points")
        assert "tool_calls" in await _columns(db, "decision_points")
        assert "annotation" in await _columns(db, "decision_points")


async def test_migration_2_adds_policy_kind_to_legacy_experiment_configs(
    tmp_path: Path,
) -> None:
    """A database stamped at v1 gains experiment_configs.policy_kind at v2."""
    sqlite_path = str(tmp_path / "legacy_cfg.db")
    async with aiosqlite.connect(sqlite_path) as db:
        await db.execute(
            """
            CREATE TABLE experiment_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                model_config TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            INSERT INTO experiment_configs (id, name, notes, model_config, created_at, updated_at)
            VALUES ('cfg_a', 'A', '', '{"provider":"openai","model_name":"m"}', 't', 't')
            """
        )
        await db.execute("PRAGMA user_version = 1")
        await db.commit()

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION
        assert "policy_kind" in await _columns(db, "experiment_configs")
        cursor = await db.execute("SELECT policy_kind FROM experiment_configs WHERE id = 'cfg_a'")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "llm"


async def test_migration_3_adds_tool_calls_to_legacy_decision_points(
    tmp_path: Path,
) -> None:
    """A database stamped at v2 gains decision_points.tool_calls at v3."""
    sqlite_path = str(tmp_path / "legacy_v2.db")
    async with aiosqlite.connect(sqlite_path) as db:
        await db.execute(
            """
            CREATE TABLE decision_points (
                id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                hand_cards TEXT NOT NULL,
                opponent_hands TEXT,
                last_action TEXT,
                game_phase TEXT NOT NULL,
                legal_actions TEXT NOT NULL,
                chosen_action TEXT NOT NULL,
                action_id TEXT NOT NULL DEFAULT '',
                prompt_messages TEXT,
                thinking TEXT,
                outcome TEXT,
                quality_score REAL DEFAULT 0.5,
                train_usable INTEGER NOT NULL DEFAULT 1,
                train_usable_reason TEXT NOT NULL DEFAULT '',
                parse_fallback INTEGER NOT NULL DEFAULT 0,
                ev_loss REAL,
                evaluator_params TEXT,
                policy_kind TEXT NOT NULL DEFAULT 'llm',
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute("PRAGMA user_version = 2")
        await db.commit()

    await init_db(sqlite_path)

    async with connect_sqlite(sqlite_path) as db:
        assert await get_schema_version(db) == SCHEMA_VERSION
        assert "tool_calls" in await _columns(db, "decision_points")
        assert "annotation" in await _columns(db, "decision_points")
