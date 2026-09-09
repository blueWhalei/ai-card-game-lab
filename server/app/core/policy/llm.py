"""A policy that asks a language model which action to take.

This is the decision procedure that used to live inside ``AIService``: run the
engine's analysis tools, build a prompt, call the model with a retry budget,
and read an action id back. It reports every step as a ``PolicyEvent`` so the
service can broadcast, trace, and persist without the policy knowing that any of
those things exist.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import structlog

from app.core.ai.action_menu import render_menu
from app.core.ai.errors import map_provider_error
from app.core.ai.parsers.action_id_parser import ActionIdParser, response_format
from app.core.policy.base import (
    ActionChosen,
    Budget,
    LlmRequest,
    LlmUsage,
    Policy,
    PolicyContext,
    PolicyEvent,
    ThinkingDelta,
    ToolCall,
    ToolResult,
)
from app.utils.exceptions import AIParseError, AITimeoutError, InvalidActionError

if TYPE_CHECKING:
    from app.core.ai.base import LLMClient
    from app.core.engine.base import LegalAction
    from app.core.engine.observation import Observation

logger = structlog.get_logger()

RETRY_BACKOFF_S = 1.0


class LLMPolicy(Policy):
    """Single-shot LLM decision: tools, one prompt, one action id.

    Attributes:
        stream: Emit the reply as ``ThinkingDelta`` events while it arrives.
            A streaming failure falls back to one plain call -- batch runs and
            several providers are more reliable without SSE, so this is a
            deliberate path rather than leftover defensiveness.
        use_response_format: Constrain ``action_id`` to the legal set with a JSON
            Schema. Clients drop the field when the vendor rejects it, leaving the
            text instructions in place.
    """

    kind = "llm"

    def __init__(
        self,
        client: LLMClient,
        *,
        provider: str = "unknown",
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        use_response_format: bool = True,
        reasoning_effort: str | None = None,
        max_thinking_tokens: int | None = None,
    ) -> None:
        self._client = client
        self._provider = provider
        self._model_name = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._stream = stream
        self._use_response_format = use_response_format
        self._reasoning_effort = reasoning_effort
        self._max_thinking_tokens = max_thinking_tokens
        self._parser = ActionIdParser()

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        if not legal_actions:
            raise InvalidActionError(self.kind, "No legal actions to choose from")

        tool_texts: list[str] = []
        async for event in self._run_tools(observation, budget, ctx, tool_texts):
            yield event

        messages = await self._build_messages(observation, legal_actions, ctx, tool_texts)
        yield LlmRequest(messages=messages)
        legal_ids = [entry.id for entry in legal_actions]
        kwargs = self._call_kwargs(legal_ids)

        last_error: Exception | None = None
        attempts = max(1, budget.max_llm_calls)
        for attempt in range(1, attempts + 1):
            reply: list[str] = []
            try:
                async for event in self._call_model(messages, kwargs, budget, reply):
                    yield event

                raw_response = "".join(reply)
                decision = self._parser.parse(raw_response, legal_ids)
                yield ActionChosen(
                    action_id=decision.action_id,
                    thinking=decision.thinking or raw_response[:400],
                    raw_response=raw_response,
                )
                return
            except AIParseError as error:
                last_error = error
                logger.warning(
                    "llm_policy_parse_failed",
                    player_id=observation.player_id,
                    attempt=attempt,
                    error=str(error),
                )
            except TimeoutError:
                last_error = AITimeoutError(self._provider, f"Timeout on attempt {attempt}")
                logger.warning(
                    "llm_policy_timeout", player_id=observation.player_id, attempt=attempt
                )
            except Exception as error:
                last_error = map_provider_error(self._provider, error)
                logger.warning(
                    "llm_policy_call_failed",
                    player_id=observation.player_id,
                    attempt=attempt,
                    error=str(last_error),
                )

            if attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_S * attempt)

        yield self._rescue(legal_actions, observation, ctx, last_error)

    async def _run_tools(
        self,
        observation: Observation,
        budget: Budget,
        ctx: PolicyContext,
        tool_texts: list[str],
    ) -> AsyncIterator[PolicyEvent]:
        """Run the engine tools that apply to this phase, within budget."""
        if budget.max_tool_calls <= 0:
            return
        for name in ctx.advisor.tool_names(observation.phase)[: budget.max_tool_calls]:
            yield ToolCall(name=name)
            try:
                result = ctx.advisor.run_tool(name, observation)
            except Exception as error:
                # An analysis tool is an aid, never a precondition for deciding.
                logger.warning("llm_policy_tool_failed", tool=name, error=str(error))
                continue
            text = result.get("text")
            if isinstance(text, str) and text:
                tool_texts.append(text)
            yield ToolResult(name=name, result=result)

    async def _build_messages(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
        tool_texts: list[str],
    ) -> list[dict[str, str]]:
        instructions = self._parser.get_format_instructions()
        system = (
            await ctx.prompts.system_message(
                phase=observation.phase,
                model_name=self._model_name,
                format_instructions=instructions,
            )
            if ctx.prompts is not None
            else instructions
        )

        parts: list[str] = [observation.text, ""]
        if tool_texts:
            parts.extend(["## AI分析", "\n".join(tool_texts), ""])
        parts.extend(["## 可选动作", render_menu(legal_actions), "", "请决策："])

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(parts)},
        ]

    def _call_kwargs(self, legal_ids: list[str]) -> dict[str, Any]:
        from app.core.ai.prompt import is_reasoning_model

        kwargs: dict[str, Any] = {}
        if self._model_name:
            kwargs["model"] = self._model_name
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        max_tokens = self._max_tokens
        if is_reasoning_model(self._model_name) and self._max_thinking_tokens is not None:
            max_tokens = self._max_thinking_tokens
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        if self._use_response_format:
            kwargs["response_format"] = response_format(legal_ids)
        return kwargs

    async def _call_model(
        self,
        messages: list[dict[str, str]],
        kwargs: dict[str, Any],
        budget: Budget,
        reply: list[str],
    ) -> AsyncIterator[PolicyEvent]:
        """One model call. Appends the reply text to ``reply`` as it arrives.

        ``budget.timeout_s`` bounds a non-streaming call. A stream is bounded by
        the client's own read timeout instead: a wall-clock cap here would cut off
        slow local models that are still producing tokens.
        """
        if self._stream:
            try:
                async for event in self._call_streaming(messages, kwargs, reply):
                    yield event
                return
            except Exception as error:
                logger.warning("llm_policy_stream_fallback", error=str(error))
                # Partial text from the abandoned stream must not be parsed
                # together with the retry's reply.
                reply.clear()

        response = await asyncio.wait_for(
            self._client.chat(messages, **kwargs), timeout=budget.timeout_s
        )
        yield LlmUsage(usage=response.usage, model=self._model_name)
        reply.append(response.content)
        yield ThinkingDelta(text=response.content)

    async def _call_streaming(
        self,
        messages: list[dict[str, str]],
        kwargs: dict[str, Any],
        reply: list[str],
    ) -> AsyncIterator[PolicyEvent]:
        async for chunk in self._client.chat_stream(messages, **kwargs):
            if chunk.usage is not None:
                yield LlmUsage(usage=chunk.usage, model=self._model_name)
            if chunk.text:
                reply.append(chunk.text)
                yield ThinkingDelta(text=chunk.text, channel=chunk.type)
        if not "".join(reply).strip():
            raise AIParseError("Empty streaming response")

    def _rescue(
        self,
        legal_actions: list[LegalAction],
        observation: Observation,
        ctx: PolicyContext,
        error: Exception | None,
    ) -> ActionChosen:
        """A legal move so the game continues, flagged so nothing counts it as one.

        ``parse_fallback`` is the signal consumers read: this sample is not
        training data and this decision is not evidence about the model. The
        engine's suggestion is used rather than the first legal action, which in
        presentation order is the strongest bomb available -- a rescue should not
        cost the player their best card.
        """
        suggested = ctx.advisor.suggest_action(observation, legal_actions)
        chosen = suggested or legal_actions[0].id
        logger.error(
            "llm_policy_exhausted",
            player_id=observation.player_id,
            action_id=chosen,
            error=str(error),
        )
        return ActionChosen(
            action_id=chosen,
            thinking=f"rescue: {error}",
            parse_fallback=True,
        )
