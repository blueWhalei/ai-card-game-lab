"""Versioned prompt templates, backed by SQLite with built-in defaults."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import aiosqlite

logger = structlog.get_logger()

DEFAULT_TEMPLATE_VERSION = "v3"
"""The action-id protocol. A version is a protocol, not a wording tweak: changing
what the model is asked to emit means a new version, so that a stored template
keeps meaning what it meant when a run used it."""

REASONING_TEMPLATE_VERSION = "v3_reasoning"
"""Same protocol, with the thinking budget spelled out for reasoning models."""


@dataclass
class PromptTemplate:
    """Represents a versioned prompt template."""

    id: str
    template_key: str  # e.g., 'doudizhu_playing', 'doudizhu_bidding'
    version: str  # e.g., 'v1', 'v2', 'v3'
    content: str
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(
        cls,
        template_key: str,
        version: str,
        content: str,
    ) -> PromptTemplate:
        now = datetime.now(UTC).isoformat()
        return cls(
            id=str(uuid.uuid4()),
            template_key=template_key,
            version=version,
            content=content,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_key": self.template_key,
            "version": self.version,
            "content": self.content,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PromptTemplateRegistry:
    """Registry for versioned prompt templates.

    Features:
    - Version management: store and retrieve different versions of prompts
    - Persistence: store templates in SQLite
    - Fallback: use in-memory defaults when DB is unavailable
    """

    # Built-in templates, seeded into the database on startup and used directly
    # when the database is unavailable.
    #
    # Every template carries ``{format_instructions}``, which is where the action-id
    # protocol is spelled out. A template that hardcodes an output format instead
    # would contradict the JSON Schema the client sends.
    DEFAULTS: dict[str, str] = {
        "doudizhu_playing_v3": """你是斗地主 AI 玩家。

## 核心规则
{rules}

## 决策要点
- 地主：主动压制，优先出组合牌型消耗手牌
- 农民：配合队友，队友牌少时让牌，地主牌少时管牌
- 有炸弹时，关键时刻才使用

{format_instructions}""",
        "doudizhu_bidding_v3": """你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择不叫，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）
- 三人都不叫则重新发牌

## 手牌评估
| 条件 | 叫分 |
|------|------|
| 有炸弹/王炸 或 ≥2张2 | 3分 |
| 有1张2 + 牌型好 | 2分 |
| 牌型一般但有大牌 | 1分 |
| 牌散且无大牌 | 不叫 |

{format_instructions}""",
        "doudizhu_playing_v3_reasoning": """你是斗地主 AI 玩家。

## 核心规则
{rules}

## 决策要点
- 地主：主动压制，优先出组合牌型消耗手牌
- 农民：配合队友，队友牌少时让牌，地主牌少时管牌
- 有炸弹时，关键时刻才使用

思考请控制在 50 字以内，然后给出结果。

{format_instructions}""",
        "doudizhu_bidding_v3_reasoning": """你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择不叫，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）

## 手牌评估（快速判断）
- 有炸弹/王炸 或 ≥2张2 → 叫3分
- 有1张2 + 牌型好 → 叫2分
- 牌型一般但有大牌 → 叫1分
- 牌散且无大牌 → 不叫

思考请控制在 30 字以内，然后给出结果。

