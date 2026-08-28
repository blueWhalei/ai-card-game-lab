"""Tests for SFT ChatML exporter include_thinking flag."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.training.exporter import export_sft_dataset


def _write_round(path: Path, *, thinking: str = "分析一下") -> None:
    record = {
        "type": "round",
        "player_id": "p1",
        "round_num": 1,
        "action_type": "SINGLE",
        "cards": ["C3"],
        "thinking": thinking,
    }
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


def test_export_default_omits_thinking(tmp_path: Path) -> None:
    src = tmp_path / "raw.jsonl"
    out = tmp_path / "sft.jsonl"
    _write_round(src)
    count = export_sft_dataset(str(src), str(out), include_thinking=False)
    assert count == 1
    sample = json.loads(out.read_text(encoding="utf-8").strip())
    assistant = json.loads(sample["messages"][2]["content"])
    assert "thinking" not in assistant
    assert assistant["action"]["type"] == "SINGLE"


def test_export_with_thinking(tmp_path: Path) -> None:
    src = tmp_path / "raw.jsonl"
    out = tmp_path / "sft.jsonl"
    _write_round(src, thinking="出最小")
    count = export_sft_dataset(str(src), str(out), include_thinking=True)
    assert count == 1
    sample = json.loads(out.read_text(encoding="utf-8").strip())
    assistant = json.loads(sample["messages"][2]["content"])
    assert assistant["thinking"] == "出最小"
