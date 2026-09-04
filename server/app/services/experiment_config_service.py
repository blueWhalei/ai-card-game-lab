"""Experiment config management — SQLite-backed, edited in the UI."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.pack import build_player_pack
from app.database import open_db_connection
from app.repositories.experiment_config_repo import ExperimentConfigRepository

logger = structlog.get_logger()

# Retired DeepSeek model ids → current default
_RETIRED_DEEPSEEK_MODELS = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


class ExperimentConfigService:
    """Manages experiment config profiles in SQLite.

    Sync ``get_config`` / ``list_configs`` read the in-memory cache (filled by
    ``initialize``). Mutating methods are async and update DB + cache.
    """

    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path
        self._configs: dict[str, dict[str, Any]] = {}
        self._ready = False

    async def initialize(self) -> None:
        """Load configs from SQLite. Empty table stays empty until the UI creates rows."""
        db = await open_db_connection(self._sqlite_path)
        try:
            repo = ExperimentConfigRepository(db)
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

    async def import_players(
        self, players: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Create missing players; never overwrite an existing id."""
        created: list[str] = []
        reused: list[str] = []
        for player in players:
            cid = str(player.get("id") or "").strip()
            if not cid:
                continue
            if self.get_config(cid) is not None:
                reused.append(cid)
                continue
            await self.create_config(
                {
                    "id": cid,
                    "name": player.get("name") or cid,
                    "notes": player.get("notes") or "",
                    "model_config": player.get("model_config") or {},
                }
            )
            created.append(cid)
        return {"created": created, "reused": reused}

    def export_pack(self, ids: list[str] | None = None) -> dict[str, Any]:
        rows = self.list_configs()
        if ids:
            wanted = set(ids)
            rows = [row for row in rows if row["id"] in wanted]
        return build_player_pack(rows, exported_at=datetime.now(tz=UTC).isoformat())

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise RuntimeError("ExperimentConfigService not initialized; call await initialize()")