{format_instructions}""",
    }

    def __init__(self, default_version: str = DEFAULT_TEMPLATE_VERSION) -> None:
        self._default_version = default_version
        self._cache: dict[str, PromptTemplate] = {}

    async def get_template(
        self,
        template_key: str,
        db: aiosqlite.Connection | None = None,
        version: str | None = None,
        *,
        require_active: bool = True,
    ) -> str:
        """Return the template content for *template_key* at *version*.

        Raises:
            ValueError: if neither the database nor the built-in defaults have it.
        """
        selected_version = version or self._default_version
        cache_key = f"{template_key}_{selected_version}"
        if not require_active:
            cache_key = f"{cache_key}_any"

        if cache_key in self._cache:
            return self._cache[cache_key].content

        if db is not None:
            template = await self._load_from_db(
                db, template_key, selected_version, require_active=require_active
            )
            if template is not None:
                self._cache[cache_key] = template
                return template.content

        defaults_key = f"{template_key}_{selected_version}"
        if defaults_key in self.DEFAULTS:
            content = self.DEFAULTS[defaults_key]
            self._cache[cache_key] = PromptTemplate(
                id="",
                template_key=template_key,
                version=selected_version,
                content=content,
            )
            return content

        raise ValueError(f"No template for {template_key} at version {selected_version}")

    async def _load_from_db(
        self,
        db: aiosqlite.Connection,
        template_key: str,
        version: str,
        *,
        require_active: bool = True,
    ) -> PromptTemplate | None:
        """Load template from database."""
        try:
            if require_active:
                sql = """
                    SELECT id, template_key, version, content, is_active, created_at, updated_at
                    FROM prompt_templates
                    WHERE template_key = ? AND version = ? AND is_active = 1
                    """
            else:
                sql = """
                    SELECT id, template_key, version, content, is_active, created_at, updated_at
                    FROM prompt_templates
                    WHERE template_key = ? AND version = ?
                    ORDER BY is_active DESC, updated_at DESC
                    LIMIT 1
                    """
            async with db.execute(sql, (template_key, version)) as cursor:
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
        except Exception as e:
            logger.warning(
                "prompt_db_load_failed",
                template_key=template_key,
                version=version,
                error=str(e),
            )
        return None

    async def save_template(
        self,
        db: aiosqlite.Connection,
        template: PromptTemplate,
    ) -> None:
        """Save template to database."""
        await db.execute(
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
        await db.commit()

        # Update cache
        cache_key = f"{template.template_key}_{template.version}"
        self._cache[cache_key] = template

        logger.info(
            "prompt_template_saved",
            template_key=template.template_key,
            version=template.version,
        )

    async def list_versions(
        self,
        db: aiosqlite.Connection,
        template_key: str,
    ) -> list[PromptTemplate]:
        """List all versions of a template."""
        templates = []
        async with db.execute(
            """
            SELECT id, template_key, version, content, is_active, created_at, updated_at
            FROM prompt_templates
            WHERE template_key = ?
            ORDER BY created_at DESC
            """,
            (template_key,),
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

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()

    def invalidate(self, template_key: str, version: str | None = None) -> None:
        """Drop cached entries for a template key (optionally one version)."""
        if version is not None:
            self._cache.pop(f"{template_key}_{version}", None)
            return
        prefix = f"{template_key}_"
        for key in list(self._cache):
            if key.startswith(prefix):
                del self._cache[key]

    async def seed_defaults(self, db: aiosqlite.Connection) -> int:
        """Insert DEFAULTS into DB when missing. Returns number of rows inserted."""
        inserted = 0
        for full_key, content in self.DEFAULTS.items():
            template_key, version = _split_default_key(full_key)
            async with db.execute(
                "SELECT 1 FROM prompt_templates WHERE template_key = ? AND version = ?",
                (template_key, version),
            ) as cursor:
                if await cursor.fetchone() is not None:
                    continue
            template = PromptTemplate.create(
                template_key=template_key,
                version=version,
                content=content,
            )
            await self.save_template(db, template)
            inserted += 1
        if inserted:
            logger.info("prompt_defaults_seeded", count=inserted)
        return inserted


def _split_default_key(full_key: str) -> tuple[str, str]:
    """Split ``doudizhu_playing_v3`` → (``doudizhu_playing``, ``v3``).

    The longer suffix is matched first so ``_v3_reasoning`` does not read as
    ``_v3`` with a ``_reasoning`` template key.
    """
    for suffix in (REASONING_TEMPLATE_VERSION, DEFAULT_TEMPLATE_VERSION):
        marker = f"_{suffix}"
        if full_key.endswith(marker):
            return full_key[: -len(marker)], suffix
    raise ValueError(f"Unrecognized default prompt key: {full_key}")


# Global registry instance
_registry_instance: PromptTemplateRegistry | None = None


def get_registry() -> PromptTemplateRegistry:
    """Get the global prompt template registry instance.

    Creates a new instance if one doesn't exist.
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = PromptTemplateRegistry()
    return _registry_instance
