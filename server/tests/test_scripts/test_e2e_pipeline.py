"""Smoke tests for e2e_pipeline CLI (no live API required for guide)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_pipeline.py"


def test_guide_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    ns = runpy.run_path(str(SCRIPT))
    main = ns["main"]
    assert main(["guide"]) == 0
    out = capsys.readouterr().out
    assert "1 小时闭环" in out
    assert "采集" in out


def test_parser_accepts_count_after_command() -> None:
    ns = runpy.run_path(str(SCRIPT))
    parser = ns["build_parser"]()
    args = parser.parse_args(["all", "--count", "2"])
    assert args.command == "all"
    assert args.count == 2
