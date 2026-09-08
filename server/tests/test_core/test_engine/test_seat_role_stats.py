"""Tests for Dou Dizhu seat-as-landlord aggregates."""

from __future__ import annotations

from app.core.engine.doudizhu.seat_role_stats import seat_as_landlord_counts


def test_seat_as_landlord_counts_finished_decisive_only() -> None:
    games = [
        {
            "status": "finished",
            "winner_role": "landlord",
            "winner_id": "a",
            "metadata": {"landlord_id": "a"},
        },
        {
            "status": "finished",
            "winner_role": "peasant",
            "winner_id": "b",
            "metadata": '{"landlord_id": "a"}',
        },
        {
            "status": "finished",
            "winner_role": "landlord",
            "winner_id": "b",
            "metadata": {"landlord_id": "b"},
        },
        {
            "status": "failed",
            "winner_role": "landlord",
            "winner_id": "a",
            "metadata": {"landlord_id": "a"},
        },
        {
            "status": "finished",
            "winner_role": "no_bid",
            "winner_id": None,
            "metadata": {"landlord_id": "a"},
        },
    ]
    games_by, wins_by = seat_as_landlord_counts(games)
    assert games_by == {"a": 2, "b": 1}
    assert wins_by == {"a": 1, "b": 1}


def test_seat_as_landlord_counts_empty() -> None:
    assert seat_as_landlord_counts([]) == ({}, {})
