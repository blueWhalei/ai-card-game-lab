"""Tests for GameService facade."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.game_service import GameService
from app.utils.exceptions import InvalidPlayerIdsError, ProviderNotConfiguredError


@pytest.fixture
def experiment_config_service() -> MagicMock:
    svc = MagicMock()
    svc.get_config.side_effect = lambda pid: {
        "id": pid,
        "model_config": {"provider": "deepseek", "model_name": "deepseek-v4-flash"},
    }
    return svc


@pytest.fixture
def game_service(experiment_config_service: MagicMock) -> GameService:
    return GameService(
        engine_registry=MagicMock(),
        collector=MagicMock(),
        sqlite_path=":memory:",
        orchestration_service=MagicMock(),
        replay_service=MagicMock(),
        experiment_config_service=experiment_config_service,
        settings=Settings(deepseek_api_key="sk-test"),
    )


class TestGameServiceInitialization:
    def test_service_initialization(self, game_service: GameService) -> None:
        assert game_service is not None

    def test_get_game_state_delegates(self, game_service: GameService) -> None:
        game_service._orchestration_service.get_game_state.return_value = None
        assert game_service.get_game_state("missing") is None
        game_service._orchestration_service.get_game_state.assert_called_once_with("missing")


class TestGameServicePlayerValidation:
    def test_unknown_player_ids_rejected(
        self,
        game_service: GameService,
        experiment_config_service: MagicMock,
    ) -> None:
        experiment_config_service.get_config.side_effect = lambda pid: None
        with pytest.raises(InvalidPlayerIdsError):
            game_service._validate_player_ids(["missing-1"])

    def test_unconfigured_provider_rejected(
        self,
        experiment_config_service: MagicMock,
    ) -> None:
        service = GameService(
            engine_registry=MagicMock(),
            collector=MagicMock(),
            sqlite_path=":memory:",
            orchestration_service=MagicMock(),
            replay_service=MagicMock(),
            experiment_config_service=experiment_config_service,
            settings=Settings(deepseek_api_key=""),
        )
        with pytest.raises(ProviderNotConfiguredError) as exc:
            service._validate_player_ids(["cfg_temp_09"])
        assert "deepseek" in exc.value.message

    def test_ollama_does_not_require_api_key(
        self,
        experiment_config_service: MagicMock,
    ) -> None:
        experiment_config_service.get_config.side_effect = lambda pid: {
            "id": pid,
            "model_config": {"provider": "ollama", "model_name": "llama3.2"},
        }
        service = GameService(
            engine_registry=MagicMock(),
            collector=MagicMock(),
            sqlite_path=":memory:",
            orchestration_service=MagicMock(),
            replay_service=MagicMock(),
            experiment_config_service=experiment_config_service,
            settings=Settings(),
        )
        service._validate_player_ids(["cfg_ollama_local"])

    def test_wrong_player_count_rejected(self, game_service: GameService) -> None:
        engine = MagicMock()
        engine.min_players = 3
        engine.max_players = 3
        game_service._engine_registry.get.return_value = engine
        from app.utils.exceptions import InvalidPlayerCountError

        with pytest.raises(InvalidPlayerCountError):
            game_service._validate_player_count("doudizhu", ["a", "b"])
