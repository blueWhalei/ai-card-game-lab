"""Mock-LLM experiment collect path: create → collect → scoped stats."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app import dependencies
from app.services.ai_service import AIDecisionResult
from tests.test_api.test_experiments import _create_experiment


async def _fake_decision(
    state: object,
    engine: object,
    player_id: str,
    player_config: dict[str, Any] | None = None,
    legal_actions: list[Any] | None = None,
    **kwargs: object,
) -> AIDecisionResult:
    actions = legal_actions or engine.get_legal_actions(state, player_id)  # type: ignore[attr-defined]
    action = actions[0]
    return AIDecisionResult(
        action=action,
        thinking="legal",
        raw_response="legal",
        messages=[],
        prompt_preview="",
        raw_response_preview="",
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        used_langchain_parser=True,
    )


async def test_collect_mock_llm_scopes_experiment_stats(client: AsyncClient) -> None:
    created = await _create_experiment(client, target_games=1)
    ai = dependencies.get_ai_service()
    orch = dependencies.get_game_orchestration_service()

    with (
        patch.object(ai, "get_decision", side_effect=_fake_decision),
        patch.object(ai, "get_decision_streaming", side_effect=_fake_decision),
        patch(
            "app.services.game_orchestration_service.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        response = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 1},
        )
        assert response.status_code == 201, response.text
        pending = list(orch._tasks.values())
        if pending:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=30,
            )

    detail = await client.get(f"/api/v1/experiments/{created['id']}")
    summary = detail.json()["data"]["summary"]
    assert summary["total_games"] == 1
    assert summary["status"] in {"ready_review", "ready_more", "collecting"}
    if summary["status"] == "collecting":
        return

    stats = await client.get(
        "/api/v1/data/stats",
        params={"experiment_id": created["id"]},
    )
    assert stats.status_code == 200
    assert stats.json()["data"]["total_games"] == 1
    traces = await client.get(
        "/api/v1/traces",
        params={"experiment_id": created["id"]},
    )
    assert traces.json()["data"]["total"] >= 1
