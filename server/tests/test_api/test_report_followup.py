"""Follow-up designs retain an exact conclusion without treating it as new evidence."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.repositories.experiment_repo import ExperimentRepository
from tests.test_api.test_prompt_design import prepare
from tests.test_api.test_studies import create_run

BASE = "/api/v1/experiments"


async def source_report(client: AsyncClient) -> tuple[dict, dict, dict]:
    a, body = await prepare(client)
    b = (await client.post(f"{BASE}/{a['id']}/prompt-variant", json=body)).json()["data"]
    comparison = (
        await client.post(
            f"{BASE}/comparisons",
            json={"experiment_ids": [a["id"], b["id"]], "title": "Source comparison"},
        )
    ).json()["data"]
    saved = await client.post(
        f"{BASE}/comparisons/{comparison['id']}/conclusions",
        json={
            "expected_revision": 0,
            "observations": "No games collected",
            "interpretation": "No performance claim",
            "limitations": "Design only",
            "evidence": [],
        },
    )
    assert saved.status_code == 201, saved.text
    return a, body, saved.json()["data"]["record"]


async def test_followup_keeps_exact_revision_and_holdout_provenance(client: AsyncClient) -> None:
    a, body, record = await source_report(client)
    await client.post(
        f"{BASE}/comparisons/{record['comparison_id']}/conclusions",
        json={
            "expected_revision": 1,
            "observations": "Later revision",
            "interpretation": "",
            "limitations": "Still no games",
            "evidence": [],
        },
    )
    # Working notes/name changes do not alter frozen experimental conditions.
    await client.patch(f"{BASE}/{a['id']}", json={"name": "Renamed", "hypothesis": "Later note"})
    response = await client.get(
        f"{BASE}/{a['id']}/prompt-design", params={"source_revision_id": record["id"]}
    )
    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    assert preview["issues"] == []
    assert preview["source_conclusion"]["revision"] == 1
    assert preview["source_conclusion"]["observations"] == "No games collected"
    assert "evidence" not in preview["source_conclusion"]
    body.update(source_revision_id=record["id"], hypothesis="A new exploratory hypothesis")
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock) as start:
        response = await client.post(f"{BASE}/{a['id']}/prompt-variant", json=body)
        assert response.status_code == 201, response.text
        followup = response.json()["data"]
        assert followup["games"] == []
        assert followup["protocol"]["design"]["source_revision_id"] == record["id"]
        assert followup["protocol"]["design"]["hypothesis"] == body["hypothesis"]
        assert (
            followup["protocol"]["dataset"]["deal_seeds"] == a["protocol"]["dataset"]["deal_seeds"]
        )
        holdout = await client.put(f"{BASE}/{followup['id']}/holdout")
        assert holdout.status_code == 200, holdout.text
        reserved = (await client.get(f"{BASE}/{holdout.json()['data']['variant_id']}")).json()[
            "data"
        ]
        assert reserved["protocol"]["design"]["source_revision_id"] == record["id"]
        assert not set(reserved["protocol"]["dataset"]["deal_seeds"]) & set(
            a["protocol"]["dataset"]["deal_seeds"]
        )
        start.assert_not_awaited()
    original = (await client.get(f"{BASE}/conclusions/{record['id']}/export")).json()["data"]
    assert original["record"] == record
    # A new design started without a conclusion does not inherit a prior origin.
    old_prompt = a["protocol"]["solver"]["prompts"][body["template_key"]]
    await client.post(
        "/api/v1/prompts",
        json={
            "template_key": body["template_key"],
            "version": "test-c",
            "content": old_prompt["content"] + "\nA separate new change.",
        },
    )
    preview = (await client.get(f"{BASE}/{followup['id']}/prompt-design")).json()["data"]
    option = next(item for item in preview["options"] if item["version"] == "test-c")
    body.pop("source_revision_id")
    body.update(
        baseline_fingerprint=preview["fingerprint"],
        version=option["version"],
        content_hash=option["content_hash"],
    )
    ordinary = await client.post(f"{BASE}/{followup['id']}/prompt-variant", json=body)
    assert ordinary.status_code == 201, ordinary.text
    assert "source_revision_id" not in ordinary.json()["data"]["protocol"]["design"]


@pytest.mark.parametrize("change", ["conditions", "non_member", "missing_revision"])
async def test_source_mismatch_never_creates_run(
    client: AsyncClient, test_settings: Settings, change: str
) -> None:
    a, body, record = await source_report(client)
    if change == "conditions":
        protocol = deepcopy(a["protocol"])
        protocol["solver"]["players"][0]["model_config"]["temperature"] = 0.123
        async with aiosqlite.connect(test_settings.sqlite_path) as db:
            await ExperimentRepository(db).update_protocol(a["id"], protocol, updated_at="changed")
    elif change == "non_member":
        a = await create_run(client, collect_mode="benchmark", target_games=2)
        body["study_id"] = a["study_id"]
    source_id = "missing" if change == "missing_revision" else record["id"]
    response = await client.get(
        f"{BASE}/{a['id']}/prompt-design", params={"source_revision_id": source_id}
    )
    if change == "missing_revision":
        assert response.status_code == 404
    else:
        data = response.json()["data"]
        assert data["issues"] == [
            "source_conditions_changed" if change == "conditions" else "source_run_not_member"
        ]
        # Even a freshly acquired current fingerprint cannot bypass source matching.
        body["baseline_fingerprint"] = data["fingerprint"]
    before = len((await client.get(BASE)).json()["data"])
    body["source_revision_id"] = source_id
    rejected = await client.post(f"{BASE}/{a['id']}/prompt-variant", json=body)
    assert rejected.status_code == (404 if change == "missing_revision" else 409), rejected.text
    assert len((await client.get(BASE)).json()["data"]) == before


async def test_source_condition_change_after_preview_is_rechecked(
    client: AsyncClient, test_settings: Settings
) -> None:
    a, body, record = await source_report(client)
    response = await client.get(
        f"{BASE}/{a['id']}/prompt-design", params={"source_revision_id": record["id"]}
    )
    assert response.json()["data"]["issues"] == []
    protocol = deepcopy(a["protocol"])
    protocol["dataset"]["deal_seeds"][0] += 123
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await ExperimentRepository(db).update_protocol(a["id"], protocol, updated_at="later")
    body["source_revision_id"] = record["id"]
    rejected = await client.post(f"{BASE}/{a['id']}/prompt-variant", json=body)
    assert rejected.status_code == 409, rejected.text
    assert len((await client.get(BASE)).json()["data"]) == 2
