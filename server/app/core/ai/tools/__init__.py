"""Agent tools for AI decision enhancement.

Game-specific analyzers (e.g. Dou Dizhu hand strength) live under the engine
package; this module keeps game-agnostic helpers and the win-probability heuristic.
"""

from __future__ import annotations

from app.core.ai.tools.serialize import (
    actions_as_dicts,
    explain_from_tools,
)
from app.core.ai.tools.win_probability import WinProbabilityResult, WinProbabilityTool

__all__ = [
    "WinProbabilityResult",
    "WinProbabilityTool",
    "actions_as_dicts",
    "explain_from_tools",
]
