"""Frozen protocol prompts are used at decide time (Wave: prompt as experiment var)."""

from __future__ import annotations

import pytest

from app.core.ai.prompt import PromptBuilder
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.task_protocol import prompt_content_hash, protocol_prompts
from app.services.prompt_source import EnginePromptSource


@pytest.mark.asyncio
async def test_engine_prompt_source_prefers_frozen_body() -> None:
    engine = DoudizhuEngine()
    key = engine.capability.prompt_keys["playing"]
    frozen = "FROZEN {game_type_cn}\n{rules}\n{format_instructions}"
    source = EnginePromptSource(
        PromptBuilder(),
        engine,
        sqlite_path=None,
        frozen_prompts={
            key: {
                "version": "v3_ab",
                "content": frozen,
                "content_hash": prompt_content_hash(frozen),
            }
        },
        frozen_prompt_version="v3_ab",
    )
    text = await source.system_message(
        phase="playing",
        model_name="gpt-4o-mini",
        format_instructions="PICK",
    )
    assert text.startswith("FROZEN")
    assert "PICK" in text
    assert source.prompt_version_label == "v3_ab"


def test_protocol_prompts_accessor() -> None:
    from app.core.task_protocol import build_protocol

    engine = DoudizhuEngine()
    body = "X {game_type_cn} {rules} {format_instructions}"
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t",
        prompt_version="v3_ab",
        collect_mode="free",
        protocol_fingerprint=engine.capability.protocol_fingerprint(),
        prompts={
            "doudizhu_playing": {
                "version": "v3_ab",
                "content": body,
                "content_hash": prompt_content_hash(body),
            }
        },
    )
    frozen = protocol_prompts(protocol)
    assert "doudizhu_playing" in frozen
    assert frozen["doudizhu_playing"]["content"] == body
