"""Compare persisted decision labels and seat statistics with the engine payoff."""

import sqlite3
from pathlib import Path

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine, DoudizhuState
from app.database import connect_sqlite, init_db
from app.repositories.game_repo import GameRepository
from app.repositories.stats_repo import StatsRepository


@pytest.mark.parametrize("finisher", ["landlord", "farmer_a", "farmer_b", None])
async def test_finish_sets_team_labels_and_model_denominator(
    tmp_path: Path, finisher: str | None
) -> None:
    path = str(tmp_path / "seats.db")
    await init_db(path)
    roles = {"landlord": "landlord", "farmer_a": "peasant", "farmer_b": "peasant"}
    role = roles[finisher] if finisher else "no_bid"
    state = DoudizhuState(
        game_type="doudizhu",
        round=10,
        player_ids=list(roles),
        current_player="farmer_a",
        is_terminal=True,
        winner=finisher,
        winner_role=role,
        roles=roles,
    )
    async with connect_sqlite(path) as db:
        games = GameRepository(db)
        await games.create("g", "doudizhu", list(roles), "g.jsonl", "now")
        for pid in roles:
            await db.execute(
                """INSERT INTO decision_points
                   (id, game_id, round_number, player_id, hand_cards, game_phase, legal_actions, chosen_action, created_at)
                   VALUES (?, 'g', 1, ?, '[]', 'playing', '[]', '{}', 'now')""",
                (pid, pid),
            )
            for turn in (1, 2):
                await db.execute(
                    """INSERT INTO rounds (game_id, round_num, player_id, action_type, model_name, created_at)
                       VALUES ('g', ?, ?, 'play', 'shared-model', 'now')""",
                    (turn, pid),
                )
        await games.update_result(
            "g",
            winner_id=finisher,
            winner_role=role,
            total_rounds=10,
            finished_at="now",
            metadata_patch={"landlord_id": "landlord"} if finisher else None,
        )
        rows = await db.execute_fetchall("SELECT player_id, outcome FROM decision_points")
        model_stats = await StatsRepository(db).model_seat_rates()
        if finisher is None:
            assert all(row["outcome"] is None for row in rows)
            assert model_stats == []
            return
        rewards = DoudizhuEngine().terminal_rewards(state)
        assert {row["player_id"]: row["outcome"] for row in rows} == {
            pid: "win" if reward else "lose" for pid, reward in rewards.items()
        }
        assert model_stats == [
            {
                "model": "shared-model",
                "wins": sum(rewards.values()),
                "seat_games": 3,
                "win_rate": round(sum(rewards.values()) / 3, 4),
            }
        ]


async def test_conflicting_role_excluded_and_failed_relabel_is_atomic(tmp_path: Path) -> None:
    path = str(tmp_path / "atomic.db")
    await init_db(path)
    async with connect_sqlite(path) as db:
        games = GameRepository(db)
        await games.create("g", "doudizhu", ["a", "b", "c"], "g.jsonl", "now")
        await db.execute(
            """INSERT INTO decision_points
               (id, game_id, round_number, player_id, hand_cards, game_phase, legal_actions, chosen_action, created_at)
               VALUES ('d', 'g', 1, 'b', '[]', 'playing', '[]', '{}', 'now')"""
        )
        await games.update_result(
            "g",
            winner_id="a",
            winner_role="peasant",
            total_rounds=1,
            finished_at="now",
            metadata_patch={"landlord_id": "a"},
        )
        assert not list(await db.execute_fetchall("SELECT * FROM game_seat_results"))
        await db.execute(
            """CREATE TRIGGER reject_labels BEFORE UPDATE ON decision_points
               BEGIN SELECT RAISE(ABORT, 'write failed'); END"""
        )
        with pytest.raises(sqlite3.IntegrityError, match="write failed"):
            await games.update_result(
                "g", winner_id="b", winner_role="peasant", total_rounds=1, finished_at="now"
            )
        assert (await games.get_by_id("g"))["winner_id"] == "a"
        assert not list(await db.execute_fetchall("SELECT * FROM game_seat_results"))
