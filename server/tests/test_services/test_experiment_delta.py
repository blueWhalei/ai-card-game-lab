"""Detail-page delta vs source/control (this minus peer)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.services.experiment_eval import (
    build_experiment_delta,
    resolve_delta_peer,
    verdict_key,
)
from app.services.experiment_service import ExperimentService


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "exp_delta.db")
    await init_db(path)
    return path


class _FakeGameService:
    def player_slots(self, game_type: str) -> tuple[int, int]:
        return (3, 3)


def test_resolve_delta_peer_prefers_source_then_ready_control() -> None:
    assert resolve_delta_peer({"protocol": {}}, {"control_experiment_ids": []}) == (
        None,
        None,
    )
    assert resolve_delta_peer(
        {
            "protocol": {
                "schema_version": 2,
                "dataset": {"source_experiment_id": "exp-base"},
            }
        },
        {"control_progress": [{"id": "exp-other", "ready": True}]},
    ) == ("exp-base", "vs_source")
    assert resolve_delta_peer(
        {"protocol": {}},
        {
            "control_progress": [
                {"id": "exp-pending", "ready": False},
                {"id": "exp-ready", "ready": True},
            ]
        },
    ) == ("exp-ready", "vs_control")


def test_build_experiment_delta_inconclusive_when_low_power() -> None:
    payload = build_experiment_delta(
        peer_id="exp-base",
        peer_name="基线",
        relation="vs_source",
        peer_ready=True,
        this_landlord_win_rate=0.6,
        peer_landlord_win_rate=0.4,
        this_landlord_win_rate_ci=[0.3, 0.8],
        peer_landlord_win_rate_ci=[0.2, 0.7],
        this_decisive_n=8,
        peer_decisive_n=8,
        this_low_power=True,
        peer_low_power=True,
        paired_n=8,
        paired_landlord_win_rate_diff=0.2,
        paired_low_power=True,
    )
    assert payload["landlord_win_rate_diff"] == 0.2
    assert payload["can_conclude"] is False
    assert payload["inconclusive_reason"] == "low_power"


def test_build_experiment_delta_can_conclude_when_powered() -> None:
    payload = build_experiment_delta(
        peer_id="exp-ctrl",
        peer_name="对照",
        relation="vs_control",
        peer_ready=True,
        this_landlord_win_rate=0.45,
        peer_landlord_win_rate=0.55,
        this_landlord_win_rate_ci=[0.32, 0.58],
        peer_landlord_win_rate_ci=[0.42, 0.68],
        this_decisive_n=40,
        peer_decisive_n=40,
        this_low_power=False,
        peer_low_power=False,
        paired_n=40,
        paired_landlord_win_rate_diff=-0.1,
        paired_low_power=False,
    )
    assert payload["landlord_win_rate_diff"] == -0.1
    assert payload["can_conclude"] is True
    assert payload["inconclusive_reason"] is None


def test_verdict_key_reports_direction_independently_of_confidence() -> None:
    # A weak claim still names a direction; `can_conclude` governs how it reads.
    assert verdict_key(overall_diff=0.07, inconclusive_reason="low_power") == "stronger"
    assert verdict_key(overall_diff=-0.07, inconclusive_reason=None) == "weaker"
    assert verdict_key(overall_diff=0.01, inconclusive_reason=None) == "even"


def test_verdict_key_falls_back_when_there_is_nothing_to_compare() -> None:
    assert verdict_key(overall_diff=None, inconclusive_reason="no_games") == "no_data"
    assert verdict_key(overall_diff=0.2, inconclusive_reason="peer_not_ready") == "peer_pending"
    assert verdict_key(overall_diff=None, inconclusive_reason=None) == "no_data"


@pytest.mark.parametrize(
    ("overall_diff", "inconclusive_reason", "expected"),
    [
        (0.05, None, "stronger"),
        (-0.05, None, "weaker"),
        (0.019, None, "even"),
        (-0.019, None, "even"),
        (0.0, None, "even"),
        (None, "no_games", "no_data"),
        (0.1, "peer_not_ready", "peer_pending"),
        (None, None, "no_data"),
        (0.1, "low_power", "stronger"),
    ],
)
def test_verdict_key_table(
    overall_diff: float | None,
    inconclusive_reason: str | None,
    expected: str,
) -> None:
    assert (
        verdict_key(overall_diff=overall_diff, inconclusive_reason=inconclusive_reason) == expected
    )


def test_build_experiment_delta_carries_verdict_key() -> None:
    payload = build_experiment_delta(
        peer_id="exp-ctrl",
        peer_name="对照",
        relation="vs_control",
        peer_ready=True,
        this_landlord_win_rate=0.6,
        peer_landlord_win_rate=0.4,
        this_landlord_win_rate_ci=[0.45, 0.72],
        peer_landlord_win_rate_ci=[0.28, 0.55],
        this_decisive_n=40,
        peer_decisive_n=40,
        this_low_power=False,
        peer_low_power=False,
        paired_n=40,
        paired_landlord_win_rate_diff=0.2,
        paired_low_power=False,
    )
    assert payload["verdict_key"] == "stronger"
    assert payload["can_conclude"] is True


async def _seed_paired(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    protocol_base = json.dumps(
        {
            "schema_version": 2,
            "dataset": {
                "collect_mode": "free",
                "deal_seeds": [10, 20],
                "pair_deals": False,
                "source_experiment_id": None,
            },
            "solver": {"players": [], "prompt_version": "v3"},
            "scorer": {"eval_metric_ids": []},
            "engine": {"game_type": "doudizhu"},
        }
    )
    protocol_ctrl = json.dumps(
        {
            "schema_version": 2,
            "dataset": {
                "collect_mode": "free",
                "deal_seeds": [10, 20],
                "pair_deals": True,
                "source_experiment_id": "exp-base",
            },
            "solver": {"players": [], "prompt_version": "v3"},
            "scorer": {"eval_metric_ids": []},
            "engine": {"game_type": "doudizhu"},
        }
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games,
                created_at, updated_at, protocol
            ) VALUES
                ('exp-base', '基线', '', 'doudizhu', ?, 2, ?, ?, ?),
                ('exp-ctrl', '对照', '', 'doudizhu', ?, 2, ?, ?, ?)
            """,
            (players, now, now, protocol_base, players, now, now, protocol_ctrl),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, winner_role,
                total_rounds, data_file, created_at, experiment_id, metadata
            ) VALUES
                ('gb1', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord',
                 10, 'a.jsonl', ?, 'exp-base', ?),
                ('gb2', 'doudizhu', 'finished', ?, 'cfg_b', 'peasant',
                 10, 'b.jsonl', ?, 'exp-base', ?),
                ('gc1', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord',
                 10, 'c.jsonl', ?, 'exp-ctrl', ?),
                ('gc2', 'doudizhu', 'finished', ?, 'cfg_a', 'landlord',
                 10, 'd.jsonl', ?, 'exp-ctrl', ?)
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
        await db.commit()


