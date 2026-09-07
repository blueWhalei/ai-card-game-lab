"""Coverage of a benchmark experiment's declared deal seeds.

The product number is the declared set written at create time
(``protocol.deal_seeds``). Extra games outside that set are counted but
never added to the denominator.
"""

from __future__ import annotations

from typing import Any

_ACTIVE_STATUSES = frozenset({"created", "running", "paused", "pending"})
_FAILED_STATUSES = frozenset({"failed", "cancelled", "interrupted", "error"})


def build_benchmark_coverage(
    *,
    protocol: dict[str, Any] | None,
    games: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return seed coverage for a benchmark run, or ``None`` otherwise."""
    if not isinstance(protocol, dict):
        return None
    if str(protocol.get("collect_mode") or "") != "benchmark":
        return None

    declared = _declared_seeds(protocol)
    seed_total = len(declared)
    declared_set = set(declared)
    latest_by_seed: dict[int, str] = {}
    extra_games = 0

    for game in games:
        seed = _deal_seed(game)
        if seed is None or seed not in declared_set:
            extra_games += 1
            continue
        # Games are listed in chronological order; later rows win for coverage.
        latest_by_seed[seed] = _status_of(game)

    seed_started = len(latest_by_seed)
    seed_running = sum(1 for status in latest_by_seed.values() if status == "running")
    seed_failed = sum(1 for status in latest_by_seed.values() if status == "failed")
    seed_finished = sum(1 for status in latest_by_seed.values() if status in {"finished", "failed"})
    seed_remaining = max(0, seed_total - seed_started)
    complete = seed_total > 0 and seed_remaining == 0 and seed_running == 0

    return {
        "seed_total": seed_total,
        "seed_started": seed_started,
        "seed_finished": seed_finished,
        "seed_failed": seed_failed,
        "seed_running": seed_running,
        "seed_remaining": seed_remaining,
        "extra_games": extra_games,
        "complete": complete,
    }


def _declared_seeds(protocol: dict[str, Any]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for raw in protocol.get("deal_seeds") or []:
        seed = int(raw)
        if seed in seen:
            continue
        seen.add(seed)
        ordered.append(seed)
    return ordered


def _deal_seed(game: dict[str, Any]) -> int | None:
    meta = game.get("metadata")
    if isinstance(meta, str):
        import json

        try:
            parsed = json.loads(meta)
        except json.JSONDecodeError:
            return None
        meta = parsed
    if not isinstance(meta, dict):
        return None
    raw = meta.get("deal_seed")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _status_of(game: dict[str, Any]) -> str:
    status = str(game.get("status") or "")
    if status in _ACTIVE_STATUSES:
        return "running"
    if status in _FAILED_STATUSES:
        return "failed"
    return "finished"
