# 设计：第 0 步 — 引擎能力地基

> 对应 `docs/ROADMAP.md` §7 第 0 步与 §9.1。
> 目标：让 Policy / Evaluator / Env / Tool 能够与具体游戏解耦，且**不改变任何现有行为**。

## 范围与顺序

拆成五个可独立验证的子步，每个都只做加法，现有调用方不动：

| 子步 | 内容 | 现有代码影响 |
|------|------|-------------|
| 0a | `ActionId` / `LegalAction` 规范化动作 | 新增方法；斗地主 prompt 格式化改为复用同一排序逻辑，输出字符串保持不变 |
| 0b | `terminal_rewards()` 终局奖励 | 纯新增 |
| 0c | `sample_hidden_state()` 隐藏状态采样 | 纯新增；能力开关声明在 `EngineCapability` |
| 0d | `Observation` 玩家可见视图 + `observe()` | 纯新增；`get_public_info` 保持不动（面向 UI），`Observation` 面向 Policy |
| 0e | `EngineCapability.tools` 工具声明 | 新增；斗地主侧声明 `analyze_hand`，包装现有 `HandAnalyzerTool` |

不在本步范围：`Policy`、`Evaluator`、env、structured output、持久化字段变更、protocol 版本升级。
因此本步**不需要** `schema_version` 或 `decision_schema_version` 变更。

## 0a. ActionId / LegalAction

```python
ActionId: TypeAlias = str

@dataclass(frozen=True)
class LegalAction:
    id: ActionId       # 稳定、不透明、可作为 JSON Schema enum 成员
    label: str         # 人类可读，供 prompt 与 UI
    action: GameAction # 引擎内部表示，Policy 不解读
```

`GameEngine` 新增（均有基类默认实现，子类可覆盖）：

- `action_id(action) -> ActionId`：确定性规范串 `"{type}|{canonical cards}|{target}"`。
  基类用 `sorted(cards)`；斗地主覆盖为 `sort_cards()`，使 id 与展示顺序一致。
- `action_label(state, action) -> str`：单个动作的展示文本。
- `legal_actions(state, player_id) -> list[LegalAction]`：基于 `get_legal_actions()`，
  **按 id 去重**并给出稳定顺序（斗地主按 `_ACTION_PRIORITY` 排序，与 prompt 中的编号一致）。
- `resolve_action(state, player_id, action_id) -> GameAction`：反查；未知 id 抛
  `InvalidActionError`。这是 structured output 与 puzzle 回放的入口。

**不变量**（写成测试）：
1. `resolve_action(state, p, la.id) == la.action`，对 `legal_actions()` 中每一项成立。
2. id 在同一状态内唯一。
3. id 与列表顺序对同一状态可复现（同 seed 两次 `legal_actions()` 结果相同）。
4. 未知 id 抛 `InvalidActionError`，不静默回退。
5. `format_legal_actions_for_prompt` 的输出与重构前逐字节相同（现有测试保证）。

`ActionId` 保持"人类可读的确定性串"而不是哈希：便于 prompt 内直接使用、便于 JSONL 归档阅读、
便于 CLI 调试。稳定性只依赖引擎的规范化函数，与 Python 的 `hash` 随机化无关。

## 0b. terminal_rewards

```python
def terminal_rewards(self, state: GameState) -> dict[str, float]
```

- 语义：仅在 `is_terminal(state)` 为真时有意义；非终局抛 `InvalidActionError`。
- 基类默认：胜者 `1.0`，其余 `0.0`；平局全 `0.0`。
- 斗地主覆盖为**阵营**语义：胜方阵营全员 `1.0`，败方 `0.0`（地主胜 → 地主 1.0、两农民 0.0；
  农民胜 → 两农民 1.0、地主 0.0）。流局（`winner_role == "no_bid"`）全 `0.0`。
- 使用者：Evaluator（EV 计算）、RL env（reward）、Scorer。
- 暂不引入叫分倍数/春天等加权：EV loss 只需要一致的排序，倍数留到德扑引入 chips 时再谈。

## 0c. sample_hidden_state

```python
def sample_hidden_state(self, observation: Observation, rng: random.Random) -> GameState
```

