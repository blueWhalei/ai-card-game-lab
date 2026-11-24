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


STUDY_FINANCE_SQL = """
CREATE TABLE IF NOT EXISTS study_budget_revisions (
    study_id TEXT NOT NULL REFERENCES studies(id),
    revision INTEGER NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('CNY','USD','EUR')),
    limit_units INTEGER CHECK (limit_units >= 0),
    enforcement_enabled INTEGER NOT NULL CHECK (enforcement_enabled IN (0,1)),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (study_id,revision),
    CHECK (enforcement_enabled = 0 OR limit_units IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS study_expenses (
    id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES studies(id),
    request_id TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('CNY','USD','EUR')),
    amount_units INTEGER NOT NULL CHECK (amount_units >= 0),
    incurred_on TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    scope_description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    voided_at TEXT,
    void_reason TEXT,
    UNIQUE (study_id,request_id),
    UNIQUE (study_id,source_reference)
);
CREATE INDEX IF NOT EXISTS idx_study_expenses_order
    ON study_expenses(study_id,created_at DESC,id DESC);
"""


async def _v7_study_finance(db: aiosqlite.Connection) -> None:
    await db.executescript(STUDY_FINANCE_SQL)


STUDY_BILLING_SQL = """
CREATE TABLE IF NOT EXISTS study_billing_configs (
    study_id TEXT NOT NULL REFERENCES studies(id),
    revision INTEGER NOT NULL,
    organization_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    start_date TEXT NOT NULL,
    limit_amount TEXT,
    enforcement_enabled INTEGER NOT NULL CHECK (enforcement_enabled IN (0,1)),
    max_age_hours INTEGER NOT NULL CHECK (max_age_hours BETWEEN 1 AND 24),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (study_id,revision),
    CHECK (enforcement_enabled = 0 OR limit_amount IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS study_billing_attempts (
    id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','interrupted')),
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_code TEXT,
    amount TEXT,
    items_json TEXT,
    FOREIGN KEY (study_id,revision) REFERENCES study_billing_configs(study_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_billing_attempts_scope
    ON study_billing_attempts(study_id,revision,started_at DESC,id DESC);
"""


async def _v8_study_billing(db: aiosqlite.Connection) -> None:
    await db.executescript(STUDY_BILLING_SQL)


STUDY_BILLING_SCHEDULE_SQL = """
CREATE TABLE IF NOT EXISTS study_billing_schedule_revisions (
    study_id TEXT NOT NULL REFERENCES studies(id),
    revision INTEGER NOT NULL,
    config_revision INTEGER NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    interval_minutes INTEGER NOT NULL CHECK (interval_minutes BETWEEN 15 AND 720),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (study_id,revision),
    FOREIGN KEY (study_id,config_revision) REFERENCES study_billing_configs(study_id,revision)
);
CREATE TABLE IF NOT EXISTS study_billing_schedule_runtime (
    study_id TEXT PRIMARY KEY,
    schedule_revision INTEGER NOT NULL,
    next_due_at TEXT,
    last_attempt_id TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (study_id,schedule_revision) REFERENCES study_billing_schedule_revisions(study_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_billing_schedule_due ON study_billing_schedule_runtime(next_due_at);
CREATE TABLE IF NOT EXISTS billing_scheduler_heartbeat (
    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
    checked_at TEXT NOT NULL
);
"""


async def _v9_billing_schedule(db: aiosqlite.Connection) -> None:
    await db.executescript(STUDY_BILLING_SCHEDULE_SQL)
    await _add_column(db, "study_billing_attempts", "trigger", "TEXT NOT NULL DEFAULT 'manual'")
    await _add_column(db, "study_billing_attempts", "schedule_revision", "INTEGER")


STUDY_BILLING_RECONCILIATION_SQL = """
CREATE TABLE IF NOT EXISTS billing_reconciliations (
    id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES studies(id),
    attempt_id TEXT NOT NULL REFERENCES study_billing_attempts(id),
    request_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('matched','difference','not_comparable')),
    comparison_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (study_id,request_id)
);
CREATE INDEX IF NOT EXISTS idx_reconciliation_study ON billing_reconciliations(study_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS billing_reconciliation_reviews (
    record_id TEXT NOT NULL REFERENCES billing_reconciliations(id),
    revision INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('resolve','reopen','void')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (record_id,revision)
);
CREATE TABLE IF NOT EXISTS billing_reconciliation_policies (
    study_id TEXT NOT NULL REFERENCES studies(id),
    revision INTEGER NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (study_id,revision)
);
"""


async def _v10_billing_reconciliation(db: aiosqlite.Connection) -> None:
    await db.executescript(STUDY_BILLING_RECONCILIATION_SQL)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "decision_points.policy_kind", _v1_decision_policy_kind),
    Migration(2, "experiment_configs.policy_kind", _v2_experiment_config_policy_kind),
    Migration(3, "decision_points.tool_calls", _v3_decision_tool_calls),
    Migration(4, "decision_points.annotation", _v4_decision_annotation),
    Migration(5, "experiment_memory", _v5_experiment_memory),
    Migration(6, "experiment_collect_requests", _v6_collect_requests),
    Migration(7, "study budgets and registered expenses", _v7_study_finance),
    Migration(8, "supplier cost snapshots and independent limits", _v8_study_billing),
    Migration(9, "opt-in supplier cost schedules and durable due times", _v9_billing_schedule),
    Migration(
        10,
        "supplier cost reconciliation evidence and review admission policy",
        _v10_billing_reconciliation,
    ),
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
