"""Experiment config management — SQLite-backed with YAML seed/export."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import structlog
import yaml

from app.database import open_db_connection
from app.repositories.experiment_config_repo import ExperimentConfigRepository

logger = structlog.get_logger()

# Retired DeepSeek model ids → current default
_RETIRED_DEEPSEEK_MODELS = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


class ExperimentConfigService:
    """Manages experiment config profiles in SQLite; YAML is seed/export only.

    Sync ``get_config`` / ``list_configs`` read the in-memory cache (filled by
    ``initialize``). Mutating methods are async and update DB + cache.
    """

    def __init__(self, sqlite_path: str, yaml_seed_path: str | None = None) -> None:
        self._sqlite_path = sqlite_path
        self._yaml_seed_path = Path(yaml_seed_path) if yaml_seed_path else None
        self._configs: dict[str, dict[str, Any]] = {}
        self._ready = False

    async def initialize(self) -> None:
        """Load from DB; if empty, seed from YAML once."""
        db = await open_db_connection(self._sqlite_path)
        try:
            repo = ExperimentConfigRepository(db)
            if await repo.count() == 0 and self._yaml_seed_path:
                seeded = await self._seed_from_yaml(repo)
                logger.info("experiment_configs_seeded_from_yaml", count=seeded)
            rows = await repo.list_all()
            migrated = await self._migrate_retired_deepseek_models(repo, rows)
            if migrated:
                rows = await repo.list_all()
            self._configs = {c["id"]: c for c in rows}
            self._ready = True
            logger.info("experiment_configs_loaded", count=len(self._configs), source="sqlite")
        finally:
            await db.close()

    async def _migrate_retired_deepseek_models(
        self,
        repo: ExperimentConfigRepository,
        rows: list[dict[str, Any]],
    ) -> int:
        """Rewrite retired deepseek-chat / deepseek-reasoner to deepseek-v4-flash."""
        updated = 0
        for config in rows:
            cfg = config.get("model_config") or {}
            if cfg.get("provider") != "deepseek":
                continue
            old = str(cfg.get("model_name") or "")
            new = _RETIRED_DEEPSEEK_MODELS.get(old)
            if not new:
                continue
            patched = deepcopy(config)
            patched["model_config"] = {**cfg, "model_name": new}
            await repo.upsert(patched)
            updated += 1
            logger.info(
                "experiment_config_model_migrated",
                config_id=config["id"],
                from_model=old,
                to_model=new,
            )
        return updated

    async def _seed_from_yaml(self, repo: ExperimentConfigRepository) -> int:
        if not self._yaml_seed_path or not self._yaml_seed_path.exists():
            logger.warning(
                "experiment_configs_yaml_missing",
                path=str(self._yaml_seed_path) if self._yaml_seed_path else None,
            )
            return 0
        with self._yaml_seed_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        count = 0
        for c in data.get("configs", []):
            await repo.upsert(c)
            count += 1
        return count

    def list_configs(self) -> list[dict[str, Any]]:
        self._ensure_ready()
        return [deepcopy(c) for c in self._configs.values()]

    def get_config(self, config_id: str) -> dict[str, Any] | None:
        self._ensure_ready()
        c = self._configs.get(config_id)
        return deepcopy(c) if c else None

    async def create_config(self, data: dict[str, Any]) -> dict[str, Any]:
        self._ensure_ready()
        cid = str(data.get("id") or "").strip()
        if not cid:
            raise ValueError("Config id is required")
        if cid in self._configs:
            raise ValueError(f"Config '{cid}' already exists")
        config = {
            "id": cid,
            "name": data.get("name", cid),
            "notes": data.get("notes", ""),
            "model_config": data.get(
                "model_config",
                {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "max_tokens": 1024,
                },
            ),
        }
        db = await open_db_connection(self._sqlite_path)
        try:
            saved = await ExperimentConfigRepository(db).upsert(config)
        finally:
            await db.close()
        self._configs[cid] = saved
        return deepcopy(saved)

    async def update_config(self, config_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._ensure_ready()
        if config_id not in self._configs:
            raise KeyError(f"Config '{config_id}' not found")
        config = deepcopy(self._configs[config_id])
        for key in ("name", "notes", "model_config"):
            if key in data and data[key] is not None:
                config[key] = data[key]
        db = await open_db_connection(self._sqlite_path)
        try:
            saved = await ExperimentConfigRepository(db).upsert(config)
        finally:
            await db.close()
        self._configs[config_id] = saved
        return deepcopy(saved)

    async def delete_config(self, config_id: str) -> None:
        self._ensure_ready()
        if config_id not in self._configs:
            raise KeyError(f"Config '{config_id}' not found")
        db = await open_db_connection(self._sqlite_path)
        try:
            await ExperimentConfigRepository(db).delete(config_id)
        finally:
            await db.close()
        del self._configs[config_id]

    async def export_to_yaml(self, path: Path | None = None) -> Path:
        """Export current configs to YAML (backup / share)."""
        self._ensure_ready()
        target = path or self._yaml_seed_path
        if target is None:
            raise ValueError("No YAML export path configured")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "configs": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "notes": c.get("notes", ""),
                    "model_config": c.get("model_config", {}),
                }
                for c in self._configs.values()
            ]
        }
        with target.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return target

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise RuntimeError("ExperimentConfigService not initialized; call await initialize()")
