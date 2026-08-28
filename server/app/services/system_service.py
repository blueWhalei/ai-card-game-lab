"""System information service — aggregates config, engine, and storage metadata."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.engine.registry import GameEngineRegistry


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

    def list_providers(self) -> list[dict[str, Any]]:
        """Return available LLM providers with configuration status."""
        return [
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "GPT-4o, GPT-4o-mini 等",
                "configured": bool(self._settings.openai_api_key),
                "default_model": "gpt-4o-mini",
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "description": "deepseek-v4-flash（默认）/ deepseek-v4-pro",
                "configured": bool(self._settings.deepseek_api_key),
                "default_model": self._settings.deepseek_model or "deepseek-v4-flash",
            },
            {
                "id": "kimi",
                "name": "Kimi / Moonshot",
                "description": "Moonshot-v1 系列",
                "configured": bool(self._settings.kimi_api_key),
                "default_model": "moonshot-v1-8k",
            },
            {
                "id": "dashscope",
                "name": "DashScope",
                "description": "阿里云通义千问系列",
                "configured": bool(self._settings.dashscope_api_key),
                "default_model": "qwen-plus",
            },
            {
                "id": "zhipu",
                "name": "智谱 AI",
                "description": "GLM-4 系列",
                "configured": bool(self._settings.zhipu_api_key),
                "default_model": "glm-4-flash",
            },
            {
                "id": "minimax",
                "name": "MiniMax",
                "description": "MiniMax-Text-01 等",
                "configured": bool(self._settings.minimax_api_key),
                "default_model": "MiniMax-Text-01",
            },
            {
                "id": "yi",
                "name": "零一万物",
                "description": "Yi-Lightning 等",
                "configured": bool(self._settings.yi_api_key),
                "default_model": "yi-lightning",
            },
            {
                "id": "baichuan",
                "name": "百川智能",
                "description": "Baichuan4 系列",
                "configured": bool(self._settings.baichuan_api_key),
                "default_model": "Baichuan4-Turbo",
            },
            {
                "id": "ollama",
                "name": "Ollama",
                "description": "本地部署的开源模型",
                "configured": True,
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
            "config_dir": self._settings.config_dir,
            "models_dir": self._settings.models_dir,
            "prompt_version": self._settings.prompt_version,
            "prompt_ab_test_enabled": self._settings.prompt_ab_test_enabled,
            "prompt_ab_test_ratio": self._settings.prompt_ab_test_ratio,
            "training_use_mock": self._settings.training_use_mock,
            "default_base_models": [
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
