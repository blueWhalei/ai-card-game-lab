"""Discovery is read-only and validates the same complete source set as publication."""

import copy
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.comparison_repo import ComparisonRepository
from app.services.research_puzzles import check_puzzle_scope
from app.utils.exceptions import AppError
from tests.test_api.test_research_batch_puzzles import batch as batch
from tests.test_api.test_research_puzzles import citation as citation


def target_url(draft):
    item = draft["puzzle_evidence"][0]
    return f"/api/v1/experiments/evidence/puzzle-results/{item['pack_id']}/{item['run_id']}/comparisons"


async def enable_snapshot(settings, comparison):
    async with connect_sqlite(settings.sqlite_path) as db:
        snapshot = await ComparisonRepository(db).get(comparison)
        snapshot["result"]["metric_version"] = "paired-cohort-v5"
        await db.execute(
            "UPDATE comparison_snapshots SET result=? WHERE id=?",
            (json.dumps(snapshot["result"]), comparison),
        )
        await db.commit()
        return snapshot


async def test_single_targets_read_only_paginated_and_scope_checked(
    client: AsyncClient, citation, test_settings: Settings
):
    _, _, draft, preview = citation
    snapshot = await enable_snapshot(test_settings, "cmp")
    async with connect_sqlite(test_settings.sqlite_path) as db:
        repo = ComparisonRepository(db)
        for index in range(22):
            await repo.create(
                f"copy-{index:02}", f"Copy {index}", f"2099-{index:02}", snapshot["result"]
            )
        wrong = copy.deepcopy(snapshot["result"])
        wrong["coverage"]["members"][0]["seed"] = 43
        await repo.create("wrong-seed", "Wrong seed", "2100", wrong)
        cutoff = copy.deepcopy(snapshot["result"])
        cutoff["computed_at"] = "2000"
        await repo.create("early", "Too early", "2101", cutoff)
    with (
        patch(
            "app.core.eval.rollout.RolloutEvaluator.action_values",
            side_effect=AssertionError("No simulation"),
        ),
        patch(
            "app.services.puzzle_service.PuzzleService._decide_action_id",
            side_effect=AssertionError("No execution"),
        ),
    ):
        first = (await client.get(target_url(draft))).json()["data"]
        assert first["report_hash"] == preview["result"]["report_hash"]
        assert len(first["items"]) == 19  # the invalid seed consumed one candidate slot
        assert first["next_offset"] == 20
        second = (await client.get(target_url(draft), params={"offset": 20})).json()["data"]
        assert second["next_offset"] is None
        ids = [item["id"] for item in first["items"] + second["items"]]
        assert len(ids) == len(set(ids)) == 23
        assert "wrong-seed" not in ids and "early" not in ids
        assert (await client.get("/api/v1/experiments/comparisons/cmp/conclusions")).json()[
            "data"
        ] == []
    assert (await client.get(target_url(draft), params={"offset": -1})).status_code == 422
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("UPDATE decision_points SET evaluator_params='{}' WHERE id='source-d2'")
        await db.commit()
    assert (await client.get(target_url(draft))).status_code == 422


async def test_batch_targets_reject_change_in_later_source(
    client: AsyncClient, batch, test_settings: Settings
):
    _, _, draft, _ = batch
    await enable_snapshot(test_settings, "batch-cmp")
    with patch(
        "app.core.eval.rollout.RolloutEvaluator.action_values",
        side_effect=AssertionError("No simulation"),
    ):
        response = await client.get(target_url(draft))
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["data"]["items"]] == ["batch-cmp"]
        async with connect_sqlite(test_settings.sqlite_path) as db:
            await db.execute("UPDATE decision_points SET hand_cards='[]' WHERE id='source-d2'")
            await db.commit()
        assert (await client.get(target_url(draft))).status_code == 422


@pytest.mark.parametrize("change", ["cutoff", "owner", "seed", "missing"])
def test_every_position_must_match_the_same_frozen_cohort(change):
    sources = [
        {
            "source": {
                "game_id": "g1",
                "experiment_id": "a",
                "deal_seed": 1,
                "decision_created_at": "2026-01-01",
            }
        },
        {
            "source": {
                "game_id": "g2",
                "experiment_id": "a",
                "deal_seed": 2,
                "decision_created_at": "2026-01-02",
            }
        },
    ]
    preview = {"result": {"report": {"pack_snapshot": {"puzzles": sources}}}}
    snapshot = {
        "result": {
            "computed_at": "2026-01-03",
            "experiments": [{"id": "a", "game_ids": ["g1", "g2"]}],
            "coverage": {
                "members": [
                    {"seed": 1, "game_ids": {"a": "g1"}},
                    {"seed": 2, "game_ids": {"a": "g2"}},
                ]
            },
        }
    }
    check_puzzle_scope(preview, snapshot)
    if change == "cutoff":
        snapshot["result"]["computed_at"] = "2026-01-01"
    else:
        key, value = {
            "owner": ("experiment_id", "b"),
            "seed": ("deal_seed", 3),
            "missing": ("game_id", "g3"),
        }[change]
        sources[1]["source"][key] = value
    with pytest.raises(AppError, match="全部来源"):
        check_puzzle_scope(preview, snapshot)
