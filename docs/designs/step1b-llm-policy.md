# 设计：把现有 LLM 决策逻辑收进 LLMPolicy

> 第 1 步的后半段。1a 已经落地了 `Policy` ABC、事件流、`Budget`、`PolicyContext`、
> `EngineAdvisor` 和三个非 LLM 基线。本文只讲一件事：怎么把 `AIService` 里那套
> LLM 决策逻辑搬进一个 `LLMPolicy`，而不弄丢它十几个月攒下来的容错行为。

## 为什么要搬

现在 `AIService` 同时是四样东西：prompt 组装器、LLM 传输的重试外壳、输出解析器、
决策点持久化入口。两个入口 `get_decision` / `get_decision_streaming` 各写了一遍
同样的流程（`ai_service.py:162-496`），中间只差流式那一段——已经出现过在一个入口修了
bug、另一个没修的情况。

更要紧的是它挡住了后面的路。`SearchAugmentedPolicy`、`ToolLoopPolicy`、
`EnsemblePolicy` 都不是"换个 prompt"，而是换整个决策过程；只要决策过程还焊死在
service 上，它们就只能靠往 `AIService` 里加分支实现。同理，评估器现在只能用
`ActionSelector`（同步基线），没法拿真实 LLM 选手做 rollout 对手。

搬完之后 `AIService` 的职责收缩成：拿到 `Observation` 和 `LegalAction`、选一个
policy、消费事件流、把事件翻译成 WS 广播 / trace / decision point。

## 契约缺口

policy 只能看见 `Observation` + `list[LegalAction]` + `EngineAdvisor`
（`policy/base.py:88-101` 明确写了这是为了让 `GameState` 够不着）。而今天的
prompt 路径要的东西更多。逐项对账：

| prompt 路径今天要的 | policy 侧能不能拿到 |
|---|---|
| `state.game_type` / `phase` / `round` | ✅ `observation` 同名字段 |
| `engine.format_for_prompt(state, pid)` 的渲染结果 | ✅ `observation.text` **就是**它 |
| `engine.format_legal_actions_for_prompt(...)` | ✅ 可由 `LegalAction.label` 拼出（斗地主的实现 `del state`，本来就不读 state） |
| 自己手牌 / 对手张数（工具输入） | ✅ `private["hand_cards"]` / `public["hand_counts"]` |
| 是否地主 | ✅ `public["roles"]` |
| `model_name` / `temperature` / `max_tokens` | ✅ policy 自己的配置 |
| `session_id`（模板 A/B） | ✅ `PolicyContext.session_id` |
| **prompt 模板正文**（registry + DB + A/B） | ❌ 要开数据库连接，policy 不该碰 |
| **规则正文**（`capability.rules_ref` 读文件） | ❌ 引擎元数据，policy 看不到 engine |
| **`list[GameAction]`**（喂给现有 parser） | ⚠️ 见下面的岔路 2 |

`observation.text` 已经等于 `format_for_prompt` 的输出，这是最大的好消息：
policy 不需要为了拼 prompt 去碰 state。真正的缺口只有两个——模板和规则，
它们都是**配置**而非**局面**。

## 决定

### 1. 模板和规则通过 `PolicyContext` 注入

`PolicyContext` 的 docstring 已经写明它是"交给 policy 的外部依赖"，模板正好是这个。
新增一个字段：

```python
class PromptSource(Protocol):
    async def system_message(
        self, *, phase: str, model_name: str | None, session_id: str | None
    ) -> str: ...
```

service 侧的实现持有 `PromptBuilder` / registry / `sqlite_path` / engine，
负责选模板 key、选版本、读规则、格式化 `format_instructions`；policy 只拿到
一段渲染好的 system 文本，再用 `observation.text` 和 `LegalAction.label`
拼 user 消息。数据库连接、A/B 分配、文件读取全部留在 service 层。

基线 policy 不看这个字段，所以它是可选的。

### 2. 重试和超时归 policy，`Budget` 说了算

今天的 `MAX_RETRIES = 3` / `DEFAULT_TIMEOUT = 60.0` 是模块常量，改不了也测不到。
搬进 policy 后由 `Budget` 表达：`max_llm_calls` 就是调用预算（一次重试算一次调用，
因为它真的花钱），`timeout_s` 是单次调用超时。默认值保持 `3` / `60.0`，行为不变。

provider 异常到 `AppError` 的映射（`_map_provider_error`）属于传输层，
下沉成 `core/ai` 的一个函数，policy 和 service 都能用。

### 3. 流式与非流式合成一条路径

policy 只有一个 `decide()`，内部按构造参数决定用 `chat_stream` 还是 `chat`，
流式时把增量吐成 `ThinkingDelta` 事件。service 根据 WS 连接数决定构造哪一种，
这个判断今天就在 `game_orchestration_service.py:267`，位置不变。

**保留流式失败回落非流式**：注释说得很清楚，批量 e2e 和部分 provider 不走 SSE 更稳
（`ai_service.py:439-445`）。这不是历史包袱，是实测结论。

