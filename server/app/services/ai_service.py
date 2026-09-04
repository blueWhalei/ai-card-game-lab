"""AI invocation service -- manages LLM calls for game decisions."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from app.core.ai.parsers.action_parser import ActionOutputParser
from app.core.ai.parsers.bid_parser import BidOutputParser
from app.core.ai.prompt import PromptBuilder
from app.core.ai.stream_chunk import StreamChunk
from app.core.ai.tools.hand_analyzer import HandAnalyzerTool
from app.core.ai.tools.win_probability import WinProbabilityTool
from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.stats.scenarios import classify_game_phase
from app.database import get_db_connection
from app.utils.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitExceededError,
    AITimeoutError,
    AppError,
)

if TYPE_CHECKING:
    from app.core.ai.base import LLMClient
    from app.core.ai.factory import LLMClientFactory
    from app.services.decision_service import DecisionService

logger = structlog.get_logger()

RATE_LIMIT_ERROR_MARKERS = (
    "rate limit",
    "too many requests",
    "429",
    "quota exceeded",
)
UNAVAILABLE_ERROR_MARKERS = (
    "service unavailable",
    "temporarily unavailable",
    "bad gateway",
    "gateway error",
    "503",
)

MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class AIDecisionResult:
    """Structured AI decision payload for live display and persistence."""

    action: GameAction
    thinking: str
    raw_response: str
    messages: list[dict[str, str]]
    prompt_preview: str
    raw_response_preview: str
    usage: dict[str, int | None]
    response_time_ms: float = 0.0
    used_langchain_parser: bool = True
    tool_results: dict[str, Any] | None = None


class AIService:
    """Manages LLM calls for game decision-making with retry and timeout."""

    def __init__(
        self,
        llm_factory: LLMClientFactory,
        prompt_builder: PromptBuilder,
        decision_service: DecisionService | None = None,
        sqlite_path: str | None = None,
    ) -> None:
        self._llm_factory = llm_factory
        self._prompt_builder = prompt_builder
        self._decision_service = decision_service
        self._sqlite_path = sqlite_path
        self._client_cache: dict[str, LLMClient] = {}
        self._action_parser = ActionOutputParser()
        self._bid_parser = BidOutputParser()
        self._hand_analyzer = HandAnalyzerTool()
        self._win_probability = WinProbabilityTool()

    def _get_client(self, player_config: dict[str, Any]) -> LLMClient:
        model_cfg = player_config.get("model_config", {})
        provider = model_cfg.get("provider", "openai")
        cache_key = provider
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = self._llm_factory.create(provider)
        return self._client_cache[cache_key]

    @staticmethod
    def _map_provider_error(provider: str, error: Exception) -> AppError:
        if isinstance(error, AppError):
            return error

        detail = str(error).strip() or error.__class__.__name__
        detail_lower = detail.lower()

        if any(marker in detail_lower for marker in RATE_LIMIT_ERROR_MARKERS):
            return AIRateLimitExceededError(provider, detail)
        if any(marker in detail_lower for marker in UNAVAILABLE_ERROR_MARKERS):
            return AIProviderUnavailableError(provider, detail)
        return AIProviderError(provider, detail)

    async def _build_prompt_messages(
        self,
        *,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        model_name: str | None,
        game_id: str | None,
        tool_analysis: str | None,
    ) -> list[dict[str, str]]:
        """Build prompt via registry, preferring DB-backed templates when available."""
        if not self._sqlite_path:
            return await self._prompt_builder.build_async(
                state=state,
                legal_actions=legal_actions,
                engine=engine,
                player_id=player_id,
                db=None,
                session_id=game_id,
                model_name=model_name,
                tool_analysis=tool_analysis,
            )

        async for db in get_db_connection(self._sqlite_path):
            return await self._prompt_builder.build_async(
                state=state,
                legal_actions=legal_actions,
                engine=engine,
                player_id=player_id,
                db=db,
                session_id=game_id,
                model_name=model_name,
                tool_analysis=tool_analysis,
            )
        return await self._prompt_builder.build_async(
            state=state,
            legal_actions=legal_actions,
            engine=engine,
            player_id=player_id,
            db=None,
            session_id=game_id,
            model_name=model_name,
            tool_analysis=tool_analysis,
        )

    async def get_decision(
        self,
        state: GameState,
        engine: GameEngine,
        player_id: str,
        player_config: dict[str, Any],
        legal_actions: list[GameAction],
        game_id: str | None = None,
    ) -> AIDecisionResult:
        """Get AI decision with retry logic and structured metadata."""
        start_time = time.perf_counter()

        model_cfg = player_config.get("model_config", {})
        model_name = model_cfg.get("model_name")

        # Run analysis tools (skip during bidding phase)
        phase = getattr(state, "phase", "playing")
        tool_data: dict[str, Any] | None = None
        if phase != "bidding":
            tool_data = self._run_tools(state, player_id)

        messages = await self._build_prompt_messages(
            state=state,
            legal_actions=legal_actions,
            engine=engine,
            player_id=player_id,
            model_name=model_name,
            game_id=game_id,
            tool_analysis=tool_data.get("tool_analysis") if tool_data else None,
        )
        client = self._get_client(player_config)

        kwargs: dict[str, Any] = {}
        if model_cfg.get("model_name"):
            kwargs["model"] = model_cfg["model_name"]
        if model_cfg.get("temperature") is not None:
            kwargs["temperature"] = model_cfg["temperature"]
        if model_cfg.get("max_tokens") is not None:
            kwargs["max_tokens"] = model_cfg["max_tokens"]

        raw_response = ""
        last_error: Exception | None = None
        prompt_preview = self._build_prompt_preview(messages)

        provider = model_cfg.get("provider", "unknown")
        used_langchain_parser = True

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await asyncio.wait_for(
                    client.chat(messages, **kwargs),
                    timeout=DEFAULT_TIMEOUT,
                )
                raw_response = response.content

                thinking, action, used_langchain_parser = self._parse_with_metrics(
                    raw_response, legal_actions, phase, engine=engine
                )
                response_time_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    "ai_decision",
                    player_id=player_id,
                    action_type=str(action.action_type),
                    cards=action.cards,
                    attempt=attempt,
                    response_time_ms=response_time_ms,
                    used_langchain_parser=used_langchain_parser,
                )

                if self._decision_service:
                    await self._record_decision_point(
                        state=state,
                        player_id=player_id,
                        legal_actions=legal_actions,
                        chosen_action=action,
                        thinking=thinking,
                        game_id=game_id,
                    )

                return AIDecisionResult(
                    action=action,
                    thinking=thinking,
                    raw_response=raw_response,
                    messages=messages,
                    prompt_preview=prompt_preview,
                    raw_response_preview=self._truncate_text(raw_response),
                    usage=response.usage,
                    response_time_ms=response_time_ms,
                    used_langchain_parser=used_langchain_parser,
                    tool_results=tool_data,
                )

            except asyncio.TimeoutError:
                last_error = AITimeoutError(provider, f"Timeout on attempt {attempt}")
                logger.warning("ai_timeout", player_id=player_id, attempt=attempt)
            except AppError as e:
                last_error = e
                logger.warning("ai_error", player_id=player_id, attempt=attempt, error=str(e))
            except Exception as e:
                last_error = self._map_provider_error(provider, e)
                logger.warning(
                    "ai_unexpected_error",
                    player_id=player_id,
                    attempt=attempt,
                    error=str(last_error),
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.0 * attempt)

        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "ai_all_retries_failed",
            player_id=player_id,
            error=str(last_error),
        )
        fallback = legal_actions[0] if legal_actions else GameAction(
            player_id=player_id, action_type="PASS"
        )
        fallback_thinking = f"[LLM调用失败，使用默认动作] {last_error}"
        if self._decision_service:
            await self._record_decision_point(
                state=state,
                player_id=player_id,
                legal_actions=legal_actions,
                chosen_action=fallback,
                thinking=fallback_thinking,
                game_id=game_id,
            )
        return AIDecisionResult(
            action=fallback,
            thinking=fallback_thinking,
            raw_response=raw_response,
            messages=messages,
            prompt_preview=prompt_preview,
            raw_response_preview=self._truncate_text(raw_response),
            usage={"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
            response_time_ms=response_time_ms,
            used_langchain_parser=False,
            tool_results=tool_data,
        )

    async def get_decision_streaming(
        self,
        state: GameState,
        engine: GameEngine,
        player_id: str,
        player_config: dict[str, Any],
        legal_actions: list[GameAction],
        game_id: str | None = None,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> AIDecisionResult:
        """Get AI decision with streaming output.

        This method streams the LLM response chunk by chunk, calling the
        on_chunk callback for each chunk. Useful for real-time display
        of AI thinking process.

        Args:
            state: Current game state
            engine: Game engine instance
            player_id: ID of the player making the decision
            player_config: Player configuration including model settings
            legal_actions: List of legal actions available
            game_id: Optional game ID for logging
            on_chunk: Optional callback function called for each text chunk

        Returns:
            AIDecisionResult with the final action and metadata
        """
        start_time = time.perf_counter()

        model_cfg = player_config.get("model_config", {})
        model_name = model_cfg.get("model_name")

        # Run analysis tools (skip during bidding phase)
        phase = getattr(state, "phase", "playing")
        tool_data: dict[str, Any] | None = None
        if phase != "bidding":
            tool_data = self._run_tools(state, player_id)

        messages = await self._build_prompt_messages(
            state=state,
            legal_actions=legal_actions,
            engine=engine,
            player_id=player_id,
            model_name=model_name,
            game_id=game_id,
            tool_analysis=tool_data.get("tool_analysis") if tool_data else None,
        )

        client = self._get_client(player_config)

        kwargs: dict[str, Any] = {}
        if model_cfg.get("model_name"):
            kwargs["model"] = model_cfg["model_name"]
        if model_cfg.get("temperature") is not None:
            kwargs["temperature"] = model_cfg["temperature"]
        if model_cfg.get("max_tokens") is not None:
            kwargs["max_tokens"] = model_cfg["max_tokens"]

        prompt_preview = self._build_prompt_preview(messages)
        raw_parts: list[str] = []
        stream_usage: dict[str, int | None] | None = None
        provider = model_cfg.get("provider", "unknown")
        phase = getattr(state, "phase", "playing")

        last_error: Exception | None = None
        try:
            # Stream the response
            async for chunk in client.chat_stream(messages, **kwargs):
                raw_parts.append(chunk.text)
                if chunk.usage is not None:
                    stream_usage = chunk.usage
                if on_chunk:
                    on_chunk(chunk)

            # Parse the complete response
            raw_response = "".join(raw_parts)
            if not raw_response.strip():
                raise AIProviderError(provider, "Empty streaming response")

            thinking, action, used_langchain_parser = self._parse_with_metrics(
                raw_response, legal_actions, phase, engine=engine
            )
            response_time_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "ai_decision_streaming",
                player_id=player_id,
                action_type=str(action.action_type),
                cards=action.cards,
                response_time_ms=response_time_ms,
                used_langchain_parser=used_langchain_parser,
            )

            if self._decision_service:
                await self._record_decision_point(
                    state=state,
                    player_id=player_id,
                    legal_actions=legal_actions,
                    chosen_action=action,
                    thinking=thinking,
                    game_id=game_id,
                )

            return AIDecisionResult(
                action=action,
                thinking=thinking,
                raw_response=raw_response,
                messages=messages,
                prompt_preview=prompt_preview,
                raw_response_preview=self._truncate_text(raw_response),
                usage=stream_usage or {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                response_time_ms=response_time_ms,
                used_langchain_parser=used_langchain_parser,
                tool_results=tool_data,
            )

        except asyncio.TimeoutError:
            last_error = AITimeoutError(provider, "Timeout during streaming")
            logger.warning("ai_streaming_timeout", player_id=player_id)
        except AppError as e:
            last_error = e
            logger.warning("ai_streaming_error", player_id=player_id, error=str(e))
        except Exception as e:
            last_error = self._map_provider_error(provider, e)
            logger.warning(
                "ai_streaming_unexpected_error",
                player_id=player_id,
                error=str(last_error),
            )

        # Streaming failed / empty → retry once with non-streaming chat
        # (batch e2e and some providers are more reliable without SSE).
        logger.warning(
            "ai_streaming_fallback_to_chat",
            player_id=player_id,
            error=str(last_error),
        )
        try:
            return await self.get_decision(
                state=state,
                engine=engine,
                player_id=player_id,
                player_config=player_config,
                legal_actions=legal_actions,
                game_id=game_id,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "ai_nonstream_fallback_failed",
                player_id=player_id,
                error=str(e),
            )

        # Last resort: legal default (still record so export is not empty)
        raw_response = "".join(raw_parts)
        response_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "ai_streaming_failed",
            player_id=player_id,
            error=str(last_error),
        )
        fallback = legal_actions[0] if legal_actions else GameAction(
            player_id=player_id, action_type="PASS"
        )
        fallback_thinking = f"[LLM流式调用失败，使用默认动作] {last_error}"
        if self._decision_service:
            await self._record_decision_point(
                state=state,
                player_id=player_id,
                legal_actions=legal_actions,
                chosen_action=fallback,
                thinking=fallback_thinking,
                game_id=game_id,
            )
        return AIDecisionResult(
            action=fallback,
            thinking=fallback_thinking,
            raw_response=raw_response,
            messages=messages,
            prompt_preview=prompt_preview,
            raw_response_preview=self._truncate_text(raw_response),
            usage={"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
            response_time_ms=response_time_ms,
            used_langchain_parser=False,
            tool_results=tool_data,
        )

    async def _record_decision_point(
        self,
        state: GameState,
        player_id: str,
        legal_actions: list[GameAction],
        chosen_action: GameAction,
        thinking: str,
        game_id: str | None = None,
    ) -> None:
        """Record a decision point for SFT training data."""
        if not self._decision_service or not game_id:
            return

        try:
            hand_cards = self._extract_hand_cards(state, player_id)
            opponent_hands = self._extract_opponent_hands(state, player_id)
            last_action = self._extract_last_action(state)
            game_phase = self._determine_game_phase(state)
            legal_actions_data = [
                {"action_type": str(a.action_type), "cards": a.cards or []}
                for a in legal_actions
            ]
            chosen_action_data = {
                "action_type": str(chosen_action.action_type),
                "cards": chosen_action.cards or [],
            }

            await self._decision_service.create_decision_point(
                game_id=game_id,
                round_number=getattr(state, "round", 0),
                player_id=player_id,
                hand_cards=hand_cards,
                opponent_hands=opponent_hands,
                last_action=last_action,
                game_phase=game_phase,
                legal_actions=legal_actions_data,
                chosen_action=chosen_action_data,
                thinking=thinking,
            )
        except Exception:
            logger.warning("record_decision_point_failed", exc_info=True)

    def _run_tools(
        self,
        state: GameState,
        player_id: str,
    ) -> dict[str, Any]:
        """Run analysis tools and return results for prompt enrichment.

        Returns a dict with 'hand_analysis', 'win_probability', and 'tool_analysis' keys.
        """
        hand_cards = self._extract_hand_cards(state, player_id)
        opponent_hands = self._extract_opponent_hands(state, player_id)
        card_strs = [
            str(c) for c in hand_cards
        ]  # HandAnalyzerTool expects card codes like 'S3', 'H4'

        # Hand analysis
        hand_analysis = self._hand_analyzer.analyze(card_strs)

        # Win probability — determine role from state
        is_landlord = False
        if hasattr(state, "landlord_id"):
            is_landlord = getattr(state, "landlord_id", None) == player_id
        current_turn = getattr(state, "round", 0)

        win_prob = self._win_probability.estimate(
            my_card_count=len(hand_cards),
            opponent_card_counts=opponent_hands,
            has_bomb=hand_analysis.bomb_count > 0,
            has_rocket=hand_analysis.rocket,
            is_landlord=is_landlord,
            current_turn=current_turn,
        )

        # Format for prompt injection
        tool_analysis = self._prompt_builder.format_tool_results(
            hand_analysis=hand_analysis,
            win_probability=win_prob,
        )

        return {
            "hand_analysis": hand_analysis,
            "win_probability": win_prob,
            "tool_analysis": tool_analysis,
        }

    def _extract_hand_cards(self, state: GameState, player_id: str) -> list[int]:
        """Extract hand cards for a player from game state."""
        if hasattr(state, "hands") and isinstance(state.hands, dict):
            cards = state.hands.get(player_id, [])
            return list(cards) if isinstance(cards, list) else []
        return []

    def _extract_opponent_hands(self, state: GameState, player_id: str) -> dict[str, int]:
        """Extract opponent hand counts from game state."""
        opponent_hands: dict[str, int] = {}
        if hasattr(state, "hands") and isinstance(state.hands, dict):
            for pid, cards in state.hands.items():
                if pid != player_id:
                    opponent_hands[pid] = len(cards) if isinstance(cards, list) else cards
        return opponent_hands

    def _extract_last_action(self, state: GameState) -> dict[str, Any] | None:
        """Extract the last action from game state."""
        if hasattr(state, "last_action") and state.last_action:
            action = state.last_action
            return {
                "player": getattr(action, "player_id", ""),
                "action_type": str(getattr(action, "action_type", "PASS")),
                "cards": getattr(action, "cards", []) or [],
            }
        return None

    def _determine_game_phase(self, state: GameState) -> str:
        """Label bidding / playing / endgame for stored decision points."""
        engine_phase = str(getattr(state, "phase", "") or "")
        if engine_phase:
            hands = getattr(state, "hands", None)
            sizes: list[int] = []
            if isinstance(hands, dict):
                for cards in hands.values():
                    if isinstance(cards, list):
                        sizes.append(len(cards))
                    elif isinstance(cards, int):
                        sizes.append(int(cards))
            return classify_game_phase(engine_phase=engine_phase, hand_sizes=sizes)
        if hasattr(state, "round_number"):
            round_num = state.round_number
            if round_num <= 5:
                return "early"
            if round_num <= 15:
                return "mid"
            return "endgame"
        return "unknown"

    def _parse_with_metrics(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
        phase: str,
        *,
        engine: GameEngine | None = None,
    ) -> tuple[str, GameAction, bool]:
        """Parse response and return whether LangChain parser was used."""
        bidding_phases = (
            set(engine.capability.phases) & {"bidding"}
            if engine is not None
            else {"bidding"}
        )
        try:
            if phase in bidding_phases or phase == "bidding":
                thinking, action = self._bid_parser.parse(raw_response, legal_actions)
            else:
                thinking, action = self._action_parser.parse(raw_response, legal_actions)
            return thinking, action, True
        except Exception:
            thinking, action = self._fallback_parse(raw_response, legal_actions)
            return thinking, action, False

    def _fallback_parse(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
    ) -> tuple[str, GameAction]:
        """Fallback parsing when LangChain parser fails."""
        # Prefix so evaluate_train_usable marks train_usable=false
        thinking = f"[LLM解析失败，使用默认动作] {raw_response[:200]}"
        if legal_actions:
            return thinking, legal_actions[0]
        return thinking, GameAction(player_id="", action_type="PASS")

    @staticmethod
    def _truncate_text(text: str, limit: int = 400) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _build_prompt_preview(self, messages: list[dict[str, str]]) -> str:
        preview_parts = [
            f"[{message['role']}]\n{message['content']}"
            for message in messages
        ]
        return self._truncate_text("\n\n".join(preview_parts), limit=800)
