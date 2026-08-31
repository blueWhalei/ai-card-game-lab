"""Ensure local runtime directories exist before serving requests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def ensure_runtime_dirs(settings: Settings) -> None:
    """Create data / games / datasets / models directories if missing."""
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "games").mkdir(parents=True, exist_ok=True)
    (data_dir / "datasets").mkdir(parents=True, exist_ok=True)
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.models_dir).mkdir(parents=True, exist_ok=True)
