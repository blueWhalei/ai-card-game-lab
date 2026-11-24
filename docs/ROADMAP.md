# 技术路线图（Roadmap）

> 本文记录 2026-09 一次完整技术评审后达成的共识：项目定位、四个方向的深化方案与推进顺序。
> 它描述的是"要去哪里"，不是当前实现；实现状态以 `CLAUDE.md` 与代码为准。
> 每完成一项，在本文对应条目标注日期，并把稳定下来的规则回写到 `CLAUDE.md`。

## 0. 定位

**CardLab 是一个可复现的 LLM 博弈决策评测与微调闭环平台**，不是"看 AI 打牌"的观察工具。

- 核心资产是评测方法：固定牌局种子（benchmark）、配对对照实验、置信区间与 verdict，
  以及决策级评分（见 §2.2）。
- 斗地主只是第一个引擎。`EngineCapability` + `GameEngineRegistry` 的通用性需要由第二个
  引擎验证（建议德州扑克 heads-up：规则简单、回合短、有成熟的非 LLM 基线策略）。
- 训练是可选的 Advanced 模块，不是主路径的一部分。

## 1. 现状诊断（评审时）

| 层 | 现状 | 问题 |
|----|------|------|
| 决策 | 单次 prompt → 自由文本 → 正则解析 → 失败回退规则动作 | 2023 范式；解析失败率是一个本不该存在的指标 |
| 工具 | `HandAnalyzerTool` 由 `_run_tools()` 预计算后注入 prompt | 模型不能主动调用；无 function calling / structured output；工具签名是斗地主专属 |
| 评分 | `experiment_eval.py` 中 landlord WR 等逻辑硬编码 | 指标未按 `eval_metric_ids` 由引擎注册，第二个引擎接不进来 |
| 推理 | 一次决策一次调用；无搜索、无跨局记忆 | 推理预算不是实验变量 |
| 训练 | 训练集从实际决策导出 | 终局胜负是席位级标签，单步分析另看估计期望收益差 |
| 评测 | 局级胜率 + 二项 CI；决策级仅 parser rate / train_usable | 样本效率低（5 局 = 5 个样本），`low_power` 常见 |
| 基线 | 所有选手都是 LLM | 胜率没有参照系；CI 无法跑真实对局 |
| 迁移 | `database.py` 中 try/except `ALTER TABLE` | 单人可用，多用户环境会成为 issue 来源 |

代码热点：i18n 单文件各 ~1300 行。
`ExperimentDetailView` 已拆为 `useExperimentDetail` + 薄视图；`experiment_service` 已拆 mixin。
工程配置：CI 已跑 `ruff check` / `ruff format --check` /
`mypy app/core app/services` / `pytest --cov`（`--cov-fail-under=80`）；
前端已有 Stage 产品规则组件测；Playwright 冒烟（demo → verdict）已接 CI。

## 2. 四个深化方向

### 2.1 决策层：从 "prompt" 到 Policy / Agent harness

**2.1.1 `Policy` 抽象（地基）**

`LLMClient` 是传输层（谁给 tokens），`Policy` 是决策层（怎么得出动作）。

```
Policy.decide(observation, legal_actions, budget) -> Decision
```

实现集合（选手配置从 "provider + model + prompt" 变成 "policy + 参数"）：

- `SingleShotLLMPolicy` — 现状（`policy_kind=llm`）
- `ToolLoopPolicy` — ReAct：模型主动调用工具后再决策 —— **已完成 2026-09-09**（`policy_kind=tool_loop`）
- `SearchAugmentedPolicy` — LLM 提议 k 个候选，rollout 评估 n 次，再选择 —— **已完成 2026-09-09**（`policy_kind=search`）
- `HeuristicPolicy` / `FirstActionPolicy` / `RandomPolicy` — 非 LLM 基线；也让 CI 能跑零成本真实对局
- `HumanPolicy` — 人类席位（观战界面替某座位出牌 / 中途接管）—— **本批不做**
- `EnsemblePolicy` — 多模型投票或大模型仲裁 —— **本批不做**

接口契约见 §9.2：输入是 `Observation` 与规范化 action id，输出是事件流，Policy 对持久化零感知。

**2.1.2 Structured output 约束合法动作**

`legal_actions` 编成 JSON Schema `enum`，走各家 `response_format` / Ollama `format`。
解析失败率归零；`fallback_parse` 仅保留给不支持约束输出的模型。
附带一个诚实的对照实验："约束输出是否让模型变笨"。

