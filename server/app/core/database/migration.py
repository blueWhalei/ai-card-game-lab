"""Database migration utilities.

Provides tools for migrating data between database backends.
Currently supports SQLite -> PostgreSQL migration path.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import structlog

from app.database import connect_sqlite

logger = structlog.get_logger()

# Valid SQL identifier pattern: alphanumeric + underscore only
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, context: str = "identifier") -> str:
    """Validate a SQL identifier (table/column name) to prevent injection.

    Only allows alphanumeric characters and underscores.
    Raises ValueError if the identifier contains unsafe characters.
    """
    if not _VALID_IDENTIFIER.match(name):
        msg = f"Invalid SQL {context}: {name!r}"
        raise ValueError(msg)
    return name


class MigrationPlan:
    """Represents a database migration plan."""

    def __init__(self, source_type: str, target_type: str) -> None:
        self.source_type = source_type
        self.target_type = target_type
        self.tables: list[str] = []
        self.estimated_rows: dict[str, int] = {}
        self.created_at = datetime.now(UTC)

    def add_table(self, table_name: str, estimated_rows: int = 0) -> None:
        self.tables.append(table_name)
        self.estimated_rows[table_name] = estimated_rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "target_type": self.target_type,
            "tables": self.tables,
            "estimated_rows": self.estimated_rows,
            "created_at": self.created_at.isoformat(),
        }


class MigrationAnalyzer:
    """Analyzes current database for migration planning."""

    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path

    async def analyze(self) -> MigrationPlan:
        """Analyze the SQLite database and create a migration plan."""
        plan = MigrationPlan("sqlite", "postgresql")

        async with connect_sqlite(self._sqlite_path) as db:

            tables_cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'skills_fts'"
            )
            tables = [row[0] for row in await tables_cursor.fetchall()]

            for table in tables:
                _validate_identifier(table, "table name")
                count_cursor = await db.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = (await count_cursor.fetchone())[0]
                plan.add_table(table, count)

        return plan

    async def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Get the schema for a specific table."""
        _validate_identifier(table_name, "table name")
        async with connect_sqlite(self._sqlite_path) as db:
            cursor = await db.execute(f"PRAGMA table_info([{table_name}])")
            return [dict(row) for row in await cursor.fetchall()]

    async def get_indexes(self, table_name: str) -> list[dict[str, Any]]:
        """Get indexes for a specific table."""
        _validate_identifier(table_name, "table name")
        async with connect_sqlite(self._sqlite_path) as db:
            cursor = await db.execute(f"PRAGMA index_list([{table_name}])")
            return [dict(row) for row in await cursor.fetchall()]


class MigrationExporter:
    """Exports SQLite data for migration."""

    def __init__(self, sqlite_path: str, export_dir: str) -> None:
        self._sqlite_path = sqlite_path
        self._export_dir = Path(export_dir)
        self._export_dir.mkdir(parents=True, exist_ok=True)

    async def export_table(
        self,
        table_name: str,
        batch_size: int = 1000,
    ) -> str:
        """Export a table to a JSONL file.

        Returns:
            Path to the exported file
        """
        export_file = self._export_dir / f"{table_name}.jsonl"
        exported_count = 0
        _validate_identifier(table_name, "table name")

        async with connect_sqlite(self._sqlite_path) as db:

            offset = 0
            with export_file.open("w", encoding="utf-8") as f:
                while True:
                    cursor = await db.execute(
                        f"SELECT * FROM [{table_name}] LIMIT ? OFFSET ?",
                        [batch_size, offset],
                    )
                    rows = await cursor.fetchall()
                    if not rows:
                        break

                    for row in rows:
                        f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
                        exported_count += 1

                    offset += batch_size

        logger.info(
            "table_exported",
            table=table_name,
            rows=exported_count,
            file=str(export_file),
        )
        return str(export_file)

    async def export_all_tables(self, tables: list[str]) -> dict[str, str]:
        """Export all specified tables.

        Returns:
            Dict mapping table names to export file paths
        """
        results = {}
        for table in tables:
            results[table] = await self.export_table(table)
        return results


class PostgreSQLSchemaGenerator:
    """Generates PostgreSQL schema from SQLite schema."""

    TYPE_MAPPING: ClassVar[dict[str, str]] = {
        "TEXT": "TEXT",
        "INTEGER": "INTEGER",
        "REAL": "DOUBLE PRECISION",
        "BLOB": "BYTEA",
        "NUMERIC": "NUMERIC",
    }

    def __init__(self) -> None:
        self._schema_parts: list[str] = []

    def add_table(
        self,
        table_name: str,
        columns: list[dict[str, Any]],
        primary_key: str | None = None,
    ) -> None:
        """Add a table definition to the schema."""
        _validate_identifier(table_name, "table name")
        col_defs = []
        for col in columns:
            pg_type = self.TYPE_MAPPING.get(col["type"], "TEXT")
            nullable = "" if col["notnull"] else " NULL"
            default = f" DEFAULT {col['dflt_value']}" if col["dflt_value"] else ""
            col_defs.append(f'    {col["name"]} {pg_type}{nullable}{default}')

        if primary_key:
            col_defs.append(f"    PRIMARY KEY ({primary_key})")

        self._schema_parts.append(
            f"CREATE TABLE IF NOT EXISTS [{table_name}] (\n"
            + ",\n".join(col_defs)
            + "\n);"
        )

    def add_index(
        self, index_name: str, table_name: str, columns: list[str], unique: bool = False
    ) -> None:
        """Add an index definition to the schema."""
        _validate_identifier(index_name, "index name")
        _validate_identifier(table_name, "table name")
        for col in columns:
            _validate_identifier(col, "column name")
        unique_str = "UNIQUE " if unique else ""
        cols = ", ".join(f"[{c}]" for c in columns)
        self._schema_parts.append(
            f"CREATE {unique_str}INDEX IF NOT EXISTS [{index_name}] "
            f"ON [{table_name}] ({cols});"
        )

    def generate(self) -> str:
        """Generate the complete PostgreSQL schema."""
        return "\n\n".join(self._schema_parts)

    async def generate_from_sqlite(
        self, analyzer: MigrationAnalyzer, tables: list[str]
    ) -> str:
        """Generate PostgreSQL schema from SQLite database."""
        for table in tables:
            _validate_identifier(table, "table name")
            columns = await analyzer.get_table_schema(table)
            pk_col = next((c["name"] for c in columns if c["pk"]), None)
            self.add_table(table, columns, pk_col)

            indexes = await analyzer.get_indexes(table)
            for idx in indexes:
                _validate_identifier(idx["name"], "index name")
                async with connect_sqlite(analyzer._sqlite_path) as db:
                    idx_cursor = await db.execute(f"PRAGMA index_info([{idx['name']}])")
                    idx_cols = [row[2] for row in await idx_cursor.fetchall()]
                self.add_index(
                    idx["name"],
                    table,
                    idx_cols,
                    unique=bool(idx["unique"]),
                )

        return self.generate()
