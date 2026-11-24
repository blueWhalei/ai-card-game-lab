# API 设计规范

> 接口约定。运行中的路径与字段以 `http://localhost:8000/docs` 和 `server/app/api/` 为准。

## 工作草稿

`GET /api/v1/drafts/{kind}/{object_id}` 读取当前草稿，`PUT` 保存。kind 为 `experiment` 或 `comparison`。响应 data 为 `{ revision, updated_at, content }`；不存在草稿时返回 revision=0、updated_at=null，以及由所属对象初始化的空/工作文本，不在读取时写库。

PUT 请求为 `{ expected_revision, content }`。content.kind 必须与路径一致，未知字段拒绝：

- experiment：`hypothesis`、`notes`、`conclusion`（工作摘要），各最多 10000 字符；`tags_input` 最多 2000 字符。
- comparison：`expected_revision`（正式结论发布基准）、`observations`、`interpretation`、`limitations`（各最多 10000 字符）、`evidence`（最多 30 条 decision_id/note）。草稿允许空文本；发布时仍执行正式结论必填与证据范围校验。

外层 expected_revision 是草稿修订号，与比较草稿内部的发布基准不同。过期写入返回 409 `DRAFT_CONFLICT`；所属对象不存在返回 404 `DRAFT_NOT_FOUND`；格式错误返回 422。草稿只存编辑内容，不发布结论、不修改已应用的实验笔记。正式发布冲突使用 409 `RESEARCH_CONFLICT`；刷新版本列表不应自动更改草稿的发布基准。

服务端在事务内检查修订号。前端串行自动保存、显式处理冲突并显示待保存/已保存/失败；已确认草稿可跨页面和应用重启恢复，尚未确认的修改不能承诺在强制关闭后恢复。

笔记编辑器调用 `PATCH /api/v1/experiments/{id}` 应用内容时携带 `expected_draft_revision`。服务在同一写事务内验证该草稿修订号，过期返回 `DRAFT_CONFLICT`，防止旧窗口应用已经被新草稿取代的内容。独立的实验重命名等操作不依赖草稿。

## 1. 通用约定

### 运行内场景记录

`GET /api/v1/experiments/{id}/scenarios` 只读当前运行的决策记录，仅支持斗地主。参数 `scenario` 可省略或取 `bidding / playing / endgame / bomb`；可选 `game_id`、`decision_id`（1–128 字符），`game_page`、`page` 为 1–100000，固定每页 20 条。决策 ID 必须属于当前场景、对局及决策页；缺失或范围不符返回 422 `SCENARIO_SELECTION_MISSING`，其他游戏返回 `SCENARIO_UNSUPPORTED`，不存在的运行返回 404。

返回 `experiment_id / scope=current_records / read_at / endgame_max_hand / scenario / totals / groups / games / selected_game / decisions`。totals 含 decision_n、game_n、evaluated_n、unrecorded_game_n；groups 为四个互斥组的前三项计数。game_n 是组内去重对局数，不能跨组相加。evaluated_n 仅统计非空 ev_loss，不证明评估覆盖或方法有效。games 与 decisions 含 items、total、page、page_size；未指定对局时不返回决策。

一个读事务保证当次计数和分页一致；后续请求可因新增/删除记录而变化，不是比较快照。所有查询限制同一运行，分类复用 `SCENARIO_SQL`。叫地主优先于炸弹/火箭，后者优先于残局，再归入一般出牌。残局阈值与局限在界面公开。决策预览只返回动作、手牌、评估范围等所需字段，不重复完整提示词和推理文字。详见[第三批 B](../specs/desktop-research-workspace/batch-3b.md)。

### Prompt A/B 设计

- `GET /api/v1/experiments/{id}/prompt-design`：返回 `{baseline, fingerprint, affected_player_ids, issues, options, source_conclusion}`。issues 是稳定原因码（见前端 `promptDesign.issues`），空列表表示基线满足条件；options 为当前持久化模板的 key、version、content、content_hash，包含未激活版本，选中后会独立冻结。可选查询 `source_revision_id` 核对来源结论；返回其 id、comparison_id、revision、created_at、observations、interpretation、limitations，不重复返回引用。未指定时 source_conclusion 为 null。
- `POST /api/v1/experiments/{id}/prompt-variant`：严格请求字段 `{study_id, baseline_fingerprint, template_key, version, content_hash, name, hypothesis, primary_metric}`，成功 201 返回普通实验详情。假设和主指标必填。主指标对象只接受 `{"kind":"landlord_win_rate"}` 或 `{"kind":"seat_team_win_rate","player_id":"…"}`。指定选手必须属于冻结基线中使用阶段提示词的模型席位；服务端在事务内核对。
- 事务内核对基线内容指纹、研究归属与当前模板正文哈希；发生变化返回 409 `PROMPT_DESIGN_CONFLICT`，基线不存在返回 404，设计不符合约束返回 400 `EXPERIMENT_VALIDATION_FAILED`，请求格式错误返回 422。创建不启动任何对局。
- B 的 `protocol.design` 保存 `kind=prompt_ab`、baseline_id、template_key、baseline_hash、variant_hash、hypothesis、primary_metric、affected_player_ids、created_at。其他实验可以没有 design；不转换不完整协议。`solver.prompts` 是运行实际使用的冻结正文。
- 从报告发起时，创建请求还可带 `source_revision_id`（1–128 字符），服务端在同一写事务读取该结论及冻结比较，核对基线是比较成员且 game_type、player_ids、完整 protocol 一致。名称与工作笔记修改不改变冻结条件。来源不存在返回 404 `RESEARCH_NOT_FOUND`，成员或条件不符返回 409 `PROMPT_DESIGN_SOURCE_CONFLICT`；预览分别显示 `source_run_not_member` / `source_conditions_changed`。仅在新 B 的 `protocol.design.source_revision_id` 保存来源；预留留出组时沿用，普通新设计不自动继承。来源版本不随后续结论更新；详见[第四批 B](../specs/desktop-research-workspace/batch-4b.md)。
- `PUT /api/v1/experiments/{id}/holdout` 从已冻结的调试变体 B 预留一组独立验证用牌，返回 `{baseline_id, variant_id}`。两组的 `dataset.holdout_for` 指向原设计 B，B′ 的来源指向 A′，两侧沿用 benchmark 采集上限。相同设计重复请求返回相同 ID。创建变体和创建验证组均不启动采集。
- 既有比较接口自动从匹配的 A/B 设计声明该阶段 version/content/content_hash 三个路径；此时 protocol_review 包含 design_changes，界面标注并锁定这些设计声明。没有匹配设计时不返回此字段。额外差异照常审核。固定 benchmark 计划在配对模式下也不能越界采集。详见 [第二批 B](../specs/desktop-research-workspace/batch-2b.md)。

### 1.1 基础路径

```
HTTP API:   /api/v1/...
WebSocket:  /api/v1/games/ws/{game_id}
```

### 1.2 统一响应格式

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**列表响应**（带分页）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 120,
    "page": 1,
    "page_size": 20
  }
}
```

**错误响应**：

```json
{
  "code": "GAME_NOT_FOUND",
  "message": "Game not found: game_abc123",
  "data": null
}
```

### 1.3 HTTP 状态码

| 状态码 | 使用场景 |
|--------|----------|
| 200 | GET 成功 / PUT 更新成功 |
| 201 | POST 创建成功 |
| 204 | DELETE 删除成功（无 body） |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 冲突（如对局状态不允许该操作） |
| 422 | 请求格式正确但语义错误（如非法动作） |
| 429 | 限流 |
| 500 | 服务端内部错误 |
| 502 / 503 / 504 | 上游供应商错误 / 不可用 / 超时 |

业务错误以 `AppError.status_code` 为准；上表是常见子集，完整映射见 `server/app/utils/exceptions.py`。

### 1.4 错误码规范

错误码采用 `UPPER_SNAKE_CASE`，按模块前缀分组：

| 前缀 | 模块 | 示例 |
|------|------|------|
| `GAME_` | 对局 | `GAME_NOT_FOUND`, `GAME_ALREADY_STARTED` |
| `AI_` | AI 调用 | `AI_PROVIDER_ERROR`, `AI_RATE_LIMIT_EXCEEDED`, `AI_TIMEOUT`, `AI_PROVIDER_UNAVAILABLE`, `AI_PARSE_FAILED` |
| `DATA_` | 数据 | `DATA_EXPORT_FAILED`, `DATASET_NOT_FOUND` |
| `TRAINING_` | 训练 | `TRAINING_TASK_NOT_FOUND` |
| `VALIDATION_` | 通用校验 | `VALIDATION_ERROR` |

### 1.5 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 当前页（从 1 开始） |
| `page_size` | int | API 默认 10（决策点/追踪）；前端工作台默认传 **20** | 每页条数（决策点/追踪上限 200） |

### 1.6 排序参数

```
GET /api/v1/games?sort_by=created_at&sort_order=desc
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sort_by` | string | `created_at` | 排序字段 |
| `sort_order` | string | `desc` | `asc` / `desc` |

## 2. API 端点设计

### 2.1 对局管理

```
GET    /api/v1/games                         # 对局列表（分页）
POST   /api/v1/games                         # 创建对局
POST   /api/v1/games/batch                   # 批量创建并启动对局
GET    /api/v1/games/{game_id}               # 对局详情
POST   /api/v1/games/{game_id}/start         # 开始对局
POST   /api/v1/games/{game_id}/pause         # 暂停对局
POST   /api/v1/games/{game_id}/resume        # 恢复对局
GET    /api/v1/games/{game_id}/replay        # 对局回放数据
GET    /api/v1/games/{game_id}/highlights    # 局后高光 3–5 步（由决策点派生，非 LLM）
WS     /api/v1/games/ws/{game_id}            # 实时观战 WebSocket
```

#### POST /api/v1/games — 创建对局

**Request**:
```json
{
  "game_type": "doudizhu",
  "player_ids": ["ai_bluffer", "ai_cautious", "ai_random"],
  "mode": "realtime",
  "config": {
    "thinking_delay_ms": 1000
  }
}
```

**Response** (201):
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "game_20240101_001",
    "game_type": "doudizhu",
    "status": "created",
    "player_ids": ["ai_bluffer", "ai_cautious", "ai_random"],
    "mode": "realtime",
    "created_at": "2024-01-01T10:00:00Z"
  }
}
```

#### GET /api/v1/games — 对局列表

**Query Parameters**:
```
?game_type=doudizhu
&status=finished
&date_from=2024-01-01
&date_to=2024-01-31
&page=1
&page_size=20
&sort_by=created_at
&sort_order=desc
```

#### GET /api/v1/games/{game_id}/highlights — 局后高光

由已存决策点打分，**不调用 LLM**。对局不存在时 404；无决策点时 `items` 为空。

