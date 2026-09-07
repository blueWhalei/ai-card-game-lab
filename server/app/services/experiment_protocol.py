"""Protocol builders and collect-time deal-seed selection."""

from __future__ import annotations

import secrets
from typing import Any

PROTOCOL_SCHEMA_VERSION = 1


def build_protocol(
    *,
    players: list[dict[str, Any]],
    source_experiment_id: str | None,
    pair_deals: bool,
    deal_seeds: list[int],
    frozen_at: str,
    prompt_version: str,
    collect_mode: str,
    protocol_fingerprint: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the frozen experiment protocol written at create time."""
    protocol: dict[str, Any] = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "frozen_at": frozen_at,
        "prompt_version": prompt_version,
        "players": players,
        "source_experiment_id": source_experiment_id,
        "pair_deals": pair_deals,
        "deal_seeds": list(deal_seeds),
        "collect_mode": collect_mode,
    }
    protocol.update(protocol_fingerprint)
    return protocol


def clamp_benchmark_collect_count(
    *,
    deal_seeds: list[int],
    start_index: int,
    count: int,
) -> int:
    """Limit a benchmark collect batch to remaining declared seeds.

    Raises ``ValueError`` when no seeds remain (caller maps to validation error).
    """
    remaining_seeds = max(0, len(deal_seeds) - start_index)
    if remaining_seeds == 0:
        raise ValueError("基准测试的固定发牌种子已用完，不能再开新对局")
    return min(count, remaining_seeds)


def pick_collect_seed(
    *,
    index: int,
    deal_seeds: list[int],
    pair_deals: bool,
    collect_mode: str,
) -> tuple[int, bool]:
    """Choose the deal seed for one collect slot.

    Mutates ``deal_seeds`` when free-mode appends a random seed (pair/compare log).
    Returns ``(seed, paired)``.
    """
    if pair_deals and index < len(deal_seeds):
        return deal_seeds[index], True
    if collect_mode == "benchmark" and index < len(deal_seeds):
        return deal_seeds[index], False

    seed = secrets.randbits(31)
    if index < len(deal_seeds):
        deal_seeds[index] = seed
    else:
        deal_seeds.append(seed)
    return seed, False
