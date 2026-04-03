"""FastAPI dependency injection providers.

Dependency Lifecycle Overview:
==============================

1. SINGLETON (Application-scoped, cached via @lru_cache):
   - Settings: Configuration loaded once at startup
   - GameEngineRegistry: Game engine registry (stateless)
   - LLMClientFactory: LLM client factory (stateless)
   - AIPlayerService: AI player configuration (stateless)
   - PromptBuilder: Prompt builder (stateless)
   - JsonlWriter: Data collector (stateless, writes to files)
   - EventBus: Event bus singleton for domain events
   - All Service classes: Business logic services

2. REQUEST-SCOPED (New instance per HTTP request):
   - Database connections (via get_db): Each request gets its own connection
   - PromptService: Per-request service with its own DB connection

3. STATEFUL SINGLETONS (Hold runtime state):
   - GameOrchestrationService: Holds active game states, tasks, pause events
   - WebSocketManager: Holds active WebSocket connections

Note: Services do NOT hold request-scoped DB connections. API handlers
pass `db` into methods that need it; background tasks open their own
connections via `open_db_connection()`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite
from fastapi import Depends

from app.config import Settings
from app.core.ai.factory import LLMClientFactory
from app.core.ai.prompt import PromptBuilder
from app.core.ai.providers.ollama_client import OllamaClient
from app.core.ai.providers.openai_client import OpenAICompatibleClient
from app.core.collector.jsonl_writer import JsonlWriter
from app.core.engine.doudizhu import DoudizhuEngine
from app.core.engine.registry import GameEngineRegistry
from app.core.events import get_event_bus
from app.database import get_db_connection
from app.services.ai_player_service import AIPlayerService
from app.services.ai_service import AIService
from app.services.data_service import DataService
from app.services.decision_service import DecisionService
from app.services.game_orchestration_service import GameOrchestrationService
from app.services.game_replay_service import GameReplayService
from app.services.game_service import GameService
from app.services.player_stats_service import PlayerStatsService

if TYPE_CHECKING:
    from app.services.prompt_service import PromptService as PromptServiceType
else:
    from app.services.prompt_service import PromptService as PromptServiceType

from app.services.system_service import SystemService
from app.services.trace_service import TraceService
from app.services.training_service import TrainingService
from app.websocket.manager import ws_manager

_event_handlers_subscribed = False


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance (cached).

    Lifecycle: Application-scoped singleton.
    Loads configuration from environment variables and .env file once.
    """
    return Settings()