**Response**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "decision_id": "dp_xxx",
        "round_number": 12,
        "player_id": "cfg_a",
        "reason": "bomb",
        "action_type": "BOMB",
        "cards": ["H3", "S3", "C3", "D3"],
        "parser_ok": true
      }
    ]
  }
}
```

`reason`：`last_play` | `bomb` | `fallback` | `endgame` | `branch`，不足 3 条时用普通出牌补 `play`。最多 5 条，按回合升序。

### 2.1a 实验（run）

研究组织接口：

| 方法与路径 | 请求与返回 |
| --- | --- |
| `GET /api/v1/studies` | `limit` 1–100，默认 50；`offset` ≥0。返回研究列表，含 `run_count`、`last_activity_at`，按研究/运行更新时间降序。 |
| `POST /api/v1/studies` | `{title, question}`；标题去空白后 1–120 字符，问题最多 2000 字符；拒绝额外字段。返回 201 与研究对象。 |
| `GET /api/v1/studies/{id}` | 返回研究字段、`runs`（既有实验摘要）、`comparisons`（id/title/created_at/revision_count）。缺失研究返回 404 `STUDY_NOT_FOUND`。 |
| `GET /api/v1/studies/{id}/operations` | `state=all\|active\|attention`（默认 all），`page` 1–1000000（默认 1）。返回 `study_id/state/page/page_size=20/total/items/read_at`；在同一只读事务内核对归属、筛选和分页，缺失研究返回 404。 |
| `POST /api/v1/studies/{id}/runs` | `{experiment_id}`，显式加入未组织运行；重复加入同一研究幂等，其他研究已占用返回 409 `STUDY_RUN_CONFLICT`。缺失运行或研究返回 404。 |

### 供应商项目费用同步与独立限制

首个适配器只读 OpenAI 官方 `GET https://api.openai.com/v1/organization/costs`。服务端配置 `OPENAI_BILLING_ADMIN_KEY`（SecretStr）与 `OPENAI_BILLING_ORGANIZATION_ID`，不复用模型密钥或可自定义的模型 base URL，不跟随跳转，不向前端、数据库或错误消息返回凭据/远端响应正文。配置后重启服务；没有凭据时界面说明未知，不显示零费用。可手动同步或明确启用下节的周期计划；尚未完成真实账户接入验收。

| 接口 | 约定 |
|------|------|
| `GET /api/v1/studies/{id}/billing` | 同一读事务返回当前配置、当前配置最近成功快照、最近尝试、状态、独立 admission_blocked、最近 10 次尝试和最近 10 版配置；不发起供应商请求。 |
| `PUT /api/v1/studies/{id}/billing/config` | `{expected_revision,project_id,start_date,limit,enforcement_enabled,max_age_hours,reason}`。项目为明确 proj_ ID；UTC 日期不可在未来，启用时在过去 365 天内；上限为非负 USD 十进制字符串或 null（启用需金额），最长同步间隔整数 1–24 小时。修改追加版本，当前服务端组织随版本保存。首次 expected_revision=0。 |
| `POST /api/v1/studies/{id}/billing/sync` | `{expected_revision}`。固定起点至请求时刻，含起点、不含终点，最长 366 天；按项目过滤，按 project_id / line_item 分组。全部分页验证成功才保存快照；重复同步覆盖当前展示基准，不累加历史快照。 |
| `GET /api/v1/studies/{id}/billing/attempts/{attempt_id}` | `page` 从 1 开始，每页 20 条。研究范围校验；返回不可变来源明细及当时组织、项目、查询区间、金额、状态、配置版本/上限/原因。失败尝试 amount=null，不能按零处理。 |

迁移 8 保存 `study_billing_configs` / `study_billing_attempts`；全部版本与尝试保留。JSON 小数直接解析为 Decimal，费用支持原币种负向调整，校验有限数、绝对值不超过 10^12、至多 18 位小数后精确累加，以十进制字符串保存。分页超过 20 页或明细超过 10000 条视为无法完整接收，不截断为成功；缺失金额、币种/项目不一致、重叠时间桶、异常游标或分页字段均失败。完整查询未返回行时快照合计为 0，但只表示接口返回空结果，不能证明实际支出为零。

同步先以短写事务登记 running，再释放写锁等待网络（单请求 30 秒、总计 120 秒）。同版本 180 秒内再次同步返回 409 BILLING_BUSY；占用过期后重试将旧尝试标为 interrupted。完成时按原配置版本保存；同步期间配置已变更时返回 BILLING_CONFLICT，不将旧快照归入新范围。失败保留成功历史但不采用部分明细；失败后的重试必须成功后才解除由失败造成的限制。配置/同步版本冲突、凭据或组织不匹配为 409；远端授权、限流、网络、格式错误分别以 BILLING_AUTH / RATE_LIMIT / NETWORK / RESPONSE 等安全错误码返回。

启用供应商限制后，当前版本无快照、最后完成的同步失败/中断、占用超时或距查询终点达到允许间隔均阻止新受控任务；金额大于等于上限返回 `SUPPLIER_BUDGET_REACHED`，其他不可用状态返回 `SUPPLIER_BILLING_UNAVAILABLE`（均为 409）。与人工登记限制在同一接受任务写事务中检查，**两种金额不相加、不换汇、不自动归属研究；任一启用限制触发即拒绝**。修改配置（包括金额、间隔）须重新同步；可显式关闭限制并保留原因。

统计覆盖仅限选定供应商组织/项目/区间，可能包含其他研究的共享项目费用；不包含项目外、组织层级、其他供应商或未入账费用，不能替代最终发票或研究完整成本。受控任务范围、在途请求和无未来费用预留的局限同下节。独立研究效果不能由费用金额或明细条数推出。官方依据与验收条件见[第五批 I](../specs/desktop-research-workspace/batch-5i.md)。

### 供应商费用周期计划

迁移 9 增加 `study_billing_schedule_revisions`、`study_billing_schedule_runtime` 和调度最近检查记录；同步尝试增加 `trigger=manual/scheduled` 与 `schedule_revision`。原有同步记录迁移为 manual，无计划默认关闭；不会因升级自动读取供应商费用。

| 接口 | 约定 |
|------|------|
| `GET /api/v1/studies/{id}/billing/schedule` | 读取当前计划、费用配置、运行状态、最近 10 版计划历史、服务端调度开关及最近检查时间；无副作用。 |
| `PUT /api/v1/studies/{id}/billing/schedule` | `{expected_revision,expected_config_revision,enabled,interval_minutes,reason}`。初次计划版本为 0；绑定当前费用配置。间隔为严格整数 15–720 分钟，启用时不大于 `max_age_hours × 30`；原因必填。 |

计划单独追加版本，不修改预算开关或费用快照。保存启用将下一次检查时间设为当前时间；暂停则清空未来执行安排，已接受的请求仍记录结果。费用配置变化后旧计划停止自动执行，GET 返回 scope_changed，用户须明确保存绑定新配置的计划。计划冲突为 409 BILLING_SCHEDULE_CONFLICT，费用版本冲突为 409 BILLING_CONFLICT，启用间隔过长为 422 BILLING_SCHEDULE_INTERVAL；失败保留前端输入。

`BillingScheduler` 与 FastAPI/桌面后端生命周期绑定，每 30 秒读取到期计划并更新最近检查时间，每进程最多 2 个进行中的同步。`BILLING_SCHEDULER_ENABLED=false` 可在服务端关闭调度（重启生效），不关闭预算限制；仅 stdio MCP 进程不运行此调度器。服务停止或电脑休眠期间不执行；重启后处理持久化的到期计划，每项只发起一次新的累计范围查询，不补发每个遗漏周期。计划时间不是准时执行保证。

周期/手动同步共用写事务占用。自动执行须再次核对计划版本、费用版本、启用与到期条件；过期候选返回 BILLING_SCHEDULE_NOT_DUE 而不访问供应商。同步期间以 180 秒占用恢复时间保护计划；旧请求的迟到结果不能覆盖后续快照，也不能改变新计划版本或其他请求的运行状态。网络阶段无写锁。正常停止服务取消本进程请求并保存 interrupted；进程异常退出后的占用超时可由下一次检查恢复。

成功按完成时间加配置间隔安排下一次。网络/限流/远端故障/中断会延后重试，按间隔倍增并限制至最多 24 小时；凭据/组织、查询周期及响应校验错误使 next_due_at=null，等待用户处理后手动同步成功或明确保存计划。配置前置错误也保留失败尝试，不再将“未发送 HTTP”解释为“没有同步问题”。成功的手动同步可刷新同配置的活动计划；暂停计划保持暂停。

GET 返回 `state` 为 not_configured / paused / scope_changed / attention / retry_wait / due / scheduled / running / recovering。`worker_recent` 仅表示 90 秒内有调度检查记录，不证明持续运行或完成费用同步。所有时间保存为 UTC，页面执行时间按本地时间显示。费用概览新增 `snapshot_valid_until`，仅按查询终点与 max_age_hours 计算，不推断供应商费用已入账；失败与金额上限仍独立阻止任务。页面可见且未编辑时每 30 秒只读刷新，后台调度不依赖页面打开。

周期同步不增加费用覆盖范围，也不改变预算接受任务范围：已同步、已登记金额仍不能代表完整成本。来源明细保留触发方式、关联计划版本和费用配置。见 [第五批 J](../specs/desktop-research-workspace/batch-5j.md)。

### 供应商费用对账

在 `/api/v1/studies/{study_id}/billing/reconciliations` 下提供：

| 方法/路径 | 用途 |
| --- | --- |
| `GET /?page=1` | 当前对账限制、最近 10 版策略、全研究待复核数量与每页 10 条记录。 |
| `POST /preview` | 只读核对已有成功快照，不访问供应商。 |
| `POST /csv-columns` | 读取所选文件的 CSV 表头。请求为 `{content_base64}`，返回列名数组。 |
| `POST /` | 明确保存经过指纹核对的预览；支持请求幂等。 |
| `PUT /policy` | 版本化启用/关闭待复核记录的任务限制，默认关闭。 |
| `GET /{record_id}` | 原比较内容及完整追加复核事件。 |
| `POST /{record_id}/reviews` | 带版本和原因的处置、重新待复核或作废。 |

预览输入为 `attempt_id/source_type/source_reference/organization_id/project_id/currency/source_amount/period_start/period_end/scope_note`。`source_type` 为 `cost_export/invoice_project_subtotal/invoice_total/payment_receipt`；`project_id` 可为空，但为空时不可直接比较。`source_amount` 使用带可选负号的十进制字符串，最多 12 位整数、18 位小数，拒绝 JSON 数字、指数形式和非有限值。日期表示已结束 UTC 整日服务期间 `[period_start,period_end)`，最长 366 天，不是支付或开票日期。

仅前两类项目费用依据且组织、项目、USD 币种、查询覆盖一致时计算。逐条纳入完全位于期间内的费用桶，不按比例拆分跨边界桶。返回 `result=matched/difference/not_comparable`、`reasons`、`interface_amount`、`difference`、纳入明细数和原快照身份/查询范围；差额定义为接口区间金额减依据金额，精确计算、无自动容差。不可比较的金额和差额为 null；无返回明细的数值零不证明真实费用为零。金额相同不证明来源真实性、费用归属或账单完整性。

保存请求在预览输入上加 `request_id/expected_preview_hash`，写事务内重算指纹，不接受改变后的预览。保留计算版本、用户输入、来源身份、区间金额和差额；重复同请求返回原记录，改变内容返回 `RECONCILIATION_CONFLICT`，预览变化返回 `RECONCILIATION_CHANGED`。不保存原始文件，不把用户录入称为已核验账单。原始 API 快照明细继续通过既有来源入口查看；历史对账内容不会被新同步覆盖。

