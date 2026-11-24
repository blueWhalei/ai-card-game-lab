"""First run uses the normal frozen protocol and checks only selected model seats."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.utils import providers
from app.utils.providers import fetch_model_catalog, is_provider_configured


async def test_offline_creates_reusable_profiles_with_the_run(client: AsyncClient) -> None:
    url = "/api/v1/experiments/offline"
    before = (await client.get("/api/v1/experiment-configs")).json()["data"]
    failed = await client.post(url, json={"name": "trial", "study_id": "missing"})
    assert failed.status_code == 404
    assert (await client.get("/api/v1/experiment-configs")).json()["data"] == before

    first, second = await asyncio.gather(
        *(client.post(url, json={"name": name}) for name in ("first", "second"))
    )
    assert first.status_code == second.status_code == 201
    run = first.json()["data"]
    assert run["player_ids"] == second.json()["data"]["player_ids"]
    assert len((await client.get("/api/v1/experiment-configs")).json()["data"]) == len(before) + 3
    assert run["target_games"] == 1
    assert run["summary"]["latest_game_id"] is None
    assert len(run["protocol"]["dataset"]["deal_seeds"]) == 1
    assert [p["policy_kind"] for p in run["protocol"]["solver"]["players"]] == [
        "heuristic",
        "first",
        "random",
    ]
    scoped = await client.post(url, json={"name": "in study", "study_id": run["study_id"]})
    assert scoped.json()["data"]["study_id"] == run["study_id"]
    with patch("app.utils.providers.fetch_model_catalog") as network:
        ready = await client.get(
            "/api/v1/system/preflight", params={"experiment_id": run["id"], "scope": "collect"}
        )
        assert ready.json()["data"]["can_collect"] is True
        network.assert_not_called()


async def test_failed_insert_rolls_back_offline_profiles_and_cache(client: AsyncClient) -> None:
    before = (await client.get("/api/v1/experiment-configs")).json()["data"]
    with patch(
        "app.repositories.experiment_repo.ExperimentRepository.create",
        side_effect=RuntimeError("insert failed"),
    ):
        with pytest.raises(RuntimeError, match="insert failed"):
            await client.post("/api/v1/experiments/offline", json={"name": "failed trial"})
    assert (await client.get("/api/v1/experiment-configs")).json()["data"] == before
    from app.dependencies import get_experiment_config_service

    await get_experiment_config_service().initialize()
    assert (await client.get("/api/v1/experiment-configs")).json()["data"] == before


async def test_offline_collect_validates_the_frozen_lineup(client: AsyncClient) -> None:
    response = await client.post("/api/v1/experiments/offline", json={"name": "frozen seats"})
    run = response.json()["data"]
    changed = await client.put(
        f"/api/v1/experiment-configs/{run['player_ids'][0]}",
        json={
            "policy_kind": "llm",
            "model_config_data": {"provider": "unknown", "model_name": "unavailable"},
        },
    )
    assert changed.status_code == 200
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock):
        queued = await client.post(f"/api/v1/experiments/{run['id']}/collect", json={"count": 1})
    assert queued.status_code == 201, queued.text
    detail = (await client.get(f"/api/v1/experiments/{run['id']}")).json()["data"]
    assert detail["games"][0]["metadata"]["players"] == run["protocol"]["solver"]["players"]


async def test_seat_readiness_reads_catalog_only_on_request(client: AsyncClient) -> None:
    ids = ["cfg_temp_09", "cfg_temp_06"]
    endpoint = "/api/v1/experiment-configs/readiness"
    with patch(
        "app.utils.providers.fetch_model_catalog", return_value={"llama3.2:latest"}
    ) as catalog:
        local = await client.post(endpoint, json={"player_ids": ids})
        rows = local.json()["data"]["checks"]
        assert [row["player_id"] for row in rows] == ids
        assert [row["status"] for row in rows] == ["configured", "configured"]
        catalog.assert_not_called()
        probe = await client.post(endpoint, json={"player_ids": ids, "check_connection": True})
        assert [row["status"] for row in probe.json()["data"]["checks"]] == ["listed", "listed"]
        catalog.assert_called_once()
    assert (await client.post(endpoint, json={"player_ids": ["unknown"]})).status_code == 400


async def test_missing_key_and_wrong_ollama_tag_block_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(openai_api_key="test")
    cloud = {
        "id": "model",
        "policy_kind": "llm",
        "model_config": {"provider": "openai", "model_name": "chosen"},
    }
    local = {
        "id": "local",
        "policy_kind": "search",
        "model_config": {"provider": "ollama", "model_name": "chosen"},
    }
    baseline = {"id": "offline", "policy_kind": "first"}
    monkeypatch.setattr(providers, "is_provider_configured", is_provider_configured)
    with patch("app.utils.providers.fetch_model_catalog", return_value={"chosen:other"}) as catalog:
        checks = await providers.seat_model_checks(
            settings, [cloud, baseline, local], check_connection=True
        )
        assert [(c["status"], c["setting"]) for c in checks] == [
            ("missing_key", "OPENAI_API_KEY"),
            ("not_listed", ""),
        ]
        catalog.assert_called_once()
        assert providers.unconfigured_providers_from_players(
            settings, [cloud, baseline, local]
        ) == ["ollama", "openai"]


@pytest.mark.parametrize(
    ("http_status", "payload", "expected"),
    [
        (200, {"data": [{"id": "chosen"}]}, "listed"),
        (200, {"data": [{"id": "different"}]}, "not_listed"),
        (200, {"data": [{}]}, "catalog_unavailable"),
        (403, {}, "access_denied"),
        (404, {}, "catalog_unavailable"),
        (302, {}, "catalog_unavailable"),
    ],
)
async def test_cloud_catalog_outcomes(
    monkeypatch: pytest.MonkeyPatch, http_status: int, payload: dict, expected: str
) -> None:
    monkeypatch.setattr(providers, "fetch_model_catalog", fetch_model_catalog)
    settings = Settings(
        openai_api_key="dummy-catalog-key", openai_base_url="https://example.invalid/v1"
    )
    seat = {
        "id": "p",
        "policy_kind": "llm",
        "model_config": {"provider": "openai", "model_name": "chosen"},
    }
    request = httpx.Request("GET", "https://example.invalid/v1/models")
    with patch(
        "httpx.get", return_value=httpx.Response(http_status, json=payload, request=request)
    ) as get:
        checks = await providers.seat_model_checks(settings, [seat], check_connection=True)
        get.assert_called_once_with(
            str(request.url), headers={"Authorization": "Bearer dummy-catalog-key"}, timeout=4.0
        )
        assert checks[0]["status"] == expected
        assert "dummy-catalog-key" not in str(checks)
    with patch("httpx.get", side_effect=httpx.ConnectTimeout("timeout")):
        checks = await providers.seat_model_checks(settings, [seat], check_connection=True)
        assert checks[0]["status"] == "unreachable"
