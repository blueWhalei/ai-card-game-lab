"""Unit tests for conclusion draft assembly."""

from __future__ import annotations

from app.core.research.conclusion_draft import (
    build_conclusion_draft,
    normalize_draft_locale,
    pick_notable_scenario,
)


def test_normalize_locale() -> None:
    assert normalize_draft_locale(None) == "zh-CN"
    assert normalize_draft_locale("en-US,en;q=0.9") == "en"
    assert normalize_draft_locale("zh") == "zh-CN"


def test_pick_notable_scenario() -> None:
    diffs = {
        "bidding": {"train_usable_rate_diff": 0.02},
        "playing": {"train_usable_rate_diff": -0.12},
        "endgame": {"train_usable_rate_diff": None},
    }
    assert pick_notable_scenario(diffs) == ("playing", -0.12)
    assert pick_notable_scenario({"bidding": {"train_usable_rate_diff": 0.01}}) is None


def test_draft_zh_strong_with_blunders() -> None:
    draft = build_conclusion_draft(
        experiment={"name": "微调后", "hypothesis": "LoRA 更强"},
        delta={
            "verdict_key": "stronger",
            "can_conclude": True,
            "peer_name": "基线",
            "paired_n": 24,
            "landlord_win_rate_diff": 0.08,
            "this_landlord_win_rate_ci": [0.45, 0.72],
            "scenario_diffs": {
                "playing": {"train_usable_rate_diff": 0.1},
            },
        },
        blunders=[
            {
                "id": "dp1",
                "game_id": "g1",
                "round_number": 3,
                "action_id": "PASS||",
                "ev_loss": 0.7,
            }
        ],
        locale="zh-CN",
    )
    assert draft.locale == "zh-CN"
    assert draft.verdict_key == "stronger"
    assert draft.can_conclude is True
    assert draft.blunder_ids == ["dp1"]
    assert "【草稿 · 待确认】" in draft.text
    assert "LoRA 更强" in draft.text
    assert "赢得更多" in draft.text
    assert "+8.0 pp" in draft.text
    assert "出牌" in draft.text
    assert "ev_loss=0.70" in draft.text


def test_draft_en_weak_and_empty_delta() -> None:
    weak = build_conclusion_draft(
        experiment={"name": "A"},
        delta={
            "verdict_key": "stronger",
            "can_conclude": False,
            "peer_name": "B",
            "paired_n": 4,
            "landlord_win_rate_diff": 0.1,
        },
        blunders=[],
        locale="en",
    )
    assert "[Draft · pending confirmation]" in weak.text
    assert "Evidence is still thin" in weak.text

    empty = build_conclusion_draft(
        experiment={"name": "solo"},
        delta=None,
        blunders=[],
        locale="en",
    )
    assert empty.verdict_key == "no_data"
    assert "Not enough games" in empty.text
