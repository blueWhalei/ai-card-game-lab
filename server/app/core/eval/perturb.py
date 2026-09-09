"""Safe presentation perturbations for frozen puzzle packs.

Order shuffles and label/symbol/seat remaps that must not change action ids,
gold labels, or (except ``rotate_seats``) seat identity of the decision.
See ``docs/designs/step4b-robustness-probes.md`` and ``wave6-perturb-extensions.md``.
"""

from __future__ import annotations

import copy
import random
from collections.abc import Sequence
from typing import Any, Literal

from app.core.eval.puzzle import Puzzle

PerturbKind = Literal[
    "shuffle_legal_actions",
    "shuffle_hand_cards",
    "zh_en_labels",
    "card_symbol_style",
    "rotate_seats",
]

DEFAULT_PERTURB_KINDS: tuple[PerturbKind, ...] = (
    "shuffle_legal_actions",
    "shuffle_hand_cards",
)

_KNOWN_KINDS: frozenset[str] = frozenset(
    {
        "shuffle_legal_actions",
        "shuffle_hand_cards",
        "zh_en_labels",
        "card_symbol_style",
        "rotate_seats",
    }
)

_ACTION_LABEL_EN: dict[str, str] = {
    "PASS": "Pass",
    "BID": "Bid",
    "SINGLE": "Single",
    "PAIR": "Pair",
    "TRIPLE": "Triple",
    "BOMB": "Bomb",
    "ROCKET": "Rocket",
    "CHAIN": "Straight",
    "CHAIN_PAIR": "Pair straight",
    "PLANE": "Plane",
}

_ACTION_LABEL_ZH: dict[str, str] = {
    "PASS": "不出",
    "BID": "叫分",
    "SINGLE": "单张",
    "PAIR": "对子",
    "TRIPLE": "三张",
    "BOMB": "炸弹",
    "ROCKET": "火箭",
    "CHAIN": "顺子",
    "CHAIN_PAIR": "连对",
    "PLANE": "飞机",
}

# Rank glyph alternate (ASCII letter/digit ↔ circled / word forms).
_RANK_STYLE_A_TO_B: dict[str, str] = {
    "3": "③",
    "4": "④",
    "5": "⑤",
    "6": "⑥",
    "7": "⑦",
    "8": "⑧",
    "9": "⑨",
    "T": "10",
    "J": "J",
    "Q": "Q",
    "K": "K",
    "A": "A",
    "B": "BJ",
    "R": "RJ",
}
_RANK_STYLE_B_TO_A: dict[str, str] = {v: k for k, v in _RANK_STYLE_A_TO_B.items() if v != k}


def ensure_perturb_kinds(
    kinds: Sequence[str] | None,
) -> list[PerturbKind]:
    """Return validated kinds; ``None`` → defaults. Raises ``ValueError`` if unknown."""
    resolved: list[str] = list(kinds) if kinds is not None else list(DEFAULT_PERTURB_KINDS)
    unknown = [k for k in resolved if k not in _KNOWN_KINDS]
    if unknown:
        raise ValueError(f"Unknown perturb kinds: {unknown}")
    return resolved  # type: ignore[return-value]


def perturb_puzzle(
    puzzle: Puzzle,
    kinds: list[PerturbKind] | tuple[PerturbKind, ...],
    rng: random.Random,
) -> Puzzle:
    """Deep-copy ``puzzle`` and apply whitelist-only presentation remaps.

    Raises:
        ValueError: if ``kinds`` contains an unknown id.
    """
    unknown = [k for k in kinds if k not in _KNOWN_KINDS]
    if unknown:
        raise ValueError(f"Unknown perturb kinds: {unknown}")

    clone = Puzzle.from_dict(copy.deepcopy(puzzle.to_dict()))
    for kind in kinds:
        if kind == "shuffle_legal_actions":
            actions = list(clone.legal_actions)
            rng.shuffle(actions)
            clone.legal_actions = actions
        elif kind == "shuffle_hand_cards":
            observation = copy.deepcopy(clone.observation)
            private = dict(observation.get("private") or {})
            hand = list(private.get("hand_cards") or [])
            rng.shuffle(hand)
            private["hand_cards"] = hand
            observation["private"] = private
            clone.observation = observation
        elif kind == "zh_en_labels":
            clone.legal_actions = [_relabel_action(row) for row in clone.legal_actions]
        elif kind == "card_symbol_style":
            clone.observation = _restyle_cards_in_observation(clone.observation)
        elif kind == "rotate_seats":
            clone.observation = _rotate_seat_ids(clone.observation)
    return clone


