"""AI invocation service -- runs a policy for one decision and records it.

The decision procedure itself lives in ``core/policy``. This service picks the
policy, supplies what the policy is not allowed to reach (prompt templates, the
database, the live ``GameState``), consumes the resulting event stream, and turns
it into the payload the rest of the app expects.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from app.core.ai.errors import map_provider_error
from app.core.ai.prompt import PromptBuilder
from app.core.ai.stream_chunk import StreamChunk
from app.core.engine.base import GameAction, GameEngine, GameState, LegalAction
from app.core.policy import get_baseline_policy_registry
from app.core.policy.base import (
    ActionChosen,
    Budget,
    LlmRequest,
    LlmUsage,
    Policy,
    PolicyContext,
    ThinkingDelta,
    ToolResult,
)
from app.core.policy.baselines import FirstActionPolicy
from app.core.policy.kinds import is_baseline_policy_kind
from app.core.policy.llm import LLMPolicy
from app.services.decision_snapshot import (
    compact_tool_calls,
    game_phase_from_observation,
    hand_cards_from_observation,
    last_action_from_observation,
    opponent_hands_from_observation,
)
from app.services.prompt_source import EnginePromptSource
from app.utils.exceptions import AppError, InvalidActionError

if TYPE_CHECKING:
    from app.core.ai.base import LLMClient
    from app.core.ai.factory import LLMClientFactory
    from app.core.ai.vcr import VcrMode, VcrStore
    from app.core.engine.observation import Observation
    from app.core.eval.rollout import EvaluatorParams
    from app.services.decision_eval import DecisionEvaluator
    from app.services.decision_service import DecisionService

logger = structlog.get_logger()

MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60.0
MAX_TOOL_CALLS = 2

EMPTY_USAGE: dict[str, int | None] = {
    "prompt_tokens": None,
    "completion_tokens": None,
    "total_tokens": None,
}

# Engine tool names mapped onto the keys the WS / trace payloads already use.
_TOOL_RESULT_KEYS = {"analyze_hand": "hand_analysis", "win_probability": "win_probability"}


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
    parser_ok: bool = True
    prompt_version: str = ""
    tool_results: dict[str, Any] | None = None


@dataclass
class _DecisionTrace:
    """What the service scrapes off one policy run."""

    messages: list[dict[str, str]] = field(default_factory=list)
    reply_parts: list[str] = field(default_factory=list)
    usage: dict[str, int | None] = field(default_factory=lambda: dict(EMPTY_USAGE))
    tool_results: dict[str, Any] = field(default_factory=dict)
    chosen: ActionChosen | None = None


class AIService:
    """Runs a policy for one decision and records it."""

    def __init__(
        self,
        llm_factory: LLMClientFactory,
        prompt_builder: PromptBuilder,
        decision_service: DecisionService | None = None,
        sqlite_path: str | None = None,
        decision_evaluator: DecisionEvaluator | None = None,
        vcr_mode: VcrMode = "off",
        vcr_store: VcrStore | None = None,
    ) -> None:
        self._llm_factory = llm_factory
        self._prompt_builder = prompt_builder
        self._decision_service = decision_service
        self._sqlite_path = sqlite_path
        self._decision_evaluator = decision_evaluator
        self._vcr_mode = vcr_mode
        self._vcr_store = vcr_store
        self._client_cache: dict[str, LLMClient] = {}
        # game_id → protocol EV knobs (None = use DecisionEvaluator defaults)
        self._ev_params_by_game: dict[str, EvaluatorParams | None] = {}

    def _get_client(self, player_config: dict[str, Any]) -> LLMClient:
        model_cfg = player_config.get("model_config", {})
        provider = model_cfg.get("provider", "openai")
        if provider not in self._client_cache:
            client = self._llm_factory.create(provider)
            if self._vcr_mode in ("record", "replay") and self._vcr_store is not None:
                from app.core.ai.vcr import VcrLLMClient

                client = VcrLLMClient(
                    client,
                    self._vcr_store,
                    self._vcr_mode,
                    provider,
                )
            self._client_cache[provider] = client
        return self._client_cache[provider]

    def _build_policy(self, player_config: dict[str, Any], *, stream: bool) -> Policy:
        """Pick LLM or baseline policy from the seat's ``policy_kind``."""
        raw = str(player_config.get("policy_kind") or "llm").strip() or "llm"
        if is_baseline_policy_kind(raw):
            try:
                return get_baseline_policy_registry().create(raw)
            except InvalidActionError:
                logger.error("unknown_baseline_policy_kind", policy_kind=raw)
                return FirstActionPolicy()
        if raw != "llm":
            # Dirty protocol / pack data: keep the game alive without spending API.
            logger.error("unknown_player_policy_kind", policy_kind=raw)
            return FirstActionPolicy()
        model_cfg = player_config.get("model_config", {})
        return LLMPolicy(
            self._get_client(player_config),
            provider=model_cfg.get("provider", "unknown"),
            model_name=model_cfg.get("model_name"),
            temperature=model_cfg.get("temperature"),
            max_tokens=model_cfg.get("max_tokens"),
            stream=stream,
        )

    @staticmethod
    def _map_provider_error(provider: str, error: Exception) -> AppError:
        return map_provider_error(provider, error)

    async def get_decision(
        self,
        state: GameState,
        engine: GameEngine,
        player_id: str,
        player_config: dict[str, Any],
        legal_actions: list[GameAction],
        game_id: str | None = None,
    ) -> AIDecisionResult:
        """Decide without streaming. Used for batch runs with no observers."""
        return await self._decide(
            state=state,
            engine=engine,
            player_id=player_id,
            player_config=player_config,
            legal_actions=legal_actions,
            game_id=game_id,
            stream=False,
            on_chunk=None,
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
        """Decide, forwarding reply text to *on_chunk* as it arrives."""
        return await self._decide(
            state=state,
            engine=engine,
            player_id=player_id,
            player_config=player_config,
            legal_actions=legal_actions,
            game_id=game_id,
            stream=True,
            on_chunk=on_chunk,
        )

    async def _decide(
        self,
        *,
        state: GameState,
        engine: GameEngine,
        player_id: str,
        player_config: dict[str, Any],
        legal_actions: list[GameAction],
        game_id: str | None,
        stream: bool,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> AIDecisionResult:
        start_time = time.perf_counter()
        model_cfg = player_config.get("model_config", {})
        policy = self._build_policy(player_config, stream=stream)
        ctx = PolicyContext(
            advisor=engine,
            rng=random.Random(),
            session_id=game_id,
            prompts=EnginePromptSource(self._prompt_builder, engine, self._sqlite_path),
        )
        budget = Budget(
            max_llm_calls=MAX_RETRIES,
            max_tool_calls=MAX_TOOL_CALLS,
            timeout_s=DEFAULT_TIMEOUT,
        )

        observation = engine.observe(state, player_id)
        presented, _omitted = engine.present_legal_actions(state, player_id)

        trace = _DecisionTrace()
        async for event in policy.decide(observation, presented, budget, ctx):
            self._absorb(event, trace, on_chunk)

        chosen = trace.chosen
        if chosen is None:
            # ``Policy.decide`` guarantees a terminal ActionChosen; a policy that
            # breaks that contract must not take the game down with it.
            logger.error("policy_returned_no_action", player_id=player_id)
            chosen = ActionChosen(
                action_id=presented[0].id if presented else "",
                thinking="rescue: policy returned no action",
                parse_fallback=True,
            )

        action = self._resolve(engine, state, player_id, chosen, legal_actions)
        raw_response = "".join(trace.reply_parts)
        response_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "ai_decision",
            player_id=player_id,
            action_type=str(action.action_type),
            cards=action.cards,
            response_time_ms=response_time_ms,
            parse_fallback=chosen.parse_fallback,
        )

        if self._decision_service:
            await self._record_decision_point(
                state=state,
                engine=engine,
                observation=observation,
                player_id=player_id,
                presented=presented,
                chosen_action=action,
                chosen=chosen,
                prompt_messages=trace.messages,
                game_id=game_id,
                policy_kind=policy.kind,
                tool_results=trace.tool_results or None,
            )

        prompt_preview = self._build_prompt_preview(trace.messages)
        return AIDecisionResult(
            action=action,
            thinking=chosen.thinking,
            raw_response=raw_response,
            messages=trace.messages,
            prompt_preview=prompt_preview,
            raw_response_preview=self._truncate_text(raw_response),
            usage=trace.usage,
            response_time_ms=response_time_ms,
            parser_ok=not chosen.parse_fallback,
            prompt_version=self._prompt_builder.version_for(model_cfg.get("model_name")),
            tool_results=trace.tool_results or None,
        )

    @staticmethod
    def _absorb(
        event: Any,
        trace: _DecisionTrace,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> None:
        """Fold one policy event into the payload the app expects."""
        if isinstance(event, LlmRequest):
            trace.messages = event.messages
        elif isinstance(event, ThinkingDelta):
            trace.reply_parts.append(event.text)
            if on_chunk:
                on_chunk(StreamChunk(type=event.channel, text=event.text))
        elif isinstance(event, LlmUsage):
            trace.usage = dict(event.usage)
        elif isinstance(event, ToolResult):
            key = _TOOL_RESULT_KEYS.get(event.name, event.name)
            trace.tool_results[key] = event.result
            text = event.result.get("text")
            if isinstance(text, str) and text:
                existing = trace.tool_results.get("tool_analysis")
                trace.tool_results["tool_analysis"] = (
                    f"{existing}\n{text}" if existing else text
                )
        elif isinstance(event, ActionChosen):
            trace.chosen = event

    @staticmethod
    def _resolve(
        engine: GameEngine,
        state: GameState,
        player_id: str,
        chosen: ActionChosen,
        legal_actions: list[GameAction],
    ) -> GameAction:
        """Turn the chosen id back into a move the engine can apply."""
        try:
            return engine.resolve_action(state, player_id, chosen.action_id)
        except Exception:
            logger.warning(
                "action_id_not_resolvable", player_id=player_id, action_id=chosen.action_id
            )
            if legal_actions:
                return legal_actions[0]
            return GameAction(player_id=player_id, action_type="PASS")

    async def _record_decision_point(
        self,
        state: GameState,
        engine: GameEngine,
        observation: Observation,
        player_id: str,
        presented: list[LegalAction],
        chosen_action: GameAction,
        chosen: ActionChosen,
        prompt_messages: list[dict[str, str]],
        game_id: str | None = None,
        policy_kind: str = "llm",
        tool_results: dict[str, Any] | None = None,
    ) -> None:
        """Record a decision point for SFT training data.

        The menu stored here is the one the model was shown, not the full legal
        set: training on options that were never on screen would teach the model
        to pick ids it will never be offered.

        Board fields (hand, opponents, last play, phase) come from the same
        ``Observation`` the policy saw. EV loss is scored here while the live
        state is still available: a stored decision point does not carry enough
        to rebuild one later.
        """
        if not self._decision_service or not game_id:
            return

        try:
            legal_actions_data = [
                {
                    "id": entry.id,
                    "label": entry.label,
                    "action_type": str(entry.action.action_type),
                    "cards": entry.action.cards or [],
                }
                for entry in presented
            ]
            chosen_action_data = {
                "action_type": str(chosen_action.action_type),
                "cards": chosen_action.cards or [],
            }
            ev_loss, evaluator_params = await self._score_decision(
                engine, state, player_id, chosen_action, game_id=game_id
            )

            await self._decision_service.create_decision_point(
                game_id=game_id,
                round_number=observation.round,
                player_id=player_id,
                hand_cards=hand_cards_from_observation(observation),
                opponent_hands=opponent_hands_from_observation(observation),
                last_action=last_action_from_observation(observation),
                game_phase=game_phase_from_observation(observation),
                legal_actions=legal_actions_data,
                chosen_action=chosen_action_data,
                action_id=chosen.action_id,
                prompt_messages=prompt_messages,
                thinking=chosen.thinking,
                ev_loss=ev_loss,
                evaluator_params=evaluator_params,
                parse_fallback=chosen.parse_fallback,
                policy_kind=policy_kind,
                tool_calls=compact_tool_calls(tool_results),
            )
        except Exception:
            logger.warning("record_decision_point_failed", exc_info=True)

    async def _score_decision(
        self,
        engine: GameEngine,
        state: GameState,
        player_id: str,
        chosen_action: GameAction,
        *,
        game_id: str | None = None,
    ) -> tuple[float | None, dict[str, Any] | None]:
        """EV loss for the move, or ``(None, None)`` when scoring is off or fails.

        ``evaluator_params`` stores the rollout knobs plus ``best_action_id`` and
        ``action_values`` so preference export can build DPO pairs without replay.
        """
        if self._decision_evaluator is None:
            return None, None
        override = await self._protocol_evaluator_params(game_id)
        result = await self._decision_evaluator.score(
            engine, state, player_id, chosen_action, params=override
        )
        if result is None:
            return None, None
        params: dict[str, Any] = dict(result.params)
        params["best_action_id"] = result.best_action_id
        params["action_values"] = {
            str(action_id): float(value) for action_id, value in result.values.items()
        }
        params["candidates_evaluated"] = result.candidates_evaluated
        params["legal_action_count"] = result.legal_action_count
        params["truncated"] = result.truncated
        return result.loss, params

    async def _protocol_evaluator_params(
        self, game_id: str | None
    ) -> EvaluatorParams | None:
        """Frozen ``scorer.evaluator`` for the game's experiment, if any."""
        if not game_id or not self._sqlite_path:
            return None
        if game_id in self._ev_params_by_game:
            return self._ev_params_by_game[game_id]
        from app.core.eval.evaluator_protocol import protocol_evaluator_params
        from app.database import open_db_connection
        from app.repositories.experiment_repo import ExperimentRepository
        from app.repositories.game_repo import GameRepository

        params: EvaluatorParams | None = None
        try:
            conn = await open_db_connection(self._sqlite_path)
            try:
                try:
                    game = await GameRepository(conn).get_by_id(game_id)
                except KeyError:
                    self._ev_params_by_game[game_id] = None
                    return None
                experiment_id = game.get("experiment_id")
                if experiment_id:
                    row = await ExperimentRepository(conn).get_by_id(str(experiment_id))
                    protocol = row.get("protocol") if row else None
                    if isinstance(protocol, dict):
                        params = protocol_evaluator_params(protocol)
            finally:
                await conn.close()
        except Exception:
            logger.warning("protocol_evaluator_lookup_failed", game_id=game_id, exc_info=True)
            params = None
        self._ev_params_by_game[game_id] = params
        return params

    @staticmethod
    def _truncate_text(text: str, limit: int = 400) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _build_prompt_preview(self, messages: list[dict[str, str]]) -> str:
        preview_parts = [f"[{message['role']}]\n{message['content']}" for message in messages]
        return self._truncate_text("\n\n".join(preview_parts), limit=800)
