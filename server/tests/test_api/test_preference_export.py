"""API smoke tests for preference export."""

from __future__ import annotations

from httpx import AsyncClient


async def test_export_preferences_empty(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/decision-points/export-preferences",
        json={"train_usable_only": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 0
    assert body["data"]["filepath"] == ""
    assert "No preference pairs" in body["message"]
