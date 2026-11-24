"""Continuous source replay and explicit, scope-checked evidence navigation."""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.comparison_repo import ComparisonRepository
from tests.test_api.test_decision_puzzles import seed_source

BASE = "/api/v1/experiments"


async def setup_board(settings: Settings) -> None:
    await seed_source(settings.sqlite_path)
    async with connect_sqlite(settings.sqlite_path) as db:
        await db.execute("UPDATE games SET total_rounds=5 WHERE id='source-game'")
        columns = [
            r[1] for r in await (await db.execute("PRAGMA table_info(experiments)")).fetchall()
        ]
        projection = ["'copy-run'" if c == "id" else c for c in columns]
        await db.execute(
            f"INSERT INTO experiments ({','.join(columns)}) SELECT {','.join(projection)} FROM experiments WHERE id='source-run'"
        )
        # Copy a continuous source under a second run identity; estimates are fixture data.
        columns = [r[1] for r in await (await db.execute("PRAGMA table_info(games)")).fetchall()]
        projection = [
            "'copy-game'" if c == "id" else "'copy-run'" if c == "experiment_id" else c
            for c in columns
        ]
        await db.execute(
            f"INSERT INTO games ({','.join(columns)}) SELECT {','.join(projection)} FROM games WHERE id='source-game'"
        )
        columns = [
            r[1] for r in await (await db.execute("PRAGMA table_info(decision_points)")).fetchall()
        ]
        projection = [
            "'copy-' || id" if c == "id" else "'copy-game'" if c == "game_id" else c
            for c in columns
        ]
        await db.execute(
            f"INSERT INTO decision_points ({','.join(columns)}) SELECT {','.join(projection)} FROM decision_points WHERE game_id='source-game'"
        )
        columns = [
            r[1]
            for r in await (await db.execute("PRAGMA table_info(rounds)")).fetchall()
            if r[1] != "id"
        ]
        projection = ["'copy-game'" if c == "game_id" else c for c in columns]
        await db.execute(
            f"INSERT INTO rounds ({','.join(columns)}) SELECT {','.join(projection)} FROM rounds WHERE game_id='source-game'"
        )
        rows = [
            {
                "id": owner,
                "name": owner,
                "game_type": "doudizhu",
                "player_ids": ["p1", "p2", "p3"],
                "game_ids": [gid],
                "protocol": {"engine": {"engine_version": "1"}},
            }
            for owner, gid in (("source-run", "source-game"), ("copy-run", "copy-game"))
        ]
        await ComparisonRepository(db).create(
            "board-cmp",
            "Board comparison",
            "2099-01-01",
            {
                "computed_at": "2099-01-01",
                "metric_version": "paired-cohort-v5",
                "experiments": rows,
                "coverage": {
                    "members": [
                        {
                            "seed": 42,
                            "game_ids": {"source-run": "source-game", "copy-run": "copy-game"},
                        }
                    ]
                },
            },
        )


async def test_board_and_citation_scope(client: AsyncClient, test_settings: Settings):
    await setup_board(test_settings)
    with patch(
        "app.core.eval.rollout.RolloutEvaluator.action_values",
        side_effect=AssertionError("No evaluation"),
    ):
        response = await client.get(f"{BASE}/comparisons/board-cmp/pairs/42")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["boards"]["left"]["status"] == "verified"
    assert len(data["boards"]["left"]["frames"]) == 5
    for frame in data["frames"]:
        board = data["boards"]["left"]["frames"][str(frame["turn"])]
        assert board["decision_id"] == frame["left"]["id"]
        assert board["snapshot"]["current_player_id"] == frame["left"]["player_id"]
        actor = next(
            p for p in board["snapshot"]["players"] if p["id"] == frame["left"]["player_id"]
        )
        assert sorted(actor["hand_cards"]) == sorted(frame["left"]["hand_cards"])
    targets = (await client.get(f"{BASE}/evidence/decisions/source-d2/comparisons")).json()["data"]
    assert [t["id"] for t in targets["items"]] == ["board-cmp"]
    assert targets["next_offset"] is None
    preview = await client.get(f"{BASE}/comparisons/board-cmp/decisions/source-d2")
    assert preview.json()["data"]["decision"]["id"] == "source-d2"
    assert (await client.get(f"{BASE}/comparisons/board-cmp/conclusions")).json()["data"] == []


@pytest.mark.parametrize("change", ["missing", "duplicate", "context", "late", "action", "engine"])
async def test_board_stops_at_first_unverified_step(
    client: AsyncClient, test_settings: Settings, change: str
):
    await setup_board(test_settings)
    async with connect_sqlite(test_settings.sqlite_path) as db:
        if change == "missing":
            await db.execute("DELETE FROM rounds WHERE game_id='source-game' AND round_num=2")
        elif change == "duplicate":
            await db.execute(
                "UPDATE rounds SET round_num=2 WHERE game_id='source-game' AND round_num=3"
            )
        elif change == "context":
            await db.execute(
                "UPDATE decision_points SET hand_cards='[\"S3\"]' WHERE id='source-d1'"
            )
        elif change == "late":
            await db.execute(
                "UPDATE rounds SET created_at='2100-01-01' WHERE game_id='source-game' AND round_num=2"
            )
        elif change == "action":
            await db.execute(
                "UPDATE rounds SET action_type='INVALID' WHERE game_id='source-game' AND round_num=2"
            )
        else:
            snapshot = await ComparisonRepository(db).get("board-cmp")
            for row in snapshot["result"]["experiments"]:
                row["protocol"]["engine"]["engine_version"] = "future"
            await db.execute(
                "UPDATE comparison_snapshots SET result=? WHERE id='board-cmp'",
                (json.dumps(snapshot["result"]),),
            )
        await db.commit()
    response = await client.get(f"{BASE}/comparisons/board-cmp/pairs/42")
    assert response.status_code == 200, response.text
    boards = response.json()["data"]["boards"]
    assert boards["left"]["status"] == (
        "unsupported_engine" if change == "engine" else "unverified"
    )
    assert list(boards["left"]["frames"]) == ([] if change == "engine" else ["0"])
    if change != "engine":
        assert len(boards["right"]["frames"]) == 5


async def test_targets_exclude_late_and_outside_decisions(
    client: AsyncClient, test_settings: Settings
):
    await setup_board(test_settings)
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("UPDATE decision_points SET created_at='2100-01-01' WHERE id='source-d2'")
        columns = [r[1] for r in await (await db.execute("PRAGMA table_info(games)")).fetchall()]
        projection = ["'outside'" if c == "id" else c for c in columns]
        await db.execute(
            f"INSERT INTO games ({','.join(columns)}) SELECT {','.join(projection)} FROM games WHERE id='source-game'"
        )
        await db.execute("UPDATE decision_points SET game_id='outside' WHERE id='source-d3'")
        await db.commit()
    for decision in ("source-d2", "source-d3"):
        assert (await client.get(f"{BASE}/evidence/decisions/{decision}/comparisons")).json()[
            "data"
        ]["items"] == []
        assert (
            await client.get(f"{BASE}/comparisons/board-cmp/decisions/{decision}")
        ).status_code == 422
    assert (await client.get(f"{BASE}/evidence/decisions/missing/comparisons")).status_code == 404
