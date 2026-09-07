"""Service-side ``PromptSource``: resolves templates for one engine.

A policy is handed rendered text. Everything needed to produce it -- the engine,
the template registry, a database connection for stored templates and their A/B
assignment -- stays on this side of the boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    ) -> None:
        self._prompt_builder = prompt_builder
        self._engine = engine
        self._sqlite_path = sqlite_path

    async def system_message(
        self,
        *,
        phase: str,
        model_name: str | None,
        session_id: str | None,
        format_instructions: str,
    ) -> str:
        if not self._sqlite_path:
            return await self._render(phase, model_name, session_id, format_instructions, None)

        async for db in get_db_connection(self._sqlite_path):
            return await self._render(phase, model_name, session_id, format_instructions, db)
        return await self._render(phase, model_name, session_id, format_instructions, None)

    async def _render(
        self,
        phase: str,
        model_name: str | None,
        session_id: str | None,
        format_instructions: str,
        db: aiosqlite.Connection | None,
    ) -> str:
        return await self._prompt_builder.system_message(
            engine=self._engine,
            phase=phase,
            format_instructions=format_instructions,
            model_name=model_name,
            session_id=session_id,
            db=db,
        )
