"""System information service — aggregates config, engine, and storage metadata."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.engine.registry import GameEngineRegistry
from app.utils.providers import is_provider_configured
from app.utils.runtime_dirs import ensure_runtime_dirs


@lru_cache(maxsize=1)
def _cached_training_deps_available() -> bool:
    """Probe training deps once per process; cached to avoid re-importing the
    torch/transformers/peft/datasets stack on every config read."""
    from app.core.training.sft import training_deps_available

    return training_deps_available()


class SystemService:
    """Provides system-level information without exposing Core/Config directly to API."""

    def __init__(
        self,
        settings: Settings,
        engine_registry: GameEngineRegistry,
    ) -> None:
        self._settings = settings
        self._registry = engine_registry

    def list_game_types(self) -> list[str]:
        """Return registered game engine types."""
        return self._registry.list_game_types()

    def list_engines(self) -> list[dict[str, Any]]:
        """Return registered engines with player-count constraints."""
        return self._registry.describe_engines()

    def list_providers(self) -> list[dict[str, Any]]:
        """Return available LLM providers with configuration status."""
        return [
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "GPT-4o, GPT-4o-mini 等",
                "configured": is_provider_configured(self._settings, "openai"),
                "default_model": "gpt-4o-mini",
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "description": "deepseek-v4-flash（默认）/ deepseek-v4-pro",
                "configured": is_provider_configured(self._settings, "deepseek"),
                "default_model": self._settings.deepseek_model or "deepseek-v4-flash",
            },
            {
                "id": "kimi",
                "name": "Kimi / Moonshot",
                "description": "Moonshot-v1 系列",
                "configured": is_provider_configured(self._settings, "kimi"),
                "default_model": "moonshot-v1-8k",
            },
            {
                "id": "dashscope",
                "name": "DashScope",
                "description": "阿里云通义千问系列",
                "configured": is_provider_configured(self._settings, "dashscope"),
                "default_model": "qwen-plus",
            },
            {
                "id": "zhipu",
                "name": "智谱 AI",
                "description": "GLM-4 系列",
                "configured": is_provider_configured(self._settings, "zhipu"),
                "default_model": "glm-4-flash",
            },
            {
                "id": "minimax",
                "name": "MiniMax",
                "description": "MiniMax-Text-01 等",
                "configured": is_provider_configured(self._settings, "minimax"),
                "default_model": "MiniMax-Text-01",
            },
            {
                "id": "yi",
                "name": "零一万物",
                "description": "Yi-Lightning 等",
                "configured": is_provider_configured(self._settings, "yi"),
                "default_model": "yi-lightning",
            },
            {
                "id": "baichuan",
                "name": "百川智能",
                "description": "Baichuan4 系列",
                "configured": is_provider_configured(self._settings, "baichuan"),
                "default_model": "Baichuan4-Turbo",
            },
            {
                "id": "ollama",
                "name": "Ollama",
                "description": "本地部署的开源模型",
                "configured": is_provider_configured(self._settings, "ollama"),
                "default_model": "llama3.2",
            },
        ]

    def get_config(self) -> dict[str, object]:
        """Return non-sensitive app configuration."""
        return {
            "app_name": self._settings.app_name,
            "version": "0.1.0",
            "debug": self._settings.app_debug,
            "data_dir": self._settings.data_dir,
            "sqlite_path": self._settings.sqlite_path,
            "models_dir": self._settings.models_dir,
            "prompt_version": self._settings.prompt_version,
            "prompt_ab_test_enabled": self._settings.prompt_ab_test_enabled,
            "prompt_ab_test_ratio": self._settings.prompt_ab_test_ratio,
            "max_concurrent_games": self._settings.max_concurrent_games,
            "training_deps_available": _cached_training_deps_available(),
            "default_base_models": [
                "Qwen/Qwen2.5-0.5B",
                "Qwen/Qwen2.5-1.5B",
                "Qwen/Qwen2.5-3B",
                "Qwen/Qwen2.5-7B",
            ],
        }

    async def get_storage_info(self) -> dict[str, Any]:
        """Return storage usage statistics (file I/O offloaded to thread)."""
        db_path = Path(self._settings.sqlite_path)
        data_dir = Path(self._settings.data_dir)
        return await asyncio.to_thread(
            _compute_storage_stats, db_path, data_dir
        )

    def get_startup_check(self) -> dict[str, Any]:
        """Return first-run readiness: dirs, providers, and collectability."""
        ensure_runtime_dirs(self._settings)
        providers = self.list_providers()
        cloud_ready = any(
            bool(item["configured"]) and item["id"] != "ollama" for item in providers
        )
        warnings: list[str] = []
        if not cloud_ready:
            warnings.append(
                "未配置云端 API 密钥。请在「实验配置」页创建选手，"
                "并填写对应供应商的 Key，或使用 ollama。"
            )
        if not _cached_training_deps_available():
            warnings.append(
                "未安装训练依赖，无法创建训练任务。"
                "请执行：cd server && poetry install --with training"
            )
        return {
            "data_dirs_ready": True,
            "can_collect": cloud_ready,
            "seed_provider": "deepseek",
            "providers": providers,
            "warnings": warnings,
        }

    def get_runtime_stats(self) -> dict[str, object]:
        from app.core.training.runtime_stats import get_runtime_stats as _snap

        data = dict(_snap())
        data["training_active"] = False  # Task 3 may enrich
        return data


def _compute_storage_stats(db_path: Path, data_dir: Path) -> dict[str, Any]:
    """Synchronous storage computation (called via asyncio.to_thread)."""
    db_size = db_path.stat().st_size if db_path.exists() else 0

    data_size = 0
    jsonl_count = 0
    if data_dir.exists():
        for f in data_dir.rglob("*"):
            if f.is_file():
                data_size += f.stat().st_size
                if f.suffix == ".jsonl":
                    jsonl_count += 1

    return {
        "db_size_bytes": db_size,
        "data_size_bytes": data_size,
        "jsonl_file_count": jsonl_count,
    }
