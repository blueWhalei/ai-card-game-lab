"""Prompt template registry for version control and A/B testing.

This module provides:
- Version management for prompt templates
- A/B testing routing logic
- SQLite persistence layer
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import aiosqlite

logger = structlog.get_logger()


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
        now = datetime.now(timezone.utc).isoformat()
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
    """Registry for managing prompt templates with version control and A/B testing.

    Features:
    - Version management: Store and retrieve different versions of prompts
    - A/B testing: Route traffic between different versions
    - Persistence: Store templates in SQLite
    - Fallback: Use in-memory defaults when DB is unavailable
    """

    # Default templates (fallback when DB is unavailable) - class variable
    DEFAULTS: dict[str, str] = {
        # === 通用 LLM 模板 (v1) ===
        "doudizhu_playing_v1": """你是斗地主 AI 玩家。

## 核心规则
{rules}

## 决策要点
- 地主：主动压制，优先出组合牌型消耗手牌
- 农民：配合队友，队友牌少时让牌，地主牌少时管牌
- 有炸弹时，关键时刻才使用

{format_instructions}

## 输出格式（严格遵守）
直接输出单行 JSON，无 markdown 代码块，无额外文字：
{{"thinking":"简短分析1-2句","action_type":"动作类型","cards":["牌1","牌2"]}}

牌面编码：S=黑桃 H=红心 D=方块 C=梅花，BJ=小王，RJ=大王""",
        "doudizhu_bidding_v1": """你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择 BID_PASS，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）
- 三人都选 BID_PASS 则重新发牌

## 手牌评估
| 条件 | 叫分 |
|------|------|
| 有炸弹/王炸 或 ≥2张2 | 3分 |
| 有1张2 + 牌型好 | 2分 |
| 牌型一般但有大牌 | 1分 |
| 牌散且无大牌 | BID_PASS |

{format_instructions}

## 输出格式（严格遵守）
直接输出单行 JSON，无 markdown 代码块，无额外文字：
{{"thinking":"简短分析1-2句","action_type":"BID或BID_PASS","value":1或2或3或null}}""",

        # === 通用 LLM 模板 (v2) - 更精简 ===
        "doudizhu_playing_v2": """斗地主 AI 玩家。规则：{rules}

策略：地主主动压制；农民配合队友。
{format_instructions}

直接输出 JSON：{{"thinking":"简短分析","action_type":"类型","cards":["牌"]}}""",
        "doudizhu_bidding_v2": """斗地主叫分阶段。

规则：叫1/2/3分或BID_PASS，叫3分立即成地主。
评估：有炸弹/≥2张2→3分；有1张2+牌好→2分；有大牌→1分；牌散→BID_PASS。
{format_instructions}

直接输出 JSON：{{"thinking":"简短分析","action_type":"BID或BID_PASS","value":1或2或3或null}}""",

        # === 推理模型专用模板 (reasoning) - 适配 DeepSeek R1 / OpenAI o1 等 ===
        # 关键：限制思考长度，强制JSON在最后一行
        "doudizhu_playing_reasoning": """你是斗地主 AI 玩家。

## 核心规则
{rules}

## 决策要点
- 地主：主动压制，优先出组合牌型消耗手牌
- 农民：配合队友，队友牌少时让牌，地主牌少时管牌
- 有炸弹时，关键时刻才使用

{format_instructions}

## 输出格式（严格遵守）
1. 先用1-2句话简短分析（不超过50字）
2. 最后一行必须是JSON，单独占一行
3. 不要使用markdown代码块

示例输出：
分析：地主剩3张需管牌，出最小单张。
{{"thinking":"地主剩3张需管牌","action_type":"SINGLE","cards":["C4"]}}

牌面编码：S=黑桃 H=红心 D=方块 C=梅花，BJ=小王，RJ=大王""",
        "doudizhu_bidding_reasoning": """你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择 BID_PASS，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）
- 三人都选 BID_PASS 则重新发牌

## 手牌评估（快速判断）
- 有炸弹/王炸 或 ≥2张2 → 叫3分
- 有1张2 + 牌型好 → 叫2分
- 牌型一般但有大牌 → 叫1分
- 牌散且无大牌 → BID_PASS

