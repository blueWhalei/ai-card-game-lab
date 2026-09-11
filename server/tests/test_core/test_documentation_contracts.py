"""Execute the documented engine and enforce the API dependency boundary."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.core.engine.base import GameAction, GameEngine
from app.utils.exceptions import InvalidActionError

ROOT = Path(__file__).resolve().parents[3]


def test_api_does_not_import_core_or_repositories() -> None:
    violations = []
    for path in (ROOT / "server/app/api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
                if node.module == "app":
                    modules.extend(f"app.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            for module in modules:
                if module in {"app.core", "app.repositories"} or module.startswith(
                    ("app.core.", "app.repositories.")
                ):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
    assert not violations, "\n".join(violations)


@pytest.fixture
def documented_engine(monkeypatch: pytest.MonkeyPatch) -> GameEngine:
    source = (ROOT / "docs/EXAMPLES.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)\n```", source, re.DOTALL)
    for name, marker in (
        ("state", "class GuessNumberState"),
        ("engine", "class GuessNumberEngine"),
    ):
        code = next(block for block in blocks if marker in block)
        module_name = f"app.core.engine.guess_number.{name}"
        module = ModuleType(module_name)
        monkeypatch.setitem(sys.modules, module_name, module)
        exec(compile(code, f"docs/EXAMPLES.md:{name}", "exec"), module.__dict__)
    engine = module.__dict__["GuessNumberEngine"]()
    assert isinstance(engine, GameEngine)
    return engine


def test_documented_engine_plays_through_action_ids(documented_engine: GameEngine) -> None:
    engine = documented_engine
    state = engine.initialize(["p1", "p2"])
    for _ in range(10):
        player = engine.get_current_player(state)
        observation = engine.observe(state, player)
        public = engine.get_public_info(state, "observer", is_observer=True)
        assert "target_number" not in public
        assert observation.player_id == player
        actions = engine.legal_actions(state, player)
        assert len({action.id for action in actions}) == len(actions)
        for entry in actions:
            assert engine.resolve_action(state, player, entry.id) == entry.action
        # Binary search using only the public remaining range.
        chosen = actions[len(actions) // 2]
        previous_round = state.round
        next_state = engine.apply_action(state, engine.resolve_action(state, player, chosen.id))
        assert state.round == previous_round
        assert next_state is not state
        state = next_state
        if engine.is_terminal(state):
            break
    assert engine.is_terminal(state)
    assert engine.get_winner(state) in {"p1", "p2"}
    assert engine.legal_actions(state, engine.get_current_player(state)) == []


def test_documented_engine_rejects_illegal_actions(documented_engine: GameEngine) -> None:
    state = documented_engine.initialize(["p1", "p2"])
    for action in (
        GameAction(player_id="p1", action_type="guess"),
        GameAction(player_id="p2", action_type="guess", target="50"),
        GameAction(player_id="p1", action_type="guess", target="101"),
    ):
        with pytest.raises(InvalidActionError):
            documented_engine.apply_action(state, action)
