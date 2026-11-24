"""Current scenario navigation is descriptive, scoped and never evaluates decisions."""

from unittest.mock import AsyncMock, patch

import aiosqlite
from httpx import AsyncClient

from app.config import Settings
from app.repositories.decision_repo import DecisionRepository
from tests.test_api.test_studies import create_run


async def seed(client: AsyncClient, settings: Settings) -> str:
    run = await create_run(client)
    other = await create_run(client)
    async with aiosqlite.connect(settings.sqlite_path) as db:
        for gid, owner, status in (
            ("g1", run["id"], "finished"),
            ("g2", run["id"], "running"),
            ("empty", run["id"], "created"),
            ("foreign", other["id"], "finished"),
        ):
            await db.execute(
                "INSERT INTO games (id,game_type,status,player_ids,data_file,created_at,experiment_id) "
                "VALUES (?,'doudizhu',?,'[]','unused','2026-01-01',?)",
                (gid, status, owner),
            )
        for ident, game, turn, phase, size, action, ev in (
            ("bid", "g1", 0, "playing", 1, "BID", None),
            ("bomb", "g1", 1, "endgame", 1, "BOMB", 0.0),
            ("stored-end", "g1", 2, "endgame", 17, "PASS", None),
            ("own-end", "g1", 3, "playing", 8, "PASS", 0.25),
            ("play", "g1", 4, "playing", 9, "PASS", None),
            ("running", "g2", 0, "playing", 17, "PASS", None),
            ("outside", "foreign", 0, "playing", 1, "BOMB", 0.8),
        ):
            await DecisionRepository(db).create(
                ident,
                game,
                turn,
                "p",
                ["S3"] * size,
                None,
                None,
                phase,
                [],
                {"action_type": action, "cards": []},
                f"{action}||",
                None,
                None,
                "2026-01-01",
                train_usable=False,
                ev_loss=ev,
            )
    return run["id"]


async def test_counts_partition_records_not_games_and_keep_unscored(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    run = await seed(client, test_settings)
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock) as start:
        response = await client.get(f"/api/v1/experiments/{run}/scenarios")
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["scope"] == "current_records" and result["read_at"]
        assert result["endgame_max_hand"] == 8
        assert result["totals"] == {
            "decision_n": 6,
            "evaluated_n": 2,
            "game_n": 2,
            "unrecorded_game_n": 1,
        }
        assert {row["scenario"]: row["decision_n"] for row in result["groups"]} == {
            "bidding": 1,
            "playing": 2,
            "endgame": 2,
            "bomb": 1,
        }
        assert sum(row["game_n"] for row in result["groups"]) == 5
        assert [g["status"] for g in result["games"]["items"]] == ["finished", "running"]
        selected = (
            await client.get(
                f"/api/v1/experiments/{run}/scenarios?scenario=bomb&game_id=g1&decision_id=bomb"
            )
        ).json()["data"]
        assert selected["decisions"]["total"] == 1
        point = selected["decisions"]["items"][0]
        assert point["id"] == "bomb" and point["ev_loss"] == 0
        assert "prompt_messages" not in point and "thinking" not in point
        unscored = (
            await client.get(f"/api/v1/experiments/{run}/scenarios?scenario=bidding&game_id=g1")
        ).json()["data"]
        assert unscored["decisions"]["items"][0]["ev_loss"] is None
        start.assert_not_awaited()


async def test_empty_missing_unsupported_and_foreign_selections(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    empty = await create_run(client)
    result = (await client.get(f"/api/v1/experiments/{empty['id']}/scenarios")).json()["data"]
    assert result["totals"]["decision_n"] == 0
    assert len(result["groups"]) == 4 and result["games"]["items"] == []
    run = await seed(client, test_settings)
    url = f"/api/v1/experiments/{run}/scenarios"
    for query in (
        "?scenario=unknown",
        "?page=0",
        "?game_page=100001",
        "?game_id=foreign",
        "?game_id=empty",
        "?decision_id=bomb",
        "?scenario=bomb&game_id=g2",
        "?scenario=bomb&game_id=g1&decision_id=bid",
    ):
        assert (await client.get(url + query)).status_code == 422, query
    assert (await client.get("/api/v1/experiments/missing/scenarios")).status_code == 404
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM decision_points WHERE id='bomb'")
        await db.commit()
    assert (await client.get(url + "?scenario=bomb&game_id=g1&decision_id=bomb")).status_code == 422
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("UPDATE experiments SET game_type='other' WHERE id=?", (run,))
        await db.commit()
    assert (await client.get(url)).json()["code"] == "SCENARIO_UNSUPPORTED"


async def test_game_and_decision_pagination_are_bounded_and_stable(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    run = await seed(client, test_settings)
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        for n in range(21):
            gid = f"extra-{n:02}"
            await db.execute(
                "INSERT INTO games (id,game_type,status,player_ids,data_file,created_at,experiment_id) "
                "VALUES (?,'doudizhu','finished','[]','unused','2026-01-01',?)",
                (gid, run),
            )
            for target, ident, turn in ((gid, gid, 0), ("g1", f"later-{n:02}", n + 5)):
                await DecisionRepository(db).create(
                    ident,
                    target,
                    turn,
                    "p",
                    ["S3"] * 17,
                    None,
                    None,
                    "playing",
                    [],
                    {"action_type": "PASS", "cards": []},
                    "PASS||",
                    None,
                    None,
                    "2026-01-01",
                )
    url = f"/api/v1/experiments/{run}/scenarios"
    first = (await client.get(url)).json()["data"]
    second = (await client.get(url + "?game_page=2&game_id=g1&page=2&decision_id=later-20")).json()[
        "data"
    ]
    assert first["games"]["total"] == 23 and len(first["games"]["items"]) == 20
    assert len(second["games"]["items"]) == 3
    assert not {g["id"] for g in first["games"]["items"]} & {
        g["id"] for g in second["games"]["items"]
    }
    assert second["decisions"]["total"] == 26
    assert [p["round_number"] for p in second["decisions"]["items"]] == list(range(20, 26))
    assert (await client.get(url + "?game_id=g1&decision_id=later-20")).status_code == 422
