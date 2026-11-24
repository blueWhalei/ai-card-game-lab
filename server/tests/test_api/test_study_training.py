"""Research scopes and saved-field validity, without starting training."""

from datetime import UTC, datetime

import pytest

from app import dependencies
from app.database import connect_sqlite
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.training_repo import TrainingTaskRepository
from tests.test_api.test_studies import create_run

PATH = "/api/v1/training/tasks"


@pytest.fixture
async def training_scope(client, test_settings):
    dependencies.get_training_service.cache_clear()
    run, other = await create_run(client), await create_run(client)
    now = datetime.now(UTC).isoformat()
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await DatasetRepository(db).create(
            {
                "id": "ds-training",
                "name": "Shared dataset",
                "game_type": "doudizhu",
                "filters": {},
                "sample_count": 0,
                "file_path": "unused",
                "created_at": now,
            }
        )
        repo = TrainingTaskRepository(db)
        states = [
            "failed",
            "pending",
            "exporting",
            "training",
            "completed",
            "cancelled",
            "unexpected",
        ]
        for index in range(26):
            await repo.create(
                {
                    "id": f"task-{index:02}",
                    "name": f"Task {index}",
                    "dataset_id": "ds-training",
                    "base_model": "synthetic",
                    "training_type": "sft",
                    "status": states[index] if index < 7 else "failed",
                    "created_at": now,
                    "experiment_id": run["id"]
                    if index < 24
                    else other["id"]
                    if index == 24
                    else None,
                }
            )
        for key, progress, result in [
            ("task-00", None, "broken"),
            ("task-01", -0.1, '{"loss":1e999}'),
            ("task-02", 1.1, "[]"),
            ("task-03", 0.25, None),
            ("task-04", 1, '{"train_loss":0}'),
        ]:
            await db.execute(
                "UPDATE training_tasks SET progress=?,result=? WHERE id=?", (progress, result, key)
            )
        await db.commit()
    return run, other


async def test_training_scope_filters_before_paging_and_exact_task(client, training_scope):
    run, other = training_scope
    params = {"study_id": run["study_id"], "page_size": 20}
    first = (await client.get(PATH, params=params)).json()["data"]
    assert first["total"] == 24 and len(first["items"]) == 20
    assert first["items"][0]["id"] == "task-23"
    assert datetime.fromisoformat(first["read_at"]).tzinfo is not None
    assert all(item["study_id"] == run["study_id"] for item in first["items"])
    second = (await client.get(PATH, params={**params, "page": 2})).json()["data"]
    assert [item["id"] for item in second["items"]] == ["task-03", "task-02", "task-01", "task-00"]
    exact = (
        await client.get(PATH, params={**params, "task_id": "task-00", "experiment_id": run["id"]})
    ).json()["data"]
    assert exact["total"] == 1 and exact["items"][0]["id"] == "task-00"
    for extra in [
        {"task_id": "task-24"},
        {"task_id": "task-25"},
        {"task_id": "absent"},
        {"task_id": "task-00", "experiment_id": other["id"]},
    ]:
        result = (await client.get(PATH, params={**params, **extra})).json()["data"]
        assert result["items"] == [] and result["total"] == 0
    active = (await client.get(PATH, params={**params, "state": "active"})).json()["data"]
    assert active["total"] == 3
    attention = (await client.get(PATH, params={**params, "state": "attention", "page": 2})).json()[
        "data"
    ]
    assert attention["total"] == 19 and attention["items"] == []
    cancelled = (
        await client.get(PATH, params={**params, "state": "attention", "status": "cancelled"})
    ).json()["data"]
    assert cancelled["total"] == 0


async def test_training_records_keep_zero_missing_invalid_and_damaged_results(
    client, training_scope
):
    run, _ = training_scope
    response = await client.get(PATH, params={"study_id": run["study_id"], "page_size": 100})
    assert response.status_code == 200, response.text
    rows = {item["id"]: item for item in response.json()["data"]["items"]}
    assert rows["task-00"]["progress"] is None and rows["task-00"]["progress_state"] == "missing"
    for key in ["task-01", "task-02"]:
        assert rows[key]["progress"] is None and rows[key]["progress_state"] == "invalid"
    for key in ["task-00", "task-01", "task-02"]:
        assert rows[key]["result"] is None and rows[key]["result_state"] == "invalid"
    assert rows["task-03"]["progress"] == 0.25
    assert rows["task-04"]["progress"] == 1 and rows["task-04"]["result"] == {"train_loss": 0}
    assert rows["task-05"]["progress"] == 0 and rows["task-05"]["progress_state"] == "recorded"


async def test_training_ownership_is_current_and_unlinked_tasks_remain_global(
    client, training_scope, test_settings
):
    run, _ = training_scope
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM study_runs WHERE experiment_id=?", (run["id"],))
        await db.commit()
    response = (await client.get(PATH, params={"study_id": run["study_id"]})).json()["data"]
    assert response["total"] == 0
    global_tasks = (await client.get(PATH, params={"page_size": 100})).json()["data"]
    assert global_tasks["total"] == 26
    assert any(item["id"] == "task-25" for item in global_tasks["items"])


@pytest.mark.parametrize(
    "query,code",
    [("study_id=absent", 404), ("state=invalid", 422), ("task_id=", 422), ("study_id=", 422)],
)
async def test_training_invalid_scope_never_widens(client, query, code):
    dependencies.get_training_service.cache_clear()
    assert (await client.get(f"{PATH}?{query}")).status_code == code