项目费用 CSV 模式使用 `source_type=cost_export`、非空 `project_id` 和 `source_amount=null`，在预览及保存中传入同一个 `csv` 对象。该对象含 `filename/content_base64/amount_column/date_column` 及可选的 `organization_column/project_column/currency_column`。文件支持 UTF-8（含 BOM），最大 512 KiB、128 列、10,000 个数据行。服务日期为 ISO 日期、带 UTC 时区的零点时间或 Unix UTC 零点秒。逐行核对日期和已映射范围字段，拒绝不合格数据。未映射的组织、项目、币种按用户声明处理。服务端用十进制计算合计，响应 `input.source_amount` 返回计算值。响应及保存记录的 `csv_evidence` 保留文件名、SHA-256、解析版本、列映射、行数和首末服务日期。成功或表单校验失败的响应均不回传文件内容。文件日期跨度和摘要无法推断账单完整性。见 [第五批 L](../specs/desktop-research-workspace/batch-5l.md)。

策略输入为 `expected_revision/enabled/reason`。复核输入为 `expected_revision/action/reason`，`action` 为 `resolve/reopen/void`，追加事件、保留原计算；作废后不再改状态，修正输入须另建记录。差异和不可比记录默认待复核；金额一致记录不产生待复核差异，只可作废。记录与所有事件受研究归属约束，跨研究不可读取或处理。

启用策略时，任何未处置、未作废的差异或不可比记录（包括旧费用配置和其他分页）拒绝新受控任务，返回 `SUPPLIER_RECONCILIATION_PENDING`。策略在既有接受任务写事务中检查，独立于快照金额、失败及时效条件；同步成功、暂停计划、改变费用配置不会自动处置差异。`GET /billing` 新增 `cost_admission_blocked/reconciliation_blocked`，原 `admission_blocked` 为两者之一触发。复核不会扣减费用、放宽金额上限或停止在途调用。

对账结果记录所选范围内的算术关系及复核过程。账单真实性、完整费用和实际支出上限不由对账结果确认。带 CSV 来源的已保存记录可用原始文件和对应数据库只读复算。 [对账策略](../specs/desktop-research-workspace/batch-5k.md) · [复算与真实账单验收流程](../specs/desktop-research-workspace/billing-acceptance.md)

### 研究预算与费用登记

本节费用只来自人工登记，不从 Token 用量估算；供应商费用同步使用独立接口和合计，不混合相加。每项研究固定一种人工登记币种 CNY、USD 或 EUR，首次保存后不可修改，不进行汇率换算。金额请求为非负十进制字符串（最多 9 位整数、6 位小数），不接受 JSON 数字、指数形式或负数；零有效。数据库保存百万分之一货币单位的整数，接口使用六位小数的字符串，合计不通过浮点数。

| 接口 | 约定 |
|------|------|
| `GET /api/v1/studies/{id}/finance` | `page` 1–1000000，默认 1，每页 20 条；在同一只读事务读取预算、全研究合计、记录和最近 20 版预算历史。 |
| `PUT /api/v1/studies/{id}/budget` | `{expected_revision, currency, limit, enforcement_enabled, reason}`；初次版本为 0，limit 可为 null，启用限制时必须有金额；说明 1–1000 字符。成功追加版本，旧版本保留。 |
| `POST /api/v1/studies/{id}/expenses` | `{request_id,currency,amount,incurred_on,source_type,source_reference,scope_description}`；成功 201。发生日期为日期字段；来源为 `provider_statement/payment_receipt/manual_allocation`。请求编号 1–128、凭据编号 1–200、归属及分摊说明 1–2000 字符。须先保存研究币种。 |
| `POST /api/v1/studies/{id}/expenses/{entry_id}/void` | `{reason}`，1–1000 字符；保留原记录、来源、作废原因和时间，不删除原金额。重复同原因作废幂等，不同原因冲突。 |

读取返回 `study_id/page/page_size/total/active_count/voided_count/recorded_amount/budget_difference/admission_blocked/budget/budget_history/items/read_at`。total 为所有记录（含作废）的条数；active_count 为未作废条数。合计包含本研究所有未作废记录，无日期限制，独立于分页；无有效记录时 recorded_amount 与 budget_difference 为 null，不暗示实际支出为零。差额等于预算减已登记合计，可以为负，**不是供应商余额或实际可用预算**。预算记录含版本、币种、limit、enforcement_enabled、原因及登记时间；费用列表按 created_at、id 降序，保留原始来源与作废字段。研究、预算及记录变化后下次读取可能不同。

写请求使用 `BEGIN IMMEDIATE`：预算过期版本返回 409 `BUDGET_CONFLICT`，变更币种返回 `BUDGET_CURRENCY_LOCKED`；费用币种未设置或不匹配返回 `EXPENSE_CURRENCY`。相同 request_id 与相同内容重试返回原记录，改变内容返回 `EXPENSE_CONFLICT`；同一研究来源凭据编号唯一（包括已作废记录），重复返回 `EXPENSE_DUPLICATE`。来源编号不能识别不同编号下的同笔费用，登记者仍需核对去重。缺失研究或费用为 404 `STUDY_NOT_FOUND/EXPENSE_NOT_FOUND`，输入不符合约定为 422。

启用限制后，内部以全部未作废金额合计（空集为零）比较上限，达到或超过即拒绝新的受控任务；因此零上限即使没有登记记录也会阻止。`ensure_study_budget` 在服务端采集预留、对局启动、对局恢复及关联训练任务创建的写事务中检查，返回 409 `STUDY_BUDGET_REACHED`。这些任务按当前 `study_runs` 归属核对，HTTP/MCP/原生入口共用服务。已接受任务及在途调用不自动中断，批量启动过程中若预算被修改，已启动的部分不回滚。试玩、未关联训练、决策预览及其他研究不在限制范围。没有为未来费用预留额度，登记延迟、遗漏和并行任务可能使实际费用超限；此功能不是实际支出的硬上限，也不是结算系统。见[第五批 H](../specs/desktop-research-workspace/batch-5h.md)。

创建实验可携带 `study_id`；省略时自动建立研究，`hypothesis` 初始化研究问题。研究/关系/运行创建在同一事务提交，指定不存在的研究不会留下运行。实验读取统一返回 `study_id: string | null`，null 表示未组织。复制继承源研究，配对对照不能指定另一研究。研究组织不改变已冻结的实验协议。

比较归属按冻结结果的全部实验 ID 判断：必须全部属于同一研究才显示在其工作区；跨研究比较仍可通过比较库读取。不会创建另一份快照或正式结论。读取接口不自动归组、运行或发布。

对局任务接口按运行统计当前保存的游戏状态，无时间限制。`active` 包含待启动（created/pending）、running、paused；`attention` 包含 failed、interrupted 或未知状态。筛选先于分页，按运行更新时间、ID 降序。`items` 提供运行 `id/name/target_games/game_count/states/no_bid_count/trace_count/usage`；无叫地主为完成记录的子集。计划局数不是预算或有效样本保证，待启动不证明已进入执行队列。

`usage` 的 `prompt_tokens/completion_tokens/total_tokens` 分别提供 `value/recorded_count/missing_count/invalid_count/overflow`。只汇总通过游戏归属当前研究与当前页运行的 trace，不重复叠加 spans 或 rounds。非负安全整数为有效字段（包括零）；缺失或 null 单独计数，损坏 JSON、非对象、布尔/字符串/负数/非整数及安全整数范围外字段计为无效。三个字段独立合计，不补算总数；无有效记录或合计超过 2^53−1 时 value=null，后者 overflow=true。读取时间带时区，不代表数据冻结。用量可能遗漏请求、重试和供应商记录，不是账单、费用、预算余额、训练用量或独立对局样本数。接口不启动、恢复或重试任务。

```
GET    /api/v1/experiments                   # 实验列表（含 summary + next_step + 精简 delta）
POST   /api/v1/experiments/offline           # 创建一局离线试跑（不自动采集）
POST   /api/v1/experiments                   # 创建实验（选手人数由引擎 min/max 校验；可选 hypothesis/tags/collect_mode）
PATCH  /api/v1/experiments/{id}             # 更新 name/notes/hypothesis/conclusion/tags
POST   /api/v1/experiments/{id}/clone        # 克隆实验（可选 copy_deal_seeds / copy_hypothesis）
GET    /api/v1/experiments/compare           # 跨实验对比（单组胜率的 Wilson 置信区间 / 延迟 / Token / 可训练占比 / 解析成功率 / 样本量与区间宽度提醒）
GET    /api/v1/experiments/{id}              # 实验详情 + summary + timeline + validation + next_step + delta + benchmark
GET    /api/v1/experiments/{id}/export       # 实验包 JSON（选手快照 + protocol + 种子；不含 API 密钥）
POST   /api/v1/experiments/import            # 导入实验包（缺选手则创建，已有 id 则复用）
POST   /api/v1/experiments/{id}/collect      # 按协议快照批量开局（座位级供应商预检；benchmark 用固定 deal_seed，种子用尽则 400）
POST   /api/v1/experiments/{id}/cancel-collect  # 停止对局：取消本实验所有活跃对局（created/running/paused/pending → cancelled）
```

采集请求体为 `{"count": 2, "idempotency_key": "调用方生成的唯一请求键"}`。`count` 为 1–50；请求键可选、长度 1–128，同一实验内唯一。未提供键表示每次请求都是新批次。

- 响应不确定或启动中途失败时，重试必须复用原键和原 `count`；服务返回原批次 `game_ids`，仅尝试启动仍为 `created` 的对局。
- 同一键更换 `count` 返回 HTTP 409，错误码 `COLLECT_IDEMPOTENCY_CONFLICT`。
- 预留阶段事务内保存整批 games、种子协议与请求记录，失败整体回滚且不启动模型调用。启动发生在事务提交后；启动失败不撤销已开始的对局，也不重新分配种子。
- 已完成、已取消、已中断或已归档的原批次不会因重试再次开局。新批次必须使用新键。请求记录随实验保留，归档对局不会重置预留序号。
- 前端阻止重复提交，并在 sessionStorage 中保留失败请求的键，收到成功响应后清除。HTTP 201 的 `count` 是原批次大小，运行结果请查询实验详情。

`GET /api/v1/experiments` 每条附带与详情同形的 `next_step`，以及可选的精简 `delta`（存在对照实验时）：`primary_metric` / `affected_player_ids` / `difference_basis` / `verdict_key` / `can_conclude` / `win_rate_diff` / `paired_n` / `inconclusive_reason` / `this_decisive_n` / `peer_decisive_n` / 对照身份字段；**不含** `scenario_diffs` 与完整置信区间矩阵。运行列表用它渲染「一句状态 + 下一步」，不必逐条拉详情。进度展示（列表 / 详情 / 对比选择器）用前端 `formatExperimentProgress`：分子不超过 `target_games`，超额写成「多跑了 N 局」，不要直接显示 `14/10` 这类未加说明的超额比。

`GET /api/v1/experiments/{id}` 的 `games[]` 带 `progress`：`{ phase, round, player_id }`。`phase` 为 `queued` / `bidding` / `playing` / `endgame`（来自该局最近一条决策点；尚无决策则为 `queued`）。详情进行中列表用一句进度文案展示，不另加 KPI 列。

