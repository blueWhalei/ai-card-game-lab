"""Prompt template API: activate / deactivate."""

from httpx import AsyncClient


async def test_activate_inactive_template(client: AsyncClient) -> None:
    key = "doudizhu_playing"
    version = "activate-fix"

    created = await client.post(
        "/api/v1/prompts",
        json={
            "template_key": key,
            "version": version,
            "content": "TEST_PROMPT {rules} {format_instructions}",
        },
    )
    assert created.status_code == 201
    assert created.json()["data"]["is_active"] is True

    deactivated = await client.post(
        f"/api/v1/prompts/{key}/deactivate",
        json={"version": version},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    activated = await client.post(
        f"/api/v1/prompts/{key}/activate",
        json={"version": version},
    )
    assert activated.status_code == 200
    body = activated.json()
    assert body["code"] == 0
    assert body["data"]["template_key"] == key
    assert body["data"]["version"] == version
    assert body["data"]["is_active"] is True
