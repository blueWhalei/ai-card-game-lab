"""Tests for experiment (run) API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

VALID_PLAYER_IDS = ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"]


async def _create_experiment(client: AsyncClient, **overrides: object) -> dict:
    payload = {
        "name": "Temp 对照实验",
        "notes": "第一刀测试",
        "game_type": "doudizhu",
        "player_ids": VALID_PLAYER_IDS,
        "target_games": 5,
        **overrides,
    }
    response = await client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_list_experiments_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/experiments")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == []


async def test_create_and_get_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client)
    assert created["name"] == "Temp 对照实验"
    assert created["player_ids"] == VALID_PLAYER_IDS
    assert created["target_games"] == 5
    assert created["summary"]["status"] == "pending_collect"
    assert created["summary"]["finished_games"] == 0
    assert created["summary"]["latest_game_id"] is None
    assert created["summary"]["player_stats"] == [
        {
            "player_id": pid,
            "wins": 0,
            "win_rate": 0.0,
            "win_rate_ci": [0.0, 0.0],
            "train_usable_decisions": 0,
            "avg_response_time_ms": 0.0,
            "trace_count": 0,
            "games_as_landlord": 0,
            "wins_as_landlord": 0,
            "landlord_win_rate": 0.0,
        }
        for pid in VALID_PLAYER_IDS
    ]

    response = await client.get(f"/api/v1/experiments/{created['id']}")
    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["id"] == created["id"]
    assert detail["games"] == []
    assert detail["summary"]["status"] == "pending_collect"

    listed = await client.get("/api/v1/experiments")
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


async def test_create_rejects_wrong_player_count(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/experiments",
        json={
            "name": "too-few",
            "player_ids": ["cfg_temp_09", "cfg_temp_06"],
            "target_games": 3,
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "EXPERIMENT_VALIDATION_FAILED"


async def test_create_rejects_duplicate_players(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/experiments",
        json={
            "name": "bad",
            "player_ids": ["cfg_temp_09", "cfg_temp_09", "cfg_temp_06"],
            "target_games": 3,
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "EXPERIMENT_VALIDATION_FAILED"


async def test_get_experiment_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/experiments/exp_missing")
    assert response.status_code == 404
    assert response.json()["code"] == "EXPERIMENT_NOT_FOUND"


async def test_collect_writes_experiment_id(client: AsyncClient) -> None:
    created = await _create_experiment(client, target_games=3)

    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
    ) as mock_start:
        mock_start.side_effect = lambda game_id, db=None: {
            "id": game_id,
            "status": "running",
        }
        response = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 2},
        )

    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["count"] == 2
    assert len(body["game_ids"]) == 2

    detail = await client.get(f"/api/v1/experiments/{created['id']}")
    games = detail.json()["data"]["games"]
    assert len(games) == 2
    for g in games:
        assert g.get("experiment_id") == created["id"]

    summary = detail.json()["data"]["summary"]
    assert summary["total_games"] == 2
    assert summary["status"] == "collecting"
    assert summary["latest_game_id"] in body["game_ids"]
    assert games[0]["progress"] == {"phase": "queued", "round": None, "player_id": None}


async def test_experiment_game_progress_from_latest_decision(client: AsyncClient) -> None:
    created = await _create_experiment(client, target_games=1)
    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
        side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
    ):
        collect = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 1},
        )
    game_id = collect.json()["data"]["game_ids"][0]

    from app.database import open_db_connection
    from app.dependencies import get_settings
    from app.repositories.decision_repo import DecisionRepository

    settings = get_settings()
    conn = await open_db_connection(settings.sqlite_path)
    try:
        repo = DecisionRepository(conn)
        await repo.create(
            decision_id="dp_progress_1",
            game_id=game_id,
            round_number=12,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[3],
            opponent_hands={"p2": 8},
            last_action=None,
            game_phase="endgame",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="think",
            train_usable=True,
            created_at="2026-09-04T00:00:00+00:00",
        )
    finally:
        await conn.close()

    detail = await client.get(f"/api/v1/experiments/{created['id']}")
    game = detail.json()["data"]["games"][0]
    assert game["progress"] == {
        "phase": "endgame",
        "round": 12,
        "player_id": VALID_PLAYER_IDS[0],
    }


async def test_decision_filter_by_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client)

    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
        side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
    ):
        collect = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 1},
        )
    game_id = collect.json()["data"]["game_ids"][0]

    # Insert a decision point tied to the experiment game via raw API path / DB
    from app.dependencies import get_settings
    from app.repositories.decision_repo import DecisionRepository
    from app.database import open_db_connection

    settings = get_settings()
    conn = await open_db_connection(settings.sqlite_path)
    try:
        repo = DecisionRepository(conn)
        await repo.create(
            decision_id="dp_exp_1",
            game_id=game_id,
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[3],
            opponent_hands={"p2": 17},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="think",
            train_usable=True,
            created_at="2026-08-30T00:00:00+00:00",
        )
        # Scatter game + decision without experiment
        await conn.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file, created_at)
            VALUES ('game_scatter', 'doudizhu', 'finished', '[]', 'x.jsonl', '2026-08-30T00:00:00+00:00')
            """
        )
        await repo.create(
            decision_id="dp_scatter",
            game_id="game_scatter",
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[4],
            opponent_hands={"p2": 16},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="other",
            train_usable=True,
            created_at="2026-08-30T00:00:01+00:00",
        )
        await conn.commit()
    finally:
        await conn.close()

    filtered = await client.get(
        "/api/v1/decision-points",
        params={"experiment_id": created["id"]},
    )
    assert filtered.status_code == 200
    payload = filtered.json()["data"]
    items = payload["items"]
    assert payload["total"] == 1
    assert len(items) == 1
    assert items[0]["id"] == "dp_exp_1"

    all_items = await client.get("/api/v1/decision-points")
    assert all_items.json()["data"]["total"] >= 2
    assert len(all_items.json()["data"]["items"]) >= 2


