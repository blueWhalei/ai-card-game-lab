from httpx import AsyncClient


async def test_runtime_stats(client: AsyncClient) -> None:
    res = await client.get("/api/v1/system/runtime-stats")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["memory_total_mb"] > 0
