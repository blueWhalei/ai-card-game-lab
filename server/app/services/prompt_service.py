"""Service layer for prompt template management.

This service provides a unified interface for prompt template CRUD operations
and A/B test configuration, wrapping both PromptRepository and PromptTemplateRegistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import aiosqlite

from app.core.ai.prompts.registry import (
    PromptTemplate,
    PromptTemplateRegistry,
    get_registry,
)
from app.repositories.prompt_repo import PromptRepository
from app.schemas.prompt import (
    ABStatsResponse,
    ABTestConfig,
    ActivatePromptRequest,
    CreatePromptRequest,
    DeactivatePromptRequest,
    PromptTemplateResponse,
    UpdatePromptRequest,
)

logger = structlog.get_logger()


class PromptService:
    """Service for managing prompt templates with persistence and A/B testing.

    Features:
    - CRUD operations for prompt templates
    - A/B test configuration management
    - A/B test statistics tracking
    - Registry cache coordination
    """

    def __init__(
        self,
        db: aiosqlite.Connection,
        registry: PromptTemplateRegistry | None = None,
    ) -> None:
        self._db = db
        self._repo = PromptRepository(db)
        self._registry = registry or get_registry()

    async def list_templates(
        self,
        template_key: str | None = None,
        active_only: bool = False,
    ) -> list[PromptTemplateResponse]:
        """List prompt templates with optional filtering."""
        templates = await self._repo.list_templates(
            template_key=template_key,
            active_only=active_only,
        )
        return [self._to_response(t) for t in templates]

    async def get_template(
        self,
        template_key: str,
        version: str,
    ) -> PromptTemplateResponse | None:
        """Get a specific template version."""
        template = await self._repo.get_template(template_key, version)
        return self._to_response(template) if template else None

    async def create_template(self, request: CreatePromptRequest) -> PromptTemplateResponse:
        """Create a new prompt template version."""
        template = PromptTemplate.create(
            template_key=request.template_key,
            version=request.version,
            content=request.content,
        )

        # Save to database
        await self._repo.save_template(template)

        # Update registry cache
        cache_key = f"{template.template_key}_{template.version}"
        self._registry._cache[cache_key] = template

        logger.info(
            "prompt_template_created",
            template_key=template.template_key,
            version=template.version,
        )

        return self._to_response(template)

    async def update_template(
        self,
        template_key: str,
        version: str,
        request: UpdatePromptRequest,
    ) -> PromptTemplateResponse | None:
        """Update an existing prompt template."""
        template = await self._repo.get_template(template_key, version)
        if not template:
            return None

        # Update content and timestamp
        import datetime

        now = datetime.datetime.now(datetime.UTC).isoformat()
        template.content = request.content
        template.updated_at = now

        await self._repo.save_template(template)

        # Update registry cache
        cache_key = f"{template.template_key}_{template.version}"
        self._registry._cache[cache_key] = template

        logger.info(
            "prompt_template_updated",
            template_key=template_key,
            version=version,
        )

        return self._to_response(template)

    async def delete_template(
        self,
        template_key: str,
        version: str,
    ) -> bool:
        """Delete a prompt template version."""
        deleted = await self._repo.delete_template(template_key, version)

        if deleted:
            # Remove from registry cache
            cache_key = f"{template_key}_{version}"
            self._registry._cache.pop(cache_key, None)

            logger.info(
                "prompt_template_deleted",
                template_key=template_key,
                version=version,
            )

        return deleted

    async def activate_template(
        self,
        template_key: str,
        request: ActivatePromptRequest,
    ) -> PromptTemplateResponse | None:
        """Activate a specific template version."""
        template = await self._repo.get_active_template(template_key, request.version)
        if not template:
            return None

        success = await self._repo.activate_template(template_key, request.version)
        if success:
            # Update cache
            cache_key = f"{template_key}_{request.version}"
            self._registry._cache[cache_key] = template

            logger.info(
                "prompt_template_activated",
                template_key=template_key,
                version=request.version,
            )

            return self._to_response(template)
        return None

    async def deactivate_template(
        self,
        template_key: str,
        request: DeactivatePromptRequest,
    ) -> PromptTemplateResponse | None:
        """Deactivate a specific template version."""
        template = await self._repo.get_active_template(template_key, request.version)
        if not template:
            return None

        success = await self._repo.deactivate_template(template_key, request.version)
        if success:
            # Remove from cache (deactivated templates shouldn't be used)
            cache_key = f"{template_key}_{request.version}"
            self._registry._cache.pop(cache_key, None)

            logger.info(
                "prompt_template_deactivated",
                template_key=template_key,
                version=request.version,
            )

            return self._to_response(template)
        return None

    def get_ab_stats(self) -> ABStatsResponse:
        """Get current A/B test statistics."""
        stats = self._registry.get_ab_stats()
        return ABStatsResponse(
            enabled=stats["enabled"],
            ratio=stats["ratio"],
            total_assignments=stats["total_assignments"],
            v1_count=stats["v1_count"],
            v2_count=stats["v2_count"],
        )

    def update_ab_config(self, config: ABTestConfig) -> ABStatsResponse:
        """Update A/B test configuration."""
        self._registry._ab_test_enabled = config.enabled
        self._registry._ab_test_ratio = config.ratio

        logger.info(
            "ab_config_updated",
            enabled=config.enabled,
            ratio=config.ratio,
        )

        return self.get_ab_stats()

    def get_registry_config(self) -> dict[str, object]:
        """Get the registry instance for AI service to use.

        This allows the AI service to access the current registry
        with A/B testing and caching enabled.
        """
        return {
            "registry": self._registry,
            "ab_enabled": self._registry._ab_test_enabled,
        }

    @staticmethod
    def _to_response(template: PromptTemplate) -> PromptTemplateResponse:
        """Convert PromptTemplate to response model."""
        return PromptTemplateResponse(
            id=template.id,
            template_key=template.template_key,
            version=template.version,
            content=template.content,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
