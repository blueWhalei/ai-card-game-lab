"""Frozen membership, identity and cutoff are enforced through the pair API."""

import json

import aiosqlite
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.decision_repo import DecisionRepository

BASE = "/api/v1/experiments/comparisons/cmp"


async def seed_pair(settings: Settings) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        rows = []
        for side in ("a", "b"):
            players = [f"{side}{n}" for n in range(3)]
            rows.append(
                {
                    "id": side,
                    "name": side,
                    "game_ids": [side, f"extra-{side}"],
                    "game_type": "doudizhu",
                    "player_ids": players,
                    "protocol": {"engine": {"engine_version": "1"}},
                }
            )
            for gid in (side, f"extra-{side}"):
                await db.execute(
                    "INSERT INTO games (id,game_type,status,player_ids,data_file,created_at,experiment_id,metadata,total_rounds) VALUES (?,'doudizhu','finished',?,'unused','2026-01-01',?,?,2)",
                    (gid, json.dumps(players), side, json.dumps({"deal_seed": 7})),
                )
                for turn in range(2):
                    await DecisionRepository(db).create(
                        f"{gid}-{turn}",
                        gid,
                        turn,
                        players[0],
                        ["S3"],
                        {players[1]: 17, players[2]: 17},
                        None,
                        "bidding",
                        [{"id": f"BID||{n}", "action_type": "BID", "cards": []} for n in (1, 3)],
                        {"action_type": "BID", "cards": []},
                        f"BID||{3 if side == 'b' and turn == 1 else 1}",
                        None,
                        None,
                        "2026-01-01",
                    )
        await ComparisonRepository(db).create(
            "cmp",
            "Pair",
            "2026-02-01",
            {
                "computed_at": "2026-02-01",
                "experiments": rows,
                "coverage": {"members": [{"seed": 7, "game_ids": {"a": "a", "b": "b"}}]},
            },
        )


async def test_pair_api_and_citations_use_only_frozen_members(
    client: AsyncClient, test_settings: Settings
) -> None:
    await seed_pair(test_settings)
    listed = await client.get(f"{BASE}/pairs")
    assert listed.status_code == 200
    assert listed.json()["data"]["items"] == [
        {"seed": 7, "left_game_id": "a", "right_game_id": "b", "left_n": 2, "right_n": 2}
    ]
    response = await client.get(f"{BASE}/pairs/7")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["first_divergence"] == 1
    assert [f["status"] for f in data["frames"]] == ["same", "divergence"]
    candidates = (await client.get(f"{BASE}/decisions")).json()["data"]["items"]
    assert {item["id"] for item in candidates} == {"a-0", "a-1", "b-0", "b-1"}
    rejected = await client.post(
        f"{BASE}/conclusions",
        json={
            "expected_revision": 0,
            "observations": "Observed",
            "limitations": "Small sample",
            "evidence": [{"decision_id": "extra-a-0"}],
        },
    )
    assert rejected.status_code == 422
    assert (await client.get(f"{BASE}/pairs/8")).status_code == 422
    assert (await client.get(f"{BASE.replace('cmp', 'missing')}/pairs")).status_code == 404
    assert (await client.get(f"{BASE.replace('cmp', 'missing')}/pairs/7")).status_code == 404


async def test_cutoff_and_duplicate_leave_explicit_holes(
    client: AsyncClient, test_settings: Settings
) -> None:
    await seed_pair(test_settings)
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("UPDATE decision_points SET created_at='2099-01-01' WHERE id='a-0'")
        await db.execute(
            "UPDATE decision_points SET game_id='b',round_number=1 WHERE id='extra-b-0'"
        )
        await db.commit()
    data = (await client.get(f"{BASE}/pairs/7")).json()["data"]
    assert data["first_divergence"] is None
    assert data["frames"][0]["left"] is None
    assert data["frames"][1]["right"] is None
    assert data["frames"][1]["reasons"] == ["duplicate"]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM games WHERE id='a'",
        "UPDATE games SET metadata='{}' WHERE id='a'",
        "UPDATE games SET player_ids='[]' WHERE id='a'",
        "UPDATE games SET status='running' WHERE id='a'",
        "UPDATE games SET total_rounds=0 WHERE id='a'",
        "UPDATE games SET experiment_id='other' WHERE id='a'",
        "UPDATE games SET created_at='2099-01-01' WHERE id='a'",
        "UPDATE decision_points SET round_number=99 WHERE id='a-0'",
    ],
)
async def test_changed_game_identity_is_rejected(
    client: AsyncClient, test_settings: Settings, sql: str
) -> None:
    await seed_pair(test_settings)
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute(sql)
        await db.commit()
    assert (await client.get(f"{BASE}/pairs/7")).status_code == 422


