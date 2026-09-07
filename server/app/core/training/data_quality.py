"""Whether a decision point is a well-formed SFT sample.

This is a **structural** test, not a judgement of the move: a legal but weak play
is still a valid sample, and whether you want it is what ``ev_loss`` is for.
"""

from __future__ import annotations

from collections.abc import Sequence


def evaluate_train_usable(
    *,
    action_id: str | None,
    legal_action_ids: Sequence[str] | None,
    prompt_messages: Sequence[dict[str, str]] | None,
    parse_fallback: bool = False,
) -> tuple[bool, str]:
    """Return whether a decision point can be trained on, and a short reason.

    A sample is the prompt the model saw plus the reply it should have given, so
    it needs all three of: a recorded prompt, an action id, and that id being one
    the menu actually offered. ``parse_fallback`` means the model did not pick
    this move at all -- the policy rescued the game, and a rescue is not evidence
    about the model.
    """
    if parse_fallback:
        return False, "rescue_action"
    if not prompt_messages:
        return False, "no_prompt_recorded"
    if not action_id:
        return False, "no_action_id"
    if not legal_action_ids:
        return False, "no_legal_actions"
    if action_id not in legal_action_ids:
        return False, "action_id_not_legal"
    return True, "ok"
