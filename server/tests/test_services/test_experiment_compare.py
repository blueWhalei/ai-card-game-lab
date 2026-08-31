"""Tests for cross-experiment comparison aggregates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.trace_repo import TraceRepository
from app.services.experiment_service import ExperimentService


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "exp_bench.db")
    await init_db(path)
    return path


async def _seed_pair(db_path: str) -> tuple[str, str]:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES
                ('exp-base', '基线', '', 'doudizhu', ?, 5, ?, ?),
                ('exp-lora', '对照', '', 'doudizhu', ?, 5, ?, ?)
            """,
            (players, now, now, players, now, now),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, total_rounds,
                data_file, created_at, experiment_id
            ) VALUES
                ('g-base', 'doudizhu', 'finished', ?, 'cfg_a', 20, 'a.jsonl', ?, 'exp-base'),
                ('g-lora', 'doudizhu', 'finished', ?, 'cfg_b', 18, 'b.jsonl', ?, 'exp-lora')
            """,
            (players, now, players, now),
        )
        await db.execute(
            """
            INSERT INTO rounds (
                game_id, round_num, player_id, action_type, prompt_tokens,
                completion_tokens, total_tokens, response_time_ms, created_at
            ) VALUES
                ('g-base', 1, 'cfg_a', 'play', 10, 5, 15, 200, ?),
                ('g-lora', 1, 'cfg_b', 'play', 20, 10, 30, 80, ?)
            """,
            (now, now),
        )
        await db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards, game_phase,
                legal_actions, chosen_action, train_usable, created_at
            ) VALUES
                ('dp-b1', 'g-base', 1, 'cfg_a', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp-b2', 'g-base', 2, 'cfg_a', '[]', 'playing', '[]', '{}', 0, ?),
                ('dp-l1', 'g-lora', 1, 'cfg_b', '[]', 'playing', '[]', '{}', 1, ?)
            """,
            (now, now, now),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        traces = TraceRepository(db)
        await traces.create_trace(
            trace_id="tr-base",
            game_id="g-base",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 200, "used_langchain_parser": 0},
            created_at=now,
        )
        await traces.create_trace(
            trace_id="tr-lora",
            game_id="g-lora",
            round_number=1,
            player_id="cfg_b",
            model="m",
            prompt_version="v2",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 80, "used_langchain_parser": 1},
            created_at=now,
        )
    return "exp-base", "exp-lora"


class _FakeGameService:
    def player_slots(self, game_type: str) -> tuple[int, int]:
        return (3, 3)


async def test_compare_aggregates_rates_and_ci(db_path: str) -> None:
    await _seed_pair(db_path)
    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]
    payload = await service.compare_experiments(["exp-base", "exp-lora"])
    by_id = {item["id"]: item for item in payload["experiments"]}

    base = by_id["exp-base"]
    lora = by_id["exp-lora"]
    assert base["decision_count"] == 2
    assert base["train_usable_rate"] == 0.5
    assert base["parser_success_rate"] == 0.0
    assert base["total_tokens"] == 15
    assert lora["train_usable_rate"] == 1.0
    assert lora["parser_success_rate"] == 1.0
    assert lora["total_tokens"] == 30

    winner_stat = next(s for s in base["player_stats"] if s["player_id"] == "cfg_a")
    low, high = winner_stat["win_rate_ci"]
    assert winner_stat["win_rate"] == 1.0
    assert 0.0 <= low < 1.0
    assert high == 1.0
