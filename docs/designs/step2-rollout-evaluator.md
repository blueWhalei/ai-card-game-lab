# 设计：第 2 步 — Rollout 评估器与决策级 EV loss

> 对应 `docs/ROADMAP.md` §7 第 2 步、§2.2.2、§9.3。
> 依赖第 0 步（`sample_hidden_state` / `terminal_rewards` / `LegalAction`）与第 1a 步（基线策略）。

## 为什么插到 1b 之前

第 2 步只需要第 0 步与 1a 已经交付的东西，且是纯新增；1b 要改 `PromptBuilder`
（556 行、7 个方法）的入参形态，而 prompt 会静默改变模型行为。先做风险低、收益大的一步。

## 它解决什么

现在衡量"这步好不好"的唯一字段是 `quality_score`——赢 0.8 / 输 0.3 的**结局代理**，
它衡量的是"这局谁赢了"。EV loss 用同一套 rollout 对每个决策点算
`best_action_ev - chosen_action_ev`，一次投入四处受益（ROADMAP §2.2.2）：
move quality、SFT 过滤硬标准、关键决策点的客观定义、评测样本效率提升 1–2 个量级。

## 同步而非异步

rollout 是纯 CPU 工作。项目约定 CPU-bound 走 `asyncio.to_thread()`，因此评估器
**是同步的**，由 service 层包进线程。

但 1a 的 `Policy.decide()` 是异步生成器（为 LLM 的 I/O 设计）。为了不产生两套基线实现，
在 `core/policy/base.py` 增加同步协议，让基线**一份逻辑两个入口**：

```python
class ActionSelector(Protocol):
    def choose(self, observation, legal_actions, rng) -> ActionId: ...
```

三个基线的真实逻辑落在 `choose()`，`decide()` 只是把它包成单事件流。评估器要的是
`ActionSelector`，不是 `Policy`——它不需要事件流，也不该被异步传染。

## 算法

```
action_values(observation, legal_actions) -> dict[ActionId, float]
```

1. 采样 `determinizations` 个与观测一致的世界（`engine.sample_hidden_state`）。
2. **同一批世界用于所有候选动作**（common random numbers）。这是关键：候选之间的差值
   才是我们要的信号，共用随机世界能把方差压掉一个量级。因此循环顺序是世界在外、候选在内。
3. 每个 (世界, 候选)：先落子，再让**所有玩家**（含被评估者）用 `opponent` selector
   走到终局，取 `terminal_rewards()[viewer]`。
4. 对世界与重复次数取平均。

```
ev_loss(observation, legal_actions, chosen_id) -> EvLoss
```

`loss = max(values) - values[chosen]`，恒 ≥ 0。

## 成本与诚实性

斗地主开局的合法动作可达上百个，全量评估太贵。`max_candidates` 限制候选数：

- **被评估的动作永远在候选里**，否则 loss 无意义。
- 其余候选按引擎展示顺序取前若干个。
- 因此 `best` 是**已评估子集**内的最优，不是全局最优。结果里带
  `candidates_evaluated` 与完整 `values`，让这个数字可被正确解读——
  宁可标注局限，不可假装全局。

默认值刻意保守（`determinizations=4`、`max_candidates=8`、`opponent="heuristic"`），
调大是实验参数，不是默认行为。

## 可复现性

`EvaluatorParams.seed` 决定全部随机性。**同参数同 seed 必须给出同一组数值**，
否则 EV loss 不能跨实验比较。所有参数随结果返回，写进决策点时一并持久化
（字段落库属于 protocol v2，本步不做）。

## 不在本步范围

- 决策点新增 `ev_loss` / `evaluator_params` 字段（需 `decision_schema_version` 升级）
- 用 EV loss 替换 `quality_score`、改 SFT 过滤、改 highlights 选取
- puzzle 抽取（第 4 步）
- service 层接线与 `asyncio.to_thread()` 包装

本步只交付 `core/eval/` 与契约测试，让上述每一项之后都只是"接线"。

## 验证

- 基线：`poetry run pytest` = 377 passed（第 1a 步提交后）。
- 完成后：**386 passed**（新增 9 项），无既有测试修改。
- 契约测试（对所有支持采样的引擎参数化）：同 seed 可复现、不同 seed 不同、loss ≥ 0、
  被评估动作必在候选内、最优动作 loss = 0、非法动作报错、参数随结果返回、
  不支持采样的引擎构造即拒绝。
- 斗地主的数值断言（答案显而易见的局面）：能一手出完的牌型 EV = 1.0；
  对手剩一张时炸弹的 EV 高于 PASS。
- 判别力实证（6 局、`determinizations=4`、`max_candidates=6`，只统计 p1 席位，非测试用例）：

  | p1 策略 | 平均 EV loss | 标准差 | 决策样本数 |
  |---------|-------------|--------|-----------|
  | `random` | 0.181 | 0.273 | 90 |
  | `heuristic` | 0.099 | 0.187 | 71 |

  两点结论：EV loss 能区分好坏策略；6 局对局产出 70–90 个决策样本，而胜率只有 6 个——
  这就是 §2.2.2 说的样本效率提升。

- 成本：上述参数下约 **0.17 秒/决策**（单线程）。50 局 × 约 20 决策 ≈ 3 分钟，
  可以接受；这也是它必须走 `asyncio.to_thread()` 而不能阻塞事件循环的原因。
