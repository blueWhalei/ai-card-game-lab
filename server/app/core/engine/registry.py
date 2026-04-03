"""游戏引擎注册表，将游戏类型标识符映射到引擎实例。

提供中心化的游戏引擎管理，支持动态注册和查找。
新游戏只需注册到注册表，无需修改现有代码。
"""

from app.core.engine.base import GameEngine
from app.utils.exceptions import UnsupportedGameTypeError


class GameEngineRegistry:
    """线程安全的游戏引擎注册表。

    管理所有可用游戏引擎的中心注册表。采用注册模式，允许游戏引擎
    动态注册，API 层通过游戏类型查找对应引擎。

    注册表是单例模式的替代方案，通过依赖注入在应用启动时初始化。
    所有注册的引擎实例应该是无状态的。

    Attributes:
        _engines: 内部存储引擎的字典，键为游戏类型，值为引擎实例。

    Example:
        >>> registry = GameEngineRegistry()
        >>> registry.register(DoudizhuEngine())
        >>> registry.register(SanguoshaEngine())
        >>> engine = registry.get("doudizhu")
        >>> registry.list_game_types()
        ['doudizhu', 'sanguosha']
    """

    def __init__(self) -> None:
        """初始化空的引擎注册表。"""
        self._engines: dict[str, GameEngine] = {}

    def register(self, engine: GameEngine) -> None:
        """注册一个游戏引擎实例。

        将引擎实例注册到注册表中，使用引擎的 game_type 属性作为键。
        如果已存在相同游戏类型的引擎，将被覆盖。

        Args:
            engine: 要注册的游戏引擎实例。必须实现 GameEngine 接口。

        Example:
            >>> registry = GameEngineRegistry()
            >>> engine = DoudizhuEngine()
            >>> registry.register(engine)
            >>> "doudizhu" in registry.list_game_types()
            True
        """
        self._engines[engine.game_type] = engine

    def get(self, game_type: str) -> GameEngine:
        """根据游戏类型获取引擎实例。

        从注册表中查找并返回指定游戏类型的引擎实例。

        Args:
            game_type: 游戏类型标识符，如 'doudizhu'、'sanguosha'。

        Returns:
            对应游戏类型的引擎实例。

        Raises:
            UnsupportedGameTypeError: 如果请求的游戏类型未注册。

        Example:
            >>> registry = GameEngineRegistry()
            >>> registry.register(DoudizhuEngine())
            >>> engine = registry.get("doudizhu")
            >>> engine.game_type
            'doudizhu'
            >>> registry.get("unknown")  # raises UnsupportedGameTypeError
        """
        engine = self._engines.get(game_type)
        if engine is None:
            raise UnsupportedGameTypeError(game_type)
        return engine

    def list_game_types(self) -> list[str]:
        """获取所有已注册的游戏类型标识符。

        返回注册表中所有游戏类型的列表，用于展示可用游戏或验证。

        Returns:
            已注册游戏类型的字符串列表，顺序不保证。

        Example:
            >>> registry = GameEngineRegistry()
            >>> registry.register(DoudizhuEngine())
            >>> registry.register(SanguoshaEngine())
            >>> sorted(registry.list_game_types())
            ['doudizhu', 'sanguosha']
        """
        return list(self._engines.keys())