async def get_prompt_service(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[PromptServiceType, None]:
    """Get PromptService with per-request database connection."""
    from app.core.ai.prompts.registry import get_registry

    async for db in get_db_connection(settings.sqlite_path):
        yield PromptServiceType(db=db, registry=get_registry())


async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield a database connection per request."""
    async for db in get_db_connection(settings.sqlite_path):
        yield db



@lru_cache
def get_engine_registry() -> GameEngineRegistry:
    """Singleton game engine registry."""
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    return registry


@lru_cache
def get_llm_factory() -> LLMClientFactory:
    """Singleton LLM client factory."""
    settings = get_settings()
    factory = LLMClientFactory()

    openai_compatible_providers: list[tuple[str, str, str, str]] = [
        ("openai", settings.openai_api_key, settings.openai_base_url, "gpt-4o-mini"),
        ("dashscope", settings.dashscope_api_key, settings.dashscope_base_url, "qwen-turbo"),  # qwen-turbo: fast; qwen-max: powerful
        ("deepseek", settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model),
        ("kimi", settings.kimi_api_key, settings.kimi_base_url, "moonshot-v1-8k"),
        ("minimax", settings.minimax_api_key, settings.minimax_base_url, "MiniMax-Text-01"),
        ("zhipu", settings.zhipu_api_key, settings.zhipu_base_url, "glm-4-flash"),
        ("yi", settings.yi_api_key, settings.yi_base_url, "yi-lightning"),
        ("baichuan", settings.baichuan_api_key, settings.baichuan_base_url, "Baichuan4-Air"),
    ]

    for provider_name, api_key, base_url, default_model in openai_compatible_providers:
        pn, ak, bu, dm = provider_name, api_key, base_url, default_model
        factory.register(type(
            f"Configured_{pn}",
            (OpenAICompatibleClient,),
            {
                "__init__": lambda self, _pn=pn, _ak=ak, _bu=bu, _dm=dm, **kw: (
                    OpenAICompatibleClient.__init__(
                        self,
                        provider_name=_pn,
                        api_key=_ak,
                        base_url=_bu,
                        model=_dm,
                        **kw,
                    )
                )
            },
        ))

    ollama_base = settings.ollama_base_url
    factory.register(type(
        "Configured_ollama",
        (OllamaClient,),
        {
            "__init__": lambda self, _bu=ollama_base, **kw: OllamaClient.__init__(
                self,
                base_url=_bu,
                **kw,
            )
        },
    ))

    return factory


@lru_cache
def get_ai_player_service() -> AIPlayerService:
    """Singleton AI player configuration service."""
    settings = get_settings()
    config_path = str(Path(settings.config_dir) / "ai_players.yaml")
    return AIPlayerService(config_path)


@lru_cache
def get_prompt_builder() -> PromptBuilder:
    """Singleton prompt builder."""
    return PromptBuilder()


@lru_cache
def get_jsonl_writer() -> JsonlWriter:
    """Singleton JSONL data writer."""
    settings = get_settings()
    return JsonlWriter(settings.data_dir)


@lru_cache
def get_ai_service() -> AIService:
    """Singleton AI service."""
    return AIService(
        llm_factory=get_llm_factory(),
        prompt_builder=get_prompt_builder(),
        ai_player_service=get_ai_player_service(),
        decision_service=get_decision_service(),
    )


@lru_cache
def get_game_orchestration_service() -> GameOrchestrationService:
    """Singleton game orchestration service."""
    settings = get_settings()
    return GameOrchestrationService(
        engine_registry=get_engine_registry(),
        collector=get_jsonl_writer(),
        ai_service=get_ai_service(),
        ai_player_service=get_ai_player_service(),
        sqlite_path=settings.sqlite_path,
        event_bus=get_event_bus(),
        decision_service=get_decision_service(),
        trace_service=get_trace_service(),
    )


@lru_cache
def get_game_replay_service() -> GameReplayService:
    """Singleton game replay service."""
    settings = get_settings()
    return GameReplayService(
        collector=get_jsonl_writer(),
        sqlite_path=settings.sqlite_path,
    )


@lru_cache
def get_game_service() -> GameService:
    """Singleton game service."""
    settings = get_settings()
    return GameService(
        engine_registry=get_engine_registry(),
        collector=get_jsonl_writer(),
        sqlite_path=settings.sqlite_path,
        orchestration_service=get_game_orchestration_service(),
        replay_service=get_game_replay_service(),
    )


@lru_cache
def get_data_service() -> DataService:
    """Singleton data service."""
    settings = get_settings()
    return DataService(
        sqlite_path=settings.sqlite_path,
        data_dir=settings.data_dir,
    )


@lru_cache
def get_training_service() -> TrainingService:
    """Singleton training service."""
    settings = get_settings()
    return TrainingService(
        sqlite_path=settings.sqlite_path,
        data_dir=settings.data_dir,
        models_dir=settings.models_dir,
    )


@lru_cache
def get_system_service() -> SystemService:
    """Singleton system service."""
    settings = get_settings()
    return SystemService(
        settings=settings,
        engine_registry=get_engine_registry(),
    )


@lru_cache
def get_trace_service() -> TraceService:
    """Singleton trace service."""
    settings = get_settings()
    return TraceService(
        sqlite_path=settings.sqlite_path,
        ws_manager=ws_manager,
    )


@lru_cache
def get_decision_service() -> DecisionService:
    """Singleton decision service."""
    settings = get_settings()
    return DecisionService(
        sqlite_path=settings.sqlite_path,
        data_dir=settings.data_dir,
    )


@lru_cache
def get_archive_service() -> "ArchiveService":
    """Singleton archive service."""
    from app.services.archive_service import ArchiveService

    settings = get_settings()
    return ArchiveService(
        sqlite_path=settings.sqlite_path,
        data_dir=settings.data_dir,
    )


@lru_cache
def get_player_stats_service() -> PlayerStatsService:
    """Singleton player stats service."""
    settings = get_settings()
    return PlayerStatsService(sqlite_path=settings.sqlite_path)