- 语义：给定某玩家的观测，采样一个与观测**一致**的完整状态（determinization）。
- 能力开关：`EngineCapability.supports_hidden_state_sampling: bool = False`；
  基类默认抛 `UnsupportedGameTypeError` 语义的异常（不静默返回近似状态）。
- 斗地主实现：已知自己手牌、已出牌记录、底牌（`playing` 阶段公开）、各家剩余张数；
  未知牌 = 全牌堆 − 自己手牌 − 已出牌 − 底牌，按各家剩余张数随机切分。
- 一致性不变量（测试）：采样出的状态里，自己手牌不变、各家张数与观测一致、
  全体手牌 + 已出牌 + 底牌恰好构成一副完整牌堆、无重复牌。
- 依赖 0d 的 `Observation`，因此实现顺序是 0a → 0b → 0d → 0c。文档编号保持语义分组。

## 0d. Observation

Policy 只能拿到 `Observation`，永远拿不到 `GameState`（否则能偷看对手手牌）。

```python
@dataclass(frozen=True)
class Observation:
    game_type: str
    phase: str
    round: int
    player_id: str          # 视角玩家
    to_act: bool
    private: dict[str, Any] # 视角玩家私有信息（手牌等）
    public: dict[str, Any]  # 全体可见（已出牌、各家张数、角色、底牌…）
    text: str               # 引擎渲染的 prompt 文本（沿用 format_for_prompt）
```

- `observe(state, player_id) -> Observation`：基类默认由 `get_public_info` + `format_for_prompt`
  组装；斗地主填 `private.hand_cards`、`public.play_history` / `hand_counts` / `roles` /
  `landlord_cards` / `last_play`，供 `sample_hidden_state` 与工具使用。
- 与 `ObserverSnapshot` 的分工写清：`get_public_info` → UI（`GenericBoard`）；
  `Observation` → Policy / Evaluator。两者不合并，避免 UI 需求污染决策输入。
- `text` 暂时复用 `format_for_prompt`，为 0e 之后的 prompt 重构留出替换点。

## 0e. EngineCapability.tools

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]                     # JSON Schema
    handler: Callable[[Observation, dict[str, Any]], dict[str, Any]]
```

- `EngineCapability.tools: tuple[ToolSpec, ...] = ()`；`to_public_dict` 只暴露
  `name/description/parameters`（`handler` 不可序列化）。
- `GameEngine.run_tool(name, observation, arguments)` 是唯一调用入口；未知工具名抛
  `InvalidActionError`。
- `core/engine/doudizhu/tools.py` 以 `analyze_hand` 声明，handler 从
  `observation.private["hand_cards"]` 取牌并包装现有 `HandAnalyzerTool`（评分逻辑仍留在
  `core/ai/tools/hand_analyzer.py`，本步不搬迁实现）。
- 不变量：`core/policy/`（尚未存在）与 `core/eval/` 不得 import 任何游戏包；工具调用只经 `ToolSpec`。

**与原计划的两处偏离**（为守住"本步不改现有行为、不动 protocol"）：

1. `protocol_fingerprint` **不**记录工具名。加入指纹会改变新实验的 protocol，按 §9.4 需要
   `schema_version: 1 → 2`，留到 protocol v2 一并处理。
2. `ai_service._run_tools()` **不**改写。它同时驱动 `WinProbability` 与
   `PromptBuilder.format_tool_results`，等价替换的收益低于回归风险；改写与主动调用一起
   放到 `ToolLoopPolicy`。当前 `analyze_hand` 声明只被契约测试消费。

## 验证

- 基线：`poetry run pytest` = 343 passed（2026-09-06）。
- 完成后：**359 passed**（新增 16 项），无既有测试修改。
- 新增测试文件：`tests/test_core/test_engine/test_engine_contract.py`——针对**注册表里所有引擎**
  跑上述不变量，第二个引擎接入时自动获得同一套约束。
- `ruff` / `mypy` 在本机未安装（`poetry run ruff` 与 `python -m mypy` 均不可用），本步靠
  IDE lint 通过；进 CI 前需补跑。这正是 ROADMAP §5「mypy / ruff format 进 CI」的动机。
