"""Tool-loop (ReAct) policy: the model requests engine tools, then an action id.

Unlike ``LLMPolicy``, tools are not pre-run and pasted into the prompt. The model
asks for them by name within ``Budget.max_tool_calls``. The wire format is plain
JSON (not vendor ``tools=``) so every OpenAI-compatible and Ollama path works
without capability probes.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import structlog

from app.core.ai.action_menu import render_menu
from app.core.ai.errors import map_provider_error
from app.core.ai.parsers.action_id_parser import response_format
from app.core.policy.base import (
    ActionChosen,
    Budget,
    LlmRequest,
    PolicyContext,
    PolicyEvent,
    ToolCall,
    ToolResult,
)
from app.core.policy.llm import LLMPolicy, RETRY_BACKOFF_S
from app.utils.exceptions import AIParseError, AITimeoutError, InvalidActionError

if TYPE_CHECKING:
    from app.core.engine.base import LegalAction
    from app.core.engine.observation import Observation

logger = structlog.get_logger()

_TOOL_JSON = re.compile(r"\{[^{}]*\}", re.DOTALL)


class ToolLoopPolicy(LLMPolicy):
    """ReAct loop over engine-declared tools, then one action id."""

    kind = "tool_loop"

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
        tool_names = list(ctx.advisor.tool_names(observation.phase))
        tool_catalog = self._tool_catalog(ctx, observation.phase)

        messages = await self._build_loop_messages(
            observation, legal_actions, ctx, tool_catalog, allow_tools=bool(tool_names)
        )
        yield LlmRequest(messages=list(messages))

        tools_used = 0
        max_tools = max(0, budget.max_tool_calls)
        last_error: Exception | None = None
        # Outer LLM attempts share the same budget as single-shot; each tool
        # round is an additional call that still counts toward max_llm_calls.
        llm_calls = 0
        max_llm = max(1, budget.max_llm_calls)

        while llm_calls < max_llm:
            allow_tools = tools_used < max_tools and bool(tool_names)
            if not allow_tools and "请决策" not in (messages[-1].get("content") or ""):
                messages = await self._build_loop_messages(
                    observation, legal_actions, ctx, tool_catalog, allow_tools=False
                )
                # Keep prior tool transcripts by appending a decisive user turn.
                messages = list(messages[:-1]) + [
                    {
                        "role": "user",
                        "content": (
                            "工具额度已用尽或无可用工具。请直接输出 "
                            '{"thinking":"...","action_id":"<合法id>"}。\n'
                            f"{render_menu(legal_actions)}"
                        ),
                    }
                ]

            kwargs = self._call_kwargs(legal_ids, allow_tools=allow_tools)
            reply: list[str] = []
            llm_calls += 1
            try:
                async for event in self._call_model(messages, kwargs, budget, reply):
                    yield event
                raw = "".join(reply)
                step = self._parse_step(raw, legal_ids, tool_names if allow_tools else [])
                if step[0] == "action":
                    _, action_id, thinking = step
                    yield ActionChosen(
                        action_id=action_id,
                        thinking=thinking or raw[:400],
                        raw_response=raw,
                    )
                    return
                _, tool_name, arguments = step
                tools_used += 1
                yield ToolCall(name=tool_name)
                try:
                    result = ctx.advisor.run_tool(tool_name, observation, arguments)
                except Exception as error:
                    logger.warning("tool_loop_tool_failed", tool=tool_name, error=str(error))
                    result = {"text": f"tool error: {error}", "error": str(error)}
                yield ToolResult(name=tool_name, result=result)
                messages.append({"role": "assistant", "content": raw})
                text = result.get("text") if isinstance(result, dict) else None
                payload = text if isinstance(text, str) and text else json.dumps(
                    result, ensure_ascii=False
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"工具 {tool_name} 结果：\n{payload}\n请继续：调用工具或给出 action_id。",
                    }
                )
                continue
            except AIParseError as error:
                last_error = error
                logger.warning(
                    "tool_loop_parse_failed",
                    player_id=observation.player_id,
                    attempt=llm_calls,
                    error=str(error),
                )
            except TimeoutError:
                last_error = AITimeoutError(self._provider, f"Timeout on attempt {llm_calls}")
            except Exception as error:
                last_error = map_provider_error(self._provider, error)
                logger.warning(
                    "tool_loop_call_failed",
                    player_id=observation.player_id,
                    attempt=llm_calls,
                    error=str(last_error),
                )
            if llm_calls < max_llm:
                await asyncio.sleep(RETRY_BACKOFF_S * llm_calls)

        yield self._rescue(legal_actions, observation, ctx, last_error)

    def _tool_catalog(self, ctx: PolicyContext, phase: str) -> str:
        names = ctx.advisor.tool_names(phase)
        return "\n".join(f"- {name}" for name in names) or "(无)"

    async def _build_loop_messages(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
        tool_catalog: str,
        *,
        allow_tools: bool,
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
        if allow_tools:
            system = (
                f"{system}\n\n你可以使用工具辅助决策。先输出 "
                '{"tool":"<name>","arguments":{}} '
                "或直接输出 "
                '{"thinking":"...","action_id":"<合法id>"}。\n'
                f"可用工具：\n{tool_catalog}"
            )
        parts = [
            observation.text,
            "",
            "## 可选动作",
            render_menu(legal_actions),
            "",
            "请决策：",
        ]
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(parts)},
        ]

    def _call_kwargs(self, legal_ids: list[str], *, allow_tools: bool = False) -> dict[str, Any]:
        # Final action turn keeps the action_id enum; tool turns stay unconstrained
        # so the model can emit a tool object without fighting the schema.
        if allow_tools:
            kwargs: dict[str, Any] = {}
            if self._model_name:
                kwargs["model"] = self._model_name
            if self._temperature is not None:
                kwargs["temperature"] = self._temperature
            if self._max_tokens is not None:
                kwargs["max_tokens"] = self._max_tokens
            return kwargs
        return super()._call_kwargs(legal_ids)

    def _parse_step(
        self,
        raw: str,
        legal_ids: list[str],
        tool_names: list[str],
    ) -> tuple[str, str, Any]:
        data = self._extract_json(raw)
        tool_name = str(data.get("tool") or data.get("tool_name") or "").strip()
        if tool_name and tool_names:
            if tool_name not in tool_names:
                raise AIParseError(f"Unknown tool '{tool_name}'")
            args = data.get("arguments") or data.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            return ("tool", tool_name, args)
        decision = self._parser.parse(raw, legal_ids)
        return ("action", decision.action_id, decision.thinking)

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        match = _TOOL_JSON.search(text)
        if match:
            try:
                value = json.loads(match.group(0))
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
        return {}