`GET /api/v1/experiments/{id}` 附加字段：

- `timeline[]` — `created` / `first_collect` / `first_finished` / `dataset_registered` / `training_completed` / `control_created`
- `validation` — `control_experiment_ids`、`validation_ready`、`suggested_compare_ids`、`control_progress[]`
- `next_step` — `{ id, action, ref_id? }` 下一步引导。采集结束且没有关联对照时为 `review_decisions`（审查全部决策），不依赖训练状态或可训练样本数；`collect_control` 跳转对照实验并打开开始确认，不自动运行。对照已就绪则为 `review` + `action=stay`（留在详情看结论，不去对比页）。
- `delta` — 相对源实验（`vs_source`）或首个对照（`vs_control`）的一屏结论：`win_rate_diff`（本实验 − 对照）、`paired_n`、`difference_basis`（paired / unpaired / null）、双方 CI 与决胜局数、`can_conclude`、`inconclusive_reason`（`no_games` / `peer_not_ready` / `low_power`）、`verdict_key`。无对照时为 `null`。`primary_metric` 和 `affected_player_ids` 指明观察对象及干预范围，`design_hypothesis` 来自这对运行的冻结设计。已设计的 A/B 缺少有效配对时差值为 null。自由比较无配对时可显示全组描述差值，标记 unpaired。双方全组胜率与区间分别使用 `this_win_rate`、`peer_win_rate` 及其 `_ci` 字段。
- `delta.verdict_key` — `stronger` / `weaker` / `even` / `peer_pending` / `no_data` 表示观察方向；`even` 仅表示差值点估计为零，不表示等效。`can_conclude=true` 要求质量门槛、有效配对、有限且有效的差值区间严格位于零的一侧、McNemar p < 0.05 及协议审查通过。不满足时主句展示证据限制。`inconclusive_reason` 还包括 `protocol_mismatch`、`missing_paired_evidence`、`uncertain_difference`。这是探索性规则，不是功效计算、多重比较校正或普遍优势证明。
- `summary.credibility` — `{ decisive_n, win_rate_ci_width, low_power }`（决胜局 < 20 或 CI 宽 > 0.3 则 `low_power`）。该字段是样本量/区间宽度提醒，没有基于备择效应量计算统计功效。
- `benchmark` — 仅 `collect_mode=benchmark`：`{ seed_total, seed_started, seed_finished, seed_failed, seed_running, seed_remaining, extra_games, complete }`。分母是创建时写入的 `deal_seeds`。随机发牌（`free`）为 `null`。详情页阶段下方用这份覆盖率加上 `summary` 里的地主胜率 / 解析 / 可训练 / P50 / 每局 Token，作为**本实验**指标。

创建请求可选 `collect_mode: "free" | "benchmark"`；`benchmark` 预填固定 `deal_seeds`（见 `GET /api/v1/system/benchmark-seeds`）。协议不完整则拒绝开局。`collect_mode=benchmark` 且声明种子已用完时，`POST .../collect` 返回 400，不会再追加随机种子。对照实验（`pair_deals`）会把 `collect_mode` 写成 `free`（同源发牌验证，不出 benchmark 覆盖报告）。`POST .../cancel-collect` 取消本实验进行中的对局，返回 `{ cancelled_game_ids, count }`。

#### 实验包 / 选手包

`kind` 为 `cardlab.experiment_pack` 或 `cardlab.player_pack`（`schema_version` 为 `1`）。导出字段不含 `api_key` / `*_api_key`；`requirements.providers` 与 `requirements.ollama_tags` 列出导入方需要在本机配置的供应商与 Ollama 标签。导入时已有选手 id **不覆盖**。

#### GET /api/v1/experiments/compare

**Query**: `ids=exp_a,exp_b`（2–5 个不同实验，顺序决定参照列）；可重复 `allowed_changes=solver.players.0.model_config.temperature`。最多 32 个精确 Solver 参数路径；规则、评估器、种子计划不可豁免，非法路径返回 400。

**Response** 保留 `experiments[]`，新增：

- 选手的 `wins` 按所在阵营计胜，`decided_games` 为可确认该席位胜负的局数。分母为零时，`win_rate` 和 `win_rate_ci` 均为 null。配对样本中有无法归属席位的结果时，`paired_wins` 为 null。
- `metric_version: "paired-cohort-v5"`、`computed_at`：指标口径版本与计算开始时间。各组数据在同一 SQLite 读事务中读取。
- `protocol_review`：首列 `baseline_id`、`allowed_changes`、逐字段 `differences`（参照/变体值、缺失标记、可声明与已声明标记）、`unknown` 缺失字段、`controlled` 和原因列表。仅两组、冻结协议完整且所有差异都在声明内时可通过配置检查；多席位同时变化、跨局记忆和不支持的配对口径仍受限制。声明是事后审查，不是预注册，也不构成显著性或能力结论。
- `coverage`：`planned_shared` 为共同计划种子数，`effective_n` / `effective_seeds` 为共同有效集合，`members` 记录每个有效种子的各实验 game_id。每组列出计划/有效/非共同有效数量、缺失/重复/未完成/无效胜负/席位不匹配的互斥排除数、冲突种子与 game_id、无种子及计划外记录数。

`coverage` 中 `planned_shared = effective_n + excluded_n`。每个 `excluded_pairs` 条目含种子、以运行 ID 为键的排除原因。发牌用途 `deal_purpose` 取 development、holdout 或 mixed；详情的 `delta` 同样提供用途、四格计数、`paired_excluded_n` 和区间方法。

有效种子必须在每组中只有一条记录、`status=finished`、已知胜者及 landlord/peasant 结果、席位顺序匹配。在设计指定选手时，每侧还须有完整席位阵营胜负，缺失计入 `missing_seat_outcome` 并排除整对。重复记录（包括失败后的重跑）全部排除，不按记录顺序挑选。`paired_n`、配对胜率、座位胜场、配对差值与统计检验均使用同一共同有效集合；没有有效样本时配对率和差值为 null，计数为 0。整体描述指标仍使用各自全部样本。比较只接受当前嵌套 Task 协议（schema_version=2）；其他结构返回 422，不提供转换或回退。

两组比较附加 `paired_summary`（`primary_metric`、`affected_player_ids`、`win_rate_diff`、`shared_seeds`、`outcome_counts`、`ci_method`、`paired_p`、`paired_ci`、`low_power`）。`shared_seeds` 始终表示共同有效样本数；有源/对照关系时差值为对照减源，无关联时为第二列减第一列。`outcome_counts` 按 A=source、B=control 给出 `both_won / a_only_won / b_only_won / both_lost`。精确 McNemar 检验及保守 95% 配对差值区间使用同一共同样本，方法为 `clopper_pearson_bonferroni`。详见[计算与验收](designs/paired-stats.md)。详情页差值仍为当前实验减关联实验；未通过无声明的协议审查时 `can_conclude=false`、`inconclusive_reason=protocol_mismatch`，引导打开比较页。

#### 比较快照

| 方法与路径 | 语义 |
|---|---|
| `POST /api/v1/experiments/comparisons` | `{title, experiment_ids, allowed_changes?}`；重新计算并保存，返回 201 和 `{id,title,created_at,result}` |
| `GET /api/v1/experiments/comparisons` | `limit` 1–100（默认 30）、`offset` ≥0；按创建时间和 ID 降序列出元数据 |
| `GET /api/v1/experiments/comparisons/{id}` | 返回已保存结果，绝不重新计算；不存在返回 404 |

`comparison_snapshots` 是独立的追加式 SQLite 表，启动幂等创建；没有修改接口，不与可删除的实验建立级联外键。保存时只接受实验 ID 和审查声明，结果由服务端计算；前端切换为服务端返回的快照。后续实验修改/补跑不改变快照，页面可通过 `?snapshot=cmp_...` 恢复并导出 JSON。比较快照本身只保存计算结果；研究结论通过独立版本关联快照。研究报告导出额外包含结论和所选证据，不包含完整对局正文或复现环境。

数据看板 `GET /api/v1/data/stats?experiment_id=` 与决策 `GET /api/v1/decision-points/stats?experiment_id=` 按实验过滤，不含试玩对局。

离线创建接收 `{name, study_id?, hypothesis?}`，成功返回 201 和普通实验记录。斗地主的三席依次使用 heuristic、first、random，目标为一局，固定牌来自引擎的第一副基准用牌。服务在同一事务内复用同策略配置、补齐缺少的选手、冻结协议并关联研究。该运行使用普通采集和回放接口，一局供验证操作流程。

### 2.2 选手配置管理（API：`/experiment-configs`）

```
GET    /api/v1/experiment-configs                    # 选手配置列表
POST   /api/v1/experiment-configs                    # 创建选手配置
POST   /api/v1/experiment-configs/readiness          # 按已选席位查看本地条件或主动查询模型目录
GET    /api/v1/experiment-configs/export             # 选手包 JSON（不含 API 密钥；可选 ?ids=）
POST   /api/v1/experiment-configs/import             # 导入选手（已有 id 不覆盖）
GET    /api/v1/experiment-configs/{config_id}        # 配置详情
PUT    /api/v1/experiment-configs/{config_id}        # 更新配置
DELETE /api/v1/experiment-configs/{config_id}        # 删除配置
```

#### 创建前检查

`POST /api/v1/experiment-configs/readiness` 接收 `{player_ids, check_connection?}`。从已保存的选手解析供应商与模型，返回 `{config_file, checks}`。每条模型席位结果含 `player_id, provider, model, status, setting`，其中 setting 只含配置项名。纯基线阵容返回空检查列表。未知选手返回 400。

