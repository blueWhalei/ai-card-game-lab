"""Unit tests for CardLab MCP tools (read + collect write)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import init_db
from app.mcp import tools as tool_impl
from app.mcp.serialize import truncate_decision_item
from app.mcp.server import build_mcp_server
from app.services.decision_service import DecisionService
from app.services.experiment_service import ExperimentService


def _fake_game_service() -> MagicMock:
    from app.core.engine.doudizhu.engine import DoudizhuEngine
    from app.core.engine.registry import GameEngineRegistry

    configs = {
        "cfg_a": {
            "id": "cfg_a",
            "name": "A",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
        "cfg_b": {
            "id": "cfg_b",
            "name": "B",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.5,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
        "cfg_c": {
            "id": "cfg_c",
            "name": "C",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.9,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
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
async def services(tmp_path: Path) -> tuple[ExperimentService, DecisionService]:
    db_path = str(tmp_path / "mcp.db")
    await init_db(db_path)
    exp = ExperimentService(sqlite_path=db_path, game_service=_fake_game_service())
    dec = DecisionService(sqlite_path=db_path, data_dir=str(tmp_path))
    return exp, dec


class TestSerialize:
    def test_truncates_long_thinking_and_prompt(self) -> None:
        item = truncate_decision_item(
            {
                "id": "d1",
                "thinking": "x" * 600,
                "prompt_messages": [{"role": "user", "content": "y" * 500}],
            }
        )
        assert item["thinking"].endswith("…")
        assert len(item["thinking"]) == 501
        assert item["prompt_messages"][0]["content_len"] == 500
        assert item["prompt_messages"][0]["content"].endswith("…")


class TestTools:
    async def test_list_and_get_experiment(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, _dec = services
        created = await exp_svc.create_experiment(
            name="mcp-exp",
            notes="",
            game_type="doudizhu",
            player_ids=["cfg_a", "cfg_b", "cfg_c"],
            target_games=2,
        )

        listed = await tool_impl.list_experiments(exp_svc)
        assert listed["count"] == 1
        assert listed["items"][0]["id"] == created["id"]
        assert "next_step" in listed["items"][0]

        detail = await tool_impl.get_experiment(exp_svc, created["id"])
        assert detail["id"] == created["id"]
        assert "delta" in detail
        assert "validation" in detail
        assert "next_step" in detail
        assert "games" not in detail or detail.get("games") in (None, [])

    async def test_decision_list_and_stats(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        _exp, dec = services
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
            prompt_messages=[{"role": "user", "content": "pick"}],
            thinking="pass",
        )

        listed = await tool_impl.list_decision_points(dec, limit=10)
        assert listed["total"] == 1
        assert listed["count"] == 1
        assert listed["items"][0]["action_id"] == "PASS||"

        stats = await tool_impl.get_decision_stats(dec)
        assert stats["total"] == 1


class TestServerRegistration:
    async def test_registers_six_tools(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, dec = services
        server = build_mcp_server(exp_svc, dec)
        tools = await server.list_tools()
        names = sorted(tool.name for tool in tools)
        assert names == [
            "cancel_collect",
            "get_decision_stats",
            "get_experiment",
            "list_decision_points",
            "list_experiments",
            "start_collect",
        ]


class TestCollectTools:
    async def test_start_collect_forwards_to_service(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, _dec = services
        created = await exp_svc.create_experiment(
            name="mcp-collect",
            notes="",
            game_type="doudizhu",
            player_ids=["cfg_a", "cfg_b", "cfg_c"],
            target_games=2,
        )
        exp_svc.collect = AsyncMock(return_value={"game_ids": ["g1"], "count": 1})  # type: ignore[method-assign]

        result = await tool_impl.start_collect(exp_svc, created["id"], count=2)
        assert result["ok"] is True
        assert result["game_ids"] == ["g1"]
        assert result["count"] == 1
        exp_svc.collect.assert_awaited_once()
        call = exp_svc.collect.await_args
        assert call.args[0] == created["id"]
        assert call.kwargs["count"] == 2
        assert call.kwargs["db"] is not None

    async def test_start_collect_clamps_count(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, _dec = services
        created = await exp_svc.create_experiment(
            name="mcp-clamp",
            notes="",
            game_type="doudizhu",
            player_ids=["cfg_a", "cfg_b", "cfg_c"],
            target_games=2,
        )
        exp_svc.collect = AsyncMock(return_value={"game_ids": [], "count": 0})  # type: ignore[method-assign]

        await tool_impl.start_collect(exp_svc, created["id"], count=999)
        assert exp_svc.collect.await_args.kwargs["count"] == 50

    async def test_start_collect_missing_experiment_raises(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, _dec = services
        from app.utils.exceptions import AppError

        with pytest.raises(AppError):
            await tool_impl.start_collect(exp_svc, "missing-exp", count=1)

    async def test_cancel_collect_forwards(
        self, services: tuple[ExperimentService, DecisionService]
    ) -> None:
        exp_svc, _dec = services
        created = await exp_svc.create_experiment(
            name="mcp-cancel",
            notes="",
            game_type="doudizhu",
            player_ids=["cfg_a", "cfg_b", "cfg_c"],
            target_games=2,
        )
        exp_svc.cancel_collect = AsyncMock(  # type: ignore[method-assign]
            return_value={"cancelled_game_ids": ["g1"], "count": 1}
        )

        result = await tool_impl.cancel_collect(exp_svc, created["id"])
        assert result["ok"] is True
        assert result["cancelled_game_ids"] == ["g1"]
        exp_svc.cancel_collect.assert_awaited_once_with(created["id"])
