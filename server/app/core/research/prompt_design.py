"""Frozen Prompt A/B design identity and exact comparison declarations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.policy.kinds import LLM_POLICY_KINDS
from app.core.task_protocol import prompt_content_hash


def baseline_fingerprint(row: dict[str, Any]) -> str:
    identity = {
        key: row.get(key)
        for key in ("id", "study_id", "game_type", "player_ids", "target_games", "protocol")
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def affected_player_ids(protocol: dict[str, Any]) -> list[str]:
    """Seats configured to consume the shared phase template, in frozen seat order."""
    return [
        player["id"]
        for player in (protocol.get("solver") or {}).get("players", [])
        if player.get("id") and player.get("policy_kind") in LLM_POLICY_KINDS
    ]


def paired_design(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(rows) == 2:
        for variant, baseline in (rows, list(reversed(rows))):
            protocol = variant.get("protocol") or {}
            design = protocol.get("design") or {}
            if (
                design.get("kind") == "prompt_ab"
                and design.get("baseline_id") == baseline["id"]
                and (protocol.get("dataset") or {}).get("source_experiment_id") == baseline["id"]
            ):
                return design
    return None


def declared_prompt_changes(rows: list[dict[str, Any]]) -> list[str]:
    """Only the recorded pair and matching frozen bodies receive declarations."""
    design = paired_design(rows)
    if design is None:
        return []
    baseline, variant = rows
    if baseline["id"] != design["baseline_id"]:
        baseline, variant = variant, baseline
    protocol = variant["protocol"]
    key = design.get("template_key")
    if not isinstance(key, str):
        return []
    a = ((baseline.get("protocol") or {}).get("solver") or {}).get("prompts", {}).get(key)
    b = (protocol.get("solver") or {}).get("prompts", {}).get(key)
    if not isinstance(a, dict) or not isinstance(b, dict):
        return []
    if any(
        not isinstance(entry.get("content"), str)
        or prompt_content_hash(entry["content"]) != design.get(f"{label}_hash")
        or entry.get("content_hash") != design.get(f"{label}_hash")
        for label, entry in (("baseline", a), ("variant", b))
    ):
        return []
    return [f"solver.prompts.{key}.{field}" for field in ("version", "content", "content_hash")]
