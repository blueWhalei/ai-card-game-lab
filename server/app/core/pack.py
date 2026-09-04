"""Shareable experiment / player JSON packs (no secrets)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PACK_SCHEMA_VERSION = 1
KIND_PLAYER_PACK = "cardlab.player_pack"
KIND_EXPERIMENT_PACK = "cardlab.experiment_pack"

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "secret",
        "token",
        "password",
        "access_token",
        "authorization",
    }
)


def is_secret_field(key: str) -> bool:
    lowered = key.lower()
    if lowered in _SECRET_KEYS:
        return True
    return lowered.endswith("_api_key") or lowered.endswith("_secret")


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Drop secret-looking keys from a flat mapping (e.g. model_config)."""
    return {key: value for key, value in data.items() if not is_secret_field(str(key))}


def sanitize_player(player: dict[str, Any]) -> dict[str, Any]:
    model_cfg = player.get("model_config") or {}
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    return {
        "id": str(player.get("id") or "").strip(),
        "name": str(player.get("name") or player.get("id") or "").strip(),
        "notes": str(player.get("notes") or ""),
        "model_config": redact_mapping(model_cfg),
    }


def sanitize_players(players: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in players:
        if not isinstance(item, dict):
            continue
        cleaned = sanitize_player(item)
        if cleaned["id"]:
            out.append(cleaned)
    return out


def build_requirements(players: list[dict[str, Any]]) -> dict[str, Any]:
    providers: list[str] = []
    ollama_tags: list[str] = []
    seen_providers: set[str] = set()
    seen_tags: set[str] = set()
    for player in players:
        cfg = player.get("model_config") or {}
        if not isinstance(cfg, dict):
            continue
        provider = str(cfg.get("provider") or "").strip()
        model_name = str(cfg.get("model_name") or "").strip()
        if provider and provider not in seen_providers:
            seen_providers.add(provider)
            providers.append(provider)
        if provider == "ollama" and model_name and model_name not in seen_tags:
            seen_tags.add(model_name)
            ollama_tags.append(model_name)
    return {"providers": providers, "ollama_tags": ollama_tags}


def redact_protocol(protocol: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(protocol, dict):
        return None
    out = deepcopy(protocol)
    raw_players = out.get("players") or []
    if isinstance(raw_players, list):
        out["players"] = sanitize_players(raw_players)
    return out


def build_player_pack(players: list[dict[str, Any]], *, exported_at: str) -> dict[str, Any]:
    cleaned = sanitize_players(players)
    return {
        "kind": KIND_PLAYER_PACK,
        "schema_version": PACK_SCHEMA_VERSION,
        "exported_at": exported_at,
        "players": cleaned,
        "requirements": build_requirements(cleaned),
    }


def build_experiment_pack(
    *,
    experiment: dict[str, Any],
    protocol: dict[str, Any] | None,
    players: list[dict[str, Any]],
    exported_at: str,
) -> dict[str, Any]:
    cleaned_players = sanitize_players(players)
    collect_mode = "free"
    deal_seeds: list[int] = []
    if isinstance(protocol, dict):
        collect_mode = str(protocol.get("collect_mode") or "free")
        deal_seeds = [int(s) for s in (protocol.get("deal_seeds") or [])]
    return {
        "kind": KIND_EXPERIMENT_PACK,
        "schema_version": PACK_SCHEMA_VERSION,
        "exported_at": exported_at,
        "experiment": {
            "name": str(experiment.get("name") or "").strip(),
            "notes": str(experiment.get("notes") or ""),
            "hypothesis": str(experiment.get("hypothesis") or ""),
            "tags": list(experiment.get("tags") or []),
            "game_type": str(experiment.get("game_type") or "doudizhu"),
            "player_ids": list(experiment.get("player_ids") or []),
            "target_games": int(experiment.get("target_games") or 1),
            "collect_mode": collect_mode,
        },
        "protocol": redact_protocol(protocol),
        "players": cleaned_players,
        "requirements": build_requirements(cleaned_players),
        "deal_seeds": deal_seeds,
    }


def parse_pack(raw: Any) -> dict[str, Any]:
    """Parse a player or experiment pack into a known kind."""
    if not isinstance(raw, dict):
        raise ValueError("pack must be a JSON object")
    kind = raw.get("kind")
    if kind == KIND_PLAYER_PACK:
        players = sanitize_players(list(raw.get("players") or []))
        if not players:
            raise ValueError("player pack has no players")
        return {
            "kind": KIND_PLAYER_PACK,
            "schema_version": int(raw.get("schema_version") or PACK_SCHEMA_VERSION),
            "players": players,
            "requirements": raw.get("requirements") or build_requirements(players),
        }
    if kind == KIND_EXPERIMENT_PACK or (
        kind is None and isinstance(raw.get("experiment"), dict)
    ):
        experiment = dict(raw.get("experiment") or {})
        protocol = raw.get("protocol") if isinstance(raw.get("protocol"), dict) else None
        players = sanitize_players(list(raw.get("players") or []))
        if not players and isinstance(protocol, dict):
            players = sanitize_players(list(protocol.get("players") or []))
        if not experiment.get("name"):
            raise ValueError("experiment pack is missing a name")
        player_ids = list(experiment.get("player_ids") or [p["id"] for p in players])
        if not player_ids:
            raise ValueError("experiment pack has no player_ids")
        deal_seeds = [int(s) for s in (raw.get("deal_seeds") or [])]
        if not deal_seeds and isinstance(protocol, dict):
            deal_seeds = [int(s) for s in (protocol.get("deal_seeds") or [])]
        collect_mode = str(experiment.get("collect_mode") or "")
        if not collect_mode and isinstance(protocol, dict):
            collect_mode = str(protocol.get("collect_mode") or "free")
        experiment["player_ids"] = player_ids
        experiment["collect_mode"] = collect_mode or "free"
        if not players:
            raise ValueError("experiment pack has no players")
        return {
            "kind": KIND_EXPERIMENT_PACK,
            "schema_version": int(raw.get("schema_version") or PACK_SCHEMA_VERSION),
            "experiment": experiment,
            "protocol": protocol,
            "players": players,
            "deal_seeds": deal_seeds,
            "requirements": raw.get("requirements") or build_requirements(players),
        }
    if isinstance(raw.get("players"), list):
        players = sanitize_players(list(raw["players"]))
        if players:
            return {
                "kind": KIND_PLAYER_PACK,
                "schema_version": PACK_SCHEMA_VERSION,
                "players": players,
                "requirements": build_requirements(players),
            }
    raise ValueError("unrecognized pack (need kind cardlab.player_pack or cardlab.experiment_pack)")