默认只检查本地字段。只有显式传入 `check_connection: true` 才对配置完整的供应商各读取一次目录。云服务使用配置的基础地址和 Bearer 密钥请求 `GET /models`，Ollama 读取 `GET /api/tags`。界面区分配置缺失、访问拒绝、无法连接、目录不可读、模型未列出以及模型已列出。检查不发送对话或游戏数据。云目录支持与权限因服务而异。采集开始时重新校验冻结席位的配置，Ollama 还核对所选标签。目录可见性不衡量推理质量或账户余额。[OpenAI 模型目录](https://developers.openai.com/api/reference/resources/models/methods/list) · [Ollama 本地目录](https://docs.ollama.com/api/tags)

目录检查通过后，实际推理仍可能失败。Ollama 对话请求返回 401、403 或 404 时，当前对局立即记为失败，比较时按缺少已决结果处理。若可重试的调用错误耗尽预算，或模型始终未给出可解析的合法动作，决策记录会标记规则接管（`parse_fallback`）。复核提示词效果时，应分别报告模型选出的动作和接管动作。

#### POST /api/v1/experiment-configs — 创建选手配置

**Request**:
```json
{
  "id": "cfg_high_temp",
  "name": "High Temp 1.2",
  "notes": "高温度对照组",
  "model_config_data": {
    "provider": "openai",
    "model_name": "gpt-4",
    "temperature": 1.2,
    "top_p": 0.95,
    "max_tokens": 1024
  }
}
```

### 2.3 数据管理

```
GET    /api/v1/data/stats                    # 数据总览统计（?experiment_id= 按实验过滤，不含试玩对局）

GET    /api/v1/datasets                      # 数据集列表
POST   /api/v1/datasets                      # 创建数据集（按对局筛选导出）
POST   /api/v1/datasets/from-decisions       # 从决策点登记 ChatML（训练页首选路径）
DELETE /api/v1/datasets/{dataset_id}         # 删除数据集
```

#### GET /api/v1/data/stats — 数据总览统计

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_games": 150,
    "total_rounds": 2300,
    "games_by_type": {"doudizhu": 150},
    "models_usage": {"deepseek-chat": 1200, "qwen-turbo": 800},
    "avg_response_time_ms": 1234.5,
    "total_tokens": 580000,
    "total_prompt_tokens": 320000,
    "total_completion_tokens": 260000,
    "tokens_by_model": {"deepseek-chat": 450000, "qwen-turbo": 130000},
    "avg_game_rounds": 15.3,
    "games_with_winner": 140,
    "wins_by_role": {"landlord": 50, "peasant": 90},
    "ai_win_rates": [
      {"model": "deepseek-chat", "seat_games": 100, "wins": 60, "win_rate": 0.6},
      {"model": "qwen-turbo", "seat_games": 100, "wins": 40, "win_rate": 0.4}
    ],
    "p50_response_ms": 980.5,
    "p95_response_ms": 3200.0,
    "response_time_by_model": {"deepseek-chat": 1500.2, "qwen-turbo": 800.0}
  }
}
```

#### POST /api/v1/datasets/from-decisions — 从决策点登记数据集

SFT 首选路径。接受 `experiment_id` / `game_id` / `train_usable` / `include_thinking`（默认 false）/ `eval_ratio`（0–0.5，验证组比例；同一游戏类型与发牌种子整体进入 train 或 eval，没有种子时按 `game_id` 分组）。登记后出现在训练页。
`POST /api/v1/decision-points/export` 只写磁盘 JSONL，**不会**自动登记。

#### POST /api/v1/datasets — 创建数据集

**Request**:
```json
{
  "name": "doudizhu_sft_v1",
  "game_type": "doudizhu",
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31",
    "player_ids": ["ai_bluffer", "ai_cautious"],
    "result": "win",
    "include_chain_of_thought": true
  }
}
```

### 2.5 训练管理

```
GET    /api/v1/training/tasks                # 训练任务列表（分页）
POST   /api/v1/training/tasks                # 创建训练任务（缺 training 依赖则拒绝）
GET    /api/v1/training/tasks/{task_id}      # 任务详情（含进度）
POST   /api/v1/training/tasks/{task_id}/cancel
DELETE /api/v1/training/tasks/{task_id}      # 删除任务记录

GET    /api/v1/models                        # 模型仓库列表
DELETE /api/v1/models/{model_id}             # 删除模型
POST   /api/v1/models/{model_id}/export      # 导出部署包
POST   /api/v1/models/{model_id}/push-ollama # merge→GGUF→ollama create（需 LLAMA_CPP_DIR）
POST   /api/v1/models/{model_id}/verify      # Ollama 快速验证
```

#### GET /api/v1/training/tasks — 当前保存的训练任务

`study_id`、`experiment_id`、`task_id`、`status` 和 `state=all|active|attention`（默认 all）联合过滤，先筛选再分页；`page` 为 1–1000000，`page_size` 为 1–100（默认 10，研究概览固定 20）。按创建时间和 ID 降序。研究不存在返回 404，空研究/运行/任务参数及非法状态组返回 422；指定任务不匹配时返回空列表，不替换任务。

研究归属仅来自 `training_tasks.experiment_id` 与当前 `study_runs`。不会从数据集名称或来源推断归属，也不证明训练数据全部来自所属运行。未关联运行的任务仍可在全局训练列表查询。active 包含 pending/exporting/training，attention 包含 failed 和所有未知状态；cancelled 不归入异常组。

同一只读事务内核对研究归属并读取列表与总数。分页数据附 `read_at`（含时区）、实际 `filters`；每条任务附 `study_id/run_name`。`progress` 只保留有限的 0–1 数字，缺失或无效返回 null，`progress_state` 为 missing/invalid/recorded，零保留；不根据 completed 状态补成 100%。`config_state/result_state` 区分缺失、有效对象和损坏/无效格式，非有限 JSON 数值也属无效。结果无效时 result=null，配置无效时 config={} 并保留 invalid 状态；不可当作默认训练配置或正常结果解释。

这些字段是当前保存记录，不证明后台仍在执行或可以原步骤续训。训练进度不是剩余耗时，完成状态不是效果验证；效果需独立留出数据与预先定义的对照。接口不报告费用、预算或完整资源用量，不启动或重试训练。研究概览只读，指定任务跳转原训练页后仍沿用既有显式操作。

#### POST /api/v1/training/tasks — 创建训练任务

**Request**:
```json
{
  "name": "doudizhu_sft_v1",
  "dataset_id": "ds_001",
  "training_type": "sft",
  "base_model": "Qwen/Qwen2.5-1.5B",
  "config": {
    "learning_rate": 2e-5,
    "batch_size": 8,
    "num_epochs": 3,
    "output_format": "pytorch",
    "qlora": false
  }
}
```

### 2.6 系统信息

```
GET    /api/v1/system/health                 # 健康检查
GET    /api/v1/system/config                 # 系统配置（脱敏，只读；设置页不提供 PATCH）
GET    /api/v1/system/preflight              # 开始前检查（scope=collect|train|all；可选 experiment_id）
POST   /api/v1/system/seed-demo              # 演示：试玩局 + 主/对照实验（返回 experiment_id / game_id）
GET    /api/v1/system/game-types             # 支持的游戏类型列表
GET    /api/v1/system/engines                # 引擎 capability（slots / phases / fingerprint / eval metrics）
GET    /api/v1/system/benchmark-seeds        # 基准测试固定发牌种子列表（50 个）
GET    /api/v1/system/providers              # 支持的 LLM 供应商列表；include_status=false 只读元数据，不探测服务
GET    /api/v1/system/storage                # 存储路径与空间信息
GET    /api/v1/system/runtime-stats          # 运行时资源快照
```

`GET /preflight` 返回 `ok` / `can_collect` / `can_train` / `checks[]`（`id` + `severity` + `ok` + `message` + 可选 `params`）/ `providers` / `warnings`。UI 按 `checks[].id` 做 i18n（`params` 用于插值，如未配置的供应商列表）；`message` 为中文回退，给 curl / 非 UI 客户端。有 `experiment_id` 时按协议座位校验 provider；设置页与实验详情采集 CTA 共用此接口。

设置页为只读展示。归档天数等通过归档/清理接口传入，不经 `PATCH /system/config`。

### 2.7 数据归档与清理

```
GET    /api/v1/system/archive/stats          # 归档统计信息
GET    /api/v1/system/archive/list           # 归档文件列表
POST   /api/v1/system/archive                # 执行归档
DELETE /api/v1/system/archive/{filename}     # 删除归档文件
POST   /api/v1/system/cleanup                # 执行数据清理
```

#### GET /api/v1/system/archive/stats — 归档统计

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_games": 150,
    "total_rounds": 2300,
    "total_traces": 2300,
    "total_decisions": 2300,
    "oldest_game": "2024-01-01T10:00:00Z",
    "archive_files": 3,
    "archive_size_bytes": 1048576
  }
}
```

#### POST /api/v1/system/archive — 执行归档

**Request**:
```json
{
  "days_old": 30,
  "game_type": "doudizhu",
  "dry_run": true
}
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "archived_games": 50,
    "archived_rounds": 750,
    "archived_traces": 750,
    "archived_decisions": 750,
    "archive_file": "archive_20240201_120000.jsonl.gz",
    "freed_bytes": 524288
  }
}
```

#### POST /api/v1/system/cleanup — 执行清理

**Request**:
```json
{
  "days_old": 90,
  "dry_run": false
}
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_games": 20,
    "deleted_rounds": 300,
    "deleted_traces": 300,
    "deleted_decisions": 300,
    "deleted_jsonl_files": 5,
    "freed_bytes": 1048576
  }
}
```

### 2.8 选手配置统计（API：`/experiment-configs/stats`）

```
GET    /api/v1/experiment-configs/stats              # 所有配置统计
```

#### GET /api/v1/experiment-configs/stats — 所有配置统计

`decided_games` 是该配置所在席位有明确阵营胜负的局数，等于 `wins + losses`。无人叫地主的流局不进入分母；分母为零时 `win_rate` 返回 null。数据分析接口的 `ai_win_rates[].seat_games` 按同一局内可归属模型的各个席位分别计数。

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "config_id": "cfg_temp_09",
      "decided_games": 50,
      "wins": 30,
      "losses": 20,
      "win_rate": 0.6,
      "last_game_id": "game_abc123",
      "last_game_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### 2.9 提示词管理

```
GET    /api/v1/prompts                       # 提示词模板列表（?template_key= & active_only=）
POST   /api/v1/prompts                       # 创建提示词模板
PUT    /api/v1/prompts/{template_key}/{version}      # 更新模板
DELETE /api/v1/prompts/{template_key}/{version}      # 删除模板
POST   /api/v1/prompts/{template_key}/activate       # 激活版本
POST   /api/v1/prompts/{template_key}/deactivate     # 停用版本
```

### 2.10 调用记录与运行诊断

```
GET    /api/v1/traces                        # 追踪列表（支持 game_id、experiment_id、player_id 筛选）
GET    /api/v1/traces/{trace_id}             # 追踪详情（含子操作 spans）
GET    /api/v1/traces/metrics                # 聚合性能指标
```

#### GET /api/v1/traces — 追踪列表

**Query Parameters**:
```
?game_id=game_xxx
&experiment_id=exp_xxx
&player_id=cfg_temp_09
&model=gpt-4o
&parser_ok=true
&start_time=2026-11-09T00:00:00Z
&end_time=2026-11-09T01:00:00Z
&page=1
&page_size=10
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "tr_xxx",
        "game_id": "game_xxx",
        "round_number": 3,
        "player_id": "cfg_temp_09",
        "model": "gpt-4o",
        "prompt_version": "v2",
        "metrics": {
          "response_time_ms": 1234,
          "parser_ok": true
        },
        "created_at": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

#### GET /api/v1/traces/{trace_id} — 追踪详情

可选 `game_id/experiment_id/player_id/model/parser_ok` 均为 AND 条件；指定记录不存在或不符合筛选返回 404，不改选其他记录。返回完整保存的 `spans`。

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "tr_xxx",
    "game_id": "game_xxx",
    "round_number": 3,
    "player_id": "ai_bluffer",
    "model": "gpt-4o",
    "prompt_version": "v2",
    "input_snapshot": {
      "game_state": { ... },
      "legal_actions": [ ... ],
      "messages": [ ... ]
    },
    "output_data": {
      "action": { "action_type": "PAIR", "cards": ["HK", "SK"] },
      "thinking": "对方出了一对3...",
      "raw_response": "..."
    },
    "metrics": {
      "response_time_ms": 1234,
      "parser_ok": true
    },
    "spans": [],
    "created_at": "2024-01-01T10:00:00Z"
  }
}
```

> `parser_ok` 表示模型自己给出了一个合法的 `action_id`。自动作 id 协议
> （`prompt_version` `v3`）起，解析器不再做"猜一个动作还算成功"的软兜底：猜出来的动作记为
> `false` 并标记 `parse_fallback`，该决策点不进训练集。因此 `parser_success_rate` 在协议切换处
> **不连续**，比旧值低但更诚实；跨越这条线的实验不能直接比较解析率，需要重跑对照组。

