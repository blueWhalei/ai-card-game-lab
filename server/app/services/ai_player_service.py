"""AI player management — SQLite-backed with YAML seed/export."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import structlog
import yaml

from app.database import open_db_connection
from app.repositories.ai_player_repo import AIPlayerRepository

logger = structlog.get_logger()

# Retired DeepSeek model ids → current default
_RETIRED_DEEPSEEK_MODELS = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


class AIPlayerService:
    """Manages AI player profiles in SQLite; YAML is seed/export only.

    Sync ``get_player`` / ``list_players`` read the in-memory cache (filled by
    ``initialize``). Mutating methods are async and update DB + cache.
    """

    def __init__(self, sqlite_path: str, yaml_seed_path: str | None = None) -> None:
        self._sqlite_path = sqlite_path
        self._yaml_seed_path = Path(yaml_seed_path) if yaml_seed_path else None
        self._players: dict[str, dict[str, Any]] = {}
        self._ready = False

    async def initialize(self) -> None:
        """Load from DB; if empty, seed from YAML once."""
        db = await open_db_connection(self._sqlite_path)
        try:
            repo = AIPlayerRepository(db)
            if await repo.count() == 0 and self._yaml_seed_path:
                seeded = await self._seed_from_yaml(repo)
                logger.info("ai_players_seeded_from_yaml", count=seeded)
            rows = await repo.list_all()
            migrated = await self._migrate_retired_deepseek_models(repo, rows)
            if migrated:
                rows = await repo.list_all()
            self._players = {p["id"]: p for p in rows}
            self._ready = True
            logger.info("ai_players_loaded", count=len(self._players), source="sqlite")
        finally:
            await db.close()

    async def _migrate_retired_deepseek_models(
        self,
        repo: AIPlayerRepository,
        rows: list[dict[str, Any]],
    ) -> int:
        """Rewrite retired deepseek-chat / deepseek-reasoner to deepseek-v4-flash."""
        updated = 0
        for player in rows:
            cfg = player.get("model_config") or {}
            if cfg.get("provider") != "deepseek":
                continue
            old = str(cfg.get("model_name") or "")
            new = _RETIRED_DEEPSEEK_MODELS.get(old)
            if not new:
                continue
            patched = deepcopy(player)
            patched["model_config"] = {**cfg, "model_name": new}
            await repo.upsert(patched)
            updated += 1
            logger.info(
                "ai_player_model_migrated",
                player_id=player["id"],
                from_model=old,
                to_model=new,
            )
        return updated

    async def _seed_from_yaml(self, repo: AIPlayerRepository) -> int:
        if not self._yaml_seed_path or not self._yaml_seed_path.exists():
            logger.warning(
                "ai_players_yaml_missing",
                path=str(self._yaml_seed_path) if self._yaml_seed_path else None,
            )
            return 0
        with self._yaml_seed_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        count = 0
        for p in data.get("players", []):
            await repo.upsert(p)
            count += 1
        return count

    def list_players(self) -> list[dict[str, Any]]:
        self._ensure_ready()
        return [deepcopy(p) for p in self._players.values()]

    def get_player(self, player_id: str) -> dict[str, Any] | None:
        self._ensure_ready()
        p = self._players.get(player_id)
        return deepcopy(p) if p else None

    async def create_player(self, data: dict[str, Any]) -> dict[str, Any]:
        self._ensure_ready()
        pid = data["id"]
        if pid in self._players:
            raise ValueError(f"Player '{pid}' already exists")
        player = {
            "id": pid,
            "name": data.get("name", pid),
            "description": data.get("description", ""),
            "avatar": data.get("avatar", ""),
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
            saved = await AIPlayerRepository(db).upsert(player)
        finally:
            await db.close()
        self._players[pid] = saved
        return deepcopy(saved)

    async def update_player(self, player_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._ensure_ready()
        if player_id not in self._players:
            raise KeyError(f"Player '{player_id}' not found")
        player = deepcopy(self._players[player_id])
        for key in ("name", "description", "avatar", "model_config"):
            if key in data and data[key] is not None:
                player[key] = data[key]
        db = await open_db_connection(self._sqlite_path)
        try:
            saved = await AIPlayerRepository(db).upsert(player)
        finally:
            await db.close()
        self._players[player_id] = saved
        return deepcopy(saved)

    async def delete_player(self, player_id: str) -> None:
        self._ensure_ready()
        if player_id not in self._players:
            raise KeyError(f"Player '{player_id}' not found")
        db = await open_db_connection(self._sqlite_path)
        try:
            await AIPlayerRepository(db).delete(player_id)
        finally:
            await db.close()
        del self._players[player_id]

    async def export_to_yaml(self, path: Path | None = None) -> Path:
        """Export current players to YAML (backup / share)."""
        self._ensure_ready()
        target = path or self._yaml_seed_path
        if target is None:
            raise ValueError("No YAML export path configured")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "players": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "description": p.get("description", ""),
                    "avatar": p.get("avatar", ""),
                    "model_config": p.get("model_config", {}),
                }
                for p in self._players.values()
            ]
        }
        with target.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return target

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise RuntimeError("AIPlayerService not initialized; call await initialize()")
