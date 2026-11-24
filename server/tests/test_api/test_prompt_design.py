"""Prompt designs preserve the frozen experiment boundary without model calls."""

import asyncio
import json
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.core.research.prompt_design import baseline_fingerprint
from app.core.stats.comparison import protocol_review
from app.dependencies import get_engine_registry, get_experiment_service
from app.repositories.experiment_repo import ExperimentRepository
from app.services.prompt_design_service import design_issues
from tests.test_api.test_studies import create_run


async def prepare(client: AsyncClient, *, target_games: int = 2) -> tuple[dict, dict]:
    a = await create_run(client, collect_mode="benchmark", target_games=target_games)
    key, prompt = next(iter(a["protocol"]["solver"]["prompts"].items()))
    response = await client.post(
        "/api/v1/prompts",
        json={
            "template_key": key,
            "version": "test-b",
            "content": prompt["content"] + "\nThink carefully.",
        },
    )
    assert response.status_code == 201, response.text
    preview = (await client.get(f"/api/v1/experiments/{a['id']}/prompt-design")).json()["data"]
    assert preview["issues"] == []
    assert preview["affected_player_ids"] == a["player_ids"]
    option = next(o for o in preview["options"] if o["version"] == "test-b")
    return a, {
        "primary_metric": {"kind": "landlord_win_rate"},
        "study_id": a["study_id"],
        "baseline_fingerprint": preview["fingerprint"],
        "template_key": key,
        "version": option["version"],
        "content_hash": option["content_hash"],
        "name": "Prompt B",
        "hypothesis": "Explicit reasoning changes decisions",
    }


async def test_variant_freezes_one_change_and_reuses_comparison(client: AsyncClient) -> None:
    a, body = await prepare(client)
    # Changing live config after A must not change B's seats or parameters.
    from app import dependencies

    config = dependencies.get_experiment_config_service().get_config(a["player_ids"][0])
    assert config is not None
    config["model_config"]["temperature"] = 0.123
    await dependencies.get_experiment_config_service().update_config(config["id"], config)
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock) as start:
        response = await client.post(f"/api/v1/experiments/{a['id']}/prompt-variant", json=body)
        assert response.status_code == 201, response.text
        start.assert_not_awaited()
    b = response.json()["data"]
    ap, bp = a["protocol"], b["protocol"]
    assert b["study_id"] == a["study_id"]
    assert b["games"] == []
    assert bp["solver"]["players"] == ap["solver"]["players"]
    assert bp["solver"]["thinking_budget"] == ap["solver"]["thinking_budget"] == {}
    assert bp["engine"] == ap["engine"] and bp["scorer"] == ap["scorer"]
    assert bp["dataset"]["deal_seeds"] == ap["dataset"]["deal_seeds"]
    assert bp["dataset"]["collect_mode"] == "benchmark" and bp["dataset"]["pair_deals"]
    assert bp["design"]["hypothesis"] == body["hypothesis"]
    for key, prompt in ap["solver"]["prompts"].items():
        if key != body["template_key"]:
            assert bp["solver"]["prompts"][key] == prompt
    for rows in ([a, b], [b, a]):
        review = protocol_review(rows, [])
        assert review["controlled"]
        assert set(review["design_changes"]) == set(review["allowed_changes"])
        assert len(review["differences"]) == 3
    saved = await client.post(
        "/api/v1/experiments/comparisons",
        json={
            "experiment_ids": [a["id"], b["id"]],
            "title": "A/B",
        },
    )
    assert saved.status_code == 201, saved.text
    result = saved.json()["data"]["result"]
    assert result["protocol_review"]["controlled"] and result["coverage"]["effective_n"] == 0
    # A valid design does not excuse an additional changed parameter or third run.
    changed = deepcopy(b)
    changed["protocol"]["solver"]["players"][0]["model_config"]["temperature"] = 8
    assert not protocol_review([a, changed], [])["controlled"]
    assert not protocol_review([a, b, {**a, "id": "other"}], [])["allowed_changes"]
    changed = deepcopy(b)
    changed["protocol"]["solver"]["prompts"][body["template_key"]]["content"] += "tampered"
    assert not protocol_review([a, changed], [])["allowed_changes"]