**2.1.3 工具成为模型可主动调用的动作** —— **ToolLoop ✅ 2026-09-09**

`analyze_hand`、`simulate_playout(action, n)`、`count_remaining_by_rank`、`opponent_history`。
每轮调用记录进 spans。"被动注入 vs 主动调用"是平台的第一份研究报告素材。

工具**属于引擎**，由 `EngineCapability.tools` 声明（名称 + JSON Schema + 实现）；Policy 只看
schema 并转发调用，不理解任何游戏语义（见 §9.1）。Dou Dizhu `HandAnalyzerTool` 已迁到
`engine/doudizhu/hand_analyzer.py`（2026-09-08）；`core/ai/tools/` 不再持有牌面分析器。

**2.1.4 搜索增强（test-time compute 作为变量）** —— **Search ✅ 2026-09-09**

引擎无状态、`GameState` 可复制，rollout 成本低。注意斗地主与德扑都是**不完美信息**博弈：
rollout 前必须先 determinization（按观测采样一组与已知信息一致的隐藏状态），依赖
`engine.sample_hidden_state()`（§9.1）。k、n、determinization 次数、thinking budget
进入 protocol 并冻结，使"同模型不同预算"成为可对照的实验。

**2.1.5 推理模型的 thinking budget 是一等变量** —— **已完成 2026-09-09**

`is_reasoning_model()` 已区分模型；预算参数（`reasoning_effort` / `max_thinking_tokens`）
写入 `protocol.solver.thinking_budget` 并在 collect 时冻结。

**2.1.6 跨局记忆与对手建模** —— **已完成 2026-09-09**（`solver.memory=none|per_experiment`；局末规则摘要，无额外 LLM）

Policy 可挂 `Memory`：每局结束更新对手风格笔记，下局注入。
农民之间的隐式协作是斗地主特有的多智能体研究点。

作用域必须受控：memory 是 protocol 的一部分（`memory: none | per_experiment`），默认 `none`。
否则第 1 局与第 50 局的选手实际上不同，"冻结的 protocol"不再冻结。

### 2.2 评测层：从"看胜率"到 harness

**2.2.1 显式 Task = Dataset × Solver × Scorer**（借鉴 Inspect AI / lm-eval-harness）—— **命名已完成 2026-09-07**

Dataset = 固定 `deal_seeds`；Solver = 各座位 Policy 配置；Scorer = 引擎注册的指标实现。
benchmark 模式即一个 Task 定义；`examples/` 中的实验包即 Task 文件；CLI 一条命令出报告。

**不引入新实体**：`Experiment` + 冻结 `protocol` 已经是 Task 实例。Task 只是 protocol 的
schema 命名（`dataset` / `solver` / `scorer` / `engine` 四段，`schema_version: 2`），
不建平行的表与 API。斗地主 `eval_metric_ids`（`train_usable` / `parser_success` /
`latency_p50_p95` / `role:landlord` / `ev_loss`）均经 `ScorerRegistry` 覆盖 summary
（2026-09-07）；计数仍由 `eval_aggregates` 供给，Scorer 只负责公式。引擎专属指标按
`game_type` 注册。

**2.2.2 决策级评分：EV loss（最重要的技术深化）**

用同一套 rollout 评估器对每个决策点计算 `best_action_ev - chosen_action_ev`。一次投入，
四处受益：

1. 冻结每步估计期望收益差及其候选范围和采样条件
2. 提供按估计收益差筛选 SFT 样本的条件，不能保证样本决策正确
3. 按估计收益差筛选待复查决策，明确阈值、采样及候选范围；筛选仍是启发式诊断
4. 增加单局的行为诊断粒度；同局决策相互关联，不据条数增长推断独立样本量或统计功效提升

评估器位于 `core/eval/`，依赖引擎的 `sample_hidden_state` 与 `terminal_rewards`（§9.1）；
对手 rollout 策略、determinization 次数、n 是评估器参数并记录在决策点上，
使 EV loss 数值可复现、可比较。

**2.2.3 静态题库（puzzle set）作为第二种 benchmark** —— **4a 已完成 2026-09-08**

从对局抽取候选估计收益极差较大的局面（观察 + 合法动作 + 已评估动作收益）。离线策略
与冻结的模拟估计比较，记录有效分母和未评估选择；这不是标准答案准确率或能力等级分。
候选、采样、续局策略及抽题条件影响结果；同一局面的重复测试不作为独立对局样本。
实现：`deal_seed` 回放重算 EV → `data/puzzles/{pack_id}/`；`POST /api/v1/puzzles/extract`
与 `/packs/{id}/run`（baseline）；Analyze UI 见 `/pipeline/puzzles`（Wave 3b）。输入扰动测试见 §2.2.5（4b）。

