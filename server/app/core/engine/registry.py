"""游戏引擎注册表，将游戏类型标识符映射到引擎实例。

提供中心化的游戏引擎管理，支持动态注册和查找。
新游戏只需注册到注册表，无需修改现有代码。
"""

from app.core.engine.base import EngineCapability, GameEngine
from app.utils.exceptions import UnsupportedGameTypeError


class GameEngineRegistry:
    """线程安全的游戏引擎注册表。

    管理所有可用游戏引擎的中心注册表。采用注册模式，允许游戏引擎
    动态注册，API 层通过游戏类型查找对应引擎。

    注册表是单例模式的替代方案，通过依赖注入在应用启动时初始化。
    所有注册的引擎实例应该是无状态的。

    Attributes:
        _engines: 内部存储引擎的字典，键为游戏类型，值为引擎实例。
    """

    def __init__(self) -> None:
        """初始化空的引擎注册表。"""
        self._engines: dict[str, GameEngine] = {}

    def register(self, engine: GameEngine) -> None:
        """注册一个游戏引擎实例。"""
        self._engines[engine.game_type] = engine

    def get(self, game_type: str) -> GameEngine:
        """根据游戏类型获取引擎实例。"""
        engine = self._engines.get(game_type)
        if engine is None:
            raise UnsupportedGameTypeError(game_type)
        return engine

    def describe_engines(self) -> list[dict[str, object]]:
        """Return registered engines with full capability (seeds as count only)."""
        return [
            engine.capability.to_public_dict(include_seeds=False)
            for engine in self._engines.values()
        ]

    def default_game_type(self) -> str | None:
        """First registered engine id, or None if empty."""
        types = self.list_game_types()
        return types[0] if types else None

    def get_capability(self, game_type: str) -> EngineCapability:
        return self.get(game_type).capability

    def list_game_types(self) -> list[str]:
        """获取所有已注册的游戏类型标识符。"""
        return list(self._engines.keys())