@pytest.mark.parametrize("change", ["prompt", "baseline", "study"])
async def test_review_conflicts_create_no_variant(
    client: AsyncClient,
    test_settings: Settings,
    change: str,
) -> None:
    a, body = await prepare(client)
    if change == "prompt":
        response = await client.put(
            f"/api/v1/prompts/{body['template_key']}/{body['version']}", json={"content": "edited"}
        )
        assert response.status_code == 200
    elif change == "study":
        body["study_id"] = "different"
    else:
        p = deepcopy(a["protocol"])
        p["dataset"]["deal_seeds"][0] += 1
        async with aiosqlite.connect(test_settings.sqlite_path) as db:
            await ExperimentRepository(db).update_protocol(a["id"], p, updated_at="changed")
    response = await client.post(f"/api/v1/experiments/{a['id']}/prompt-variant", json=body)
    assert response.status_code == 409, response.text
    assert len((await client.get("/api/v1/experiments")).json()["data"]) == 1


async def test_same_content_rejected_and_missing_baseline_is_404(client: AsyncClient) -> None:
    a, body = await prepare(client)
    original = a["protocol"]["solver"]["prompts"][body["template_key"]]
    await client.put(
        f"/api/v1/prompts/{body['template_key']}/{body['version']}",
        json={"content": original["content"]},
    )
    body["content_hash"] = original["content_hash"]
    response = await client.post(f"/api/v1/experiments/{a['id']}/prompt-variant", json=body)
    assert response.status_code == 400, response.text
    assert (await client.get("/api/v1/experiments/missing/prompt-design")).status_code == 404


async def test_paired_benchmark_never_extends_plan(client: AsyncClient) -> None:
    a, body = await prepare(client)
    b = (await client.post(f"/api/v1/experiments/{a['id']}/prompt-variant", json=body)).json()[
        "data"
    ]
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock):
        response = await client.post(f"/api/v1/experiments/{b['id']}/collect", json={"count": 50})
        assert response.status_code == 201, response.text
        assert response.json()["data"]["count"] == 2
        exhausted = await client.post(f"/api/v1/experiments/{b['id']}/collect", json={"count": 1})
        assert exhausted.status_code == 400, exhausted.text
    after = (await client.get(f"/api/v1/experiments/{b['id']}")).json()["data"]
    assert after["protocol"]["dataset"]["deal_seeds"] == a["protocol"]["dataset"]["deal_seeds"]


async def test_eligibility_explains_missing_scientific_conditions(client: AsyncClient) -> None:
    a, _ = await prepare(client)
    for field, value, issue in (
        ("memory", "per_experiment", "independent_games_required"),
        ("thinking_budget", None, "complete_protocol_required"),
        (
            "players",
            [{**p, "policy_kind": "heuristic"} for p in a["protocol"]["solver"]["players"]],
            "model_player_required",
        ),
    ):
        changed = deepcopy(a)
        changed["protocol"]["solver"][field] = value
        assert issue in design_issues(changed, get_engine_registry())
        assert baseline_fingerprint(changed) != baseline_fingerprint(a)
    a["protocol"]["dataset"]["collect_mode"] = "free"
    assert "fixed_plan_required" in design_issues(a, get_engine_registry())
    a["protocol"]["engine"]["decision_schema_version"] -= 1
    assert "runtime_protocol_required" in design_issues(a, get_engine_registry())


