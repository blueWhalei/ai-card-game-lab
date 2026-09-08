"""PuzzleService.extract: freeze high-spread positions from experiment games."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.engine.registry import GameEngineRegistry
from app.core.eval.puzzle import load_pack
from app.core.eval.rollout import EvaluatorParams
from app.core.policy import HeuristicPolicy, PolicyContext
from app.database import connect_sqlite, init_db
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.services.puzzle_service import PuzzleService, match_recorded_action

_FAST = EvaluatorParams(
    determinizations=1,
    rollouts_per_world=1,
    max_candidates=2,
    max_steps=200,
)


@pytest.fixture
async def extract_env(tmp_path: Path) -> tuple[PuzzleService, str, Path]:
    db_path = str(tmp_path / "puzzle.db")
    await init_db(db_path)
    puzzle_dir = tmp_path / "puzzles"
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    service = PuzzleService(
        sqlite_path=db_path,
        puzzle_dir=str(puzzle_dir),
        engine_registry=registry,
    )
    return service, db_path, puzzle_dir


async def _insert_experiment(db_path: str, experiment_id: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with connect_sqlite(db_path) as db:
        await ExperimentRepository(db).create(
            experiment_id=experiment_id,
            name="puzzle extract",
            notes="",
            game_type="doudizhu",
            player_ids=["p1", "p2", "p3"],
            target_games=1,
            created_at=now,
            updated_at=now,
        )


def _play_plies(
    engine: DoudizhuEngine,
    n: int,
    *,
    seed: int,
    players: list[str],
    rng: random.Random,
) -> list[tuple[int, object, str]]:
    """Return (pre_round, action, action_id) for *n* heuristic plies."""
    policy = HeuristicPolicy()
    ctx = PolicyContext(advisor=engine, rng=rng)
    state = engine.initialize(players, seed=seed)
    recorded: list[tuple[int, object, str]] = []
    for _ in range(n):
        if engine.is_terminal(state):
            break
        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        if not legal:
            break
        chosen_id = policy.choose(engine.observe(state, player_id), legal, ctx)
        action = next(la.action for la in legal if la.id == chosen_id)
        recorded.append((int(state.round), action, chosen_id))
        state = engine.apply_action(state, action)
    return recorded


async def test_extract_empty_experiment_returns_zero(
    extract_env: tuple[PuzzleService, str, Path],
) -> None:
    service, db_path, puzzle_dir = extract_env
    await _insert_experiment(db_path, "exp-empty")

    manifest = await service.extract("exp-empty")

    assert manifest.puzzle_count == 0
    assert manifest.source_experiment_id == "exp-empty"
    assert manifest.pack_id.startswith("exp_exp-empt_")
    packed, puzzles = load_pack(puzzle_dir / manifest.pack_id)
    assert packed.puzzle_count == 0
    assert puzzles == []


async def test_extract_seeded_short_game_yields_puzzle(
    extract_env: tuple[PuzzleService, str, Path],
) -> None:
    service, db_path, puzzle_dir = extract_env
    experiment_id = "exp-seeded-short"
    game_id = "g-seeded"
    players = ["p1", "p2", "p3"]
    seed = 42
    now = datetime.now(tz=UTC).isoformat()

    engine = DoudizhuEngine()
    recorded = _play_plies(engine, 6, seed=seed, players=players, rng=random.Random(7))
    assert recorded, "heuristic should play at least one ply"

    await _insert_experiment(db_path, experiment_id)
    async with connect_sqlite(db_path) as db:
        await GameRepository(db).create(
            game_id=game_id,
            game_type="doudizhu",
            player_ids=players,
            data_file="seeded.jsonl",
            created_at=now,
            status="finished",
            metadata={"deal_seed": seed},
            experiment_id=experiment_id,
        )
        rounds = RoundRepository(db)
        for pre_round, action, action_id in recorded:
            await rounds.create(
                {
                    "game_id": game_id,
                    "round_num": pre_round + 1,
                    "player_id": action.player_id,
                    "action_type": str(action.action_type),
                    "cards": list(action.cards or []),
                    "created_at": now,
                }
            )
            await db.execute(
                """
                INSERT INTO decision_points (
                    id, game_id, round_number, player_id, hand_cards,
                    game_phase, legal_actions, chosen_action, action_id, created_at
                ) VALUES (?, ?, ?, ?, '[]', 'playing', '[]', '{}', ?, ?)
                """,
                (
                    f"dp-{pre_round}-{action.player_id}",
                    game_id,
                    pre_round,
                    action.player_id,
                    action_id,
                    now,
                ),
            )
        await db.commit()

    manifest = await service.extract(
        experiment_id,
        min_spread=0.0,
        max_per_game=5,
        max_total=20,
        evaluator_params=_FAST,
    )

    assert manifest.puzzle_count >= 1
    _, puzzles = load_pack(puzzle_dir / manifest.pack_id)
    assert len(puzzles) == manifest.puzzle_count
    assert all(p.source["game_id"] == game_id for p in puzzles)
    assert all(p.source["experiment_id"] == experiment_id for p in puzzles)
    assert all(p.best_action_id for p in puzzles)


def test_match_recorded_bid_uses_legal_action_target() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["p1", "p2", "p3"], seed=42)
    actor = engine.get_current_player(state)

    ambiguous = match_recorded_action(
        engine,
        state,
        player_id=actor,
        action_type="BID",
        cards=[],
        dp_action_id="",
    )
    assert ambiguous is None

    matched = match_recorded_action(
        engine,
        state,
        player_id=actor,
        action_type="BID",
        cards=[],
        dp_action_id="BID||3",
    )
    assert matched is not None
    assert str(matched.action_type) == "BID"
    assert matched.target == "3"
    assert matched.player_id == actor


async def test_extract_skips_game_without_deal_seed(
    extract_env: tuple[PuzzleService, str, Path],
) -> None:
    service, db_path, _puzzle_dir = extract_env
    experiment_id = "exp-no-seed"
    now = datetime.now(tz=UTC).isoformat()
    await _insert_experiment(db_path, experiment_id)
    async with connect_sqlite(db_path) as db:
        await GameRepository(db).create(
            game_id="g-no-seed",
            game_type="doudizhu",
            player_ids=["p1", "p2", "p3"],
            data_file="none.jsonl",
            created_at=now,
            status="finished",
            metadata={},
            experiment_id=experiment_id,
        )

    manifest = await service.extract(experiment_id, min_spread=0.0)
    assert manifest.puzzle_count == 0