**2.2.4 录制—重放（VCR）** —— **已完成 2026-09-07**

记录每次 LLM 请求/响应及哈希，支持 replay 模式：零成本回归、CI 跑完整实验流水线、
审计"改 prompt 后相同局面输出是否变化"。实现：`VcrLLMClient` 包装 provider client；
cassette 为 `data/vcr/*.jsonl`。

**2.2.5 输入扰动测试** —— **4b 已完成 2026-09-08**

表示扰动（牌面符号、顺序、zh/en）、座位位置偏差、合法动作列表顺序打乱。
同局面动作一致率描述策略对特定输入变换的敏感性，不能据此判定模型是否理解规则。
本阶段落地：题包上 `shuffle_legal_actions` + `shuffle_hand_cards`；
`POST /api/v1/puzzles/packs/{id}/probe` 报告同随机流对照下的动作一致率、原输入重复一致率及冻结模拟估计下的条件评分，并展示已评估分母；冻结估计不是金标准。
座位旋转 / zh-en / 牌面符号替换 —— **已完成 2026-09-09**（`rotate_seats` / `zh_en_labels` / `card_symbol_style`）。

**2.2.6 双层指标 + 更严谨的配对统计**

- 局级：配对胜负四格计数、精确 McNemar 检验、保守 95% 差值区间及独立验证用牌已接入。见[配对统计](designs/paired-stats.md)。Elo / Bradley-Terry 锦标赛延后。
- 决策级：估计期望收益差、候选覆盖范围、指定输入变换下的动作一致率；均注明模拟条件与有效分母。
- 待开发：跨重复运行的变异报告及事先定义的效应阈值。统计功效需指定备择效应、显著性水平和采样设计；现有样本量/区间宽度提醒不作功效估计。

### 2.3 训练层：从 SFT 到可验证奖励

**2.3.1 CardLab 作为 RL environment，而不是自研 RL 训练器** —— **5a 已完成 2026-09-08**

游戏结局可由引擎规则确定奖励。暴露环境接口后，可研究基于终局奖励的强化学习；具体算法适用性仍需实验验证。
由 verl、TRL GRPOTrainer、Unsloth、SkyRL 等框架 rollout。三人回合制是多智能体，
接口对齐 **PettingZoo AEC**（`reset(seed) / agent_iter() / last() / step(action)`）而非单智能体
Gym，否则接每个框架都要自己包一层。奖励来自 `engine.terminal_rewards()`。我们维护环境与评测，训练栈交给专业工具。
这也把 issue 重灾区（GPU / llama.cpp / 平台差异）移出主路径。

实现：`core/env/aec.py` 的 duck-typed `CardLabAECEnv`（**不硬依赖** pettingzoo）；
`step(int)` 为合法菜单下标；非 learner 座位默认 `HeuristicPolicy` 自动走。
偏好数据导出见 §2.3.2（**5b ✅**）。

**2.3.2 从现有决策点自动构造偏好数据** — **5b 已完成 2026-09-08**（EV 偏好对）

- 候选内最高估计收益动作 vs 模型选择（估计期望收益差 > 阈值）→ DPO/KTO chosen/rejected：记分时把
  `best_action_id` / `action_values` 写入 `evaluator_params`；
  `POST /api/v1/decision-points/export-preferences` 读库导出 JSONL（缺少模拟参考动作的行跳过；
  默认 `min_ev_gap=0.05`）。**不做** deal_seed 重算旧行。
- 大模型选择 vs 小模型选择 → 蒸馏对 —— **已完成 2026-09-09**
  （`POST .../export-distill-preferences`；2026-11-06 收紧为冻结协议一致、唯一同源发牌且连续记录中的首次可验证行动分歧；教师选择不代表客观最优）

**2.3.3 拒绝采样微调（RFT）替代裸 SFT**

同一局面采样 N 次，以续局模拟估计筛选训练目标。需要记录候选、采样预算和筛选规则，并在独立留出对局上验证训练增益；模拟估计最高不代表真实最优。

**2.3.4 评估—训练闭环自动化**

计划在训练完成后运行固定条件的评测，并生成模型说明，记录指定席位/角色的胜率、样本数与区间、估计期望收益差的评估范围及每局 token 用量。不同训练方案需共享未用于调参的留出牌局，再比较训练增益。

