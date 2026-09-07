"""Deal-seed state replay: rebuild a ``GameState`` from a seed and actions.

The puzzle extractor needs the live state at a past decision point to recompute
gold labels with the current evaluator. A stored decision point is not enough --
it carries no hidden information -- so the extractor replays the deal from the
recorded seed and the ordered action list (see
``docs/designs/step4-puzzle-set.md`` §3.1).

This module is engine-agnostic and lives in ``core/eval`` because the replay
contract (same seed + same actions ⇒ same state) is the foundation under every
puzzle gold label. The service layer is responsible for turning ``rounds`` rows
into ``GameAction`` objects; ``action_from_round_row`` is the engine-agnostic
helper that builds the action body from the row's ``action_type`` / ``cards``
fields. Callers must set ``player_id`` (and, for games that need it, ``target``)
before applying the action.
"""

from __future__ import annotations

from app.core.engine.base import GameAction, GameEngine, GameState


def rebuild_state(
    engine: GameEngine,
    player_ids: list[str],
    seed: int,
    actions: list[GameAction],
) -> GameState:
    """Rebuild the state reached by playing ``actions`` from a seeded deal.

    The engine is the single source of truth for state transitions, so replay
    is just ``initialize`` followed by ``apply_action`` for each recorded move.
    Because engines are deterministic given a seed and an action sequence, the
    rebuilt state is bit-for-bit the state the live game reached -- which is the
    contract the puzzle extractor relies on.

    Args:
        engine: The game engine that produced the original run.
        player_ids: Player ids in the same order used to start the original game.
        seed: The deal seed recorded on the original game.
        actions: The ordered actions played so far. Each must be a legal action
            for the state it was played in; replay re-raises ``InvalidActionError``
            if a recorded action no longer applies (e.g. the engine changed).

    Returns:
        The state after applying every action, or the initial state when
        ``actions`` is empty.
    """
    state = engine.initialize(player_ids, seed=seed)
    for action in actions:
        state = engine.apply_action(state, action)
    return state


def action_from_round_row(action_type: str, cards: list[str] | None) -> GameAction:
    """Build a ``GameAction`` body from a round row's action_type / cards fields.

    The puzzle extractor reads ``rounds`` rows, which store ``action_type`` and
    ``cards`` but not the full ``GameAction`` envelope. This helper converts the
    engine-agnostic pair into a ``GameAction`` with empty ``player_id`` and no
    ``target``; the service layer fills in ``player_id`` (from the row) and, for
    games whose actions carry a target (e.g. Dou Dizhu bidding), the target
    before applying the action. Keeping the helper narrow avoids dragging
    per-game row schemas into ``core/eval``.
    """
    return GameAction(
        player_id="",
        action_type=action_type,
        cards=list(cards) if cards else [],
        target=None,
    )
