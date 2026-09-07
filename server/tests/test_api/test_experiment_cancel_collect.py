"""Cancel in-flight experiment collect."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

VALID_PLAYER_IDS = ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"]


async def test_cancel_collect_marks_active_games_cancelled(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/experiments",
        json={
            "name": "cancel-collect-run",
            "player_ids": VALID_PLAYER_IDS,
            "target_games": 2,
        },
    )
    assert create.status_code == 201, create.text
    exp_id = create.json()["data"]["id"]

    with (
        patch(
            "app.services.game_service.is_provider_configured",
            return_value=True,
        ),
        patch(
            "app.services.game_service.GameService.start_game",
            new_callable=AsyncMock,
            side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
        ),
        patch(
            "app.services.game_service.GameService.cancel_game",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        collect = await client.post(
            f"/api/v1/experiments/{exp_id}/collect",
            json={"count": 2},
        )
        assert collect.status_code == 201, collect.text

        cancel = await client.post(f"/api/v1/experiments/{exp_id}/cancel-collect")
        assert cancel.status_code == 200, cancel.text
        body = cancel.json()["data"]
        assert body["count"] == 2
        assert len(body["cancelled_game_ids"]) == 2

    detail = await client.get(f"/api/v1/experiments/{exp_id}")
    games = detail.json()["data"]["games"]
    assert all(g["status"] == "cancelled" for g in games)
    assert detail.json()["data"]["summary"]["status"] != "collecting"
