"""API smoke for distill preference export."""

from __future__ import annotations

from httpx import AsyncClient


async def test_export_distill_preferences_empty(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/decision-points/export-distill-preferences",
        json={
            "teacher_experiment_id": "exp_teacher_missing",
            "student_experiment_id": "exp_student_missing",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 0
    assert body["data"]["filepath"] == ""
    assert "No distill" in body["message"]
