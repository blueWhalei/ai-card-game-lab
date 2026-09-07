# 设计：把 EV loss 接进产品

> 第 2 步的后半段。core 部分（`app/core/eval/rollout.py`）已完成，本文只讲接线：
> 什么时候算、存在哪、谁消费。

## 为什么值得接

现在衡量一步棋只有 `quality_score`：赢了 0.8、输了 0.3。它是**局结果的代理**，
一局 40 多个决策共享同一个分数——臭棋和好棋在数据里长得一模一样。
EV loss 是 per-decision 的：这一步比评估到的最优候选少赚了多少。
一局 43 个决策就是 43 个信号，而不是 1 个。

## 什么时候算

**在决策发生的当下同步算**（`AIService._record_decision_point`），不是局后补算。

理由是重建成本。评估器需要 `Observation` + `list[LegalAction]`，而落库的决策点存的是
手牌数组、对手张数、动作 dict——不含 `ActionId`，也不含 `sample_hidden_state` 需要的
完整公共信息。局后要么额外存一份 observation 快照，要么无法重建。决策当下这些对象都在手上，
零重建风险。

代价实测（斗地主一整局，默认参数，heuristic 对手）：

| 指标 | 值 |
|------|-----|
| 单次决策 | 中位数 93 ms / p95 382 ms |
| 一局 43 个决策合计 | 5.75 s |

对照一次 LLM 调用通常是数秒，一局 LLM 侧就是几分钟——EV 计算约占 4% 墙钟时间，且不花 API 钱。
可以接受，所以**默认开启**，`EV_LOSS_ENABLED=false` 可关。

代价换来的东西是：过滤 SFT 数据时能扔掉"赢了但走了臭棋"的样本，highlights 能指出真正的失误，
而不只是"出了炸弹"这类形状特征。

## 三个不做的决定

**1. 不合并进 `train_usable`。**
`evaluate_train_usable` 判的是**结构有效性**（动作合法、思考与动作不矛盾），
EV loss 判的是**棋力好坏**。一步合法而愚蠢的棋，结构上仍然是可用样本——
是否要它取决于你在训练什么。混成一个布尔量会让两个问题都答不清楚，
所以 EV 过滤是导出侧的独立参数 `max_ev_loss`，默认不过滤。

**2. 算不出来就存 NULL，绝不影响对局。**
引擎不支持 `sample_hidden_state`、rollout 超步数、任何异常——都记一条 warn 日志然后
`ev_loss = NULL`。EV loss 是分析信号，不是游戏规则的一部分。已有对局数据的 `ev_loss`
也一律是 NULL，所以下游必须把"没算过"和"算出来是 0"区分开：
`ev_loss = 0` 表示这步是评估到的最优，`NULL` 表示没有结论。

**3. `evaluator_params` 与每条记录同存。**
determinizations 从 4 改成 16 会得到不同的数，两批数不能直接比。参数跟着记录走，
比较时才有依据。这也是 `EvaluatorParams` 一开始就设计成可序列化的原因。

## 字段与版本

`decision_points` 新增两列（迁移 3）：

| 列 | 类型 | 含义 |
|----|------|------|
| `ev_loss` | `REAL`（可空） | 让出的期望收益，`>= 0`；`NULL` = 未评估 |
| `evaluator_params` | `TEXT`（可空） | `EvaluatorParams.to_dict()` 的 JSON |

`decision_schema_version` 从 1 升到 2：决策点的 payload 契约变了。它写在
`EngineCapability` 与实验 `protocol` 指纹里，旧实验的 protocol 保持 1 不动
（不静默迁移，沿用现有规则）。

## 消费方

- **导出 / 数据集注册**：新增 `max_ev_loss` 过滤。未评估（NULL）的点不因该过滤被排除——
  否则打开过滤就会静默丢掉所有历史数据。
- **`GET /decision-points/stats`**：新增 `evaluated_count`、`avg_ev_loss`、`blunder_count`。
- **highlights**：新增 `blunder` reason，优先级仅次于 `last_play`。阈值
  `BLUNDER_EV_LOSS = 0.5`（斗地主 terminal reward 是 ±1 量级，让出半个身位才算失误）。
- **前端**：决策详情显示 EV loss 与"未评估"，highlights 显示"失误"标签。
  Δ 一样不上色——它是证据强度，不是好坏色块。

## 验证

- 评估器算出的 `ev_loss` 落库、读回、经 API 出现在决策详情。
- 引擎不支持采样时决策点照常写入且 `ev_loss` 为 NULL。
- 评估抛异常时对局不中断。
- `max_ev_loss` 过滤保留未评估的点。
- highlights 把高 EV loss 的一步标成 `blunder` 且排在 `bomb` 之前。
