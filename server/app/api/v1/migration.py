"""Database migration API endpoints.

Provides endpoints for analyzing and preparing database migrations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.config import Settings
from app.core.database.migration import (
    MigrationAnalyzer,
    MigrationExporter,
    PostgreSQLSchemaGenerator,
)
from app.dependencies import get_settings
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/analyze")
async def analyze_database(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[dict[str, Any]]:
    """Analyze the current database for migration planning.

    Returns table sizes, row counts, and migration readiness.
    """
    analyzer = MigrationAnalyzer(settings.sqlite_path)
    plan = await analyzer.analyze()
    return ApiResponse(data=plan.to_dict())


@router.get("/schema/{table_name}")
async def get_table_schema(
    table_name: str,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[list[dict[str, Any]]]:
    """Get the schema for a specific table."""
    analyzer = MigrationAnalyzer(settings.sqlite_path)
    schema = await analyzer.get_table_schema(table_name)
    return ApiResponse(data=schema)


@router.post("/export")
async def export_tables(
    tables: list[str] | None = None,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[dict[str, str]]:
    """Export database tables to JSONL files for migration.

    Args:
        tables: List of table names to export (optional, defaults to all)

    Returns:
        Dict mapping table names to export file paths
    """
    analyzer = MigrationAnalyzer(settings.sqlite_path)
    plan = await analyzer.analyze()

    tables_to_export = tables or plan.tables
    exporter = MigrationExporter(
        settings.sqlite_path,
        f"{settings.data_dir}/migration_exports",
    )

    results = await exporter.export_all_tables(tables_to_export)
    return ApiResponse(data=results)


@router.post("/generate-postgres-schema")
async def generate_postgres_schema(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[str]:
    """Generate PostgreSQL schema from current SQLite database.

    Returns SQL statements to create equivalent PostgreSQL tables.
    """
    analyzer = MigrationAnalyzer(settings.sqlite_path)
    plan = await analyzer.analyze()

    generator = PostgreSQLSchemaGenerator()
    schema = await generator.generate_from_sqlite(analyzer, plan.tables)

    return ApiResponse(data=schema)