@pytest.mark.parametrize(
    ("kind", "n", "diff"), [("landlord_win_rate", 2, 1), ("seat_team_win_rate", 1, -1)]
)
async def test_primary_outcome_through_comparison_draft_and_export(
    client: AsyncClient, test_settings: Settings, kind: str, n: int, diff: int
) -> None:
    a, body = await prepare(client)
    target, landlord, partner = a["player_ids"]
    metric = {"kind": kind}
    if kind == "seat_team_win_rate":
        metric["player_id"] = target
    body["primary_metric"] = metric
    runs = "/api/v1/experiments"
    b = (await client.post(f"{runs}/{a['id']}/prompt-variant", json=body)).json()["data"]
    assert b["protocol"]["design"]["affected_player_ids"] == a["player_ids"]
    assert b["protocol"]["design"]["primary_metric"] == metric
    assert b["delta"]["win_rate_diff"] is None

    seeds = a["protocol"]["dataset"]["deal_seeds"]
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        for index, seed in enumerate(seeds):
            for run, role, winner in ((a, "peasant", partner), (b, "landlord", landlord)):
                # The selected farmer never goes out first. One B game lacks role attribution.
                metadata = {"deal_seed": seed}
                if run is a or index == 0:
                    metadata["landlord_id"] = landlord
                await record_outcome(db, run, winner, role, metadata)
        await db.commit()

    for left, right in ((a, b), (b, a)):
        result = (
            await client.get(f"{runs}/compare", params={"ids": f"{left['id']},{right['id']}"})
        ).json()["data"]
        paired = result["paired_summary"]
        assert paired["primary_metric"] == metric and paired["source_id"] == a["id"]
        assert paired["shared_seeds"] == result["coverage"]["effective_n"] == n
        assert paired["win_rate_diff"] == diff
        assert paired["outcome_counts"]["b_only_won" if diff > 0 else "a_only_won"] == n
        assert sum(paired["outcome_counts"].values()) == n
        assert [row["paired_landlord_win_rate"] for row in result["experiments"]] == (
            [0, 1] if left is a else [1, 0]
        )
        if kind == "seat_team_win_rate":
            b_coverage = next(
                c for c in result["coverage"]["experiments"] if c["experiment_id"] == b["id"]
            )
            assert b_coverage["excluded"] == {"missing_seat_outcome": 1}

    for run, sign in ((a, -1), (b, 1)):
        delta = (await client.get(f"{runs}/{run['id']}")).json()["data"]["delta"]
        assert delta["primary_metric"] == metric and delta["win_rate_diff"] == sign * diff
        lo, hi = paired["paired_ci"]
        assert lo < 0 < hi
        assert delta["paired_ci"] == ([lo, hi] if sign == 1 else [-hi, -lo])
        assert delta["paired_n"] == n and not delta["can_conclude"]
        draft = (await client.post(f"{runs}/{run['id']}/conclusion-draft")).json()["data"]["text"]
        assert body["hypothesis"] in draft
        assert ("所在阵营胜率" if kind == "seat_team_win_rate" else "全桌地主胜率") in draft

    snapshot = (
        await client.post(
            f"{runs}/comparisons", json={"experiment_ids": [a["id"], b["id"]], "title": "Scope"}
        )
    ).json()["data"]
    revision = (
        await client.post(
            f"{runs}/comparisons/{snapshot['id']}/conclusions",
            json={
                "expected_revision": 0,
                "observations": "Paired outcomes",
                "limitations": "Few deals",
            },
        )
    ).json()["data"]["record"]
    report = (await client.get(f"{runs}/conclusions/{revision['id']}/export")).json()["data"]
    assert report["comparison"]["result"]["paired_summary"] == paired
    assert report["comparison"]["result"]["coverage"]["effective_n"] == n

    if kind == "seat_team_win_rate":
        # Each run still has assessable seat outcomes, but on different seeds.
        async with aiosqlite.connect(test_settings.sqlite_path) as db:
            await db.execute("DELETE FROM games WHERE id = ?", (f"{a['id']}-{seeds[0]}",))
            await db.commit()
        delta = (await client.get(f"{runs}/{b['id']}")).json()["data"]["delta"]
        assert delta["this_decisive_n"] == delta["peer_decisive_n"] == 1
        assert delta["paired_n"] == 0 and delta["win_rate_diff"] is None
        assert delta["difference_basis"] is None and not delta["can_conclude"]
        frozen = (await client.get(f"{runs}/comparisons/{snapshot['id']}")).json()["data"]
        assert frozen["result"]["paired_summary"] == paired