async def test_get_experiment_delta_vs_control_and_source(db_path: str) -> None:
    await _seed_paired(db_path)
    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]

    base = await service.get_experiment("exp-base", include_games=False)
    assert base["validation"]["suggested_compare_ids"] == ["exp-base", "exp-ctrl"]
    delta = base["delta"]
    assert delta is not None
    assert delta["peer_id"] == "exp-ctrl"
    assert delta["relation"] == "vs_control"
    assert delta["landlord_win_rate_diff"] == -0.5
    assert delta["paired_n"] == 2
    assert delta["paired_landlord_win_rate_diff"] == -0.5
    assert delta["can_conclude"] is False
    assert delta["inconclusive_reason"] == "protocol_mismatch"
    assert "bidding" in delta["scenario_diffs"]

    ctrl = await service.get_experiment("exp-ctrl", include_games=False)
    assert ctrl["validation"]["suggested_compare_ids"] == ["exp-ctrl", "exp-base"]
    ctrl_delta = ctrl["delta"]
    assert ctrl_delta is not None
    assert ctrl_delta["peer_id"] == "exp-base"
    assert ctrl_delta["relation"] == "vs_source"
    assert ctrl_delta["landlord_win_rate_diff"] == 0.5
    assert ctrl_delta["paired_landlord_win_rate_diff"] == 0.5
    assert ctrl_delta["can_conclude"] is False


@pytest.mark.parametrize("usable", [0, 10])
def test_next_step_reviews_results_without_training_requirement(usable: int) -> None:
    step = ExperimentService._build_next_step(
        {},
        {"status": "ready_review", "train_usable_decisions": usable},
        {"control_experiment_ids": []},
    )
    assert step == {"id": "review_decisions", "action": "decisions"}


@pytest.mark.parametrize(
    "status, expected",
    [
        ("pending_collect", {"id": "collect", "action": "collect"}),
        ("collecting", {"id": "watch", "action": "games"}),
        ("ready_review", {"id": "collect_control", "action": "control_collect", "ref_id": "ctrl"}),
    ],
)
def test_next_step_prioritizes_running_work(status: str, expected: dict) -> None:
    step = ExperimentService._build_next_step(
        {},
        {"status": status},
        {"control_experiment_ids": ["ctrl"], "control_progress": [{"id": "ctrl", "ready": False}]},
    )
    assert step == expected


def test_completed_control_stays_for_review() -> None:
    step = ExperimentService._build_next_step(
        {"protocol": {"dataset": {"source_experiment_id": "source"}}},
        {"status": "ready_review"},
        {},
    )
    assert step == {"id": "review", "action": "stay"}


def test_next_step_stays_on_detail_when_validation_ready() -> None:
    summary = {
        "status": "ready_review",
        "train_usable_decisions": 10,
        "decision_count": 10,
    }
    validation = {
        "control_experiment_ids": ["exp-ctrl"],
        "control_progress": [{"id": "exp-ctrl", "ready": True}],
        "validation_ready": True,
    }
    step = ExperimentService._build_next_step({}, summary, validation)
    assert step == {"id": "review", "action": "stay"}
