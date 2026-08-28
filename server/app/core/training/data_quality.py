"""Heuristics for marking decision points as usable for SFT training.

``quality_score`` on decision points is an end-game outcome proxy (win/lose/draw),
not a measure of reasoning quality. Training filters should use ``train_usable``.
"""

from __future__ import annotations

import re
from typing import Any

# Thinking that clearly signals PASS / skip
_PASS_THINKING = re.compile(
    r"(?:选择)?(?:PASS|过牌|不出|不要|过)\b|选择过|决定过|准备过",
    re.IGNORECASE,
)

# Thinking that clearly signals playing cards (not PASS)
_PLAY_THINKING = re.compile(
    r"(?:出|打出|选择出|决定出).{0,12}(?:单|对|三|顺|炸|牌)|(?:不能|不该|不要)过",
    re.IGNORECASE,
)


def _normalize_cards(cards: Any) -> list[str]:
    if not cards:
        return []
    if not isinstance(cards, list):
        return [str(cards)]
    return sorted(str(c) for c in cards)


def _action_type(action: dict[str, Any] | None) -> str:
    if not action:
        return ""
    raw = action.get("action_type", action.get("type", ""))
    return str(raw).upper().strip()


def _actions_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if _action_type(a) != _action_type(b):
        return False
    return _normalize_cards(a.get("cards")) == _normalize_cards(b.get("cards"))


def evaluate_train_usable(
    *,
    chosen_action: dict[str, Any] | None,
    legal_actions: list[dict[str, Any]] | None,
    thinking: str | None,
) -> tuple[bool, str]:
    """Return whether a decision point is suitable for SFT and a short reason.

    Rules (all must pass for usable=True):
    1. chosen_action is non-empty and matches an entry in legal_actions
    2. Light reasoning-action consistency when thinking is present
    """
    if not chosen_action:
        return False, "empty_chosen_action"

    action_type = _action_type(chosen_action)
    if not action_type:
        return False, "missing_action_type"

    legal = legal_actions or []
    if not legal:
        return False, "empty_legal_actions"

    if not any(_actions_match(chosen_action, la) for la in legal):
        return False, "chosen_not_in_legal_actions"

    text = (thinking or "").strip()
    if text.startswith("[LLM") or "使用默认动作" in text:
        return False, "llm_fallback_action"

    if text:
        is_pass = action_type == "PASS"
        mentions_pass = bool(_PASS_THINKING.search(text))
        mentions_play = bool(_PLAY_THINKING.search(text))

        if mentions_pass and not is_pass and not mentions_play:
            return False, "thinking_pass_action_play"
        if mentions_play and is_pass and not mentions_pass:
            return False, "thinking_play_action_pass"

    return True, "ok"