**2.3.5 外部训练工具作为主路径**

支持导出 ChatML / DPO 数据集给 LLaMA-Factory / Unsloth；`deploy.py` 中 llama.cpp 调用抽成
可替换的 `Exporter` 接口。

### 2.4 平台层：让平台可被 agent 使用

- **MCP server** — **6a 已完成 2026-09-08**：stdio `python -m app.mcp`（官方 `mcp` 2.x
  `MCPServer`）；只读工具 `list_experiments` / `get_experiment` / `list_decision_points` /
  `get_decision_stats`，直接调 Service。**写工具 Wave 3a**：`start_collect` /
  `cancel_collect`（对齐 HTTP collect）。**HTTP MCP ✅ 2026-09-09**：API 进程挂载
  Streamable HTTP 于 `/mcp/`（`MCP_HTTP_ENABLED`，默认真）；亦可
  `python -m app.mcp --transport streamable-http --port 8001`。
- **研究助手草稿** — **6b 已完成 2026-09-08**：模板拼装（不调 LLM）`POST .../conclusion-draft`；
  verdict 阶段预览确认后 `PATCH conclusion`。**只做草稿**，统计 verdict 不变。
  Wave 3a：草稿坏手深链到决策页。
- **Trace 导出兼容 OpenTelemetry / OpenInference**：自研 traces/spans 保留，加导出器接
  Langfuse / Phoenix / Arize。
- **不引入 LangGraph / CrewAI 等多智能体框架**：回合制引擎本身就是编排器，Policy 循环
  几十行足够，框架只带来版本漂移和抽象泄漏。

## 3. 功能项（评审认同，按贡献排序）

1. 实验模板 / 一键复现：`examples/` 放 3 个可导入 pack（基线对比、prompt A/B、微调前后对照）—— **已完成 2026-09-08**（`examples/*.json`；导入重建 protocol，Prompt A/B 需人工挂模板）
2. Prompt 作为实验变量：protocol 冻结 prompt 版本哈希，支持"同模型不同 prompt"对照 —— **已完成 2026-09-08**（`solver.prompts` 正文+hash；采集优先用冻结体；创建可选 `prompt_version`）
3. ~~决策点人工标注（好 / 坏 / 存疑）写回 `decision_points`~~ ✅ 2026-09-09（见 §4）
4. 人类席位（见 `HumanPolicy`）
5. 锦标赛 / 天梯：多选手两两对打，Elo / Bradley-Terry 排名
6. CLI：`cardlab run --experiment pack.json`、`cardlab export`（`e2e_pipeline.py` 是雏形）
7. 成本：各 provider 单价表 × tokens 的费用估算；实验开始前给出预算预估
8. 非 LLM 基线选手（见 `HeuristicPolicy` / `FirstActionPolicy` / `RandomPolicy`；选手 `policy_kind` 产品化 ✅ Wave 2b / W2.1）

## 4. UI/UX 项

- ~~Demo 数据应产出一个**已走到 verdict 阶段**的完整实验，零成本看到五阶段终点~~ ✅ 2026-09-08（`seed-demo` → 主/对照 + `delta`）
- 回放解说层：关键决策点叠加 “记录行动 X、基线行动 Y、已评估候选中的最高估计收益行动 Z、估计收益差 w”（依赖 §2.2.2；高光列表 ✅ Wave 4d + Wave 5；回放当前帧 ✅ 2026-09-09；live 每帧基线仍不做）
- 决策点人工标注（好 / 坏 / 存疑）写回 `decision_points`，作为 SFT 过滤与偏好数据来源 —— **已完成 2026-09-09**（`annotation` 列 migration 4 + PATCH + DecisionView）
- ~~全站阻塞态审计：每个阻塞态遵守"替换状态行与 CTA，而不是 banner + 无效按钮"~~
  ✅ 2026-09-09（实验 harvest/empty/verdict 阻塞替换 CTA；训练页 block 替换创建按钮，warn 才用 banner）
- ~~拆分 `ExperimentDetailView.vue`（`useExperimentDetail()` composable + 阶段容器）~~
  ✅ 2026-09-09（逻辑进 `composables/useExperimentDetail.ts`；视图只留模板组装）
- i18n 按页面拆目录 `locales/zh-CN/{experiment,game,...}.ts` —— **已完成 2026-09-09**
  （`common` / `guide` / `experiment` / `game` / `analyze` / `settings`；入口仍为 `locales/zh-CN.ts`）
- 可访问性：`CardDisplay` / 表格 aria、键盘导航、`prefers-reduced-motion`

