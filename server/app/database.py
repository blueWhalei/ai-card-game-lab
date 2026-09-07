"""SQLite database connection management and schema initialization."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

import aiosqlite
import structlog

from app.migrations import migrate

_bound_connection: ContextVar[aiosqlite.Connection | None] = ContextVar(
    "bound_sqlite_connection",
    default=None,
)

logger = structlog.get_logger()

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    hypothesis    TEXT    NOT NULL DEFAULT '',
    conclusion    TEXT    NOT NULL DEFAULT '',
    tags          TEXT    NOT NULL DEFAULT '[]',
    game_type     TEXT    NOT NULL,
    player_ids    TEXT    NOT NULL,
    target_games  INTEGER NOT NULL DEFAULT 1,
    protocol      TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);

CREATE TABLE IF NOT EXISTS games (
    id             TEXT PRIMARY KEY,
    game_type      TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'created',
    player_ids     TEXT    NOT NULL,
    winner_id      TEXT,
    winner_role    TEXT,
    total_rounds   INTEGER DEFAULT 0,
    data_file      TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    finished_at    TEXT,
    metadata       TEXT,
    experiment_id  TEXT    REFERENCES experiments(id)
);

CREATE INDEX IF NOT EXISTS idx_games_type         ON games(game_type);
CREATE INDEX IF NOT EXISTS idx_games_status       ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_created      ON games(created_at);

CREATE TABLE IF NOT EXISTS rounds (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id          TEXT    NOT NULL REFERENCES games(id),
    round_num        INTEGER NOT NULL,
    player_id        TEXT    NOT NULL,
    action_type      TEXT    NOT NULL,
    cards            TEXT,
    hand_snapshot    TEXT,
    prompt           TEXT,
    raw_response     TEXT,
    prompt_tokens    INTEGER,
    completion_tokens INTEGER,
    total_tokens     INTEGER,
    response_time_ms INTEGER,
    model_provider   TEXT,
    model_name       TEXT,
    created_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rounds_game   ON rounds(game_id);
CREATE INDEX IF NOT EXISTS idx_rounds_player ON rounds(player_id);

CREATE TABLE IF NOT EXISTS datasets (
    id           TEXT PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE,
    game_type    TEXT    NOT NULL,
    filters      TEXT    NOT NULL,
    sample_count INTEGER NOT NULL,
    file_path    TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS training_tasks (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    dataset_id    TEXT    NOT NULL REFERENCES datasets(id),
    base_model    TEXT    NOT NULL,
    training_type TEXT    NOT NULL,
    config        TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    progress      REAL    DEFAULT 0,
    result        TEXT,
    model_path    TEXT,
    created_at    TEXT    NOT NULL,
    finished_at   TEXT,
    experiment_id TEXT    REFERENCES experiments(id)
);

-- Prompt template versions for A/B testing and version control
CREATE TABLE IF NOT EXISTS prompt_templates (
    id           TEXT PRIMARY KEY,
    template_key TEXT    NOT NULL,  -- e.g., 'doudizhu_playing', 'doudizhu_bidding'
    version      TEXT    NOT NULL,  -- e.g., 'v1', 'v2'
    content      TEXT    NOT NULL,  -- Full prompt template content
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    UNIQUE(template_key, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_key      ON prompt_templates(template_key);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_active   ON prompt_templates(is_active);

-- AI Decision Traces for observability
CREATE TABLE IF NOT EXISTS traces (
    id              TEXT PRIMARY KEY,
    game_id         TEXT    NOT NULL,
    round_number    INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    prompt_version  TEXT    NOT NULL,
    input_snapshot  TEXT    NOT NULL,
    output_data     TEXT    NOT NULL,
    metrics         TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_traces_game     ON traces(game_id);
CREATE INDEX IF NOT EXISTS idx_traces_player   ON traces(player_id);
CREATE INDEX IF NOT EXISTS idx_traces_created  ON traces(created_at);

-- Spans for sub-operations within a trace
CREATE TABLE IF NOT EXISTS spans (
    id          TEXT PRIMARY KEY,
    trace_id    TEXT    NOT NULL REFERENCES traces(id),
    span_type   TEXT    NOT NULL,
    start_time  TEXT    NOT NULL,
    end_time    TEXT,
    status      TEXT    NOT NULL DEFAULT 'pending',
    data        TEXT
);

CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);

-- Decision Points for SFT training data
-- quality_score is an end-game outcome proxy (win=0.8 / lose=0.3 / draw=0.5),
-- not reasoning quality. Use train_usable for SFT filtering.
-- ev_loss is the per-decision signal: value given up versus the best evaluated
-- candidate. NULL means not evaluated, which is not the same as 0.0 (best move).
CREATE TABLE IF NOT EXISTS decision_points (
    id              TEXT PRIMARY KEY,
    game_id         TEXT    NOT NULL,
    round_number    INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    hand_cards      TEXT    NOT NULL,
    opponent_hands  TEXT,
    last_action     TEXT,
    game_phase      TEXT    NOT NULL,
    legal_actions   TEXT    NOT NULL,
    chosen_action   TEXT    NOT NULL,
    thinking        TEXT,
    outcome         TEXT,
    quality_score   REAL    DEFAULT 0.5,
    train_usable    INTEGER NOT NULL DEFAULT 1,
    train_usable_reason TEXT NOT NULL DEFAULT '',
    ev_loss         REAL,
    evaluator_params TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_points_game    ON decision_points(game_id);
CREATE INDEX IF NOT EXISTS idx_decision_points_player  ON decision_points(player_id);
CREATE INDEX IF NOT EXISTS idx_decision_points_quality ON decision_points(quality_score);
-- idx_decision_points_train_usable lives in migration 1: this script also runs
-- against pre-migration databases, where indexing a migration-added column fails.

CREATE TABLE IF NOT EXISTS experiment_configs (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    model_config  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
"""


