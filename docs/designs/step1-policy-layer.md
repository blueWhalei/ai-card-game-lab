# 设计：第 1 步 — Policy 决策层

> 对应 `docs/ROADMAP.md` §7 第 1 步与 §9.2。
> 依赖第 0 步（`Observation` / `LegalAction` / `ToolSpec` / `terminal_rewards`）。

## 为什么要拆成三段

现有 `AIService` 一个方法里同时做七件事：跑工具、拼 prompt（含 DB 模板）、调 LLM（流式/非流式）、
解析、重试、流式失败回退非流式、写决策点。把它整体换成 Policy 会一次性动到 359 个测试里
最脆弱的一片。所以：

| 子步 | 内容 | 风险 |
|------|------|------|
| 1a | `core/policy/` 类型 + `PolicyRegistry` + 非 LLM 基线策略 + 引擎 `suggest_action` | 纯新增，不改任何调用方 |
| 1b | `LLMPolicy`：把现有 prompt→调用→解析包成事件流；`AIService` 退化为事件消费者 | 高，单独一步 |
| 1c | structured output：合法动作编成 JSON Schema `enum`，解析失败率归零 | 中，依赖 1b |

本文档先定 1a，并把 1b/1c 的接口边界钉住，避免 1a 做出一个 1b 用不了的接口。

## 1a. 接口

```python
PolicyEvent = ThinkingDelta | ToolCall | ToolResult | LlmUsage | ActionChosen

class Policy(ABC):
    kind: str
    def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]
```

- **事件流是 core 与 service 之间唯一的接口。** Policy 不 import `services/` / `repositories/`，
  对 WS 广播、span、决策点落库零感知。Service 消费事件后决定广播什么、持久化什么。
- **最后一个事件必须是 `ActionChosen`**，且 `action_id` 必须在 `legal_actions` 里。写成契约测试。
- `Policy.decide_action()` 是排空事件流、只取终局动作的便捷方法，给 Evaluator 的 rollout 用
  （那里没人关心思考过程）。

`Budget` 只放"花多少算力"的旋钮，模型参数（temperature / max_tokens）属于 LLM 策略自己的
配置，不进 Budget：

```python
@dataclass(frozen=True)
class Budget:
    max_llm_calls: int = 1
    max_tool_calls: int = 0
    timeout_s: float | None = None
```

`PolicyContext` 是 Policy 的外部依赖注入点，Policy 不自行读环境变量或全局状态：

```python
@dataclass(frozen=True)
class PolicyContext:
    advisor: EngineAdvisor      # 引擎工具与启发式建议
    rng: random.Random          # 唯一随机源，保证可复现
    session_id: str | None      # 供 trace 关联，Policy 只透传
```

`EngineAdvisor` 是窄 Protocol（`run_tool` + `suggest_action`），`GameEngine` 结构化满足它。
Policy 因此拿不到 `GameState`，也拿不到引擎的其他方法。`Memory`、VCR 句柄在 1b/后续加入
`PolicyContext`，字段追加不破坏 1a。

## 1a. 基线策略

三个都与游戏无关，靠引擎提供游戏知识：

| kind | 行为 | 用途 |
|------|------|------|
| `random` | 从 `legal_actions` 均匀随机 | 评测下界；rollout 的最弱对手 |
| `first` | 取引擎给出的展示顺序第一项（斗地主 = 最强牌型） | 确定性基线；测试用 |
| `heuristic` | 委托 `advisor.suggest_action()`，无建议时退化为 `random` | 有意义的非 LLM 对手；胜率参照系；step 2 的 rollout 对手 |

三者都不调 LLM，因此 CI 可以跑真实对局而不花钱——这是 ROADMAP §1「基线」那一行的解法。

## 1a. 引擎新增 suggest_action

```python
def suggest_action(
    self, observation: Observation, legal_actions: list[LegalAction]
) -> ActionId | None
```

- 基类返回 `None`（无内建启发式）。
- 游戏知识留在引擎侧，`core/policy/` 不出现任何游戏名（§9.6）。
- 斗地主实现（刻意简单、可解释，不追求强度）：
  - 叫分阶段：按 `analyze_hand` 的强度评分决定叫 3 / 2 / 1 / 不叫。
  - 领出时：出**最便宜**的一手，且不动炸弹与火箭。
  - 跟牌时：出能压住的**最便宜**一手；只有当上家是对手且其手牌 ≤ 2 张时才允许炸。
  - 其余情况 PASS。
- 不变量（契约测试）：返回值必须是传入 `legal_actions` 中的 id，或 `None`。
  合法性由测试保证，而不是靠调用方兜底。

## 1b/1c 的边界（现在就钉住，避免 1a 白做）

- `LLMPolicy` 的 prompt 构造仍走 `PromptBuilder`，但输入从 `GameState` 换成
  `Observation.text` + `legal_actions` 的 label。`AIService` 保留重试、超时、
  流式→非流式回退这些**传输层**职责，它们不属于 Policy。
- 流式文本以 `ThinkingDelta` 事件透出，`AIService` 把它转成现有的 `StreamChunk` 回调，
  `game_orchestration_service` 无需改动。
- token 用量以 `LlmUsage` 事件透出，替代 `AIDecisionResult.usage` 的内部拼装。
- structured output（1c）用 `LegalAction.id` 作为 `enum` 成员；`resolve_action()` 已在第 0 步就位。
  解析失败仍会发生（不支持约束输出的模型），因此 `used_langchain_parser` /
  `parse fallback` 指标保留。

## 不在本步范围

`ToolLoopPolicy`、`SearchAugmentedPolicy`、`EnsemblePolicy`、`HumanPolicy`、`Memory`、
protocol 的 `policy` 段（需 `schema_version: 1 → 2`）、决策点新字段。
1a 结束时没有任何调用方使用 Policy——它是给 1b 与 step 2 准备的地基，由契约测试保证正确。

## 验证

- 基线：`poetry run pytest` = 359 passed（第 0 步提交后）。
- 新增 `tests/test_core/test_policy/test_policy_contract.py`：对**注册表里所有策略**
  × **注册表里所有引擎**参数化跑不变量（终局事件、动作合法、同 seed 可复现、空动作列表报错），
  并用基线策略跑完整对局验证事件流能驱动一局到终局。
- 启发式的**行为**（而非仅合法性）在 `test_doudizhu.py` 中断言：领出取最便宜、
  无人临近出完时留住炸弹、对手剩 ≤2 张时炸。
- 强度实证（300 局固定种子，p1 席位平均收益，非测试用例，因为它会波动）：

  | p1 策略 | p1 收益 |
  |---------|---------|
  | `random` | 0.537 |
  | `first` | 0.737 |
  | `heuristic` | 0.883 |

  排序符合预期，说明 `heuristic` 是一个有意义的参照系而不是伪基线。