## 5. 工程质量项

- ~~拆 `experiment_service.py`：继续拆出 `experiment_collect`、`experiment_delta`，本体只留 CRUD + 组装~~
  ✅ 2026-09-08（`ExperimentCollectMixin` / `ExperimentDeltaMixin` + `experiment_errors`）
- ~~mypy strict、`ruff format --check` 进 CI（可先对 `app/core`、`app/services` 生效）~~
  ✅ 2026-09-08（`app/core`）；✅ 2026-09-09（扩到 `app/services`；`app.core.training.*` ignore）
- ~~pytest-cov 覆盖率报告~~
  ✅ 2026-09-08（报告）；✅ 2026-09-09（`--cov-fail-under=80`）
- ~~前端组件测试：把 `CLAUDE.md` 中的产品规则（"不出现 `14/10`"、"Δ 不上色"）变成对
  `ExperimentStage` / `StageVerdict` 的可执行断言~~
  ✅ 2026-09-09（`StageAction.spec.ts` 进度封顶；`StageVerdict.spec.ts` Δ 不用 success/danger）
- ~~Playwright 冒烟：启动 → load demo → 详情 → 看到 verdict~~
  ✅ 2026-09-09（`web/e2e/demo-verdict.spec.ts`；CI `e2e` job 起后端+Vite）
- ~~数据库迁移：`PRAGMA user_version` + 编号迁移列表，替代 try/except `ALTER TABLE`~~
  ✅ 已完成（`app/migrations.py`）
- 统一换行符：`git add --renormalize .`
- 安全：仅监听 localhost；任何 API 不回显 `.env` 中的 key（Settings 只返回 `configured: true`）
- 大批未提交改动按功能拆成多个 conventional commits
- ~~mypy 闸扩到 `app/services`（下一批）~~ ✅ 2026-09-09
- ~~cov `--cov-fail-under` 门槛（下一批，先有报告）~~ ✅ 2026-09-09（80）

## 6. 开源基础设施（最低优先级）

当前为单人维护，以下项延后：Dockerfile / docker-compose、`CONTRIBUTING.md`、
`CODE_OF_CONDUCT.md`、`SECURITY.md`、issue/PR 模板、`CHANGELOG.md`、版本 tag 与 Release。

## 7. 推进顺序

| 序 | 项 | 解锁 |
|----|----|------|
| 0 | 引擎四项新能力（§9.1）+ `Observation` / action id 规范化 —— **已完成 2026-09-06** | 一切抽象的地基；不先做这步，Policy 会绑死在斗地主上 |
| 1 | `Policy` 事件流接口 + `PolicyRegistry` + structured output + 非 LLM 基线 —— **已完成**：1a 2026-09-06（接口 + 注册表 + `HeuristicPolicy` / `FirstActionPolicy` / `RandomPolicy` + 引擎 `suggest_action`）；1b+1c 2026-09-07（`LLMPolicy` 接管提示词 / 工具 / 重试 / 解析，`AIService` 退化为事件消费者，动作 id 协议 + JSON Schema `enum`） | 解析问题消失；CI 可跑真实对局；Service 与 core 边界确定 |
| 2 | rollout 评估器 → 决策级 EV loss —— **已完成**：core 2026-09-06（`core/eval/`，含 determinization 与 common random numbers），接线 2026-09-07（决策点 `ev_loss` / `max_ev_loss` 过滤 / `blunder` highlight） | 支持决策诊断、数据筛选和记录定位；样本效率改善尚待独立验证 |
| — | schema 迁移机制（§5、§9.4 的前置项）—— **已完成 2026-09-07**（`app/migrations.py`） | 解锁第 2 步接线所需的 `decision_points` 加列 |
| 3 | 录制—重放 + Task/Solver/Scorer 显式化 —— **已完成 2026-09-07**：VCR + protocol v2 + ScorerRegistry（斗地主五指标全覆盖，含 `ev_loss`；按 `game_type` 注册） | harness 成型 |
| 4 | puzzle set + 输入扰动测试 —— **已完成 2026-09-08**：4a 题库抽取/跑题；4b `POST .../probe`（合法动作/手牌顺序扰动 → consistency） | 所选局面的探索性行为诊断 |
| 5 | RL env 接口 + 偏好数据导出 —— **已完成 2026-09-08**：5a duck-typed AEC `CardLabAECEnv`；5b EV 偏好 JSONL（`export-preferences`）；蒸馏对 ✅ 2026-09-09（`export-distill-preferences`） | 训练升级，不自研训练器 |
| 6 | MCP server + 研究助手草稿 —— **已完成 2026-09-08**：6a stdio MCP（读 + Wave 3a 写 `start_collect`/`cancel_collect`）；6b 结论草稿（模板+确认写入；坏手深链 Wave 3a） | 平台可被 agent 使用 |
| 7 | 第二个引擎（德扑 heads-up） | 验证引擎抽象；可穿插在 2–4 之间 |

