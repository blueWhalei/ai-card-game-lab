"""Abstract base classes for the game engine layer.

All concrete game engines (doudizhu, sanguosha, etc.) inherit from
``GameEngine`` and implement every abstract method.  Engine instances
are **stateless** -- game state is carried by ``GameState`` objects.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EngineCapability:
    """Declarative engine identity and product-facing abilities.

    Frozen into experiment protocol fingerprints and exposed via
    ``GET /system/engines``. Concrete engines override via ``capability``.
    """

    game_type: str
    min_players: int
    max_players: int
    engine_version: str = "1"
    phases: tuple[str, ...] = ("playing",)
    prompt_keys: dict[str, str] = field(default_factory=dict)
    supports_deal_seed: bool = False
    benchmark_seeds: tuple[int, ...] = ()
    roles: tuple[str, ...] = ()
    eval_metric_ids: tuple[str, ...] = ()
    decision_schema_version: int = 1
    rules_ref: str | None = None

    def to_public_dict(self, *, include_seeds: bool = False) -> dict[str, Any]:
        """JSON-safe view for ``GET /system/engines``. Seeds omitted unless requested."""
        data = asdict(self)
        seeds = list(self.benchmark_seeds)
        data["id"] = self.game_type
        data["benchmark_seed_count"] = len(seeds)
        if include_seeds:
            data["benchmark_seeds"] = seeds
        else:
            data.pop("benchmark_seeds", None)
        data["phases"] = list(self.phases)
        data["roles"] = list(self.roles)
        data["eval_metric_ids"] = list(self.eval_metric_ids)
        data["prompt_keys"] = dict(self.prompt_keys)
        return data

    def protocol_fingerprint(self) -> dict[str, Any]:
        """Subset frozen into experiment.protocol (no full seed list)."""
        return {
            "game_type": self.game_type,
            "engine_version": self.engine_version,
            "decision_schema_version": self.decision_schema_version,
            "rules_ref": self.rules_ref,
            "phases": list(self.phases),
            "prompt_keys": dict(self.prompt_keys),
            "roles": list(self.roles),
            "eval_metric_ids": list(self.eval_metric_ids),
            "supports_deal_seed": self.supports_deal_seed,
            "benchmark_seed_count": len(self.benchmark_seeds),
        }


@dataclass
class GameState:
    """游戏状态的基类，表示某一时刻游戏的完整状态。

    所有具体游戏的 GameState 都应继承此类并扩展特定于游戏的字段。
    GameState 是不可变的数据载体，引擎本身不持有状态。

    Attributes:
        game_type: 游戏类型标识符，如 'doudizhu'、'sanguosha'。
        round: 当前回合数，从 1 开始计数。
        player_ids: 参与游戏的玩家 ID 列表。
        current_player: 当前需要行动的玩家 ID。
        is_terminal: 游戏是否已结束。
        winner: 获胜玩家的 ID，若游戏未结束或平局则为 None。
        winner_role: 获胜玩家的角色（如地主/农民），若不适用则为 None。
    """

    game_type: str
    round: int
    player_ids: list[str]
    current_player: str
    is_terminal: bool
    winner: str | None = None
    winner_role: str | None = None


@dataclass
class GameAction:
    """玩家执行的单个动作。

    表示玩家在游戏中的一次行动，如出牌、跳过等。

    Attributes:
        player_id: 执行动作的玩家 ID。
        action_type: 动作类型，如 'play'、'pass'、'draw' 等。
        cards: 涉及的卡牌列表，如出牌时打出的牌。默认为空列表。
        target: 动作的目标玩家 ID，若不适用则为 None。
    """

    player_id: str
    action_type: str
    cards: list[str] = field(default_factory=list)
    target: str | None = None


@dataclass
class PlayerState:
    """单个玩家的状态信息。

    存储每个玩家在游戏中的状态，包括手牌、存活状态和其他属性。

    Attributes:
        player_id: 玩家唯一标识符。
        hand_cards: 玩家当前手牌列表。
        alive: 玩家是否仍在游戏中。默认为 True。
        attributes: 玩家的其他属性字典，如角色、技能状态等。默认为空字典。
    """

    player_id: str
    hand_cards: list[str]
    alive: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


class GameEngine(ABC):
    """抽象游戏引擎基类，所有卡牌游戏引擎都必须实现此接口。

    游戏引擎负责管理游戏规则、状态转换和动作验证。引擎实例是**无状态**的，
    所有游戏状态通过 GameState 对象传递。这种设计允许同一个引擎实例
    同时处理多个游戏。

    子类必须实现所有抽象方法，包括：
        - game_type 属性：返回游戏类型标识符
        - initialize：初始化新游戏
        - get_legal_actions：获取合法动作
        - apply_action：应用动作并返回新状态
        - is_terminal：判断游戏是否结束
        - get_winner：获取获胜者
        - get_current_player：获取当前玩家
        - format_for_prompt：格式化状态为提示文本
        - parse_action：解析 LLM 输出为动作
        - get_public_info：获取公开信息

    Example:
        >>> class DoudizhuEngine(GameEngine):
        ...     @property
        ...     def game_type(self) -> str:
        ...         return "doudizhu"
        ...     # ... 实现其他抽象方法
    """

    @property
    def min_players(self) -> int:
        """Minimum number of players this engine accepts."""
        return 2

    @property
    def max_players(self) -> int:
        """Maximum number of players this engine accepts."""
        return 8

    @property
    def capability(self) -> EngineCapability:
        """Engine ability declaration. Subclasses should override with full fields."""
        return EngineCapability(
            game_type=self.game_type,
            min_players=self.min_players,
            max_players=self.max_players,
            prompt_keys={"playing": f"{self.game_type}_playing"},
        )

    def format_legal_actions_for_prompt(
        self, state: GameState, actions: list[GameAction]
    ) -> str:
        """Format legal actions for LLM prompts. Override for game-specific ordering."""
        del state  # unused in generic formatter
        if not actions:
            return "无可选动作"
        lines: list[str] = []
        for i, action in enumerate(actions, start=1):
            cards_str = " ".join(action.cards) if action.cards else ""
            if cards_str:
                lines.append(f"{i}. {action.action_type}: [{cards_str}]")
            elif action.target:
                lines.append(f"{i}. {action.action_type} {action.target}")
            else:
                lines.append(f"{i}. {action.action_type}")
            if i >= 80:
                remaining = len(actions) - i
                if remaining > 0:
                    lines.append(f"...还有 {remaining} 个可选动作未列出")
                break
        return "\n".join(lines)

    @property
    @abstractmethod
    def game_type(self) -> str:
        """返回游戏类型的唯一标识符。

        标识符用于在注册表中注册引擎，以及在前端路由中识别游戏类型。
        应使用小写字母和下划线，如 'doudizhu'、'sanguosha'。

        Returns:
            游戏类型的唯一字符串标识符。
        """

    @abstractmethod
    def initialize(self, player_ids: list[str], **params: Any) -> GameState:
        """初始化新游戏并返回初始状态。

        创建新的游戏实例，包括洗牌、发牌、设置初始玩家顺序等。
        返回的 GameState 包含游戏开始时的完整状态。

        Args:
            player_ids: 参与游戏的玩家 ID 列表。列表顺序决定出牌顺序。
            **params: 游戏特定的参数，如地主身份、初始手牌数等。

        Returns:
            包含初始游戏状态的 GameState 对象。

        Example:
            >>> state = engine.initialize(["p1", "p2", "p3"])
            >>> state.round  # 1
            >>> state.current_player  # "p1"
        """

    @abstractmethod
    def get_legal_actions(self, state: GameState, player_id: str) -> list[GameAction]:
        """获取指定玩家在当前状态下的所有合法动作。

        返回玩家可以执行的所有合法动作列表。如果玩家没有合法动作
        （如必须跳过），返回包含跳过动作的单元素列表。

        Args:
            state: 当前游戏状态。
            player_id: 要查询的玩家 ID。

        Returns:
            合法动作列表。如果玩家不是当前行动者，返回空列表。

        Example:
            >>> actions = engine.get_legal_actions(state, "p1")
            >>> [a.action_type for a in actions]
            ['play', 'pass']
        """

    @abstractmethod
    def apply_action(self, state: GameState, action: GameAction) -> GameState:
        """将动作应用到当前状态并返回新状态。

        执行给定动作，更新游戏状态，并返回新的 GameState 对象。
        原始状态不会被修改（不可变模式）。

        Args:
            state: 当前游戏状态。
            action: 要执行的动作。

        Returns:
            应用动作后的新 GameState 对象。

        Raises:
            InvalidActionError: 如果动作不合法或不是当前玩家的动作。

        Example:
            >>> new_state = engine.apply_action(state, action)
            >>> new_state.round  # 可能增加
        """

    @abstractmethod
    def is_terminal(self, state: GameState) -> bool:
        """判断游戏是否已结束。

        检查游戏是否达到终止条件，如某玩家出完所有牌、
        某方阵营获胜等。

        Args:
            state: 当前游戏状态。

        Returns:
            如果游戏已结束返回 True，否则返回 False。

        Example:
            >>> if engine.is_terminal(state):
            ...     print(f"Winner: {engine.get_winner(state)}")
        """

    @abstractmethod
    def get_winner(self, state: GameState) -> str | None:
        """获取获胜玩家的 ID。

        如果游戏已结束且有明确获胜者，返回获胜玩家的 ID。
        如果游戏未结束或平局，返回 None。

        Args:
            state: 当前游戏状态。

        Returns:
            获胜玩家的 ID，或 None（游戏未结束或平局）。

        Example:
            >>> winner = engine.get_winner(state)
            >>> if winner:
            ...     print(f"Player {winner} wins!")
        """

    @abstractmethod
    def get_current_player(self, state: GameState) -> str:
        """获取当前需要行动的玩家 ID。

        返回在当前状态下应该执行动作的玩家。

        Args:
            state: 当前游戏状态。

        Returns:
            当前行动玩家的 ID。

        Example:
            >>> current = engine.get_current_player(state)
            >>> print(f"It's {current}'s turn")
        """

    @abstractmethod
    def format_for_prompt(self, state: GameState, player_id: str) -> str:
        """将游戏状态格式化为人类可读的提示文本。

        生成用于 LLM 提示的状态描述，包含该玩家可见的所有信息。
        文本应该清晰、结构化，便于 AI 理解和决策。

        Args:
            state: 当前游戏状态。
            player_id: 视角玩家的 ID（只能看到自己的手牌）。

        Returns:
            格式化的状态描述文本。

        Example:
            >>> prompt = engine.format_for_prompt(state, "p1")
            >>> print(prompt)
            "你的手牌: [♠A, ♥K, ♦Q]\\n对手剩余: 5张\\n..."
        """

    @abstractmethod
    def parse_action(
        self, llm_output: str, legal_actions: list[GameAction]
    ) -> GameAction:
        """将 LLM 输出解析为游戏动作。

        将 LLM 生成的文本响应映射到合法动作之一。
        解析器应该尽可能宽松地处理各种格式的输出。

        Args:
            llm_output: LLM 生成的原始文本输出。
            legal_actions: 当前合法动作列表。

        Returns:
            解析得到的 GameAction 对象。

        Raises:
            InvalidActionError: 如果无法将输出映射到任何合法动作。

        Example:
            >>> output = "我出对子：33"
            >>> action = engine.parse_action(output, legal_actions)
            >>> action.action_type  # 'play'
            >>> action.cards  # ['3', '3']
        """

    @abstractmethod
    def get_public_info(
        self, state: GameState, viewer_id: str, is_observer: bool = False
    ) -> dict[str, Any]:
        """获取指定观察者可见的公开信息。

        返回对指定玩家可见的游戏信息，自动隐藏其他玩家的私密信息
        （如手牌）。用于前端展示和 WebSocket 广播。

        Args:
            state: 当前游戏状态。
            viewer_id: 观察者的玩家 ID。
            is_observer: 是否为全局观察者（可以看到所有玩家手牌）。

        Returns:
            包含公开信息的字典，结构适合 JSON 序列化。

        Example:
            >>> info = engine.get_public_info(state, "p1")
            >>> info["hand_cards"]  # p1 的手牌
            >>> info["opponents"][0]["card_count"]  # 对手牌数（不显示具体牌）
            >>> # 观察者模式可以看到所有手牌
            >>> info = engine.get_public_info(state, "observer", is_observer=True)
            >>> info["all_hands"]  # 所有玩家的手牌
        """