{format_instructions}

## 输出格式（严格遵守）
1. 先用1句话简短分析（不超过30字）
2. 最后一行必须是JSON，单独占一行
3. 不要使用markdown代码块

示例输出：
分析：有小王和A，牌型一般但有大牌。
{{"thinking":"有小王和A，叫1分","action_type":"BID","value":1}}""",
    }

    def __init__(
        self,
        default_version: str = "v1",
        ab_test_enabled: bool = False,
        ab_test_ratio: float = 0.5,
    ) -> None:
        self._default_version = default_version
        self._ab_test_enabled = ab_test_enabled
        self._ab_test_ratio = ab_test_ratio
        self._cache: dict[str, PromptTemplate] = {}
        self._ab_assignments: dict[str, str] = {}  # session_id -> version

    async def get_template(
        self,
        template_key: str,
        db: aiosqlite.Connection | None = None,
        version: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Get prompt template content.

        Args:
            template_key: Template identifier (e.g., 'doudizhu_playing')
            db: Optional database connection for persistence
            version: Specific version to retrieve (overrides defaults)
            session_id: Session ID for A/B testing consistency

        Returns:
            Template content string
        """
        # Determine version to use
        selected_version = self._select_version(
            template_key=template_key,
            requested_version=version,
            session_id=session_id,
        )

        cache_key = f"{template_key}_{selected_version}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key].content

        # Try to load from database
        if db is not None:
            template = await self._load_from_db(db, template_key, selected_version)
            if template is not None:
                self._cache[cache_key] = template
                return template.content

        # Fallback to defaults
        default_key = f"{template_key}_{selected_version}"
        if default_key in self.DEFAULTS:
            content = self.DEFAULTS[default_key]
            self._cache[cache_key] = PromptTemplate(
                id="",
                template_key=template_key,
                version=selected_version,
                content=content,
            )
            return content

        # Ultimate fallback to v1
        fallback_key = f"{template_key}_v1"
        if fallback_key in self.DEFAULTS:
            logger.warning(
                "prompt_version_fallback",
                template_key=template_key,
                requested_version=selected_version,
            )
            return self.DEFAULTS[fallback_key]

        raise ValueError(f"No template found for key: {template_key}")

    def _select_version(
        self,
        template_key: str,
        requested_version: str | None,
        session_id: str | None,
    ) -> str:
        """Select template version based on priority:
        1. Explicitly requested version
        2. A/B test assignment for session
        3. A/B test random assignment
        4. Default version
        """
        # Priority 1: Explicit version
        if requested_version is not None:
            return requested_version

        # Priority 2: Existing A/B assignment
        if session_id and session_id in self._ab_assignments:
            return self._ab_assignments[session_id]

        # Priority 3: A/B test assignment
        if self._ab_test_enabled and session_id:
            # Use consistent hashing for assignment
            hash_input = f"{template_key}_{session_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            ratio = (hash_value % 10000) / 10000

            if ratio < self._ab_test_ratio:
                assigned_version = "v2"
            else:
                assigned_version = "v1"

            self._ab_assignments[session_id] = assigned_version
            logger.info(
                "ab_test_assignment",
                template_key=template_key,
                session_id=session_id,
                assigned_version=assigned_version,
            )
            return assigned_version

        # Priority 4: Default version
        return self._default_version

    async def _load_from_db(
        self,
        db: aiosqlite.Connection,
        template_key: str,
        version: str,
    ) -> PromptTemplate | None:
        """Load template from database."""
        try:
            async with db.execute(
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
        self._ab_assignments.clear()

    def get_ab_stats(self) -> dict[str, Any]:
        """Get A/B test statistics."""
        v1_count = sum(1 for v in self._ab_assignments.values() if v == "v1")
        v2_count = sum(1 for v in self._ab_assignments.values() if v == "v2")
        return {
            "enabled": self._ab_test_enabled,
            "ratio": self._ab_test_ratio,
            "total_assignments": len(self._ab_assignments),
            "v1_count": v1_count,
            "v2_count": v2_count,
        }


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
