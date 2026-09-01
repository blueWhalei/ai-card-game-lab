"""Tests for datasets/from-decisions ChatML registration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.decision_service import DecisionService


@pytest.mark.asyncio
async def test_from_decisions_empty_returns_400(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/datasets/from-decisions",
        json={"name": "empty-ds", "game_type": "doudizhu", "train_usable_only": True},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "NO_EXPORTABLE_DATA"


@pytest.mark.asyncio
async def test_from_decisions_creates_chatml_dataset(
    client: AsyncClient,
    test_settings: object,
) -> None:
    settings = test_settings  # typed as Settings in conftest
    sqlite_path = settings.sqlite_path  # type: ignore[attr-defined]
    data_dir = settings.data_dir  # type: ignore[attr-defined]

    decisions = DecisionService(sqlite_path=str(sqlite_path), data_dir=str(data_dir))
    await decisions.create_decision_point(
        game_id="game_from_dec",
        round_number=1,
        player_id="p1",
        hand_cards=[3, 4, 5],
        opponent_hands={"p2": 5, "p3": 5},
        last_action=None,
        game_phase="playing",
        legal_actions=[{"type": "SINGLE", "cards": [3]}, {"type": "PASS", "cards": []}],
        chosen_action={"type": "SINGLE", "cards": [3]},
        thinking="出单张",
    )

    res = await client.post(
        "/api/v1/datasets/from-decisions",
        json={
            "name": "decisions-chatml",
            "game_type": "doudizhu",
            "train_usable_only": True,
        },
    )
    assert res.status_code == 201, res.text
    ds = res.json()["data"]
    assert ds["sample_count"] >= 1
    assert ds["filters"]["format"] == "chatml"
    assert ds["filters"]["source"] == "decisions"

    file_path = Path(data_dir) / ds["file_path"]
    assert file_path.exists()
    first = json.loads(file_path.read_text(encoding="utf-8").splitlines()[0])
    assert "messages" in first


@pytest.mark.asyncio
async def test_from_decisions_eval_ratio_splits_by_game(
    client: AsyncClient,
    test_settings: object,
) -> None:
    settings = test_settings  # typed as Settings in conftest
    sqlite_path = settings.sqlite_path  # type: ignore[attr-defined]
    data_dir = settings.data_dir  # type: ignore[attr-defined]

    decisions = DecisionService(sqlite_path=str(sqlite_path), data_dir=str(data_dir))
    for game_id in ("game_eval_a", "game_eval_b", "game_eval_c", "game_eval_d"):
        await decisions.create_decision_point(
            game_id=game_id,
            round_number=1,
            player_id="p1",
            hand_cards=[3, 4, 5],
            opponent_hands={"p2": 5, "p3": 5},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "SINGLE", "cards": [3]}, {"type": "PASS", "cards": []}],
            chosen_action={"type": "SINGLE", "cards": [3]},
            thinking="test",
        )

    res = await client.post(
        "/api/v1/datasets/from-decisions",
        json={
            "name": "decisions-eval-split",
            "game_type": "doudizhu",
            "train_usable_only": True,
            "eval_ratio": 0.25,
        },
    )
    assert res.status_code == 201, res.text
    ds = res.json()["data"]
    assert ds["sample_count"] >= 1
    filters = ds["filters"]
    assert filters.get("eval_sample_count", 0) >= 1
    assert filters.get("eval_ratio") == 0.25
    assert filters.get("eval_file_path")

    train_path = Path(data_dir) / ds["file_path"]
    eval_path = Path(data_dir) / filters["eval_file_path"]
    assert train_path.exists()
    assert eval_path.exists()
    train_lines = train_path.read_text(encoding="utf-8").splitlines()
    eval_lines = eval_path.read_text(encoding="utf-8").splitlines()
    assert len(train_lines) + len(eval_lines) == 4