async def test_decision_stats_filters_by_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client)

    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
        side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
    ):
        collect = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 1},
        )
    game_id = collect.json()["data"]["game_ids"][0]

    from app.database import open_db_connection
    from app.dependencies import get_settings
    from app.repositories.decision_repo import DecisionRepository

    settings = get_settings()
    conn = await open_db_connection(settings.sqlite_path)
    try:
        repo = DecisionRepository(conn)
        await repo.create(
            decision_id="dp_stats_exp",
            game_id=game_id,
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[3],
            opponent_hands={"p2": 17},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="think",
            train_usable=True,
            created_at="2026-08-30T00:00:00+00:00",
        )
        await conn.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file, created_at)
            VALUES ('game_stats_scatter', 'doudizhu', 'finished', '[]', 'x.jsonl',
                    '2026-08-30T00:00:00+00:00')
            """
        )
        await repo.create(
            decision_id="dp_stats_scatter",
            game_id="game_stats_scatter",
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[4],
            opponent_hands={"p2": 16},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="other",
            train_usable=True,
            created_at="2026-08-30T00:00:01+00:00",
        )
        await conn.commit()
    finally:
        await conn.close()

    scoped = await client.get(
        "/api/v1/decision-points/stats",
        params={"experiment_id": created["id"]},
    )
    assert scoped.status_code == 200
    assert scoped.json()["data"]["total"] == 1

    global_stats = await client.get("/api/v1/decision-points/stats")
    assert global_stats.status_code == 200
    assert global_stats.json()["data"]["total"] >= 2


async def test_from_decisions_filters_by_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client)

    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
        side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
    ):
        collect = await client.post(
            f"/api/v1/experiments/{created['id']}/collect",
            json={"count": 1},
        )
    game_id = collect.json()["data"]["game_ids"][0]

    from app.database import open_db_connection
    from app.dependencies import get_settings
    from app.repositories.decision_repo import DecisionRepository

    settings = get_settings()
    conn = await open_db_connection(settings.sqlite_path)
    try:
        repo = DecisionRepository(conn)
        await repo.create(
            decision_id="dp_exp_reg",
            game_id=game_id,
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[3],
            opponent_hands={"p2": 17},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="think",
            train_usable=True,
            created_at="2026-08-30T00:00:00+00:00",
        )
        await conn.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file, created_at)
            VALUES ('game_scatter2', 'doudizhu', 'finished', '[]', 'y.jsonl', '2026-08-30T00:00:00+00:00')
            """
        )
        await repo.create(
            decision_id="dp_scatter_reg",
            game_id="game_scatter2",
            round_number=1,
            player_id=VALID_PLAYER_IDS[0],
            hand_cards=[4],
            opponent_hands={"p2": 16},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"type": "pass"}],
            chosen_action={"type": "pass"},
            thinking="other",
            train_usable=True,
            created_at="2026-08-30T00:00:01+00:00",
        )
        await conn.commit()
    finally:
        await conn.close()

    response = await client.post(
        "/api/v1/datasets/from-decisions",
        json={
            "name": "exp-only-ds",
            "game_type": "doudizhu",
            "experiment_id": created["id"],
            "train_usable_only": True,
            "include_thinking": False,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["sample_count"] == 1
    assert body["filters"]["experiment_id"] == created["id"]


async def test_patch_experiment_notebook_fields(client: AsyncClient) -> None:
    created = await _create_experiment(client)
    response = await client.patch(
        f"/api/v1/experiments/{created['id']}",
        json={
            "hypothesis": "LoRA 提升地主胜率",
            "conclusion": "待验证",
            "tags": ["lora", "baseline"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["hypothesis"] == "LoRA 提升地主胜率"
    assert body["conclusion"] == "待验证"
    assert body["tags"] == ["lora", "baseline"]


async def test_get_experiment_includes_timeline_and_next_step(client: AsyncClient) -> None:
    created = await _create_experiment(client)
    response = await client.get(f"/api/v1/experiments/{created['id']}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["timeline"], list)
    assert data["timeline"][0]["id"] == "created"
    assert data["next_step"]["id"] == "collect"
    assert "validation" in data
    assert data["validation"]["control_experiment_ids"] == []
    assert data.get("delta") is None


async def test_clone_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client, name="源实验")
    response = await client.post(
        f"/api/v1/experiments/{created['id']}/clone",
        json={"name": "克隆实验", "copy_deal_seeds": True},
    )
    assert response.status_code == 201, response.text
    cloned = response.json()["data"]
    assert cloned["id"] != created["id"]
    assert cloned["name"] == "克隆实验"
    assert cloned["player_ids"] == created["player_ids"]


async def test_create_benchmark_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(
        client,
        name="基准测验",
        collect_mode="benchmark",
        target_games=5,
    )
    protocol = created.get("protocol") or {}
    assert protocol.get("collect_mode") == "benchmark"
    assert len(protocol.get("deal_seeds") or []) == 5


async def test_compare_experiments_returns_wilson_ci(client: AsyncClient) -> None:
    left = await _create_experiment(client, name="基线 A")
    right = await _create_experiment(client, name="对照 B")
    response = await client.get(
        "/api/v1/experiments/compare",
        params={"ids": f"{left['id']},{right['id']}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert len(payload["experiments"]) == 2
    for item in payload["experiments"]:
        assert "train_usable_rate" in item
        assert "parser_success_rate" in item
        assert len(item["player_stats"]) == 3
        for stat in item["player_stats"]:
            low, high = stat["win_rate_ci"]
            assert 0.0 <= low <= high <= 1.0


async def test_compare_rejects_single_id(client: AsyncClient) -> None:
    created = await _create_experiment(client)
    response = await client.get(
        "/api/v1/experiments/compare",
        params={"ids": created["id"]},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "EXPERIMENT_VALIDATION_FAILED"
