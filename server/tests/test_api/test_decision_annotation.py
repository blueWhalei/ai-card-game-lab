"""Decision point annotation PATCH / filter."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository


@pytest.mark.asyncio
async def test_annotation_patch_and_filter(
    client: AsyncClient, test_settings: Settings
) -> None:
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO games (id, game_type, status, player_ids, data_file, created_at) "
            "VALUES ('g_ann', 'doudizhu', 'finished', '[]', '', '2026-01-01')"
        )
        await db.commit()
        repo = DecisionRepository(db)
        await repo.create(
            decision_id="dp_ann",
            game_id="g_ann",
            round_number=1,
            player_id="p1",
            hand_cards=["C3"],
            opponent_hands={"p2": 17},
            last_action=None,
            game_phase="playing",
            legal_actions=[{"id": "PASS||", "label": "pass", "action_type": "PASS", "cards": []}],
            chosen_action={"action_type": "PASS", "cards": []},
            action_id="PASS||",
            prompt_messages=[{"role": "user", "content": "hi"}],
            thinking=None,
            created_at="2026-01-01T00:00:00Z",
        )

    patched = await client.patch(
        "/api/v1/decision-points/dp_ann",
        json={"annotation": "good"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["annotation"] == "good"

    listed = await client.get(
        "/api/v1/decision-points",
        params={"annotation": "good"},
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert any(i["id"] == "dp_ann" for i in items)

    empty = await client.get(
        "/api/v1/decision-points",
        params={"annotation": "bad"},
    )
    assert empty.json()["data"]["total"] == 0

    cleared = await client.patch(
        "/api/v1/decision-points/dp_ann",
        json={"annotation": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["annotation"] is None
