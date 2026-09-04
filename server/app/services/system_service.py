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


def _preflight_item(
    check_id: str,
    *,
    ok: bool,
    message: str,
    severity: str = "block",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": check_id,
        "severity": severity,
        "ok": ok,
        "message": message,
    }
    if params:
        item["params"] = params
    return item


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
        """Return registered engines with full capability metadata."""
        return self._registry.describe_engines()

    def get_benchmark_seeds(self, game_type: str | None = None) -> dict[str, Any]:
        """Return fixed deal seeds for benchmark mode from engine capability."""
        resolved = game_type or self._registry.default_game_type()
        if not resolved:
            return {
                "game_type": None,
                "count": 0,
                "seeds": [],
                "description": "No engines registered",
            }
        cap = self._registry.get_capability(resolved)
        seeds = list(cap.benchmark_seeds)
        return {
            "game_type": resolved,
            "count": len(seeds),
            "seeds": seeds,
            "supports_deal_seed": cap.supports_deal_seed,
            "description": "Fixed deal seeds for benchmark-mode experiments",
        }

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

    async def get_preflight(
        self,
        *,
        scope: str = "all",
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        """Run collect/train readiness checks (optionally seat-scoped to an experiment)."""
        return await self._preflight_async(scope=scope, experiment_id=experiment_id)

    def _preflight_sync(
        self,
        *,
        scope: str,
        experiment_id: str | None,
        protocol: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_runtime_dirs(self._settings)
        providers = self.list_providers()
        checks: list[dict[str, Any]] = []
        resolved_scope = scope if scope in {"collect", "train", "all"} else "all"
        need_collect = resolved_scope in {"collect", "all"}
        need_train = resolved_scope in {"train", "all"}

        any_ready = any(bool(item["configured"]) for item in providers)
        if need_collect and experiment_id is None:
            checks.append(
                _preflight_item(
                    "providers_any",
                    ok=any_ready,
                    message=(
                        "未配置可用模型供应商。请在项目根目录 .env 填写云厂商 API 密钥，"
                        "或安装 Ollama 并拉取至少一个本地模型（如 ollama pull qwen2.5:7b）。"
                        if not any_ready
                        else "至少有一个模型供应商可用"
                    ),
                )
            )

        protocol_ok = True
        seats_ok = True
        if need_collect and experiment_id is not None:
            proto = protocol if isinstance(protocol, dict) else None
            players = list((proto or {}).get("players") or []) if proto else []
            protocol_ok = bool(proto) and bool(players)
            checks.append(
                _preflight_item(
                    "protocol",
                    ok=protocol_ok,
                    message=(
                        "实验协议完整"
                        if protocol_ok
                        else "实验协议缺失或不完整，请重新创建实验后再采集"
                    ),
                )
            )
            if protocol_ok:
                from app.utils.providers import unconfigured_providers_from_players

                missing = unconfigured_providers_from_players(self._settings, players)
                seats_ok = len(missing) == 0
                checks.append(
                    _preflight_item(
                        "providers_seats",
                        ok=seats_ok,
                        message=(
                            "实验座位所用供应商均已配置"
                            if seats_ok
                            else (
                                "实验座位供应商未配置："
                                + ", ".join(missing)
                                + "。请在 .env 配置密钥，或改选手配置。"
                            )
                        ),
                        params=None if seats_ok else {"providers": ", ".join(missing)},
                    )
                )
            else:
                seats_ok = False
                checks.append(
                    _preflight_item(
                        "providers_seats",
                        ok=False,
                        message="无法校验座位供应商（协议不完整）",
                        params={"incomplete": True},
                    )
                )

        train_deps = _cached_training_deps_available()
        if need_train:
            checks.append(
                _preflight_item(
                    "training_deps",
                    ok=train_deps,
                    message=(
                        "训练依赖已安装"
                        if train_deps
                        else "未安装训练依赖，无法创建训练任务。"
                        "请执行：cd server && poetry install --with training"
                    ),
                )
            )
            mem_ok = True
            mem_msg = "可用内存足以做 CPU smoke 训练"
            mem_params: dict[str, Any] | None = None
            try:
                from app.core.training.cpu_smoke import MIN_AVAILABLE_MEMORY_MB
                from app.core.training.runtime_stats import get_runtime_stats as _snap

                available = float(_snap().get("memory_available_mb") or 0)
                if available < MIN_AVAILABLE_MEMORY_MB:
                    mem_ok = False
                    mem_params = {
                        "available_mb": int(available),
                        "threshold_mb": int(MIN_AVAILABLE_MEMORY_MB),
                    }
                    mem_msg = (
                        f"可用内存约 {available:.0f}MB，低于 CPU smoke 建议阈值 "
                        f"{MIN_AVAILABLE_MEMORY_MB}MB；创建任务时可能被拒绝。"
                    )
            except Exception:
                mem_ok = True
                mem_msg = "未能探测内存，跳过警告"
            checks.append(
                _preflight_item(
                    "memory_smoke",
                    ok=mem_ok,
                    severity="warn",
                    message=mem_msg,
                    params=mem_params,
                )
            )

        can_collect = True
        if need_collect:
            if experiment_id is None:
                can_collect = any_ready
            else:
                can_collect = protocol_ok and seats_ok
        can_train = train_deps if need_train else True
        # For scope=collect, can_train stays True (not in scope); ok only cares about scoped blocks
        block_failed = any(
            (not c["ok"]) and c["severity"] == "block" for c in checks
        )
        warnings = [str(c["message"]) for c in checks if not c["ok"]]
        return {
            "ok": not block_failed,
            "can_collect": can_collect,
            "can_train": can_train if need_train else train_deps,
            "checks": checks,
            "providers": providers,
            "warnings": warnings,
        }

    async def _preflight_async(
        self,
        *,
        scope: str,
        experiment_id: str | None,
    ) -> dict[str, Any]:
        protocol: dict[str, Any] | None = None
        if experiment_id:
            from app.database import open_db_connection
            from app.repositories.experiment_repo import ExperimentRepository

            conn = await open_db_connection(self._settings.sqlite_path)
            try:
                repo = ExperimentRepository(conn)
                try:
                    row = await repo.get_by_id(experiment_id)
                except KeyError:
                    return self._preflight_sync(
                        scope=scope,
                        experiment_id=experiment_id,
                        protocol=None,
                    )
                proto = row.get("protocol")
                protocol = proto if isinstance(proto, dict) else None
            finally:
                await conn.close()
        return self._preflight_sync(
            scope=scope, experiment_id=experiment_id, protocol=protocol
        )

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
