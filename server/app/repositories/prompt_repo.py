"""Repository for prompt template persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiosqlite
import structlog

from app.core.ai.prompts.registry import PromptTemplate

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class PromptRepository:
    """Repository for managing prompt templates in SQLite."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get_template(
        self,
        template_key: str,
        version: str,
    ) -> PromptTemplate | None:
        """Get a specific template version."""
        async with self._db.execute(
            """
            SELECT id, template_key, version, content, is_active, created_at, updated_at
            FROM prompt_templates
            WHERE template_key = ? AND version = ?
            """,
            (template_key, version),
        ) as cursor:
            row = await cursor.fetchone()
            if row is not None:
                return PromptTemplate(
                    id=row[0],
                    template_key=row[1],
                    version=row[2],
                    content=row[3],
                    is_active=bool(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                )
        return None

    async def get_active_template(
        self,
        template_key: str,
        version: str,
    ) -> PromptTemplate | None:
        """Get an active template version."""
        async with self._db.execute(
            """
            SELECT id, template_key, version, content, is_active, created_at, updated_at
            FROM prompt_templates
            WHERE template_key = ? AND version = ? AND is_active = 1
            """,
            (template_key, version),
        ) as cursor:
            row = await cursor.fetchone()
            if row is not None:
                return PromptTemplate(
                    id=row[0],
                    template_key=row[1],
                    version=row[2],
                    content=row[3],
                    is_active=bool(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                )
        return None

    async def list_templates(
        self,
        template_key: str | None = None,
        active_only: bool = True,
    ) -> list[PromptTemplate]:
        """List templates, optionally filtered by key and active status."""
        conditions = []
        params: list[Any] = []

        if template_key is not None:
            conditions.append("template_key = ?")
            params.append(template_key)
        if active_only:
            conditions.append("is_active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        templates = []
        async with self._db.execute(
            f"""
            SELECT id, template_key, version, content, is_active, created_at, updated_at
            FROM prompt_templates
            WHERE {where_clause}
            ORDER BY template_key, created_at DESC
            """,
            params,
        ) as cursor:
            async for row in cursor:
                templates.append(
                    PromptTemplate(
                        id=row[0],
                        template_key=row[1],
                        version=row[2],
                        content=row[3],
                        is_active=bool(row[4]),
                        created_at=row[5],
                        updated_at=row[6],
                    )
                )
        return templates

    async def save_template(self, template: PromptTemplate) -> None:
        """Insert or update a template."""
        await self._db.execute(
            """
            INSERT OR REPLACE INTO prompt_templates
            (id, template_key, version, content, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.id,
                template.template_key,
                template.version,
                template.content,
                1 if template.is_active else 0,
                template.created_at,
                template.updated_at,
            ),
        )
        await self._db.commit()
        logger.info(
            "prompt_template_saved",
            template_key=template.template_key,
            version=template.version,
        )

    async def deactivate_template(self, template_key: str, version: str) -> bool:
        """Deactivate a template version."""
        cursor = await self._db.execute(
            """
            UPDATE prompt_templates
            SET is_active = 0, updated_at = ?
            WHERE template_key = ? AND version = ?
            """,
            (
                __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                template_key,
                version,
            ),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def activate_template(self, template_key: str, version: str) -> bool:
        """Activate a template version."""
        cursor = await self._db.execute(
            """
            UPDATE prompt_templates
            SET is_active = 1, updated_at = ?
            WHERE template_key = ? AND version = ?
            """,
            (
                __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                template_key,
                version,
            ),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_template(self, template_key: str, version: str) -> bool:
        """Delete a template version."""
        cursor = await self._db.execute(
            """
            DELETE FROM prompt_templates
            WHERE template_key = ? AND version = ?
            """,
            (template_key, version),
        )
        await self._db.commit()
        return cursor.rowcount > 0
