"""Rendering legal actions as a menu the model picks an id from.

The prompt and the JSON Schema ``enum`` must offer exactly the same set: an id
the model never saw is one it cannot reasonably choose, and an id in the menu
but not the enum is one the decoder will refuse. Both come from here.
"""

from __future__ import annotations

from app.core.engine.base import ActionId, LegalAction

EMPTY_MENU = "无可选动作"


def render_menu(actions: list[LegalAction], omitted: int = 0) -> str:
    """One line per action: the id to echo back, then the human label."""
    if not actions:
        return EMPTY_MENU

    lines = [f"{index}. `{entry.id}` — {entry.label}" for index, entry in enumerate(actions, 1)]
    if omitted > 0:
        lines.append(f"（另有 {omitted} 个同类动作未列出，只能从上面选）")
    return "\n".join(lines)


def action_ids(actions: list[LegalAction]) -> list[ActionId]:
    return [entry.id for entry in actions]
