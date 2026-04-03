"""Game engine package.

Import and register all concrete engines here so they are available
via the ``GameEngineRegistry`` at application startup.
"""

from app.core.engine.registry import GameEngineRegistry

__all__ = ["GameEngineRegistry"]
