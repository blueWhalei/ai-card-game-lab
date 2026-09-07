"""Numbered schema migrations tracked by ``PRAGMA user_version``.

Replaces a stack of ``try: ALTER TABLE ... except OperationalError: pass``, which
could neither tell what version a database was at nor distinguish "column already
exists" from a read-only disk.

No Alembic: a single-file, single-machine SQLite database does not earn the
dependency.

``_SCHEMA_SQL`` in ``database.py`` creates a database; migrations only change one.
Adding a column therefore means two edits: the column in the schema (so fresh
databases get it) and a migration (so existing ones do too).
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


async def _v1_baseline(db: aiosqlite.Connection) -> None:
    """Columns and indexes that used to be added by best-effort ALTER statements.

    Deliberately idempotent: an existing database sits at ``user_version = 0``
    whether or not those statements ever ran, so version 1 has to check rather
    than assume. Fresh databases already have everything from the schema, making
    this a no-op for them.
    """
    for table, column, definition in (
        ("rounds", "total_tokens", "INTEGER"),
        ("rounds", "all_hands", "TEXT"),
        ("decision_points", "train_usable", "INTEGER NOT NULL DEFAULT 1"),
        ("decision_points", "train_usable_reason", "TEXT NOT NULL DEFAULT ''"),
        ("games", "experiment_id", "TEXT"),
        ("training_tasks", "experiment_id", "TEXT"),
        ("experiments", "protocol", "TEXT"),
        ("experiments", "hypothesis", "TEXT NOT NULL DEFAULT ''"),
        ("experiments", "conclusion", "TEXT NOT NULL DEFAULT ''"),
        ("experiments", "tags", "TEXT NOT NULL DEFAULT '[]'"),
    ):
        await _add_column(db, table, column, definition)

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_decision_points_train_usable "
        "ON decision_points(train_usable)",
        "CREATE INDEX IF NOT EXISTS idx_games_experiment ON games(experiment_id)",
        "CREATE INDEX IF NOT EXISTS idx_training_tasks_experiment ON training_tasks(experiment_id)",
    ):
        await db.execute(statement)


async def _v2_ai_players_to_experiment_configs(db: aiosqlite.Connection) -> None:
    """Fold the retired ``ai_players`` table into ``experiment_configs``."""
    if not await _has_table(db, "ai_players"):
        return
    await db.execute(
        """
        INSERT OR IGNORE INTO experiment_configs
            (id, name, notes, model_config, created_at, updated_at)
        SELECT id, name, COALESCE(description, ''), model_config, created_at, updated_at
        FROM ai_players
        """
    )
    await db.execute("DROP TABLE ai_players")
    logger.info("migrated_ai_players_to_experiment_configs")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "baseline columns and indexes", _v1_baseline),
    Migration(2, "ai_players -> experiment_configs", _v2_ai_players_to_experiment_configs),
)

SCHEMA_VERSION = MIGRATIONS[-1].version


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