async def test_requires_exact_metric_and_affected_seat(
    client: AsyncClient, test_settings: Settings
) -> None:
    a, body = await prepare(client)
    protocol = a["protocol"]
    offline = protocol["solver"]["players"][0]
    offline["policy_kind"] = "heuristic"
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await ExperimentRepository(db).update_protocol(a["id"], protocol, updated_at="changed")
    url = f"/api/v1/experiments/{a['id']}"
    preview = (await client.get(f"{url}/prompt-design")).json()["data"]
    assert preview["affected_player_ids"] == a["player_ids"][1:]
    body["baseline_fingerprint"] = preview["fingerprint"]
    for metric in (
        {"kind": "landlord_win_rate", "player_id": offline["id"]},
        {"kind": "seat_team_win_rate"},
        None,
    ):
        request = {k: v for k, v in body.items() if k != "primary_metric"}
        if metric is not None:
            request["primary_metric"] = metric
        assert (await client.post(f"{url}/prompt-variant", json=request)).status_code == 422
    body["primary_metric"] = {"kind": "seat_team_win_rate", "player_id": offline["id"]}
    assert (await client.post(f"{url}/prompt-variant", json=body)).status_code == 400


async def test_holdout_reserves_one_new_frozen_pair_without_collection(client: AsyncClient) -> None:
    a, body = await prepare(client)
    runs = "/api/v1/experiments"
    body["primary_metric"] = {"kind": "seat_team_win_rate", "player_id": a["player_ids"][0]}
    b = (await client.post(f"{runs}/{a['id']}/prompt-variant", json=body)).json()["data"]
    assert (await client.put(f"{runs}/{a['id']}/holdout")).status_code == 400
    url = f"{runs}/{b['id']}/holdout"
    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock) as start:
        first, retry = await asyncio.gather(client.put(url), client.put(url))
        start.assert_not_awaited()
    assert first.status_code == retry.status_code == 200, first.text
    pair = first.json()["data"]
    assert pair == retry.json()["data"]
    ha, hb = [
        (await client.get(f"{runs}/{eid}")).json()["data"]
        for eid in (pair["baseline_id"], pair["variant_id"])
    ]
    seeds = ha["protocol"]["dataset"]["deal_seeds"]
    assert len(set(seeds)) == a["target_games"] and seeds == hb["protocol"]["dataset"]["deal_seeds"]
    assert set(seeds).isdisjoint(a["protocol"]["dataset"]["deal_seeds"])
    for run, origin in ((ha, a), (hb, b)):
        assert run["study_id"] == origin["study_id"] and run["games"] == []
        assert run["protocol"]["dataset"]["holdout_for"] == b["id"]
        assert run["protocol"]["solver"] == origin["protocol"]["solver"]
        assert run["protocol"]["scorer"] == origin["protocol"]["scorer"]
        assert run["protocol"]["engine"] == origin["protocol"]["engine"]
        assert run["delta"]["deal_purpose"] == "holdout"
        assert run["delta"]["primary_metric"] == body["primary_metric"]
    assert "design" not in ha["protocol"]
    assert hb["protocol"]["design"]["baseline_id"] == ha["id"]
    assert hb["protocol"]["design"]["hypothesis"] == body["hypothesis"]
    assert (await client.put(f"{runs}/{hb['id']}/holdout")).status_code == 400
    preview = (await client.get(f"{runs}/{ha['id']}/prompt-design")).json()["data"]
    assert "holdout_locked" in preview["issues"]
    assert len((await client.get(runs)).json()["data"]) == 4
    assert (
        await client.post(f"{runs}/{ha['id']}/clone", json={"copy_deal_seeds": True})
    ).status_code == 400

    saved = (
        await client.post(
            f"{runs}/comparisons", json={"experiment_ids": [hb["id"], ha["id"]], "title": "Holdout"}
        )
    ).json()["data"]
    coverage = saved["result"]["coverage"]
    assert (
        coverage["deal_purpose"] == "holdout" and saved["result"]["protocol_review"]["controlled"]
    )
    assert coverage["excluded_n"] == len(seeds) and coverage["effective_n"] == 0
    assert {entry["seed"] for entry in coverage["excluded_pairs"]} == set(seeds)
    assert all(
        entry["reasons"] == {ha["id"]: "missing", hb["id"]: "missing"}
        for entry in coverage["excluded_pairs"]
    )
    mixed = (await client.get(f"{runs}/compare", params={"ids": f"{a['id']},{hb['id']}"})).json()[
        "data"
    ]
    assert mixed["coverage"]["deal_purpose"] == "mixed"
    assert not mixed["protocol_review"]["controlled"]

    with patch("app.services.game_service.GameService.start_game", new_callable=AsyncMock):
        for run in (ha, hb):
            collected = await client.post(f"{runs}/{run['id']}/collect", json={"count": 50})
            assert collected.status_code == 201 and collected.json()["data"]["count"] == len(seeds)
            detail = (await client.get(f"{runs}/{run['id']}")).json()["data"]
            assert {game["metadata"]["deal_seed"] for game in detail["games"]} == set(seeds)


