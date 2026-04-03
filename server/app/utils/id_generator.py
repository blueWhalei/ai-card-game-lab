"""Unique ID generation utilities."""

import random
import string
from datetime import datetime, timezone


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with an optional prefix.

    Format: ``{prefix}_{YYYYMMDD}_{random6}``

    Examples:
        >>> generate_id("game")
        'game_20240101_a3f2b1'
        >>> generate_id("ds")
        'ds_20240101_c9e7d4'
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    if prefix:
        return f"{prefix}_{now}_{suffix}"
    return f"{now}_{suffix}"