async def test_scenario_counts_use_frozen_members_and_cutoff_with_one_sided_matches(
    client: AsyncClient, test_settings: Settings
) -> None:
    await seed_pair(test_settings)
    frozen = (await client.get(BASE)).json()
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute(
            "UPDATE decision_points SET game_phase='endgame', chosen_action=?, action_id=? "
            "WHERE id='a-1'",
            (json.dumps({"action_type": "BOMB", "cards": ["S3"]}), "BOMB|S3|"),
        )
        await db.execute("UPDATE decision_points SET created_at='2099-01-01' WHERE id='b-1'")
        await db.commit()
    listed = (await client.get(f"{BASE}/pairs?scenario=bomb")).json()["data"]
    assert listed["cohort_n"] == 1
    assert listed["cutoff"] == "2026-02-01"
    assert listed["items"] == [
        {"seed": 7, "left_game_id": "a", "right_game_id": "b", "left_n": 1, "right_n": 0}
    ]
    groups = {g["scenario"]: g for g in listed["groups"]}
    assert groups[None]["left_n"] == 2
    assert groups[None]["right_n"] == 1
    assert groups["bomb"] == dict(
        scenario="bomb", left_n=1, right_n=0, left_game_n=1, right_game_n=0, pair_n=1
    )
    assert groups["bidding"]["left_n"] == 1
    assert groups["endgame"]["left_n"] == 0  # Bomb takes priority over stored endgame.
    response = (await client.get(f"{BASE}/pairs/7?scenario=bomb")).json()["data"]
    assert response["matching_turns"] == [1]
    assert len(response["frames"]) == 2  # Do not align separately filtered sequences.
    assert response["frames"][0]["status"] == "same"
    assert response["frames"][1]["left_scenario"] == "bomb"
    assert response["frames"][1]["right_scenario"] is None
    assert (await client.get(BASE)).json() == frozen  # Navigation does not rewrite snapshots.
    empty = (await client.get(f"{BASE}/pairs?scenario=playing")).json()["data"]
    assert empty["items"] == []
    assert (await client.get(f"{BASE}/pairs/7?scenario=playing")).status_code == 422
    assert (await client.get(f"{BASE}/pairs?scenario=invalid")).status_code == 422


async def test_scenario_filter_cannot_hide_prior_gaps_or_choose_duplicate_records(
    client: AsyncClient, test_settings: Settings
) -> None:
    await seed_pair(test_settings)
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM decision_points WHERE id='a-0'")
        await db.commit()
    data = (await client.get(f"{BASE}/pairs/7?scenario=bidding")).json()["data"]
    assert data["frames"][1]["status"] == "unverified"
    assert data["first_divergence"] is None
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("UPDATE decision_points SET game_id='a' WHERE id='extra-a-1'")
        await db.execute("UPDATE decision_points SET game_id='b' WHERE id='extra-b-1'")
        await db.execute("DELETE FROM decision_points WHERE id='b-0'")
        await db.commit()
    assert (await client.get(f"{BASE}/pairs?scenario=bidding")).json()["data"]["items"]
    assert (await client.get(f"{BASE}/pairs/7?scenario=bidding")).status_code == 422


async def test_scenario_list_rejects_changed_or_deleted_frozen_game(
    client: AsyncClient, test_settings: Settings
) -> None:
    await seed_pair(test_settings)
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("UPDATE games SET experiment_id='foreign' WHERE id='a'")
        await db.commit()
    assert (await client.get(f"{BASE}/pairs?scenario=bidding")).status_code == 422
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM games WHERE id='a'")
        await db.commit()
    assert (await client.get(f"{BASE}/pairs")).status_code == 422