#### GET /api/v1/traces/metrics — 聚合指标

列表与统计支持相同的 AND 筛选：`experiment_id`、`game_id`、`player_id`、`model`、`parser_ok`、`start_time`、`end_time`。起止时间必须是带时区的 ISO 8601 时间，边界包含，统一转换 UTC 后按时间比较；无时区、格式错误或起点晚于终点返回 422。未传时间则不限制时间。列表按时间降序、ID 降序稳定分页，`page_size` 最大 200。

`response_time_count` 只计入有限非负 JSON 数值；缺失、字符串、布尔值及负值排除。平均、最小、最大耗时使用这个分母；无有效记录时均为 null。`parser_evaluated_count` 只计明确 JSON 布尔状态，`parser_success_count` 只计 true；成功率由两者相除，分母为零时不展示比例。`parser_ok=false` 仅匹配明确 false，未知不算失败。

耗时图和汇总使用同一组筛选与固定起止窗口。图读取窗口内最新 200 条，按实际时间展示有效点，不平滑或插值；汇总覆盖窗口内所有符合条件记录。两次读取反映当前数据库内容，不是同一冻结快照；并发修改可能改变记录数。列表页统计无时间限制。多次调用不是独立对局样本，混合运行条件的统计不能用于因果归因或能力判断。

**Query Parameters**:
```
?game_id=game_xxx
&model=gpt-4o
&start_time=2026-11-01T00:00:00Z
&end_time=2026-11-09T00:00:00Z
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_traces": 150,
    "response_time_count": 148,
    "avg_response_time_ms": 1234.56,
    "min_response_time_ms": 500,
    "max_response_time_ms": 3000,
    "parser_success_count": 145,
    "parser_evaluated_count": 149
  }
}
```

调用记录统计不是 Prompt 对照研究。提示词效果比较从研究内的冻结基线设计开始，复用 Prompt A/B 和保存的比较快照；模板管理不提供混合全历史条件的版本差值。

## 3. WebSocket 接口设计

### 3.1 连接端点

```
WS /api/v1/games/ws/{game_id}
```

### 3.2 消息协议

所有消息使用 JSON 格式，包含 `type` 字段标识消息类型。

#### 服务端 → 客户端

| type | 说明 | 触发时机 |
|------|------|----------|
| `game_started` | 对局开始 | 调用 start 接口后 |
| `thinking` | AI 开始思考 | AI 推理开始 |
| `thinking_chunk` | AI 思考流式输出 | 推理过程中每个 token |
| `thinking_complete` | AI 思考完成（含 token 统计） | 推理结束后 |
| `action` | AI 出牌 | AI 完成决策 |
| `state_update` | 全局状态更新 | 每次动作后 |
| `game_ended` | 对局结束 | 游戏结束 |
| `game_paused` | 对局暂停 | 调用 pause 接口后 |
| `game_resumed` | 对局恢复 | 调用 resume 接口后 |
| `error` | 错误通知 | 异常发生时 |

**`thinking` 消息**：
```json
{
  "type": "thinking",
  "game_id": "game_xxx",
  "data": {
    "player_id": "ai_bluffer",
    "player_name": "诈胡大师"
  }
}
```

**`thinking_chunk` 消息**：
```json
{
  "type": "thinking_chunk",
  "game_id": "game_xxx",
  "data": {
    "player_id": "ai_bluffer",
    "chunk": "对方出了一对3",
    "chunk_type": "reasoning"
  }
}
```

**`thinking_complete` 消息**：
```json
{
  "type": "thinking_complete",
  "game_id": "game_xxx",
  "data": {
    "player_id": "ai_bluffer",
    "thinking": "对方出了一对3，我手上有一对K可以压...",
    "response_time_ms": 1234,
    "action_preview": {"action_type": "PAIR", "cards": ["HK", "SK"]},
    "prompt_tokens": 150,
    "completion_tokens": 80,
    "total_tokens": 230,
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "legal_actions": [{"action_type": "PAIR", "cards": ["HK", "SK"]}, {"action_type": "PASS", "cards": []}],
    "parser_ok": true,
    "hand_analysis": {"bomb_count": 1, "rocket": false, "strength_score": 48}
  }
}
```

**`action` 消息**：
```json
{
  "type": "action",
  "game_id": "game_xxx",
  "data": {
    "player_id": "ai_bluffer",
    "action_type": "PAIR",
    "cards": ["HK", "SK"],
    "round": 5
  }
}
```

**`state_update` 消息**：
```json
{
  "type": "state_update",
  "game_id": "game_xxx",
  "data": {
    "current_player": "ai_cautious",
    "players": {
      "ai_bluffer":  { "cardsLeft": 10, "role": "landlord" },
      "ai_cautious": { "cardsLeft": 15, "role": "peasant" },
      "ai_random":   { "cardsLeft": 12, "role": "peasant" }
    },
    "landlord_cards": ["SA", "RJ", "BJ"]
  }
}
```

**`game_ended` 消息**：
```json
{
  "type": "game_ended",
  "game_id": "game_xxx",
  "data": {
    "winner_id": "ai_bluffer",
    "winner_name": "诈胡大师",
    "winner_role": "landlord",
    "total_rounds": 23
  }
}
```

#### 客户端 → 服务端

| type | 说明 |
|------|------|
| `ping` | 心跳检测（服务端回复 `pong`） |

> 注：暂停/恢复对局通过 REST API（`POST /games/{id}/pause`、`POST /games/{id}/resume`）实现，不通过 WebSocket。

## 4. Pydantic Schema 设计原则

### 4.1 请求/响应模型分离

```python
# 创建请求 — 不包含 id、时间戳等服务端生成字段
class CreateGameRequest(BaseModel):
    game_type: str
    player_ids: list[str]
    mode: str = "realtime"

# 响应模型 — 包含完整字段
class GameResponse(BaseModel):
    id: str
    game_type: str
    status: str
    player_ids: list[str]
    created_at: datetime

    @classmethod
    def from_domain(cls, game: Game) -> "GameResponse":
        ...
```

### 4.2 通用响应包装

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T

class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

### 4.3 决策点 API

用于 SFT 训练数据的采集和导出。

```
GET    /api/v1/decision-points              # 决策点列表（PaginatedData；API page_size 默认 10，前端常传 20）
GET    /api/v1/decision-points/{id}         # 决策点详情
GET    /api/v1/decision-points/stats        # 统计数据（?experiment_id=）
POST   /api/v1/decision-points/export       # 导出 ChatML 到磁盘（不登记数据集）
POST   /api/v1/decision-points/export-preferences       # DPO JSONL（所选行动与已评估候选中的最高估计收益行动）；无 UI
POST   /api/v1/decision-points/export-distill-preferences  # 师生蒸馏对 JSONL；无 UI
PATCH  /api/v1/decision-points/{id}         # 设置/清除人工标注 annotation
```

#### GET /api/v1/decision-points — 决策点列表

**Query Parameters**:
```
?game_id=game_xxx
&experiment_id=exp_xxx
&player_id=cfg_temp_09
&game_phase=endgame
&outcome=win
&train_usable=true
&max_ev_loss=0.3
&annotation=good
&page=1
&page_size=10
```

**Response**:
```json
{
  "code": 0,
  "message": "Found 50 decision points",
  "data": {
    "items": [
      {
        "id": "dp_xxx",
        "game_id": "game_xxx",
        "round_number": 15,
        "player_id": "cfg_temp_09",
        "hand_cards": [3, 3, 4, 4, 5, 5, 13, 13, 14, 14, 53],
        "opponent_hands": {"cfg_low_temp": 5, "cfg_ollama": 3},
        "last_action": {"player": "cfg_low_temp", "action_type": "PAIR", "cards": [7, 7]},
        "game_phase": "endgame",
        "legal_actions": [
          {"action_type": "PASS"},
          {"action_type": "PAIR", "cards": [3, 3]}
        ],
        "chosen_action": {"action_type": "PAIR", "cards": [13, 13]},
        "thinking": "对手牌数较少，用中等对子压制...",
        "outcome": "win",
        "parser_ok": true,
        "train_usable": true,
        "train_usable_reason": "ok",
        "ev_loss": 0.125,
        "evaluator_params": {"candidates_evaluated": 2, "legal_action_count": 2, "determinizations": 4, "rollouts_per_world": 8, "max_candidates": 2, "opponent_kind_effective": "heuristic", "max_steps": 400, "seed": 0},
        "created_at": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 10
  }
}
```

