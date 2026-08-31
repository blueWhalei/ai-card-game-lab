"""Shared pytest fixtures for the test suite."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.database import init_db
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings that point to a temporary directory for data."""
    return Settings(
        app_debug=True,
        data_dir=str(tmp_path),
        sqlite_path=str(tmp_path) + "/test.db",
        deepseek_api_key="sk-test",
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client backed by the FastAPI app."""
    await init_db(test_settings.sqlite_path)

    from app import dependencies
    dependencies.get_settings.cache_clear()
    if hasattr(dependencies, "get_skill_service"):
        dependencies.get_skill_service.cache_clear()
    dependencies.get_experiment_config_service.cache_clear()
    dependencies.get_experiment_config_stats_service.cache_clear()
    dependencies.get_game_service.cache_clear()
    dependencies.get_game_orchestration_service.cache_clear()
    dependencies.get_game_replay_service.cache_clear()
    dependencies.get_jsonl_writer.cache_clear()
    dependencies.get_trace_service.cache_clear()
    dependencies.get_experiment_service.cache_clear()
    dependencies.get_ai_service.cache_clear()
    dependencies.get_decision_service.cache_clear()
    dependencies.get_data_service.cache_clear()
    dependencies.get_demo_seed_service.cache_clear()

    with pytest.MonkeyPatch.context() as m:
        m.setenv("SQLITE_PATH", test_settings.sqlite_path)
        m.setenv("DATA_DIR", test_settings.data_dir)

        app = create_app(settings=test_settings)
        await dependencies.get_experiment_config_service().initialize()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