其中 1 与 2 是"技术护城河"级别：一个把选手从 prompt 变成可组合的智能体，
一个在对局结果之外提供决策级估计收益差。后者受候选范围、隐藏牌面采样和续局策略限制，不等同于真实最优策略的遗憾值，也不能据此宣称样本效率或策略能力提升。

**原则：思考全面再实施。** 每一步动手前先落一份短设计（接口签名、持久化字段、版本号变化、
对现有测试的影响），经 §9 的约束校验后再写代码。

## 8. 待展开的设计问题

- ~~rollout 评估器的对手模型选择与默认值~~ ✅ 默认 `heuristic`；`opponent_kind` 可切 `random` / `first` / `heuristic` / `self`（`self` 对 baseline 真自博弈，LLM 席走 `self_proxy` 并写 honesty 字段，2026-09-09）
- 决策记录分别提供阵营终局标签、估计期望收益差与训练格式诊断。见[决策指标](../specs/desktop-research-workspace/decision-metrics.md)。
- ~~软兜底解析算不算成功~~ ✅ 算失败：兜底动作记 `parse_fallback` 且不进训练集。代价是
  `parser_success_rate` 在 `v3` 协议处断档（更低但更诚实），跨线实验的解析率不可直接比较
- `HumanPolicy` 等待外部输入的超时与断线语义（对局是否暂停、是否回退到规则动作）
- `EnsemblePolicy` 内部各成员的 trace 如何嵌套展示
- ~~VCR 的匹配键（prompt 哈希 + 模型 + 采样参数）与缓存失效规则~~ ✅ 匹配键 =
  SHA-256(provider + messages + model/temperature/max_tokens/top_p/response_format)；
  `response_format` 入键所以 action_id enum 一变即失效；`replay` 未命中抛 `VcrMissError`，
  不静默打真 API（见 `docs/designs/step3-vcr.md`）

## 9. 抽象层设计约束

本节是实施前的检查清单：任何改动若违反以下约束，先改设计再写代码。

### 9.1 引擎必须新增的能力

`GameEngine` 保持无状态；以下四项使 Policy / Evaluator / Env / Tool 全部与游戏解耦：

| 能力 | 签名（示意） | 使用者 |
|------|-------------|--------|
| 隐藏状态采样 | `sample_hidden_state(observation, rng) -> GameState` | Evaluator（determinization）、SearchPolicy |
| 终局奖励 | `terminal_rewards(state) -> dict[player_id, float]` | Evaluator、RL env、Scorer |
| 工具声明 | `EngineCapability.tools: list[ToolSpec]`（名称 + JSON Schema + 实现） | ToolLoopPolicy |
| 规范化动作 | `legal_actions(state, player) -> list[ActionId]` + `describe_action(id) -> str` | Policy、structured output enum、puzzle、决策点 |

`Observation` 是引擎输出的**玩家可见视图**（扩展现有 `get_public_info`），Policy 永远拿不到完整 `GameState`。
指标实现按 `EngineCapability.eval_metric_ids` 注册；斗地主 `role:landlord` 公式在
`engine/doudizhu/scorers.py`（`LandlordRoleScorer`）。仓库只出计数；summary 仍暴露稳定键
`landlord_win_rate`（Scorer overlay）。座位「当过地主」计数来自 `game_seat_results` 视图。

### 9.2 Policy 接口契约

```
Policy.decide(observation: Observation,
              legal_actions: list[ActionId],
              budget: Budget,
              ctx: PolicyContext) -> AsyncIterator[PolicyEvent]
```

- `PolicyEvent` 是封闭联合：`thinking_delta | tool_call | tool_result | llm_request | llm_usage | action`。
  最后一个事件必须是 `action`，携带一个合法的 `ActionId`。
- Policy 位于 `core/policy/`，**只依赖** `core/ai`（LLMClient）、`core/engine`（Observation、ToolSpec）。
  不 import 任何 `services/` 或 `repositories/`；对 WS 广播、span、决策点落库零感知。
