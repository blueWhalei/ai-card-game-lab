"""AI player management service -- YAML-backed CRUD."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger()


class AIPlayerService:
    """Manages AI player profiles: load from YAML, in-memory CRUD, persist back."""

    def __init__(self, config_path: str) -> None:
        self._path = Path(config_path)
        self._players: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("ai_players_yaml_missing", path=str(self._path))
            return
        with self._path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for p in data.get("players", []):
            self._players[p["id"]] = p
        logger.info("ai_players_loaded", count=len(self._players))

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"players": list(self._players.values())}
        with self._path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def list_players(self) -> list[dict[str, Any]]:
        return [deepcopy(p) for p in self._players.values()]

    def get_player(self, player_id: str) -> dict[str, Any] | None:
        p = self._players.get(player_id)
        return deepcopy(p) if p else None

    def create_player(self, data: dict[str, Any]) -> dict[str, Any]:
        pid = data["id"]
        if pid in self._players:
            raise ValueError(f"Player '{pid}' already exists")
        player = {
            "id": pid,
            "name": data.get("name", pid),
            "description": data.get("description", ""),
            "avatar": data.get("avatar", "🤖"),
            "model_config": data.get("model_config", {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 1024,
            }),
        }
        self._players[pid] = player
        self._persist()
        return deepcopy(player)

    def update_player(self, player_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if player_id not in self._players:
            raise KeyError(f"Player '{player_id}' not found")
        player = self._players[player_id]
        for key in ("name", "description", "avatar", "model_config"):
            if key in data and data[key] is not None:
                player[key] = data[key]
        self._persist()
        return deepcopy(player)

    def delete_player(self, player_id: str) -> None:
        if player_id not in self._players:
            raise KeyError(f"Player '{player_id}' not found")
        del self._players[player_id]
        self._persist()
