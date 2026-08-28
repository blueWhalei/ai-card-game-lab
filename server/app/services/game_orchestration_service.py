"""Game orchestration service - manages game execution flow."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiosqlite
import structlog

from app.core.ai.stream_chunk import StreamChunk
from app.core.events import EventBus, GameEndedEvent
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.utils.exceptions import GameNotFoundError
from app.websocket.manager import ws_manager

if TYPE_CHECKING:
    from app.core.collector.jsonl_writer import JsonlWriter
    from app.core.engine.base import GameState
    from app.core.engine.registry import GameEngineRegistry
    from app.services.ai_player_service import AIPlayerService
    from app.services.ai_service import AIService
    from app.services.decision_service import DecisionService
    from app.services.trace_service import TraceService

logger = structlog.get_logger()


class GameOrchestrationService:
    """Manages game execution flow, state, and lifecycle.

    This service is responsible for:
    - Running game loops and rounds
    - Managing active game states, tasks, and pause controls
    - Broadcasting WebSocket events
    - Publishing domain events when games end
    """

    def __init__(
        self,
        engine_registry: GameEngineRegistry,
        collector: JsonlWriter,
        ai_service: AIService,
        ai_player_service: AIPlayerService,
        sqlite_path: str,
        event_bus: EventBus,
        decision_service: DecisionService | None = None,
        trace_service: TraceService | None = None,
    ) -> None:
        self._engine_registry = engine_registry
        self._collector = collector
        self._ai_service = ai_service
        self._ai_player_service = ai_player_service
        self._sqlite_path = sqlite_path
        self._event_bus = event_bus
        self._decision_service = decision_service
        self._trace_service = trace_service
        self._states: dict[str, GameState] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._pause_events: dict[str, asyncio.Event] = {}

    def has_active_game(self, game_id: str) -> bool:
        """Check if a game is currently active."""
        return game_id in self._states

    def get_game_state(self, game_id: str) -> GameState | None:
        """Get the current state of an active game."""
        return self._states.get(game_id)

    async def start_game_execution(
        self,
        game_id: str,
        game_type: str,
        player_ids: list[str],
    ) -> None:
        """Start executing a game in the background.

        Args:
            game_id: The game identifier
            game_type: The type of game engine to use
            player_ids: List of player identifiers
        """
        engine = self._engine_registry.get(game_type)
        state = engine.initialize(player_ids)
        self._states[game_id] = state

        event = asyncio.Event()
        event.set()
        self._pause_events[game_id] = event

        task = asyncio.create_task(self._run_game_loop(game_id))
        self._tasks[game_id] = task

        # Add task exception callback to log any errors
        def on_task_done(t: asyncio.Task[None]) -> None:
            exc = t.exception()
            if exc:
                logger.exception("game_loop_task_error", game_id=game_id, error=str(exc), exc_info=True)

        task.add_done_callback(on_task_done)

        await ws_manager.broadcast(game_id, {
            "type": "game_started",
            "game_id": game_id,
            "data": engine.get_public_info(state, "observer", is_observer=True),
        })

        logger.info("game_execution_started", game_id=game_id)

    async def _run_game_loop(self, game_id: str) -> None:
        """Run the main game loop until completion."""
        logger.info("game_loop_entering", game_id=game_id)

        # Use aiosqlite.connect directly with async context manager
        # This avoids the "threads can only be started once" error
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            logger.info("game_loop_db_connected", game_id=game_id)

            bg_game_repo = GameRepository(db)
            bg_round_repo = RoundRepository(db)

            state = self._states.get(game_id)
            if state is None:
                logger.error("game_loop_state_not_found", game_id=game_id)
                return

            engine = self._engine_registry.get(state.game_type)
            logger.info("game_loop_starting", game_id=game_id, game_type=state.game_type)

            try:
                while not engine.is_terminal(state):
                    event = self._pause_events.get(game_id)
                    if event:
                        await event.wait()

                    state = await self._run_round(game_id, state, engine, bg_round_repo)
                    self._states[game_id] = state

                    await asyncio.sleep(0.5)

                await self._finish_game(game_id, state, engine, bg_game_repo)
            except asyncio.CancelledError:
                logger.info("game_loop_cancelled", game_id=game_id)
            except Exception as exc:
                logger.exception("game_loop_error", game_id=game_id)
                await ws_manager.broadcast(game_id, {
                    "type": "error",
                    "game_id": game_id,
                    "data": {
                        "message": f"对局循环出错: {type(exc).__name__}: {exc}",
                    },
                })

    async def _run_round(
        self,
        game_id: str,
        state: GameState,
        engine: Any,
        round_repo: RoundRepository,
    ) -> GameState:
        """Execute a single round of gameplay."""
        current_player = engine.get_current_player(state)
        player_config = self._ai_player_service.get_player(current_player)
        model_cfg = (player_config or {}).get("model_config", {})
        legal_actions = engine.get_legal_actions(state, current_player)
        all_hands = {pid: list(cards) for pid, cards in getattr(state, "hands", {}).items()}
        hand_snapshot = list(getattr(state, "hands", {}).get(current_player, []))

        await ws_manager.broadcast(game_id, {
            "type": "thinking",
            "game_id": game_id,
            "data": {
                "player_id": current_player,
                "player_name": player_config["name"] if player_config else current_player,
            },
        })

        streamed_chunks: list[StreamChunk] = []
        use_streaming = ws_manager.get_connection_count(game_id) > 0

        def on_chunk(chunk: StreamChunk) -> None:
            streamed_chunks.append(chunk)
            async def _broadcast_chunk() -> None:
                try:
                    await ws_manager.broadcast(game_id, {
                        "type": "thinking_chunk",
                        "game_id": game_id,
                        "data": {
                            "player_id": current_player,
                            "chunk": chunk.text,
                            "chunk_type": chunk.type,
                        },
                    })
                except Exception:
                    logger.warning("broadcast_chunk_failed", game_id=game_id, exc_info=True)
            asyncio.create_task(_broadcast_chunk())

        t0 = time.monotonic()
        if use_streaming:
            decision = await self._ai_service.get_decision_streaming(
                state=state,
                engine=engine,
                player_id=current_player,
                player_config=player_config or {},
                legal_actions=legal_actions,
                game_id=game_id,
                on_chunk=on_chunk,
            )
        else:
            # Batch / e2e: no observers — non-streaming is more reliable
            decision = await self._ai_service.get_decision(
                state=state,
                engine=engine,
                player_id=current_player,
                player_config=player_config or {},
                legal_actions=legal_actions,
                game_id=game_id,
            )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        full_thinking = "".join(c.text for c in streamed_chunks) if streamed_chunks else decision.thinking

        new_state = engine.apply_action(state, decision.action)

        # Broadcast updates, persist data, record traces
        await self._broadcast_round_events(
            game_id, current_player, new_state, decision,
            full_thinking, elapsed_ms, model_cfg, engine,
        )
        await self._persist_round(
            game_id, current_player, new_state, decision,
            hand_snapshot, all_hands, elapsed_ms, model_cfg, round_repo,
        )
        await self._record_trace(
            game_id, current_player, new_state, decision,
            hand_snapshot, legal_actions, elapsed_ms, model_cfg,
        )

        return new_state

    async def _broadcast_round_events(
        self,
        game_id: str,
        current_player: str,
        new_state: GameState,
        decision: Any,
        full_thinking: str,
        elapsed_ms: int,
        model_cfg: dict[str, Any],
        engine: Any,
    ) -> None:
        """Broadcast thinking_complete, action, and state_update via WebSocket."""
        await ws_manager.broadcast(game_id, {
            "type": "thinking_complete",
            "game_id": game_id,
            "data": {
                "player_id": current_player,
                "thinking": full_thinking,
                "response_time_ms": elapsed_ms,
                "round": new_state.round,
                "action_preview": {
                    "action_type": str(decision.action.action_type),
                    "cards": decision.action.cards,
                    "target": decision.action.target,
                },
                "prompt_preview": decision.prompt_preview,
                "raw_response_preview": decision.raw_response_preview,
                "prompt_messages": decision.messages,
                "raw_response_full": decision.raw_response,
                "prompt_tokens": decision.usage.get("prompt_tokens"),
                "completion_tokens": decision.usage.get("completion_tokens"),
                "total_tokens": decision.usage.get("total_tokens"),
                "model_provider": model_cfg.get("provider"),
                "model_name": model_cfg.get("model_name"),
            },
        })

        await ws_manager.broadcast(game_id, {
            "type": "action",
            "game_id": game_id,
            "data": {
                "player_id": current_player,
                "action_type": str(decision.action.action_type),
                "cards": decision.action.cards,
                "round": new_state.round,
            },
        })

        await ws_manager.broadcast(game_id, {
            "type": "state_update",
            "game_id": game_id,
            "data": engine.get_public_info(new_state, "observer", is_observer=True),
        })

    async def _persist_round(
        self,
        game_id: str,
        current_player: str,
        new_state: GameState,
        decision: Any,
        hand_snapshot: list[int],
        all_hands: dict[str, list[int]],
        elapsed_ms: int,
        model_cfg: dict[str, Any],
        round_repo: RoundRepository,
    ) -> None:
        """Persist round data to collector and database."""
        self._collector.record_round(game_id, {
            "game_id": game_id,
            "round_num": new_state.round,
            "player_id": current_player,
            "action_type": str(decision.action.action_type),
            "cards": decision.action.cards,
            "hand_snapshot": hand_snapshot,
            "all_hands": all_hands,
            "prompt": decision.messages,
            "thinking": decision.thinking,
            "raw_response": decision.raw_response,
            "response_time_ms": elapsed_ms,
            "prompt_tokens": decision.usage.get("prompt_tokens"),
            "completion_tokens": decision.usage.get("completion_tokens"),
            "total_tokens": decision.usage.get("total_tokens"),
            "model_provider": model_cfg.get("provider"),
            "model_name": model_cfg.get("model_name"),
        })

        now = datetime.now(tz=UTC).isoformat()
        await round_repo.create({
            "game_id": game_id,
            "round_num": new_state.round,
            "player_id": current_player,
            "action_type": str(decision.action.action_type),
            "cards": decision.action.cards,
            "hand_snapshot": hand_snapshot,
            "all_hands": all_hands,
            "prompt": decision.messages,
            "raw_response": decision.raw_response,
            "prompt_tokens": decision.usage.get("prompt_tokens"),
            "completion_tokens": decision.usage.get("completion_tokens"),
            "total_tokens": decision.usage.get("total_tokens"),
            "response_time_ms": elapsed_ms,
            "model_provider": model_cfg.get("provider"),
            "model_name": model_cfg.get("model_name"),
            "created_at": now,
        })

    async def _record_trace(
        self,
        game_id: str,
        current_player: str,
        new_state: GameState,
        decision: Any,
        hand_snapshot: list[int],
        legal_actions: list[Any],
        elapsed_ms: int,
        model_cfg: dict[str, Any],
    ) -> None:
        """Record trace and spans for observability."""
        if self._trace_service is None:
            return

        try:
            trace_id = await self._trace_service.create_trace(
                game_id=game_id,
                round_number=new_state.round,
                player_id=current_player,
                model=model_cfg.get("model_name", "unknown"),
                prompt_version="default",
                input_snapshot={
                    "legal_actions": [
                        {"action_type": str(a.action_type), "cards": a.cards}
                        for a in legal_actions
                    ],
                    "hand_snapshot": hand_snapshot,
                },
                output_data={
                    "action_type": str(decision.action.action_type),
                    "cards": decision.action.cards,
                    "thinking": decision.thinking[:500],
                },
                metrics={
                    "response_time_ms": elapsed_ms,
                    "used_langchain_parser": decision.used_langchain_parser,
                    **decision.usage,
                },
            )

            now_iso = datetime.now(tz=UTC).isoformat()

            tool_results = decision.tool_results
            if tool_results:
                await self._create_tool_spans(trace_id, tool_results, now_iso)

            await self._trace_service.create_span(
                trace_id=trace_id,
                span_type="llm_call",
                start_time=now_iso,
                end_time=now_iso,
                data={
                    "provider": model_cfg.get("provider"),
                    "model": model_cfg.get("model_name"),
                    "usage": decision.usage,
                    "response_time_ms": elapsed_ms,
                },
            )
        except Exception:
            logger.warning("trace_recording_failed", game_id=game_id, exc_info=True)

    async def _create_tool_spans(
        self,
        trace_id: str,
        tool_results: dict[str, Any],
        now_iso: str,
    ) -> None:
        """Create spans for tool call results."""
        if "hand_analysis" in tool_results:
            await self._trace_service.create_span(
                trace_id=trace_id,
                span_type="hand_analysis",
                start_time=now_iso,
                end_time=now_iso,
                data={"analysis": str(tool_results["hand_analysis"])},
            )
        if "win_probability" in tool_results:
            await self._trace_service.create_span(
                trace_id=trace_id,
                span_type="win_probability_estimation",
                start_time=now_iso,
                end_time=now_iso,
                data={"estimation": str(tool_results["win_probability"])},
            )

    async def _finish_game(
        self,
        game_id: str,
        state: GameState,
        engine: Any,
        game_repo: GameRepository,
    ) -> None:
        """Finalize a completed game."""
        winner = engine.get_winner(state)
        now = datetime.now(tz=UTC).isoformat()

        await game_repo.update_result(
            game_id,
            winner_id=winner,
            winner_role=state.winner_role,
            total_rounds=state.round,
            finished_at=now,
        )

        self._collector.end_game(game_id, {
            "winner_id": winner,
            "winner_role": state.winner_role,
            "total_rounds": state.round,
        })

        winner_config = self._ai_player_service.get_player(winner) if winner else None

        await ws_manager.broadcast(game_id, {
            "type": "game_ended",
            "game_id": game_id,
            "data": {
                "winner_id": winner,
                "winner_name": winner_config["name"] if winner_config else winner,
                "winner_role": state.winner_role,
                "total_rounds": state.round,
            },
        })

        self._states.pop(game_id, None)
        self._tasks.pop(game_id, None)
        self._pause_events.pop(game_id, None)

        logger.info("game_finished", game_id=game_id, winner=winner)

        if self._decision_service is not None:
            try:
                updated = await self._decision_service.update_outcome(game_id, winner)
                logger.info("decision_outcome_updated", game_id=game_id, updated_count=updated)
            except Exception:
                logger.warning("update_decision_outcome_failed", game_id=game_id, exc_info=True)

        event = GameEndedEvent(
            game_id=game_id,
            game_type=state.game_type,
            winner_id=winner,
            winner_role=state.winner_role,
            total_rounds=state.round,
        )
        await self._event_bus.publish(event)

    async def pause_game(self, game_id: str) -> None:
        """Pause an active game."""
        event = self._pause_events.get(game_id)
        if not event:
            raise GameNotFoundError(game_id)
        event.clear()
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = GameRepository(db)
            await repo.update_status(game_id, "paused")
        await ws_manager.broadcast(game_id, {
            "type": "game_paused",
            "game_id": game_id,
        })

    async def resume_game(self, game_id: str) -> None:
        """Resume a paused game."""
        event = self._pause_events.get(game_id)
        if not event:
            raise GameNotFoundError(game_id)
        event.set()
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = GameRepository(db)
            await repo.update_status(game_id, "running")
        await ws_manager.broadcast(game_id, {
            "type": "game_resumed",
            "game_id": game_id,
        })