- Service（现 `ai_service`）消费事件流：转发 WS、写 span、组装决策点。这是 core 与 service
  之间**唯一**的接口；`get_decision_streaming` 退化为事件消费者。
- `PolicyRegistry` 与 `LLMClientFactory` / `GameEngineRegistry` 对称；Search / Ensemble 通过
  注册表组合子 Policy，不硬编码。
- `PolicyContext` 携带 `Memory`（按 §2.1.6 作用域）、VCR 句柄、随机源；Policy 不自行读环境变量或全局状态。
- `HumanPolicy` 通过 `ctx` 提供的 awaitable 等待外部输入，接口与其他 Policy 完全相同。

### 9.3 评估与环境

- `core/eval/Evaluator(engine, rollout_policy, determinizations, n)`：对 `(observation, action)`
  返回候选期望收益估计。参数写入决策点供审查；复算还依赖相同引擎/策略实现、记录完整性与随机条件。
- `core/env/`：PettingZoo AEC 风格；仅包装 `engine` + `terminal_rewards`，不含 LLM 逻辑。
- Scorer 只消费已持久化的 games / rounds / decision_points，不重新跑对局。

### 9.4 持久化与版本

| 变化 | 承载 | 版本 |
|------|------|------|
| protocol 新增 `dataset` / `solver` / `scorer` / `engine`（Task 命名）；~~`scorer.evaluator` EV 旋钮~~ ✅ Wave 4d | `experiments.protocol` | `schema_version: 1 → 2` ✅ 2026-09-07；旧版本在 collect 时拒绝，不静默迁移 |
| 决策点 ~~`ev_loss` / `evaluator_params`~~ ✅（绿野 `_SCHEMA_SQL`）；~~`policy_kind`~~ ✅（迁移 1）；~~`tool_calls`~~ ✅ Wave 5（迁移 3，摘要形） | `decision_points` | `decision_schema_version` 1 → 2 已升；SQLite `user_version` 见下行 |
| LLM 请求/响应录制 | JSONL cassette（`data/vcr/`），按 §8 匹配键索引；`VCR_MODE=off\|record\|replay` | 独立；**已完成 2026-09-07** |
| ~~迁移机制~~ ✅ | `app/migrations.py`：`PRAGMA user_version` + 编号列表，空库初始化也执行迁移 | 迁移 5 增加 `experiment_memory`。当前迁移 10 增加供应商费用对账记录、复核事件与任务限制策略。 |

### 9.5 分层与目录

```
core/engine/   GameEngine + EngineCapability（+ §9.1 四项能力、Observation、ActionId、ToolSpec、Scorer）
core/policy/   Policy、PolicyEvent、Budget、PolicyContext、PolicyRegistry、各实现
core/eval/     Evaluator、determinization、EV loss；ScorerRegistry；puzzle pack + perturb/probe（Step 4 ✅；Analyze UI Wave 3b ✅）
core/env/      AEC 环境包装（`CardLabAECEnv` duck-typed；5a ✅）
core/training/ preference.py DPO + distill.py 蒸馏对（5b ✅；`export-distill-preferences` ✅）
core/ai/       LLMClient 不变；VCR 录制/回放（`vcr.py`）；structured output：**无** per-provider 探测，4xx 时降级丢 stream_options / response_format（Ollama→format）
app/mcp/       stdio MCP（6a ✅ 读；Wave 3a ✅ start_collect / cancel_collect；HTTP ✅ `/mcp/` 挂载）
core/research/ conclusion_draft 模板草稿（6b ✅；坏手深链 Wave 3a ✅）
services/      事件流消费（WS / span / 决策点）；Task = protocol schema，不建新实体
```

依赖方向不变：`api → services → repositories`，`services → core`，core 内部
`policy → ai, engine`；`eval → engine, policy`；`env → engine`。任何反向 import 视为违规。

### 9.6 不做的事

- 不引入多智能体编排框架（LangGraph / CrewAI 等）
- 不自研 RL 训练器
- 不为 Task 建新表 / 新 API
- 不在 Policy 或 Evaluator 中出现任何游戏名（`doudizhu` 只能出现在 `core/engine/doudizhu/`）
- 不让 Memory 默认开启

## 研究工作台主流程（2026-09-11）

已实现：对局后默认审查全部决策；实验详情直接编辑假设与结论、比较已有实验、用已有选手创建对照。训练为可选路径，零可训练样本仍可诊断；对照创建与运行分开，URL 入口仅打开开始确认。

