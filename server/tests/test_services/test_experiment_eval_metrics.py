"""Experiment evaluation metrics: landlord metadata, summary, compare."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.game_repo import GameRepository
from app.repositories.trace_repo import TraceRepository
from app.services.experiment_service import ExperimentService


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "exp_eval.db")
    await init_db(path)
    return path


class _FakeGameService:
    def player_slots(self, game_type: str) -> tuple[int, int]:
        return (3, 3)


async def test_update_result_merges_landlord_id_preserves_deal_seed(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, data_file, created_at, metadata
            ) VALUES (?, 'doudizhu', 'running', ?, 'a.jsonl', ?, ?)
            """,
            (
                "g-meta",
                players,
                now,
                json.dumps({"deal_seed": 42, "paired": True}),
            ),
        )
        await db.commit()
        repo = GameRepository(db)
        await repo.update_result(
            "g-meta",
            winner_id="cfg_a",
            winner_role="landlord",
            total_rounds=12,
            finished_at=now,
            metadata_patch={"landlord_id": "cfg_a"},
        )
        cursor = await db.execute("SELECT metadata, winner_role FROM games WHERE id = ?", ("g-meta",))
        row = await cursor.fetchone()
        assert row is not None
        meta = json.loads(row["metadata"])
        assert meta["deal_seed"] == 42
        assert meta["paired"] is True
        assert meta["landlord_id"] == "cfg_a"
        assert row["winner_role"] == "landlord"


