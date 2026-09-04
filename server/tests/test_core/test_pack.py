"""Unit tests for shareable experiment / player packs."""

from __future__ import annotations

from app.core.pack import (
    KIND_EXPERIMENT_PACK,
    KIND_PLAYER_PACK,
    build_experiment_pack,
    parse_pack,
    redact_mapping,
    sanitize_player,
)


def test_redact_mapping_drops_api_keys() -> None:
    cleaned = redact_mapping(
        {
            "provider": "deepseek",
            "model_name": "deepseek-v4-flash",
            "api_key": "sk-secret",
            "openai_api_key": "sk-other",
            "temperature": 0.7,
        }
    )
    assert "api_key" not in cleaned
    assert "openai_api_key" not in cleaned
    assert cleaned["provider"] == "deepseek"
    assert cleaned["temperature"] == 0.7


def test_sanitize_player_strips_secrets() -> None:
    player = sanitize_player(
        {
            "id": "cfg_a",
            "name": "A",
            "notes": "n",
            "model_config": {"provider": "ollama", "model_name": "lora_x", "token": "nope"},
        }
    )
    assert "token" not in player["model_config"]
    assert player["model_config"]["model_name"] == "lora_x"


def test_build_experiment_pack_lists_ollama_tags() -> None:
    pack = build_experiment_pack(
        experiment={
            "name": "run",
            "player_ids": ["a", "b", "c"],
            "target_games": 5,
            "game_type": "doudizhu",
        },
        protocol={"collect_mode": "benchmark", "deal_seeds": [1, 2], "players": []},
        players=[
            {
                "id": "a",
                "name": "A",
                "notes": "",
                "model_config": {"provider": "ollama", "model_name": "qwen2.5:7b"},
            },
            {
                "id": "b",
                "name": "B",
                "notes": "",
                "model_config": {"provider": "deepseek", "model_name": "deepseek-v4-flash"},
            },
            {
                "id": "c",
                "name": "C",
                "notes": "",
                "model_config": {"provider": "ollama", "model_name": "qwen2.5:7b"},
            },
        ],
        exported_at="2026-09-03T00:00:00+00:00",
    )
    assert pack["kind"] == KIND_EXPERIMENT_PACK
    assert pack["requirements"]["providers"] == ["ollama", "deepseek"]
    assert pack["requirements"]["ollama_tags"] == ["qwen2.5:7b"]
    assert pack["deal_seeds"] == [1, 2]


def test_parse_experiment_object_without_kind() -> None:
    parsed = parse_pack(
        {
            "experiment": {
                "id": "exp-1",
                "name": "对照实验",
                "player_ids": ["a"],
                "game_type": "doudizhu",
                "target_games": 3,
            },
            "protocol": {
                "collect_mode": "free",
                "deal_seeds": [9],
                "players": [
                    {
                        "id": "a",
                        "name": "A",
                        "notes": "",
                        "model_config": {"provider": "openai", "model_name": "gpt-4o-mini"},
                    }
                ],
            },
            "summary": {"finished_games": 3},
        }
    )
    assert parsed["kind"] == KIND_EXPERIMENT_PACK
    assert parsed["players"][0]["id"] == "a"
    assert parsed["deal_seeds"] == [9]
    assert "summary" not in parsed


def test_parse_player_pack() -> None:
    parsed = parse_pack(
        {
            "kind": KIND_PLAYER_PACK,
            "players": [{"id": "x", "name": "X", "model_config": {"provider": "openai"}}],
        }
    )
    assert parsed["kind"] == KIND_PLAYER_PACK
    assert parsed["players"][0]["id"] == "x"
