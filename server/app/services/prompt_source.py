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

    def version_for_phase(self, phase: str) -> str:
        """Version string to record on traces for this decision."""
        entry = self._frozen_entry(phase)
        if entry.get("version"):
            return str(entry["version"])
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
        frozen = self._frozen_entry(phase).get("content")
        if frozen:
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

    def _frozen_entry(self, phase: str) -> dict[str, Any]:
        key = self._prompt_builder.template_key_for(self._engine, phase)
        return self._frozen_prompts.get(key, {})

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