#### GET /api/v1/decision-points/stats — 统计数据

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 150,
    "outcome_counts": {"win": 50, "lose": 80},
    "phase_counts": {"early": 30, "mid": 70, "endgame": 50},
    "train_usable_count": 120,
    "not_usable_count": 30,
    "usable_rate": 0.8,
    "not_usable_reason_counts": {
      "chosen_not_in_legal_actions": 12,
      "llm_fallback_action": 10,
      "thinking_pass_action_play": 8
    },
    "evaluated_count": 130,
    "avg_ev_loss": 0.18,
    "max_ev_loss": 0.7,
    "blunder_count": 9
  }
}
```

`ev_loss` 为 `null` 表示该手未评估，与 0.0（在已评估候选及本次采样条件下并列最高；单候选时必为零）不是一回事；
上面的聚合只统计已评估的决策点，`evaluated_count` 与平均值并列返回，
避免三条记录的平均被当成整轮结论。

#### POST /api/v1/decision-points/export — 导出 ChatML

**Request**:
```json
{
  "experiment_id": "exp_xxx",
  "outcome": "win",
  "train_usable_only": true,
  "max_ev_loss": 0.3,
  "include_thinking": false
}
```

`train_usable_only` 过滤结构有效性，`max_ev_loss` 筛选估计期望收益差，两者是不同的问题，
所以是两个独立开关。`max_ev_loss` 保留未评估的决策点，否则一打开就会静默丢掉历史数据。

**Response**:
```json
{
  "code": 0,
  "message": "Exported 50 decision points to data/datasets/decision_points_20240101_100000.jsonl",
  "data": {
    "filepath": "data/datasets/decision_points_20240101_100000.jsonl",
    "count": 50
  }
}
```

#### PATCH /api/v1/decision-points/{id} — 人工标注

**Request**:
```json
{ "annotation": "good" }
```

`annotation` 取 `good` / `bad` / `doubt`，或 `null` 清除。Decision 工作台 UI 可筛可写。

#### POST /api/v1/decision-points/export-preferences — DPO 偏好（无 UI）

按决策点过滤器导出 JSONL：`chosen` = rollout `best_action_id`，`rejected` = 模型 `action_id`。
缺少 `best_action_id` 的行跳过；默认 `min_ev_gap=0.05`。思考文本默认只出现在 rejected 侧（可选）。

单步记录的 `outcome` 为本席位终局阵营胜负，未判定为 null。`ev_loss` 为已评估候选内的估计期望收益差，缺失时为 null。`evaluator_params` 存储实际评估条件；回放和关键点的 `evaluation_scope` 投影候选数、合法动作数、牌面数、每牌面模拟次数、生效策略、步数上限和种子。见[决策指标](../specs/desktop-research-workspace/decision-metrics.md)。

#### POST /api/v1/decision-points/export-distill-preferences — 师生蒸馏对（无 UI）

请求体指定 `teacher_experiment_id` 与 `student_experiment_id`，prompt 取学生实际记录。两组需有一致的冻结引擎与决策协议，否则返回 400 / `DISTILL_PROTOCOL_MISMATCH`。在单个读事务中读取对局和决策，按唯一的发牌种子配对，并核对结束状态、类型、席位、轮次与连续记录路径。仅首次可验证行动分歧产生一条偏好；缺口、重复、上下文不一致或分歧后的记录不重新配对。双方动作均须属于该记录的合法菜单，解析回退动作排除。

响应包含 `skipped_missing_seed/unpaired/duplicate_seed/seat_mismatch/incomplete_game/invalid_context/different_path/tie/missing_prompt/missing_action`，这些计数以学生决策记录为单位，不能当作独立对局数。输出写入 `{data_dir}/datasets/distill_*.jsonl`；`metadata.preference_source=teacher_choice` 表示偏好来自教师选择，不证明教师动作具有更高期望收益。

SFT 登记保存 `filters.split_method=deal_seed_group_v1`、`group_count`、`eval_group_count` 和 `eval_groups`（组键与对局 ID）。验证比例按组取整，至少保留一组验证和一组训练；不足两组时拒绝请求，`eval_ratio=0` 不划分验证集。同源发牌隔离不保证提示词、模型输出或其他内容不存在重复。

**ChatML 输出格式**:
```json
{
  "messages": [
    {"role": "system", "content": "你是斗地主AI，根据当前状态选择最优出牌。"},
    {"role": "user", "content": "手牌: [3, 3, 4, 4, 5, 5, 13, 13, 14, 14, 53]\n对手剩余: ai_cautious(5张), ai_random(3张)\n上家出牌: ai_cautious: PAIR [7, 7]\n游戏阶段: endgame\n可选动作: 过, [3, 3], [4, 4], [5, 5], [13, 13], [14, 14]"},
    {"role": "assistant", "content": "出 [13, 13]\n\n原因: 对手牌数较少，用中等对子压制，保留小对子和炸弹作为后手。"}
  ],
  "metadata": {
    "decision_id": "dp_xxx",
    "game_id": "game_xxx",
    "round_number": 15,
    "player_id": "ai_bluffer",
    "outcome": "win"
  }
}
```

实验研究主流程允许不经过训练直接审查、创建对照、比较和编辑假设/结论。对照实验的 `validation.suggested_compare_ids` 包含当前实验与源实验；普通实验优先建议第一个对照。`hypothesis` / `conclusion` 仍是原有可编辑文本字段，不提供版本化证据快照。

### 研究结论与证据

比较快照保存后可引用冻结共同有效样本中的决策，并追加结论版本。实验笔记用于工作中编辑；这里的版本是不可覆盖的研究记录。

| 方法 | 路径（前缀 `/api/v1/experiments`） | 行为 |
|------|------|------|
| GET | `/comparisons/{id}/decisions` | 候选决策 `{total,items}`；`limit=20`（最多100）、`offset=0` |
| GET | `/comparisons/{id}/pairs` | 双组斗地主的冻结同源对局、当前场景记录计数；可选 `scenario` |
| GET | `/comparisons/{id}/pairs/{seed}` | 单副牌的双方身份、完整记录帧、首次行动分歧与场景定位；可选 `scenario` |
| GET | `/comparisons/{id}/conclusions` | 版本摘要，按版本倒序；同样支持分页 |
| POST | `/comparisons/{id}/conclusions` | 创建版本，成功201 |
| GET | `/conclusions/{id}` | 不可变 `record` 与读取时的 `evidence_status` |
| GET | `/conclusions/{id}/export` | 研究报告 JSON：比较快照、结论、所选冻结证据及读取时状态 |

创建请求包含 `expected_revision`（首次0）、`observations`、`interpretation`、`limitations`、`evidence:[{decision_id,note}]`。观察与局限必填非空白，每段最多10000字符；解释可空；最多30条不重复引用，每条说明最多1000字符。

候选和引用统一限定在 `result.coverage.members[].game_ids`，且创建时间不晚于 `computed_at`。成员必须唯一且属于对应冻结运行，不回退到运行的全部对局；缺失或无效的成员结构返回422。引用数量是决策数，不能当作有效配对样本数。保存时冻结决策动作、局面、阵营胜负、训练格式与评估字段；不复制完整提示消息和推理轨迹。版本序号在 SQLite 写事务中检查：版本冲突409，证据缺失/越界/重复422，快照或版本不存在404。

记录对照仅接受两组斗地主、相同冻结引擎条件和完整三席位。服务在读事务中核对游戏的种子、席位、所属运行、类型、结束状态与截止时间；已删除或身份不符的游戏、未知种子返回422，缺失比较快照返回404。每侧最多2000条决策，`total_rounds` 为1–2000；超限或越界轮次拒绝处理，不截断后伪装完整。

列表响应含 `comparison_id/scenario/cutoff/read_at/endgame_max_hand/cohort_n/runs/groups/items`。`scenario` 可省略或为 `bidding/playing/endgame/bomb`，非法值返回422。groups 含全部与四个互斥分类，每项的 `left_n/right_n` 为两侧决策记录数，`left_game_n/right_game_n` 为各侧涉及对局数，`pair_n` 为任一侧有记录的同源对局组数。items 含 `seed/left_game_id/right_game_id/left_n/right_n`；筛选后仅列任一侧有该场景记录的组，不要求两侧同时匹配。空组返回空列表；未筛选时保留全部冻结成员，即使记录已缺失。列表与单局均校验冻结游戏身份，不能用已删除成员的剩余数据静默重算。

计数复用 `SCENARIO_SQL` 并限制在冻结成员和截止时间内的当前记录，不是逐条冻结归档；源记录的删除或修改可能改变计数。运行整体格式诊断表使用快照保存的另一范围，不与这些导航计数混用分母。决策数不代表独立样本数，各场景对局数不能相加；单侧匹配不表示对侧表现较差。

单局响应为 `{seed,scenario,matching_turns,left,right,first_divergence,frames}`；`left/right` 含 `experiment_id/name/game_id`。帧的 `turn` 从0开始，包含 `status/reasons/left/right/left_ended/right_ended/left_scenario/right_scenario`。先对完整序列判断路径，再根据可展示的任一侧场景生成 `matching_turns`；不删减帧，不对筛选后的两列重新对齐。所选场景没有可定位步骤（包括记录缺失或重复）返回422。帧内双方只带决策标识、席位、阶段、记录手牌/对手张数/上一动作、实际动作与动作ID，不带模型推理或隐藏手牌。`first_divergence` 为首个可确认行动分歧的0基轮次，否则为null。`status` 为 `same/divergence/different_path/different_context/unverified`；`reasons` 为 `missing/duplicate/invalid_context` 的去重列表。缺失、重复或无法呈现的记录用null占位，结束侧另设标识。

仅连续且此前一致的记录路径可产生首次行动分歧；不同局面、缺口或无效上下文之后不恢复“同一路径”。记录局面包含席位、阶段、本人手牌、对手张数、上一动作与展示菜单；不表示完整模型输入相同或证明策略因果效应。页面用 `snapshot/scenario/seed/turn` 保留位置；决策现场通过 `comparison_id/compare_scenario/compare_seed/compare_turn` 返回。记录内容在读取时验证，只有发布引用时才冻结证据正文。

`evidence_status` 为 `available`、`changed`、`missing` 或 `identity_mismatch`。状态变化不修改冻结内容。导出 `kind=cardlab.research_report`，用于阅读与审查，不是包含模型、依赖和完整对局文件的可运行复现包。

`/research-reports/{revision_id}` 页面使用上述唯一导出接口，展示该结论版本及其冻结比较；新比较保存运行假设，历史缺失不从当前运行补齐。HTML 与 JSON 使用同次读取的数据，原记录状态的核对时间单列。HTML 由同一 Vue 正文生成，保留页内导航、移除应用内路由与主动内容，可离线阅读和浏览器打印。

报告地址的 `evidence` 指定引用决策。跳转至当前决策或比较时携带 `report_id/evidence`；继续查看其他步骤仍保留原报告引用，返回时恢复引用位置。运行/发牌来源仅解析冻结共同成员，不从实时对局猜测。原始内容变化有显式提示，原记录缺失或身份不符时不提供直接决策入口；冻结证据仍可查看。


### 局面测试报告的评分定义

`POST /api/v1/puzzles/packs/{pack_id}/run` 与 `/probe` 新报告使用 `metric_version=puzzle-scoring-v2`。`hit` 表示所选动作的已保存估计收益达到该局面候选最大值，并列值均计入；未评估选择的 `hit/ev_loss` 均为 null。`accuracy` 是已评估选择中达到最高估计收益的比例，`mean_ev_loss` 是同一分母的平均估计期望收益差；不是有客观正确答案的准确率。`evaluated_n/unevaluated_n` 显式报告覆盖范围；没有已评估选择时两个汇总值均为 null。

扰动测试每次使用相同决策随机种子运行原始输入和扰动输入。`consistency` 是两者的动作 ID 一致率；`repeat_consistency` 是原始输入重复运行与独立初次运行的一致率。`comparisons_n` 为局面数乘重复次数；`base_*/pert_*` 分别汇总每次对照和扰动的有效评分。重复使用同一局面不能增加独立对局数，动作一致率也不是整体鲁棒性或策略优劣的结论。旧报告保持原始计算结果，不追溯重算。


### 从单次决策建立局面测试（2026-11-08）

- `GET /api/v1/puzzles/decisions/{decision_id}`：在一个读事务内加载决策、运行、对局和历史，按发牌种子与当前引擎回放，核对每一步上下文和合法行动。返回来源 ID、运行名称、决策时间、读取时间、步骤、已有估计覆盖及完整评估参数、`source_hash`。查阅不保存文件、不模拟、不调用模型。
- `POST /api/v1/puzzles/from-decision`：提交 `decision_id`、非空 `question`（最多 2000 字符）、`expected_source_hash`（64 位 SHA-256）。再次核对来源；有效则保存一个局面的既有 pack 并返回 manifest。`extract.method=decision_record`，问题和来源分别位于 `extract.question/source`。估计逐值保留，未评估候选不补值。
- 缺失来源返回 404；历史断点/重复、上下文不一致、解析回退、未结束对局、少于两个合法行动、无有效估计或参数不完整返回 422 `PUZZLE_SOURCE_INVALID`。来源指纹发生变化返回 409 `PUZZLE_SOURCE_CHANGED`，应重新查阅，不自动重试保存。缺失运行使用既有 `EXPERIMENT_NOT_FOUND`。
- 冻结的是该次读取的数据。后续源记录变化不改变 pack；返回链接读取当前决策。不是独立验证集或历史引擎环境复现包；详见[第四批 C](../specs/desktop-research-workspace/batch-4c.md)。

### 历史局面测试记录（2026-11-08）

- `GET /api/v1/puzzles/packs/{pack_id}/results?page=1`：固定每页 20 条，返回 `items/total/page/page_size/read_at`。列表包含可查阅、无效及不支持指标版本的记录，后两者不显示推测的时间或指标。读取不会运行策略。
- `GET /api/v1/puzzles/packs/{pack_id}/results/{run_id}`：返回原始 `report`、`source_status`、本次 `read_at` 和规范化 JSON 的 SHA-256 `report_hash`。缺失返回 404；无效、结构或分母不一致返回 422 `PUZZLE_RESULT_INVALID`；未知指标版本返回 422 `PUZZLE_RESULT_UNSUPPORTED`。不替代或改写原文件。
- 新 run/probe 结果附带 `pack_snapshot`（manifest、每个局面的来源与评估条件）及 `pack_fingerprint`（规范化 manifest 和完整局面内容的 SHA-256）。原子发布且不覆盖已有记录，评分版本仍为 `puzzle-scoring-v2`。保存的逐条结果可核对相应汇总，但原输入重复选择的逐条收益未保存，不能从旧文件单独重建该部分汇总。
- `source_status` 为 `matched/changed/missing/unreadable/unrecorded`：分别表示当前测试集指纹一致、已变更、文件缺失、无法读取/校验或旧记录未保存来源。不查询当前决策以填补历史来源。内容指纹用于一致性检查，不是数字签名，也不证明当前数据库记录一致。
- URL `pack_id/result_id/result_page` 保留测试位置；来源决策携带 `puzzle_pack/puzzle_result/puzzle_page` 返回。页面和 HTML 导出共用可读正文，JSON 导出读取响应。单次测试记录仍是探索性诊断；符合下述条件的单决策或批量测试可显式加入比较结论。历史读取见[第四批 D](../specs/desktop-research-workspace/batch-4d.md)。

### 正式结论引用局面测试（2026-11-08）

- `GET /api/v1/experiments/comparisons/{id}/puzzle-packs`：列出来自比较运行的 `decision_record` 和 `rollout_spread` 测试集；列表归属不等于已通过引用核对。
- `GET /api/v1/experiments/comparisons/{id}/puzzle-results/{pack_id}/{run_id}`：返回 `result`（同历史读取结构）和 `sources:[{decision}]`。接受有来源核对的 v2 记录；单决策为一个局面，批量最多 200 个。测试集指纹、摘要、完整局面须与保存依据和来源重建结果一致；每个决策须属于冻结共同样本且不晚于统计截止。单决策要求保存评估参数与原记录一致；批量核对原决策内容指纹，使用抽取时单独保存的收益估计与参数，不声称原记录曾使用相同估计。重放已有动作以核对来源，不运行新策略或模拟。缺少依据、变化或范围不符返回 422 `RESEARCH_PUZZLE_SOURCE/SCOPE`；不自动删除不合格局面。
- 现有比较草稿及创建结论请求增加 `puzzle_evidence:[{pack_id,run_id,expected_report_hash,note}]`，默认空列表；每版最多 5 条、不重复，说明最多 1000 字符。发布事务再次核对并冻结测试、来源决策及说明，合计最多 8 MiB。预览哈希变化返回 409 `RESEARCH_PUZZLE_CHANGED`；数量、重复或体积超限返回 422 `RESEARCH_PUZZLE_LIMIT`（请求结构超限由模式校验拒绝）。任何失败不创建版本，不覆盖草稿。
- 正式 `record.puzzle_evidence` 保存引用全文；旧版本无该字段时不补写。读取/导出另给 `puzzle_evidence_status`，顺序对应引用：`record_status=available|changed|missing|invalid|unsupported`、当前文件的 `source_status`、来源 `decisions` 状态。状态变化不改写发布内容。
- 报告、测试及来源决策通过 `report_id/puzzle_evidence` 保留具体版本和测试身份（`pack_id/run_id`），返回定位到原引用；页面和 HTML 复用测试正文。仅作为探索性诊断，不改变共同样本、配对统计或有效对局数。哈希是内容一致性检查，不是数字签名或运行真实性证明。见[第四批 E](../specs/desktop-research-workspace/batch-4e.md)。

批量抽取沿用 `POST /api/v1/puzzles/extract`，`min_spread` 须为有限非负数。新 manifest 的 `extract.method=rollout_spread`，保留 `min_spread/max_per_game/max_total/evaluator_params`，后者包含实际 `opponent_kind_effective`。`selection` 保存 `order=spread_desc_stable`、已完成对局 `source_game_ids`、入选 `selected_game_ids`、按生成顺序保存的 `candidates:[{puzzle_id,game_id,spread}]`。排序与引用核对共用核心实现，极差并列保留候选原顺序。

`source_checks` 按局面 ID 保存完整原决策的 `decision_hash` 与完整局面的 `puzzle_hash`；无法核对则保存 `unverified:true`，测试仍可单独运行/查阅，但正式引用拒绝整个测试。引用时要求候选与选取规则一致、每个入选局面的观测与合法行动可由连续记录核对、全部原决策指纹一致。候选仅统计成功生成估计的局面，不是全部记录或随机抽样；阈值、上限及评估失败可能造成选择偏差，同局局面并非独立对局。历史无依据记录不补造核对结果。详见[第四批 F](../specs/desktop-research-workspace/batch-4f.md)。

### 比较牌桌与决策引用入口（第三批 D）

- `GET /experiments/comparisons/{id}/pairs/{seed}` 在既有响应增加 `boards`：`cutoff/read_at/engine_version` 与 `left/right`。每侧含 `status=verified|unverified|unsupported_engine`、`stopped_at` 和按零基轮次索引的 `frames`；每帧为 `decision_id/snapshot`，snapshot 复用 ObserverSnapshot。
- 使用当前同版本引擎、冻结种子与席位，核对连续决策及截止时间内的动作记录，输出行动前牌桌。缺失、重复、非法动作、上下文或版本不一致时停止该侧；保留已核对前缀，不跳过缺口。与局面测试共用 `services/decision_replay.py`，不调用模型或收益模拟。此处 `verified` 表示记录前缀与重建一致，不证明历史运行环境真实性或完整模型输入相同。
- `GET /experiments/evidence/decisions/{decision_id}/comparisons?offset=0` 返回 `decision_id/items/next_offset`，每页扫描 20 个候选；`items` 包含比较 `id/title/created_at/seed`。按冻结共同样本与决策截止时间查询，再通过规范范围核对；不按所属运行猜测证据范围。决策不存在返回 404。
- `GET /experiments/comparisons/{id}/decisions/{decision_id}` 返回 `comparison_id/seed/decision`，decision 使用现有引用字段。越出范围或来源缺失返回 422；比较不存在返回 404。
- `review_decision` 仅用于比较页的指定来源预览，纳入桌面地址恢复白名单。打开链接不改草稿；显式加入才复用已有草稿服务。单侧与双侧共用引用按钮，去重、30 条原子上限及明确发布规则不变。
- 页面默认隐藏其他席位重建手牌，显式研究者视角与行动者可见信息分开说明。正式报告冻结原有决策字段，不保存这次重建画面；局面/轮次数不增加独立对局数。见[设计](../specs/desktop-research-workspace/batch-3d.md)。


### 测试结果直接选择比较（第三批 E）

`GET /api/v1/experiments/evidence/puzzle-results/{pack_id}/{run_id}/comparisons?offset=0` 是只读查询。先复用正式引用的完整测试及来源核对，再按首个来源对局查询最多 20 个 `paired-cohort-v5` 候选；每个候选须通过全部来源的成员、运行、发牌种子及截止时间核对。不会按运行归属或第一条来源直接放行批量测试。

返回 `{pack_id, run_id, report_hash, read_at, items:[{id,title,created_at}], next_offset}`。`offset` 非负，下一偏移按候选数推进；本页通过条目可为空但仍有下一页。不存在或损坏/不支持的测试沿用历史读取错误，来源不符沿用 `RESEARCH_PUZZLE_SOURCE/SCOPE`。查询不保存草稿、不创建版本、不运行策略或新模拟。

结果页先核对 `report_hash` 与刚查阅内容一致，再以 `review_pack/review_result/review_hash/review_page` 打开比较内预览。预览再次读取范围与指纹；只有明确加入才更新原有 `puzzle_evidence`，重复不覆盖说明、最多 5 条。发布继续由原接口重新核对并冻结全部内容，保留 8 MiB 限制。`report_id/puzzle_evidence` 保留具体报告引用返回位置。预览地址恢复不会自动加入引用。见[设计及验收](../specs/desktop-research-workspace/batch-3e.md)。

### 正式结论引用调用记录（2026-11-09）

- `GET /api/v1/experiments/evidence/traces/{trace_id}/comparisons?offset=0`：从冻结共同样本发现候选，每次核对 20 个候选，返回 `{trace_id,source_hash,items:[{id,title,created_at}],next_offset}`。过滤后可出现空页，仍按 `next_offset` 继续；创建时间按绝对时间比较。只读，不写草稿或运行策略。
- `GET /api/v1/experiments/comparisons/{id}/traces/{trace_id}`：返回 `{comparison_id,cutoff,read_at,source_hash,trace,source}`。`trace` 含保存的输入、输出、指标及按时间和 ID 排序的全部子操作；`source` 含运行、对局、游戏类型、席位列表、发牌种子、对局时间和状态。
- 发现、预览和发布均要求 `paired-cohort-v5`，调用所属对局须在 `coverage.members` 中有唯一匹配的运行/种子，并与冻结游戏类型和席位列表一致；调用席位属于对局，对局已结束。对局、调用及子操作时间须含时区且不晚于截止；不以运行归属替代样本核对。
- 比较草稿和发布请求增加 `trace_evidence:[{trace_id,expected_source_hash,note}]`，默认空列表。每版最多 5 条不同记录，说明最多 1000 字符；单条规范化正文和来源最多 2 MiB，冻结引用总计最多 8 MiB，超限拒绝而不截断。规范化 JSON（键排序、无多余空白、UTF-8、禁止非有限值）的 SHA-256 覆盖正文、子操作和来源身份，不含读取时间或引用说明。
- 发布在原有写事务中重新核对范围和指纹，保存 `record.trace_evidence` 副本。缺失返回 404 `RESEARCH_TRACE_MISSING`，不可核对或范围不符返回 422 `RESEARCH_TRACE_INVALID/SCOPE`，体积或重复超限返回 422 `RESEARCH_TRACE_LIMIT`（请求长度超限由模式校验拒绝）。预览后变化返回 409 `RESEARCH_TRACE_CHANGED`，不发布、不覆盖草稿；重新选择比较并查阅后，可明确更新已有引用指纹并保留说明。
- 读取/导出另附 `trace_evidence_status:{[trace_id]:available|changed|missing|identity_mismatch|invalid}`；当前内容变化不影响已发布正文。旧版本未含调用引用时仍可读取。报告及 HTML/JSON 导出使用同一冻结正文，当前来源链接保留 `report_id/trace_evidence`，调用详情按 `trace_id` 精确读取，允许定位到当前列表页以外的记录。
- 记录时间符合截止不代表内容在比较创建时已经冻结；指纹用于一致性核对，不证明真实性或完整复现。保存输入可能不等于完整供应商请求，模型输出不能证明内部推理；调用及子操作是运行诊断，不增加独立对局或配对样本量，事后选取的个例不支持总体效果或因果结论。见[第三批 F](../specs/desktop-research-workspace/batch-3f.md)。