async def test_summary_eval_metrics_and_seat_landlord_win_rate(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES (?, ?, '', 'doudizhu', ?, 5, ?, ?)
            """,
            ("exp-eval", "eval", players, now, now),
        )
        # g1: cfg_a landlord wins; g2: cfg_b landlord loses (peasant wins)
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, winner_role,
                total_rounds, data_file, created_at, experiment_id, metadata
            ) VALUES
                ('g1', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord', 10, 'a.jsonl', ?, 'exp-eval', ?),
                ('g2', 'doudizhu', 'finished', ?, 'cfg_a', 'peasant', 8, 'b.jsonl', ?, 'exp-eval', ?),
                ('g3', 'doudizhu', 'failed', ?, NULL, NULL, NULL, 'c.jsonl', ?, 'exp-eval', NULL)
            """,
            (
                players,
                now,
                json.dumps({"landlord_id": "cfg_a", "deal_seed": 1}),
                players,
                now,
                json.dumps({"landlord_id": "cfg_b", "deal_seed": 2}),
                players,
                now,
            ),
        )
        await db.execute(
            """
            INSERT INTO rounds (
                game_id, round_num, player_id, action_type, prompt_tokens,
                completion_tokens, total_tokens, response_time_ms, created_at
            ) VALUES
                ('g1', 1, 'cfg_a', 'play', 10, 5, 100, 100, ?),
                ('g1', 2, 'cfg_b', 'play', 10, 5, 100, 200, ?),
                ('g2', 1, 'cfg_a', 'play', 10, 5, 100, 300, ?)
            """,
            (now, now, now),
        )
        await db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards, game_phase,
                legal_actions, chosen_action, train_usable, created_at
            ) VALUES
                ('dp1', 'g1', 1, 'cfg_a', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp2', 'g1', 2, 'cfg_b', '[]', 'playing', '[]', '{}', 0, ?)
            """,
            (now, now),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        traces = TraceRepository(db)
        await traces.create_trace(
            trace_id="tr1",
            game_id="g1",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"used_langchain_parser": 1},
            created_at=now,
        )
        await traces.create_trace(
            trace_id="tr2",
            game_id="g2",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"used_langchain_parser": 0},
            created_at=now,
        )

    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]
    detail = await service.get_experiment("exp-eval")
    summary = detail["summary"]

    assert summary["wins_by_role"] == {"landlord": 1, "peasant": 1}
    assert summary["decisive_games"] == 2
    assert summary["landlord_win_rate"] == 0.5
    assert summary["parser_success_rate"] == 0.5
    assert summary["parser_n"] == 2
    assert summary["p50_response_ms"] == 200.0
    assert summary["p95_response_ms"] == 300.0
    assert summary["total_tokens"] == 300
    assert summary["tokens_per_game"] == 150.0  # 300 / 2 finished
    assert summary["status_counts"]["finished"] == 2
    assert summary["status_counts"]["failed"] == 1

    by_pid = {s["player_id"]: s for s in summary["player_stats"]}
    assert by_pid["cfg_a"]["games_as_landlord"] == 1
    assert by_pid["cfg_a"]["wins_as_landlord"] == 1
    assert by_pid["cfg_a"]["landlord_win_rate"] == 1.0
    assert by_pid["cfg_b"]["games_as_landlord"] == 1
    assert by_pid["cfg_b"]["wins_as_landlord"] == 0
    assert by_pid["cfg_b"]["landlord_win_rate"] == 0.0
    assert by_pid["cfg_c"]["games_as_landlord"] == 0


async def test_compare_eval_fields_and_paired_landlord_win_rate(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    protocol_base = json.dumps(
        {
            "schema_version": 1,
            "frozen_at": now,
            "prompt_version": "v1",
            "players": [],
            "source_experiment_id": None,
            "pair_deals": True,
            "deal_seeds": [10, 20],
        }
    )
    protocol_ctrl = json.dumps(
        {
            "schema_version": 1,
            "frozen_at": now,
            "prompt_version": "v1",
            "players": [],
            "source_experiment_id": "exp-base",
            "pair_deals": True,
            "deal_seeds": [10, 20],
        }
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games,
                created_at, updated_at, protocol
            ) VALUES
                ('exp-base', '基线', '', 'doudizhu', ?, 5, ?, ?, ?),
                ('exp-ctrl', '对照', '', 'doudizhu', ?, 5, ?, ?, ?)
            """,
            (players, now, now, protocol_base, players, now, now, protocol_ctrl),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, winner_role,
                total_rounds, data_file, created_at, experiment_id, metadata
            ) VALUES
                ('gb1', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord', 10, 'a.jsonl', ?, 'exp-base', ?),
                ('gb2', 'doudizhu', 'finished', ?, 'cfg_b', 'peasant', 10, 'b.jsonl', ?, 'exp-base', ?),
                ('gc1', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord', 10, 'c.jsonl', ?, 'exp-ctrl', ?),
                ('gc2', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord', 10, 'd.jsonl', ?, 'exp-ctrl', ?)
            """,
            (
                players,
                now,
                json.dumps({"deal_seed": 10, "landlord_id": "cfg_a", "paired": True}),
                players,
                now,
                json.dumps({"deal_seed": 20, "landlord_id": "cfg_b", "paired": True}),
                players,
                now,
                json.dumps({"deal_seed": 10, "landlord_id": "cfg_a", "paired": True}),
                players,
                now,
                json.dumps({"deal_seed": 20, "landlord_id": "cfg_b", "paired": True}),
            ),
        )
        await db.execute(
            """
            INSERT INTO rounds (
                game_id, round_num, player_id, action_type, prompt_tokens,
                completion_tokens, total_tokens, response_time_ms, created_at
            ) VALUES
                ('gb1', 1, 'cfg_a', 'play', 10, 5, 50, 100, ?),
                ('gc1', 1, 'cfg_a', 'play', 10, 5, 80, 50, ?)
            """,
            (now, now),
        )
        await db.commit()

    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]
    payload = await service.compare_experiments(["exp-base", "exp-ctrl"])
    by_id = {item["id"]: item for item in payload["experiments"]}

    base = by_id["exp-base"]
    ctrl = by_id["exp-ctrl"]

    assert base["landlord_win_rate"] == 0.5
    assert ctrl["landlord_win_rate"] == 1.0
    assert "p50_response_ms" in base
    assert "tokens_per_game" in base
    assert base["paired_n"] == 2
    assert ctrl["paired_n"] == 2
    # paired: seed 10 landlord wins + seed 20 peasant wins on base → 0.5
    assert base["paired_landlord_win_rate"] == 0.5
    # paired: both landlord wins on ctrl → 1.0
    assert ctrl["paired_landlord_win_rate"] == 1.0

    base_a = next(s for s in base["player_stats"] if s["player_id"] == "cfg_a")
    assert base_a["games_as_landlord"] == 1
    assert base_a["landlord_win_rate"] == 1.0

    ps = payload.get("paired_summary")
    assert ps is not None
    assert ps["source_id"] == "exp-base"
    assert ps["control_id"] == "exp-ctrl"
    assert ps["shared_seeds"] == 2
    assert ps["landlord_win_rate_diff"] == 0.5