两个入口合并后 `AIService` 少一份重复实现。

### 4. 工具走 `advisor.run_tool`，并补一个 `win_probability` ToolSpec

今天 service 预跑 `HandAnalyzerTool` + `WinProbabilityTool` 再把文本塞进 prompt。
引擎侧的 `DOUDIZHU_TOOLS` 只声明了 `analyze_hand`，`win_probability` 没有对应物。

搬进 policy 后走 `ctx.advisor.run_tool(...)`，每次调用吐 `ToolCall` / `ToolResult`
事件——这是 1a 定义这两个事件的全部意义。为此给斗地主补一个 `win_probability`
ToolSpec，它本来就只吃张数和炸弹数，没有依赖 `GameState` 的部分。

`Budget.max_tool_calls` 默认从 0 改成 2（现在就是跑两个工具）。

### 5. 失败兜底留在 policy，但换成结构化信号

LLM 调用全败或解析失败时，今天塞一个 `legal_actions[0]`，并往 thinking 里写
`[LLM调用失败，使用默认动作]` 前缀——下游 `evaluate_train_usable` **靠匹配这个中文字符串**
判 `train_usable=False`。这很脆：改一个字就静默漏采样本。

`ActionChosen.parse_fallback` 就是为此准备的。policy 照旧返回一个合法动作
（对局不能卡住），但把 `parse_fallback=True` 带出来，service 据此写
`train_usable`，不再嗅字符串。前缀文本保留（人要看），但不再是唯一判据。

## 6. 解析路径直接换成 `action_id`（1c 并入本步）

现有 parser 吃 `list[GameAction]`、吐 `GameAction`，而 policy 手上只有 `LegalAction`。
可以让 policy 把 `LegalAction.action` 掏出来喂给旧 parser，但那明着违反
"policy 必须永不解读 `.action`"；也可以改成对着 `label` 匹配，但那是纯过渡态——
1c 做完立刻被推翻，同一段匹配逻辑要写两遍。

所以**把 1c 一起做了**：prompt 展示 `id — label`，要求模型返回 `action_id`；
支持的 provider 用 JSON Schema `response_format` 把 `action_id` 限定成
合法 id 的 `enum`，模型在解码层面就无法产出非法动作；parser 退化成
"取一个 id、校验在集合里"。

代价是 prompt 协议变了，模型行为要重新验证。缓解在于 `format_instructions`
是通过 `{format_instructions}` 占位符注入的：用户存在数据库里的模板只要保留
这个占位符就自动拿到新指令，不需要手工迁移。

**降级路径**：不支持 `response_format` 的 provider（或调用被拒）走纯文本 JSON 指令，
解析逻辑完全一样，只是少了解码层的硬约束。这条路必须保留，Ollama 和部分
OpenAI 兼容端点没有 schema 支持。

## 7. soft fallback 一律计为解析失败

`used_langchain_parser` 被 trace metrics 和实验 `parser_success` 指标消费。
今天 parser 内部还有一层 soft fallback：解析不出来也不抛异常，照样返回一个动作，
于是 `used_langchain_parser=True`——指标显示"解析成功"，而模型其实没答对。

换成 id 协议之后这层 soft fallback 本来就没有存在意义了：一个响应要么给出集合内的
合法 id，要么没有。**任何拿不到合法 id 的响应都记为 `parse_fallback=True`。**

代价明确：`parser_success` 指标会在改点**断档**，改点前后的实验不能直接比。
接受这个代价，因为一个把失败算成成功的指标不值得为了连续性保留。改点会记在
路线图里，比较页面上跨改点的对比要当心。

## 不做的事

- **不动 `_record_decision_point` 和 EV 评分**。它们需要 live `GameState`，
  和 policy 抽象正交，留在 service（step2b 已经论证过为什么必须在决策当下算）。
- **不引入 LLM 原生 tool-calling**。现有 provider 客户端没有这个能力，
  工具仍是"预跑 + 文本注入"，只是改由 policy 触发并产生事件。
- **不改 WS 事件格式**。事件流是 policy 与 service 之间的内部接口，
  广播出去的 payload 保持原样，前端零改动。
- **不做 policy 的持久化配置**。选手配置里还是 provider/model，
  `kind="llm"` 是默认值；把 policy kind 暴露到 UI 是后面的事。

## 验证

现有测试里**没有**覆盖重试、超时、流式回落这三条路径（生产路径靠 orchestration 层
mock 掉了 `get_decision`）。搬家会动到它们，所以先补测试再搬：

1. `LLMPolicy` 契约测试：接入 `test_policy_contract.py` 的既有矩阵（合法动作、
   RNG 可复现、空动作列表拒绝），用假 LLM 客户端。
2. 补今天缺的：调用预算耗尽 → 兜底动作 + `parse_fallback=True`；单次超时触发重试；
   流式抛错 → 落非流式 → 成功。
3. `test_experiment_eval_metrics.py` / `test_data_quality_fallback.py` 必须原样通过——
   它们钉住的是对外语义。
