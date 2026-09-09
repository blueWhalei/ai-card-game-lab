"""Safe presentation perturbations for frozen puzzle packs.

Order shuffles that must not change action ids, gold labels, or temporal /
seat semantics. See ``docs/designs/step4b-robustness-probes.md``.
"""

from __future__ import annotations

import copy
import random
from collections.abc import Sequence
from typing import Literal

from app.core.eval.puzzle import Puzzle

PerturbKind = Literal["shuffle_legal_actions", "shuffle_hand_cards"]

DEFAULT_PERTURB_KINDS: tuple[PerturbKind, ...] = (
    "shuffle_legal_actions",
    "shuffle_hand_cards",
)

_KNOWN_KINDS: frozenset[str] = frozenset(DEFAULT_PERTURB_KINDS)


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
    """Deep-copy ``puzzle`` and apply whitelist-only order shuffles.

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
    return clone
