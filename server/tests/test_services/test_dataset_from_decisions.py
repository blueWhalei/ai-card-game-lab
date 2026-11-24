"""Tests for datasets/from-decisions ChatML registration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.game_repo import GameRepository
from app.services.decision_service import DecisionService

_PROMPT = [{"role": "user", "content": "pick an action"}]
_LEGAL = [
    {"id": "SINGLE|C3|", "type": "SINGLE", "cards": ["C3"]},
    {"id": "PASS||", "type": "PASS", "cards": []},
]
_CHOSEN = {"id": "SINGLE|C3|", "type": "SINGLE", "cards": ["C3"]}


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
        legal_actions=_LEGAL,
        chosen_action=_CHOSEN,
        action_id="SINGLE|C3|",
        prompt_messages=_PROMPT,
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
            legal_actions=_LEGAL,
            chosen_action=_CHOSEN,
            action_id="SINGLE|C3|",
            prompt_messages=_PROMPT,
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


async def test_dataset_split_keeps_repeated_deals_in_one_group(
    client: AsyncClient, test_settings: Settings
) -> None:
    decisions = DecisionService(test_settings.sqlite_path, test_settings.data_dir)
    source = {"a1": 1, "b1": 1, "a2": 2, "b2": 2}
    async with connect_sqlite(test_settings.sqlite_path) as db:
        for gid, seed in source.items():
            await GameRepository(db).create(
                game_id=gid,
                game_type="doudizhu",
                player_ids=["p1", "p2", "p3"],
                data_file="unused.jsonl",
                created_at=datetime.now(tz=UTC).isoformat(),
                metadata={"deal_seed": seed},
            )
    for gid in source:
        await decisions.create_decision_point(
            game_id=gid,
            round_number=0,
            player_id="p1",
            hand_cards=["C3"],
            opponent_hands={"p2": 1, "p3": 1},
            last_action=None,
            game_phase="playing",
            legal_actions=_LEGAL,
            chosen_action=_CHOSEN,
            action_id="SINGLE|C3|",
            prompt_messages=[{"role": "user", "content": gid}],
        )
    response = await client.post(
        "/api/v1/datasets/from-decisions",
        json={
            "name": "grouped",
            "game_type": "doudizhu",
            "eval_ratio": 0.5,
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()["data"]
    meta = result["filters"]
    assert meta["group_count"] == 2 and meta["eval_group_count"] == 1
    assert set(meta["eval_game_ids"]) in ({"a1", "b1"}, {"a2", "b2"})
    root = Path(test_settings.data_dir)

    def seeds(path: Path) -> set[int]:
        return {
            source[json.loads(line)["messages"][0]["content"]]
            for line in path.read_text(encoding="utf-8").splitlines()
        }

    assert seeds(root / result["file_path"]).isdisjoint(seeds(root / meta["eval_file_path"]))