async def record_outcome(
    db: aiosqlite.Connection, run: dict, winner: str, role: str, metadata: dict
) -> None:
    await db.execute(
        """INSERT INTO games
        (id, game_type, status, player_ids, winner_id, winner_role, data_file,
         created_at, experiment_id, metadata)
        VALUES (?, 'doudizhu', 'finished', ?, ?, ?, 'test.jsonl', ?, ?, ?)""",
        (
            f"{run['id']}-{metadata['deal_seed']}",
            json.dumps(run["player_ids"]),
            winner,
            role,
            run["created_at"],
            run["id"],
            json.dumps(metadata),
        ),
    )


async def test_holdout_requires_every_planned_pair_before_concluding(
    client: AsyncClient, test_settings: Settings
) -> None:
    a, body = await prepare(client, target_games=25)
    runs = "/api/v1/experiments"
    b = (await client.post(f"{runs}/{a['id']}/prompt-variant", json=body)).json()["data"]
    pair = (await client.put(f"{runs}/{b['id']}/holdout")).json()["data"]
    ha, hb = [
        (await client.get(f"{runs}/{eid}")).json()["data"]
        for eid in (pair["baseline_id"], pair["variant_id"])
    ]
    seeds = hb["protocol"]["dataset"]["deal_seeds"]
    landlord, partner, _ = hb["player_ids"]
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        for batch in (seeds[:-1], seeds[-1:]):
            for seed in batch:
                metadata = {"deal_seed": seed, "landlord_id": landlord}
                await record_outcome(db, ha, partner, "peasant", metadata)
                await record_outcome(db, hb, landlord, "landlord", metadata)
            await db.commit()
            delta = (await client.get(f"{runs}/{hb['id']}")).json()["data"]["delta"]
            assert delta["win_rate_diff"] == 1 and delta["paired_ci"][0] > 0
            if len(batch) == 24:
                assert delta["paired_n"] == 24 and delta["paired_excluded_n"] == 1
                assert (
                    not delta["can_conclude"]
                    and delta["inconclusive_reason"] == "incomplete_holdout"
                )
            else:
                assert delta["paired_n"] == 25 and delta["paired_excluded_n"] == 0
                assert delta["can_conclude"]


async def test_failed_holdout_reservation_rolls_back_both_arms(
    client: AsyncClient, test_settings: Settings
) -> None:
    a, body = await prepare(client)
    runs = "/api/v1/experiments"
    b = (await client.post(f"{runs}/{a['id']}/prompt-variant", json=body)).json()["data"]
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("""CREATE TRIGGER fail_holdout_b BEFORE INSERT ON experiments
            WHEN json_extract(NEW.protocol, '$.dataset.holdout_for') IS NOT NULL
             AND json_extract(NEW.protocol, '$.dataset.pair_deals') = 1
            BEGIN SELECT RAISE(ABORT, 'test write failure'); END""")
        await db.commit()
        with pytest.raises(aiosqlite.IntegrityError, match="test write failure"):
            await get_experiment_service().reserve_prompt_holdout(b["id"])
        assert len((await client.get(runs)).json()["data"]) == 2
        await db.execute("DROP TRIGGER fail_holdout_b")
        await db.commit()
    assert (await client.put(f"{runs}/{b['id']}/holdout")).status_code == 200
    assert len((await client.get(runs)).json()["data"]) == 4