def _relabel_action(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    action_type = str((row.get("action") or {}).get("action_type") or row.get("action_type") or "")
    label = str(row.get("label") or "")
    # Prefer switching to the other language family.
    if any("\u4e00" <= ch <= "\u9fff" for ch in label):
        out["label"] = _ACTION_LABEL_EN.get(action_type, action_type or label)
    else:
        out["label"] = _ACTION_LABEL_ZH.get(action_type, label)
    return out


def _restyle_card(card: str) -> str:
    if not card:
        return card
    # Suit+rank (e.g. C3, ST) or bare rank.
    if len(card) >= 2 and card[0] in "CDHS" and card[1:] in _RANK_STYLE_A_TO_B:
        return card[0] + _RANK_STYLE_A_TO_B[card[1:]]
    if card in _RANK_STYLE_A_TO_B:
        return _RANK_STYLE_A_TO_B[card]
    if card in _RANK_STYLE_B_TO_A:
        return _RANK_STYLE_B_TO_A[card]
    if len(card) >= 2 and card[0] in "CDHS":
        rest = card[1:]
        if rest in _RANK_STYLE_B_TO_A:
            return card[0] + _RANK_STYLE_B_TO_A[rest]
    return card


def _restyle_cards_in_observation(observation: dict[str, Any]) -> dict[str, Any]:
    obs = copy.deepcopy(observation)
    private = dict(obs.get("private") or {})
    hand = private.get("hand_cards")
    if isinstance(hand, list):
        private["hand_cards"] = [_restyle_card(str(c)) for c in hand]
        obs["private"] = private
    public = dict(obs.get("public") or {})
    history = public.get("play_history")
    if isinstance(history, list):
        new_hist: list[Any] = []
        for entry in history:
            if not isinstance(entry, dict):
                new_hist.append(entry)
                continue
            item = dict(entry)
            cards = item.get("cards")
            if isinstance(cards, list):
                item["cards"] = [_restyle_card(str(c)) for c in cards]
            new_hist.append(item)
        public["play_history"] = new_hist
        obs["public"] = public
    return obs


def _collect_seat_ids(observation: dict[str, Any]) -> list[str]:
    seats: list[str] = []
    pid = observation.get("player_id")
    if isinstance(pid, str) and pid:
        seats.append(pid)
    public = observation.get("public") or {}
    if isinstance(public, dict):
        for key in ("turn_order", "player_ids"):
            raw = public.get(key)
            if isinstance(raw, list):
                for item in raw:
                    s = str(item)
                    if s and s not in seats:
                        seats.append(s)
        counts = public.get("hand_counts")
        if isinstance(counts, dict):
            for key in counts:
                s = str(key)
                if s and s not in seats:
                    seats.append(s)
    return seats


def _rotate_seat_ids(observation: dict[str, Any]) -> dict[str, Any]:
    seats = _collect_seat_ids(observation)
    if len(seats) < 2:
        return copy.deepcopy(observation)
    mapping = {seats[i]: seats[(i + 1) % len(seats)] for i in range(len(seats))}
    obs = copy.deepcopy(observation)
    if isinstance(obs.get("player_id"), str):
        obs["player_id"] = mapping.get(str(obs["player_id"]), obs["player_id"])
    public = dict(obs.get("public") or {})
    for key in ("turn_order", "player_ids"):
        raw = public.get(key)
        if isinstance(raw, list):
            public[key] = [mapping.get(str(x), x) for x in raw]
    counts = public.get("hand_counts")
    if isinstance(counts, dict):
        public["hand_counts"] = {mapping.get(str(k), str(k)): v for k, v in counts.items()}
    history = public.get("play_history")
    if isinstance(history, list):
        new_hist = []
        for entry in history:
            if not isinstance(entry, dict):
                new_hist.append(entry)
                continue
            item = dict(entry)
            if "player_id" in item:
                item["player_id"] = mapping.get(str(item["player_id"]), item["player_id"])
            new_hist.append(item)
        public["play_history"] = new_hist
    obs["public"] = public
    return obs
