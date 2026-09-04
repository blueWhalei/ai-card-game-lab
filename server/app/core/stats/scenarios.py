"""Scenario buckets for experiment contrast (not a separate eval harness).

Decision points already store ``game_phase``. Dou Dizhu engines only emit
``bidding`` / ``playing``; residual-hand size and bomb/rocket actions are
derived so contrast can split 叫分 / 出牌 / 残局 / 炸弹.

Buckets are mutually exclusive, in this order:

1. bidding
2. bomb (BOMB / ROCKET)
3. endgame (stored ``endgame``, or own hand 1–``ENDGAME_MAX_HAND`` cards)
4. playing
"""

from __future__ import annotations

from typing import Any

ENDGAME_MAX_HAND = 8
SCENARIO_IDS: tuple[str, ...] = ("bidding", "playing", "endgame", "bomb")

_BID_ACTIONS = frozenset({"BID", "BID_PASS"})
_BOMB_ACTIONS = frozenset({"BOMB", "ROCKET"})

SCENARIO_SQL = f"""
CASE
  WHEN dp.game_phase = 'bidding'
    OR json_extract(dp.chosen_action, '$.action_type') IN ('BID', 'BID_PASS')
    THEN 'bidding'
  WHEN json_extract(dp.chosen_action, '$.action_type') IN ('BOMB', 'ROCKET')
    THEN 'bomb'
  WHEN dp.game_phase = 'endgame'
    OR json_array_length(dp.hand_cards) BETWEEN 1 AND {ENDGAME_MAX_HAND}
    THEN 'endgame'
  ELSE 'playing'
END
""".strip()


def classify_game_phase(*, engine_phase: str, hand_sizes: list[int]) -> str:
    """Label stored ``game_phase`` (bidding / playing / endgame)."""
    phase = (engine_phase or "").strip() or "playing"
    if phase == "bidding":
        return "bidding"
    positive = [n for n in hand_sizes if n > 0]
    if positive and min(positive) <= ENDGAME_MAX_HAND:
        return "endgame"
    if phase in {"playing", "early", "mid", "unknown"}:
        return "playing"
    return phase


def classify_scenario(
    *,
    game_phase: str,
    hand_size: int,
    action_type: str | None = None,
) -> str:
    """Mirror of ``SCENARIO_SQL`` for tests and write-path documentation."""
    phase = (game_phase or "").strip()
    action = (action_type or "").upper()
    if phase == "bidding" or action in _BID_ACTIONS:
        return "bidding"
    if action in _BOMB_ACTIONS:
        return "bomb"
    if phase == "endgame" or 1 <= hand_size <= ENDGAME_MAX_HAND:
        return "endgame"
    return "playing"


def empty_scenario_bucket() -> dict[str, Any]:
    return {
        "n": 0,
        "train_usable_n": 0,
        "train_usable_rate": 0.0,
        "parser_n": 0,
        "parser_ok": 0,
        "parser_success_rate": 0.0,
    }


def fill_scenario_scores(grouped: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    """Always return all four buckets; unknown keys merge into playing."""
    out = {sid: empty_scenario_bucket() for sid in SCENARIO_IDS}
    for sid, raw in grouped.items():
        key = sid if sid in out else "playing"
        n = int(raw.get("n") or 0)
        usable = int(raw.get("train_usable_n") or 0)
        parser_n = int(raw.get("parser_n") or 0)
        parser_ok = int(raw.get("parser_ok") or 0)
        prev = out[key]
        n_total = int(prev["n"]) + n
        usable_total = int(prev["train_usable_n"]) + usable
        parser_total = int(prev["parser_n"]) + parser_n
        parser_ok_total = int(prev["parser_ok"]) + parser_ok
        out[key] = {
            "n": n_total,
            "train_usable_n": usable_total,
            "train_usable_rate": round((usable_total / n_total) if n_total else 0.0, 4),
            "parser_n": parser_total,
            "parser_ok": parser_ok_total,
            "parser_success_rate": round(
                (parser_ok_total / parser_total) if parser_total else 0.0, 4
            ),
        }
    return out


def _bucket_or_empty(scores: dict[str, dict[str, Any]] | None, sid: str) -> dict[str, Any]:
    if scores and isinstance(scores.get(sid), dict):
        return scores[sid]
    return empty_scenario_bucket()


def scenario_rate_diffs(
    this_scores: dict[str, dict[str, Any]] | None,
    peer_scores: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """This minus peer, per scenario. Diff is null when either side has n=0."""
    diffs: dict[str, dict[str, Any]] = {}
    for sid in SCENARIO_IDS:
        this_b = _bucket_or_empty(this_scores, sid)
        peer_b = _bucket_or_empty(peer_scores, sid)
        this_n = int(this_b.get("n") or 0)
        peer_n = int(peer_b.get("n") or 0)
        this_parser_n = int(this_b.get("parser_n") or 0)
        peer_parser_n = int(peer_b.get("parser_n") or 0)
        train_diff: float | None = None
        parser_diff: float | None = None
        if this_n > 0 and peer_n > 0:
            train_diff = round(
                float(this_b.get("train_usable_rate") or 0.0)
                - float(peer_b.get("train_usable_rate") or 0.0),
                4,
            )
        if this_parser_n > 0 and peer_parser_n > 0:
            parser_diff = round(
                float(this_b.get("parser_success_rate") or 0.0)
                - float(peer_b.get("parser_success_rate") or 0.0),
                4,
            )
        diffs[sid] = {
            "this_n": this_n,
            "peer_n": peer_n,
            "train_usable_rate_diff": train_diff,
            "parser_success_rate_diff": parser_diff,
        }
    return diffs
