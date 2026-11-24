"""Resolve read-only application resources for source and packaged execution."""

import os
from pathlib import Path


def resource_root() -> Path:
    return Path(os.environ.get("CARDLAB_RESOURCE_ROOT", str(Path(__file__).resolve().parents[3])))
