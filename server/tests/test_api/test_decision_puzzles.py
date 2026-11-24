"""Source-bound position diagnostics, with real replay and synthetic stored estimates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.eval.rollout import EvaluatorParams
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.services.decision_snapshot import (
    game_phase_from_observation,
    hand_cards_from_observation,
    last_action_from_observation,
    opponent_hands_from_observation,
)


async def seed_source(db_path: str) -> None:
    now = datetime.now(UTC).isoformat()
    players = ["p1", "p2", "p3"]
    engine = DoudizhuEngine()
    state = engine.initialize(players, seed=42)
    async with connect_sqlite(db_path) as db:
        await ExperimentRepository(db).create(
            experiment_id="source-run",
            name="Synthetic position source",
            notes="Fixture only",
            game_type="doudizhu",
            player_ids=players,
            target_games=1,
            created_at=now,
            updated_at=now,
        )
        await GameRepository(db).create(
            game_id="source-game",
            game_type="doudizhu",
            player_ids=players,
            data_file="fixture.jsonl",
            created_at=now,
            status="finished",
            experiment_id="source-run",
            metadata={"deal_seed": 42},
        )
        for turn in range(5):
            actor = engine.get_current_player(state)
            obs = engine.observe(state, actor)
            legal = engine.legal_actions(state, actor)
            chosen = legal[-1] if turn == 0 else legal[0]
            values = {entry.id: (0.7 if i == 0 else 0.2) for i, entry in enumerate(legal[:2])}
            await DecisionRepository(db).create(
                decision_id=f"source-d{turn}",
                game_id="source-game",
                round_number=turn,
                player_id=actor,
                hand_cards=hand_cards_from_observation(obs),
                opponent_hands=opponent_hands_from_observation(obs),
                last_action=last_action_from_observation(obs),
                game_phase=game_phase_from_observation(obs),
                legal_actions=[
                    {
                        "id": entry.id,
                        "label": entry.label,
                        "action_type": entry.action.action_type,
                        "cards": entry.action.cards or [],
                    }
                    for entry in legal
                ],
                chosen_action={
                    "action_type": chosen.action.action_type,
                    "cards": chosen.action.cards or [],
                },
                action_id=chosen.id,
                prompt_messages=None,
                thinking=None,
                created_at=now,
                ev_loss=0,
                evaluator_params={
                    **EvaluatorParams().to_dict(),
                    "action_values": values,
                    "best_action_id": legal[0].id,
                    "candidates_evaluated": len(values),
                    "legal_action_count": len(legal),
                    "truncated": len(values) < len(legal),
                    "opponent_kind_effective": "heuristic",
                },
            )
            await RoundRepository(db).create(
                {
                    "game_id": "source-game",
                    "round_num": turn + 1,
                    "player_id": actor,
                    "action_type": chosen.action.action_type,
                    "cards": chosen.action.cards,
                    "created_at": now,
                }
            )
            state = engine.apply_action(state, chosen.action)


@pytest.fixture
async def source(client: AsyncClient, tmp_path: Path) -> str:
    db_path = str(tmp_path / "test.db")
    await seed_source(db_path)
    return db_path


async def test_inspect_freeze_and_offline_run(client: AsyncClient, source: str) -> None:
    with patch(
        "app.core.eval.rollout.RolloutEvaluator.action_values",
        side_effect=AssertionError("No re-evaluation"),
    ):
        inspected = await client.get("/api/v1/puzzles/decisions/source-d2")
        assert inspected.status_code == 200, inspected.text
        info = inspected.json()["data"]
        assert info["round_num"] == 3
        assert info["experiment_id"] == "source-run"
        assert (await client.get("/api/v1/puzzles/packs")).json()["data"] == []
        saved = await client.post(
            "/api/v1/puzzles/from-decision",
            json={
                "decision_id": "source-d2",
                "question": "  Does action order change the choice?  ",
                "expected_source_hash": info["source_hash"],
            },
        )
        assert saved.status_code == 200, saved.text
        manifest = saved.json()["data"]
        assert manifest["puzzle_count"] == 1
        assert manifest["extract"]["question"] == "Does action order change the choice?"
        pack_id = manifest["pack_id"]
        detail = (await client.get(f"/api/v1/puzzles/packs/{pack_id}")).json()["data"]
        puzzle = detail["preview"][0]
        assert puzzle["source"]["decision_point_id"] == "source-d2"
        assert puzzle["action_values"] == info["evaluator_params"]["action_values"]
        async with connect_sqlite(source) as db:
            await db.execute("DELETE FROM decision_points")
            await db.commit()
        assert (await client.get("/api/v1/puzzles/decisions/source-d2")).status_code == 404
        assert (await client.get(f"/api/v1/puzzles/packs/{pack_id}")).json()["data"] == detail
        for action in ("run", "probe"):
            result = await client.post(
                f"/api/v1/puzzles/packs/{pack_id}/{action}", json={"baseline_kind": "first"}
            )
            assert result.status_code == 200
            assert result.json()["data"]["summary"]["n"] == 1


async def test_source_changed_and_blank_question(client: AsyncClient, source: str) -> None:
    info = (await client.get("/api/v1/puzzles/decisions/source-d0")).json()["data"]
    body = {
        "decision_id": "source-d0",
        "question": "Question",
        "expected_source_hash": info["source_hash"],
    }
    async with connect_sqlite(source) as db:
        await db.execute(
            "UPDATE decision_points SET created_at = '2020-01-01' WHERE id = 'source-d0'"
        )
        await db.commit()
    assert (await client.post("/api/v1/puzzles/from-decision", json=body)).status_code == 409
    assert (
        await client.post("/api/v1/puzzles/from-decision", json={**body, "question": "  "})
    ).status_code == 422
    assert (await client.get("/api/v1/puzzles/packs")).json()["data"] == []


async def test_forced_action_is_not_a_choice_test(client: AsyncClient, source: str) -> None:
    response = await client.get("/api/v1/puzzles/decisions/source-d4")
    assert response.status_code == 422
    assert response.json()["code"] == "PUZZLE_SOURCE_INVALID"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM decision_points WHERE id = 'source-d1'",
        "DELETE FROM rounds WHERE round_num = 2",
        "UPDATE decision_points SET round_number = 1 WHERE id = 'source-d2'",
        "UPDATE rounds SET round_num = 2 WHERE round_num = 3",
        "UPDATE decision_points SET hand_cards = '[\"invalid\"]' WHERE id = 'source-d1'",
        "UPDATE decision_points SET parse_fallback = 1 WHERE id = 'source-d1'",
        "UPDATE decision_points SET evaluator_params = NULL WHERE id = 'source-d2'",
        "UPDATE games SET status = 'playing'",
        "UPDATE games SET metadata = '{\"deal_seed\":42.5}'",
        "UPDATE rounds SET action_type = 'PASS' WHERE round_num = 1",
    ],
)
async def test_invalid_source_never_saves(client: AsyncClient, source: str, sql: str) -> None:
    async with connect_sqlite(source) as db:
        await db.execute(sql)
        await db.commit()
    inspected = await client.get("/api/v1/puzzles/decisions/source-d2")
    assert inspected.status_code == 422, inspected.text
    saved = await client.post(
        "/api/v1/puzzles/from-decision",
        json={
            "decision_id": "source-d2",
            "question": "Question",
            "expected_source_hash": "0" * 64,
        },
    )
    assert saved.status_code == 422
    assert (await client.get("/api/v1/puzzles/packs")).json()["data"] == []


@pytest.mark.parametrize(
    "change", ["nonfinite", "foreign_action", "wrong_best", "counts", "params"]
)
async def test_invalid_estimates(client: AsyncClient, source: str, change: str) -> None:
    async with connect_sqlite(source) as db:
        point = await DecisionRepository(db).get_by_id("source-d0")
        params = point["evaluator_params"]
        if change == "nonfinite":
            params["action_values"][params["best_action_id"]] = float("inf")
        elif change == "foreign_action":
            params["action_values"] = {"foreign": 0.8}
        elif change == "wrong_best":
            params["best_action_id"] = "foreign"
        elif change == "counts":
            params["legal_action_count"] = 999
        else:
            params["determinizations"] = -1
        await db.execute(
            "UPDATE decision_points SET evaluator_params = ? WHERE id = 'source-d0'",
            (json.dumps(params),),
        )
        await db.commit()
    result = await client.get("/api/v1/puzzles/decisions/source-d0")
    assert result.status_code == 422, result.text
