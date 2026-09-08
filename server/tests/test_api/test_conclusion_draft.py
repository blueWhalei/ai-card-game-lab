"""API / service tests for conclusion drafts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.database import init_db
from app.services.decision_service import DecisionService
from app.services.experiment_service import ExperimentService


def _fake_game_service() -> MagicMock:
    from app.core.engine.doudizhu.engine import DoudizhuEngine
    from app.core.engine.registry import GameEngineRegistry

    configs = {
        f"cfg_{i}": {
            "id": f"cfg_{i}",
            "name": f"P{i}",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        }
        for i in ("a", "b", "c")
    }
    cfg_svc = MagicMock()
    cfg_svc.get_config.side_effect = lambda pid: configs.get(pid)
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    gs = MagicMock()
    gs.player_slots.return_value = (3, 3)
    gs._experiment_config_service = cfg_svc
    gs._engine_registry = registry
    gs.create_game = AsyncMock()
    gs.start_game = AsyncMock()
    return gs


@pytest.fixture
async def experiment_service(tmp_path: Path) -> ExperimentService:
    db_path = str(tmp_path / "draft.db")
    await init_db(db_path)
    return ExperimentService(sqlite_path=db_path, game_service=_fake_game_service())


async def test_draft_does_not_write_conclusion(
    experiment_service: ExperimentService, tmp_path: Path
) -> None:
    created = await experiment_service.create_experiment(
        name="draft-exp",
        notes="",
        hypothesis="H",
        game_type="doudizhu",
        player_ids=["cfg_a", "cfg_b", "cfg_c"],
        target_games=2,
    )
    dec = DecisionService(sqlite_path=experiment_service._sqlite_path, data_dir=str(tmp_path))
    await dec.create_decision_point(
        game_id="g1",
        round_number=1,
        player_id="p1",
        hand_cards=[3],
        opponent_hands=None,
        last_action=None,
        game_phase="playing",
        legal_actions=[{"id": "PASS||", "action_type": "PASS", "cards": []}],
        chosen_action={"action_type": "PASS", "cards": []},
        action_id="PASS||",
        prompt_messages=[{"role": "user", "content": "x"}],
        ev_loss=0.8,
        evaluator_params={"best_action_id": "PLAY|3|"},
    )

    draft = await experiment_service.draft_conclusion(created["id"], locale="zh-CN")
    assert "【草稿 · 待确认】" in draft["text"]
    assert draft["verdict_key"] == "no_data"
    assert "blunders" in draft
    assert isinstance(draft["blunders"], list)
    assert draft["blunder_ids"] == [b["id"] for b in draft["blunders"]]

    again = await experiment_service.get_experiment(created["id"], include_games=False)
    assert again.get("conclusion") in ("", None)


async def test_conclusion_draft_api(client: AsyncClient) -> None:
    from tests.test_api.test_experiments import _create_experiment

    created = await _create_experiment(client, name="api-draft")
    resp = await client.post(
        f"/api/v1/experiments/{created['id']}/conclusion-draft",
        params={"locale": "en"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "[Draft · pending confirmation]" in data["text"]
    assert data["locale"] == "en"

    refreshed = await client.get(f"/api/v1/experiments/{created['id']}")
    assert refreshed.json()["data"]["conclusion"] in ("", None)
