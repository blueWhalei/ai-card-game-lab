"""Player-facing view of a game state.

``Observation`` is what a policy receives. It never carries hidden information,
which is why policies take an ``Observation`` instead of a ``GameState``.

Not to be confused with ``observer_types.ObserverSnapshot``: that one shapes the
UI board (and may reveal every hand in observer mode), this one is the decision
input for policies and the rollout evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Observation:
    """One player's knowledge at a decision point.

    Attributes:
        game_type: Engine identifier.
        phase: Engine phase, e.g. ``bidding`` / ``playing``.
        round: Round counter of the underlying state.
        player_id: The viewer. ``private`` belongs to this player only.
        to_act: Whether it is this player's turn.
        private: Information only the viewer knows (own hand, ...).
        public: Information every player knows (counts, roles, history, ...).
            Must be rich enough for ``GameEngine.sample_hidden_state`` to rebuild a
            full state consistent with this observation.
        text: Engine-rendered prompt text for this viewpoint.
    """

    game_type: str
    phase: str
    round: int
    player_id: str
    to_act: bool
    private: dict[str, Any] = field(default_factory=dict)
    public: dict[str, Any] = field(default_factory=dict)
    text: str = ""