第二批已实现：冻结协议逐字段审查与允许变化声明；统一共同有效配对集合；重复种子排除与冲突列表；以首列为参照的中性矩阵；服务端计算并持久保存、重开、导出比较快照。详情页对缺失或未声明差异不作受控结论。比较只接受当前嵌套 Task 协议。

第三批已实现：引用快照范围内的决策，追加保存观察、解释、局限与证据内容；检测原始决策变化或删除；导出比较与所选证据的研究报告。

可读成果（2026-11-06）：正式版本可进入独立报告，展示冻结条件、配对统计、作者解释和证据来源；支持引用与当前决策/比较位置往返、离线 HTML 与数据 JSON 导出。明确统计假设、选择偏差、原记录变化和复现边界，见[第四批 A](../specs/desktop-research-workspace/batch-4a.md)。

后续设计（2026-11-07）：从正式报告选择基线并核对冻结条件，复用单阶段 Prompt A/B 向导，以新假设和主指标保存变体。新变体及其留出组保留来源结论的具体版本；复用已观察的调试发牌仍属探索性工作，见[第四批 B](../specs/desktop-research-workspace/batch-4b.md)。单个决策的局面测试见后续第四批 C；整组场景抽样仍待实现。

场景导航（2026-11-07）：运行内当前记录可按互斥规则筛选，逐层进入对局与决策，并返回原筛选、分页和记录，见[第三批 B](../specs/desktop-research-workspace/batch-3b.md)。冻结比较已支持从场景诊断进入共同有效样本中的同源对局和决策，保留原场景及步骤，见[第三批 C](../specs/desktop-research-workspace/batch-3c.md)。公开分类阈值、分母、单侧匹配及事后分组局限；整体诊断与导航计数使用不同范围，不新增场景胜率或策略排名。牌桌联动见第三批 D；整组场景抽样仍待实现。

后续验收项：运行前预注册设计、显式重复编号/冲突选择、完整可运行复现包、评估器校准、运行预算与恢复及真实案例验证。当前声明为事后审查；保存比较不代表这些能力已完成。

针对性测试（2026-11-08）：从决策证据填写问题，严格核对连续历史与至少两个合法行动，冻结原有行动收益估计和评估参数。复用离线基线与输入顺序扰动测试，提供来源决策往返、来源变化拒绝和显式分母，见[第四批 C](../specs/desktop-research-workspace/batch-4c.md)。限于已评估且可回放的单个局面，不代表模型优势、整体稳健性或独立验证。

历史测试（2026-11-08）：分页读取已保存基线/扰动记录，保留测试时的来源、参数及规范化内容指纹；当前来源变化或历史来源未记录时显式说明。可读 HTML 与 JSON 导出共用所选记录，来源决策往返和刷新保留原结果，见[第四批 D](../specs/desktop-research-workspace/batch-4d.md)。读取不执行策略、不改写历史。

测试引用（2026-11-08）：可核对的单决策测试可显式加入比较草稿；预览与发布核对冻结样本、来源及评估条件，发布时保留全文。报告和 HTML/JSON 显示冻结内容与当前文件状态，支持测试—决策—原报告引用往返。仅作探索性诊断，不增加有效样本。见[第四批 E](../specs/desktop-research-workspace/batch-4e.md)。

批量引用（2026-11-08）：新抽取记录保存候选清单、阈值、排序和数量上限，并逐局面核对连续来源；全部入选来源通过比较范围及发布检查后方可引用。明确抽取时重新估计与原决策估计的区别，展示候选、入选和来源对局数，说明选择偏差与同局相关性。旧记录缺少依据时不补造来源；不自动缩小引用范围。见[第四批 F](../specs/desktop-research-workspace/batch-4f.md)。

牌桌与决策引用入口（2026-11-08）：共同样本的共享步骤同步显示两侧行动前牌桌、记录动作和引用，重建核对与局面测试共用连续来源实现。缺口或版本不符停止该侧，默认行动者信息与研究者重建手牌明确区分。决策现场按冻结样本和截止时间选择比较，先预览后显式加入既有草稿；报告不把重建画面当作原始历史快照。见[第三批 D](../specs/desktop-research-workspace/batch-3d.md)。

测试直接引用入口（2026-11-08）：单局面和批量测试结果可选择符合全部来源及截止范围的比较，复用预览与既有草稿。查阅后内容变化会阻止引用，重复不覆盖原说明；导航保留测试和报告位置。仅支持有完整来源依据的既有测试格式，不表示原始调用记录或任意附件已可正式引用。见[第三批 E](../specs/desktop-research-workspace/batch-3e.md)。
