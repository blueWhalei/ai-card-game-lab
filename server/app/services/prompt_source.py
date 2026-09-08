"""Service-side ``PromptSource``: resolves templates for one engine.

A policy is handed rendered text. Everything needed to produce it -- the engine,
the template registry, a database connection for stored templates -- stays on this
side of the boundary.

When an experiment freezes prompt bodies into ``protocol.solver.prompts``, those
bodies win over the live DB so collect stays reproducible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.database import get_db_connection

if TYPE_CHECKING:
    import aiosqlite

    from app.core.ai.prompt import PromptBuilder
    from app.core.engine.base import GameEngine

logger = structlog.get_logger()


class EnginePromptSource:
    """Binds a ``PromptBuilder`` to one engine for the duration of a decision."""

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        engine: GameEngine,
        sqlite_path: str | None = None,
        *,
        frozen_prompts: dict[str, dict[str, Any]] | None = None,
        frozen_prompt_version: str | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._engine = engine
        self._sqlite_path = sqlite_path
        self._frozen_prompts = frozen_prompts or {}
        self._frozen_prompt_version = frozen_prompt_version or ""

    @property
    def prompt_version_label(self) -> str:
        """Version string to record on traces for this decision."""
        if self._frozen_prompt_version:
            return self._frozen_prompt_version
        return ""

    async def system_message(
        self,
        *,
        phase: str,
        model_name: str | None,
        format_instructions: str,
    ) -> str:
        frozen = self._frozen_content_for(phase)
        if frozen is not None:
            return await self._prompt_builder.system_message(
                engine=self._engine,
                phase=phase,
                format_instructions=format_instructions,
                model_name=model_name,
                db=None,
                frozen_content=frozen,
            )

        if not self._sqlite_path:
            return await self._render(phase, model_name, format_instructions, None)

        async for db in get_db_connection(self._sqlite_path):
            return await self._render(phase, model_name, format_instructions, db)
        return await self._render(phase, model_name, format_instructions, None)

    def _frozen_content_for(self, phase: str) -> str | None:
        if not self._frozen_prompts:
            return None
        keys = self._engine.capability.prompt_keys
        template_key = keys.get(phase) or keys.get("playing") or f"{self._engine.game_type}_{phase}"
        entry = self._frozen_prompts.get(template_key)
        if not isinstance(entry, dict):
            return None
        content = entry.get("content")
        return str(content) if content else None

    async def _render(
        self,
        phase: str,
        model_name: str | None,
        format_instructions: str,
        db: aiosqlite.Connection | None,
    ) -> str:
        return await self._prompt_builder.system_message(
            engine=self._engine,
            phase=phase,
            format_instructions=format_instructions,
            model_name=model_name,
            db=db,
        )
