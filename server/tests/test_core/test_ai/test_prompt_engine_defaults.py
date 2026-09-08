"""PromptBuilder engine defaults (no doudizhu hardcoding in ai/prompt)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.ai.prompt import PromptBuilder, _load_rules
from app.core.engine.base import EngineCapability, GameEngine, GameState
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.engine.doudizhu.prompts import DOUDIZHU_BIDDING_SYSTEM_TEMPLATE
from app.core.engine.prompt_defaults import SYSTEM_TEMPLATE


class _StubEngine(GameEngine):
    """Minimal engine without rules_ref / display_name."""

    @property
    def game_type(self) -> str:
        return "stubpoker"

    def initialize(self, player_ids: list[str], seed: int | None = None) -> GameState:  # type: ignore[override]
        raise NotImplementedError

    def get_legal_actions(self, state: GameState, player_id: str):  # type: ignore[override]
        raise NotImplementedError

    def apply_action(self, state: GameState, action):  # type: ignore[override]
        raise NotImplementedError

    def is_terminal(self, state: GameState) -> bool:
        raise NotImplementedError

    def get_winner(self, state: GameState) -> str | None:
        raise NotImplementedError

    def get_current_player(self, state: GameState) -> str:
        raise NotImplementedError

    def format_for_prompt(self, state: GameState, player_id: str) -> str:
        raise NotImplementedError

    def parse_action(self, text: str, state: GameState, player_id: str):  # type: ignore[override]
        raise NotImplementedError

    def get_public_info(self, state: GameState, player_id: str | None = None, **kwargs):  # type: ignore[override]
        raise NotImplementedError


class _NamedStubEngine(_StubEngine):
    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            game_type=self.game_type,
            min_players=2,
            max_players=2,
            display_name="假扑克",
            prompt_keys={"playing": "stubpoker_playing"},
        )


@pytest.mark.asyncio
async def test_doudizhu_missing_template_uses_bidding_default() -> None:
    builder = PromptBuilder(registry=_EmptyRegistry())
    engine = DoudizhuEngine()
    msg = await builder.system_message(
        engine=engine,
        phase="bidding",
        format_instructions="FMT",
    )
    assert "叫地主阶段" in msg
    assert "有炸弹/王炸" in msg
    assert "FMT" in msg
    assert "斗地主" in msg
    assert msg == DOUDIZHU_BIDDING_SYSTEM_TEMPLATE.format(format_instructions="FMT")


@pytest.mark.asyncio
async def test_stub_engine_uses_generic_template_and_display_name() -> None:
    builder = PromptBuilder(registry=_EmptyRegistry())
    msg = await builder.system_message(
        engine=_NamedStubEngine(),
        phase="playing",
        format_instructions="FMT",
    )
    assert "假扑克" in msg
    assert "核心规则" in msg
    assert "FMT" in msg
    assert msg == SYSTEM_TEMPLATE.format(
        game_type_cn="假扑克",
        rules="（未配置 rules_ref，或规则文件不存在。）",
        format_instructions="FMT",
    )


@pytest.mark.asyncio
async def test_stub_without_display_name_falls_back_to_game_type() -> None:
    builder = PromptBuilder(registry=_EmptyRegistry())
    msg = await builder.system_message(
        engine=_StubEngine(),
        phase="playing",
        format_instructions="X",
    )
    assert "stubpoker" in msg


def test_load_rules_only_via_rules_ref() -> None:
    missing = _load_rules(None)
    assert "rules_ref" in missing
    # Dou Dizhu rules_ref still resolves the docs file
    text = _load_rules("docs/欢乐斗地主经典玩法规则.md")
    assert "斗地主" in text or len(text) > 50


def test_ai_tools_package_has_no_doudizhu_import() -> None:
    tools_dir = Path(__file__).resolve().parents[3] / "app" / "core" / "ai" / "tools"
    for path in tools_dir.rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        assert "doudizhu" not in body, f"{path.name} still mentions doudizhu"


class _EmptyRegistry:
    """Always miss so PromptBuilder falls back to engine.default_system_template."""

    async def get_template(self, **kwargs: object) -> str:
        del kwargs
        raise ValueError("no template")