async def init_db(sqlite_path: str) -> None:
    """Create the database file, apply the schema, then run pending migrations."""
    db_dir = Path(sqlite_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    async with connect_sqlite(sqlite_path) as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()
        version = await migrate(db)

    logger.info("database_initialized", path=sqlite_path, schema_version=version)


async def apply_connection_pragmas(db: aiosqlite.Connection) -> None:
    """Apply WAL, busy timeout, and foreign keys on a live connection."""
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")


@asynccontextmanager
async def connect_sqlite(sqlite_path: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield a pragma-configured SQLite connection."""
    db = await aiosqlite.connect(sqlite_path)
    try:
        await apply_connection_pragmas(db)
        yield db
    finally:
        await db.close()


async def open_db_connection(sqlite_path: str) -> aiosqlite.Connection:
    """Open a configured SQLite connection for non-request usage."""
    db = await aiosqlite.connect(sqlite_path)
    await apply_connection_pragmas(db)
    return db


async def get_db_connection(sqlite_path: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection, closing it on exit."""
    async with connect_sqlite(sqlite_path) as db:
        yield db


@asynccontextmanager
async def bind_game_connection(
    db: aiosqlite.Connection,
) -> AsyncIterator[aiosqlite.Connection]:
    """Reuse ``db`` for Decision/Trace writes inside a game loop."""
    token = _bound_connection.set(db)
    try:
        yield db
    finally:
        _bound_connection.reset(token)


@asynccontextmanager
async def connect_or_reuse(
    sqlite_path: str,
    db: aiosqlite.Connection | None = None,
) -> AsyncIterator[aiosqlite.Connection]:
    """Yield ``db``, the bound game connection, or a new pragma-configured one."""
    if db is not None:
        yield db
        return
    bound = _bound_connection.get()
    if bound is not None:
        yield bound
        return
    async with connect_sqlite(sqlite_path) as owned:
        yield owned
