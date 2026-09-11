"""Numbered schema migrations tracked by ``PRAGMA user_version``.

``_SCHEMA_SQL`` in ``database.py`` creates a database; migrations only change one
that already exists.

Adding a column therefore means two edits — the column in ``_SCHEMA_SQL`` so new
databases get it, and a migration here so existing ones do too:

    async def _vN_thing(db: aiosqlite.Connection) -> None:
        await _add_column(db, "table", "thing", "TEXT")

    MIGRATIONS = (..., Migration(N, "table.thing", _vN_thing),)

An index over a migration-added column belongs in the migration as well.

No Alembic: a single-file, single-machine SQLite database does not earn the
dependency.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiosqlite
import structlog

from app.utils.exceptions import SchemaVersionError

logger = structlog.get_logger()


@dataclass(frozen=True)
class Migration:
    """One forward step. ``apply`` must leave the database usable if it raises."""

    version: int
    description: str
    apply: Callable[[aiosqlite.Connection], Awaitable[None]]


async def _has_table(db: aiosqlite.Connection, table: str) -> bool:
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return await cursor.fetchone() is not None


async def _has_column(db: aiosqlite.Connection, table: str, column: str) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in await cursor.fetchall())


async def _add_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    """Add a column only when it is missing, so the step can run on any database."""
    if not await _has_table(db, table) or await _has_column(db, table, column):
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _v1_decision_policy_kind(db: aiosqlite.Connection) -> None:
    await _add_column(db, "decision_points", "policy_kind", "TEXT NOT NULL DEFAULT 'llm'")


async def _v2_experiment_config_policy_kind(db: aiosqlite.Connection) -> None:
    await _add_column(db, "experiment_configs", "policy_kind", "TEXT NOT NULL DEFAULT 'llm'")


async def _v3_decision_tool_calls(db: aiosqlite.Connection) -> None:
    await _add_column(db, "decision_points", "tool_calls", "TEXT")


async def _v4_decision_annotation(db: aiosqlite.Connection) -> None:
    await _add_column(db, "decision_points", "annotation", "TEXT")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_points_annotation ON decision_points(annotation)"
    )


async def _v5_experiment_memory(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS experiment_memory (
            experiment_id TEXT NOT NULL,
            player_id     TEXT NOT NULL,
            notes         TEXT NOT NULL DEFAULT '',
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (experiment_id, player_id)
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_experiment_memory_experiment "
        "ON experiment_memory(experiment_id)"
    )


async def _v6_collect_requests(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS experiment_collect_requests (
            experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            request_key TEXT NOT NULL,
            requested_count INTEGER NOT NULL,
            start_index INTEGER NOT NULL,
            game_count INTEGER NOT NULL,
            game_ids TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (experiment_id, request_key)
        )
    """)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "decision_points.policy_kind", _v1_decision_policy_kind),
    Migration(2, "experiment_configs.policy_kind", _v2_experiment_config_policy_kind),
    Migration(3, "decision_points.tool_calls", _v3_decision_tool_calls),
    Migration(4, "decision_points.annotation", _v4_decision_annotation),
    Migration(5, "experiment_memory", _v5_experiment_memory),
    Migration(6, "experiment_collect_requests", _v6_collect_requests),
)

SCHEMA_VERSION = MIGRATIONS[-1].version if MIGRATIONS else 0


async def get_schema_version(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def migrate(db: aiosqlite.Connection) -> int:
    """Apply every pending migration and return the resulting version.

    Each step commits on its own, so an interrupted run leaves the recorded
    version telling the truth and resumes from there.

    Raises:
        SchemaVersionError: if the database is newer than this build understands.
    """
    current = await get_schema_version(db)
    if current > SCHEMA_VERSION:
        raise SchemaVersionError(found=current, supported=SCHEMA_VERSION)

    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        await migration.apply(db)
        # PRAGMA does not accept bind parameters; version comes from our own table.
        await db.execute(f"PRAGMA user_version = {migration.version:d}")
        await db.commit()
        logger.info(
            "schema_migrated",
            version=migration.version,
            description=migration.description,
        )

    return SCHEMA_VERSION
