"""Search-augmented policy: LLM proposes candidates, rollouts pick the best EV."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import structlog

from app.core.ai.action_menu import render_menu
from app.core.ai.errors import map_provider_error
from app.core.engine.base import ActionId
from app.core.policy.base import (
    ActionChosen,
    Budget,
    LlmRequest,
    PolicyContext,
    PolicyEvent,
)
from app.core.policy.llm import LLMPolicy
from app.utils.exceptions import AIParseError, AITimeoutError, InvalidActionError

if TYPE_CHECKING:
    from app.core.engine.base import LegalAction
    from app.core.engine.observation import Observation

logger = structlog.get_logger()

_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


class SearchAugmentedPolicy(LLMPolicy):
    """Propose ≤k legal ids, score with ``ctx.score_actions``, pick the max EV."""

    kind = "search"

    def __init__(self, *args: Any, search_k: int = 4, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._search_k = max(1, int(search_k))

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        if not legal_actions:
            raise InvalidActionError(self.kind, "No legal actions to choose from")

        legal_ids = [entry.id for entry in legal_actions]
        messages = await self._build_search_messages(observation, legal_actions, ctx)
        yield LlmRequest(messages=messages)
        kwargs = self._search_call_kwargs()

        last_error: Exception | None = None
        attempts = max(1, budget.max_llm_calls)
        candidates: list[ActionId] = []
        thinking = ""
        raw_response = ""

        for attempt in range(1, attempts + 1):
            reply: list[str] = []
            try:
                async for event in self._call_model(messages, kwargs, budget, reply):
                    yield event
                raw_response = "".join(reply)
                thinking, candidates = self._parse_candidates(raw_response, legal_ids)
                break
            except AIParseError as error:
                last_error = error
                logger.warning(
                    "search_policy_parse_failed",
                    player_id=observation.player_id,
                    attempt=attempt,
                    error=str(error),
                )
            except TimeoutError:
                last_error = AITimeoutError(self._provider, f"Timeout on attempt {attempt}")
            except Exception as error:
                last_error = map_provider_error(self._provider, error)
                logger.warning(
                    "search_policy_call_failed",
                    player_id=observation.player_id,
                    attempt=attempt,
                    error=str(last_error),
                )
            if attempt >= attempts:
                yield self._rescue(legal_actions, observation, ctx, last_error)
                return

        if not candidates:
            suggested = ctx.advisor.suggest_action(observation, legal_actions)
            pick = suggested if suggested in legal_ids else legal_ids[0]
            yield ActionChosen(
                action_id=pick,
                thinking=thinking or "search: empty candidates → heuristic/first",
                raw_response=raw_response,
                parse_fallback=True,
            )
            return

        chosen = self._pick_by_score(observation, legal_actions, candidates, ctx)
        yield ActionChosen(
            action_id=chosen,
            thinking=thinking or f"search among {len(candidates)} candidates",
            raw_response=raw_response,
        )

    async def _build_search_messages(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> list[dict[str, str]]:
        instructions = (
            '先输出 JSON：{"thinking":"...","candidates":["合法action_id",...]}，'
            f"candidates 最多 {self._search_k} 个，且必须全部合法。"
        )
        system = (
            await ctx.prompts.system_message(
                phase=observation.phase,
                model_name=self._model_name,
                format_instructions=instructions,
            )
            if ctx.prompts is not None
            else instructions
        )
        parts = [
            observation.text,
            "",
            "## 可选动作",
            render_menu(legal_actions),
            "",
            f"请给出最多 {self._search_k} 个候选 action_id：",
        ]
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(parts)},
        ]

    def _search_call_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self._model_name:
            kwargs["model"] = self._model_name
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        # Do not attach action_id enum — candidates is an array.
        return kwargs

    def _parse_candidates(self, raw: str, legal_ids: list[str]) -> tuple[str, list[ActionId]]:
        data = self._extract_json(raw)
        thinking = str(data.get("thinking") or "")
        raw_cands = data.get("candidates")
        if not isinstance(raw_cands, list):
            # Fall back to single action_id replies.
            action_id = str(data.get("action_id") or "")
            if action_id in legal_ids:
                return thinking, [action_id]
            raise AIParseError("Search reply missing candidates")
        legal_set = set(legal_ids)
        out: list[ActionId] = []
        for item in raw_cands:
            aid = str(item)
            if aid in legal_set and aid not in out:
                out.append(aid)
            if len(out) >= self._search_k:
                break
        if not out:
            raise AIParseError("No legal candidates in search reply")
        return thinking, out

    def _pick_by_score(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        candidates: list[ActionId],
        ctx: PolicyContext,
    ) -> ActionId:
        if ctx.score_actions is not None:
            try:
                values = ctx.score_actions(observation, legal_actions, candidates)
                if values:
                    return max(values, key=lambda action_id: values[action_id])
            except Exception as error:
                logger.warning("search_score_failed", error=str(error))
        subset = [la for la in legal_actions if la.id in set(candidates)]
        suggested = ctx.advisor.suggest_action(observation, subset or legal_actions)
        if suggested and suggested in candidates:
            return suggested
        return candidates[0]

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        match = _JSON_OBJ.search(text)
        if match:
            try:
                value = json.loads(match.group(0))
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
        return {}
