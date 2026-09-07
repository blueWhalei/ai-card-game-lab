"""Engine-declared analysis tools.

Tools belong to the engine, not to a policy: only the engine knows what a hand
is worth or how a playout unfolds. A policy sees a name and a JSON Schema and
forwards the call, which keeps ``core/policy`` free of game semantics.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.engine.observation import Observation

ToolHandler = Callable[[Observation, dict[str, Any]], dict[str, Any]]


def _empty_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}}


@dataclass(frozen=True)
class ToolSpec:
    """One callable analysis tool exposed to policies.

    Attributes:
        name: Stable identifier used in prompts, traces, and tool-call payloads.
        description: Shown to the model; explains when the tool helps.
        parameters: JSON Schema for the arguments object.
        handler: Runs the tool. Must return a JSON-safe dict and must not mutate
            the observation. A ``text`` key, when present, is the one-line human
            rendering a policy injects into its prompt; everything else is
            structured detail for traces and the UI.
        phases: Phases this tool applies to. Empty means every phase. Declaring it
            here is what keeps phase names out of ``core/policy``: a win-rate
            estimate is meaningless before roles exist, and only the engine knows
            that.
    """

    name: str
    description: str
    handler: ToolHandler
    parameters: dict[str, Any] = field(default_factory=_empty_schema)
    phases: tuple[str, ...] = ()

    def applies_to(self, phase: str) -> bool:
        return not self.phases or phase in self.phases

    def to_public_dict(self) -> dict[str, Any]:
        """JSON-safe view (the handler is not serializable)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
            "phases": list(self.phases),
        }
