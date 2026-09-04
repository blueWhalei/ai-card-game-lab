# API 设计规范

> 接口约定。运行中的路径与字段以 `http://localhost:8000/docs` 和 `server/app/api/` 为准。

## 1. 通用约定

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
| 422 | 请求格式正确但语义错误（如非法动作） |
| 500 | 服务端内部错误 |

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

```
GET    /api/v1/experiments                   # 实验列表
POST   /api/v1/experiments                   # 创建实验（选手人数由引擎 min/max 校验；可选 hypothesis/tags/collect_mode）
PATCH  /api/v1/experiments/{id}             # 更新 name/notes/hypothesis/conclusion/tags
POST   /api/v1/experiments/{id}/clone        # 克隆实验（可选 copy_deal_seeds / copy_hypothesis）
GET    /api/v1/experiments/compare           # 跨实验对比（Wilson CI / 延迟 / Token / 可训率 / 解析成功率 / credibility）
GET    /api/v1/experiments/{id}              # 实验详情 + summary + timeline + validation + next_step + delta
GET    /api/v1/experiments/{id}/export       # 实验包 JSON（选手快照 + protocol + 种子；不含密钥）
POST   /api/v1/experiments/import            # 导入实验包（缺选手则创建，已有 id 则复用）
POST   /api/v1/experiments/{id}/collect      # 按协议快照批量开局（座位级 provider 门闩；benchmark 用固定 deal_seed）
```

`GET /api/v1/experiments/{id}` 的 `games[]` 带 `progress`：`{ phase, round, player_id }`。`phase` 为 `queued` / `bidding` / `playing` / `endgame`（来自该局最近一条决策点；尚无决策则为 `queued`）。详情进行中列表用它拼一句进度，不加多列 KPI。

`GET /api/v1/experiments/{id}` 附加字段：

- `timeline[]` — `created` / `first_collect` / `first_finished` / `dataset_registered` / `training_completed` / `control_created`
- `validation` — `control_experiment_ids`、`validation_ready`、`suggested_compare_ids`、`control_progress[]`
- `next_step` — `{ id, action, ref_id? }` 下一步引导。训练完成后若尚无对照则为 `open_control`（开始对照实验）；`collect_control` 跳转对照实验并开始对局。对照已就绪则为 `review` + `action=stay`（留在详情看结论，不去对比页）。
- `delta` — 相对源实验（`vs_source`）或首个对照（`vs_control`）的一屏结论：`landlord_win_rate_diff`（本实验 − 对照）、`paired_n` / `paired_landlord_win_rate_diff`、双方 CI 与决胜局数、`can_conclude`、`inconclusive_reason`（`no_games` / `peer_not_ready` / `low_power`）、`verdict_key`。无对照时为 `null`。Δ **不以红绿表示好坏**（地主胜率升降取决于假设）。
- `delta.verdict_key` — `stronger` / `weaker` / `even` / `peer_pending` / `no_data`，前端渲染为 `stage.verdict.<key>` 那一句人话结论。放在后端计算是为了让评估公式与它的措辞留在同一处；`even` 的阈值是 `VERDICT_EVEN_THRESHOLD`（2 个百分点）。`can_conclude` 只决定这句话的视觉重量，不改变方向。
- `summary.credibility` — `{ decisive_n, landlord_ci_width, low_power }`（决胜局 < 20 或 CI 宽 > 0.3 则 `low_power`）

创建请求可选 `collect_mode: "free" | "benchmark"`；`benchmark` 预填固定 `deal_seeds`（见 `GET /api/v1/system/benchmark-seeds`）。协议不完整则拒采集（无懒升级）。

#### 实验包 / 选手包

`kind` 为 `cardlab.experiment_pack` 或 `cardlab.player_pack`（`schema_version` 目前 `1`）。导出时剥掉 `api_key` / `*_api_key` 等密钥字段；`requirements.providers` 与 `requirements.ollama_tags` 供导入方对照本机环境。导入时已有选手 id **不覆盖**。旧版浏览器下载的 manifest（含 `experiment` + `protocol`、无 `kind`）仍可导入。

#### GET /api/v1/experiments/compare

**Query**: `ids=exp_a,exp_b`（2–5 个，逗号分隔）

**Response** `data.experiments[]` 含 `train_usable_rate`、`parser_success_rate`、`player_stats[].win_rate_ci`、`credibility`、`protocol`、`paired_n` / `paired_landlord_win_rate`、`scenario_scores`（叫分 / 出牌 / 残局 / 炸弹的可训练占比与解析率）。  
2 个实验且存在源/对照关系时，附加 `paired_summary`（`landlord_win_rate_diff`、`shared_seeds`、`low_power`）。`GET /experiments/{id}` 的 `delta.scenario_diffs` 为相对对照的同场景 Δ。

数据看板 `GET /api/v1/data/stats?experiment_id=` 与决策 `GET /api/v1/decision-points/stats?experiment_id=` 按实验过滤，不含试玩对局。

### 2.2 选手配置管理（API：`/experiment-configs`）

```
GET    /api/v1/experiment-configs                    # 选手配置列表
POST   /api/v1/experiment-configs                    # 创建选手配置
GET    /api/v1/experiment-configs/export             # 选手包 JSON（不含密钥；可选 ?ids=）
POST   /api/v1/experiment-configs/import             # 导入选手（已有 id 不覆盖）
GET    /api/v1/experiment-configs/{config_id}        # 配置详情
PUT    /api/v1/experiment-configs/{config_id}        # 更新配置
DELETE /api/v1/experiment-configs/{config_id}        # 删除配置
```

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
      {"model": "deepseek-chat", "games": 100, "wins": 60, "win_rate": 0.6},
      {"model": "qwen-turbo", "games": 100, "wins": 40, "win_rate": 0.4}
    ],
    "p50_response_ms": 980.5,
    "p95_response_ms": 3200.0,
    "response_time_by_model": {"deepseek-chat": 1500.2, "qwen-turbo": 800.0}
  }
}
```

#### POST /api/v1/datasets/from-decisions — 从决策点登记数据集

SFT 首选路径。接受 `experiment_id` / `game_id` / `train_usable` / `include_thinking`（默认 false）/ `eval_ratio`（0–0.5，验证集比例；按 `game_id` 拆分 train/eval 两个 JSONL）。登记后出现在训练页。  
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
    "min_quality_score": 0.7,
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
POST   /api/v1/system/seed-demo              # 加载演示对局（不挂实验）
GET    /api/v1/system/game-types             # 支持的游戏类型列表
GET    /api/v1/system/engines                # 引擎 capability（slots / phases / fingerprint / eval metrics）
GET    /api/v1/system/benchmark-seeds        # 基准测验固定发牌种子列表（50 个）
GET    /api/v1/system/providers              # 支持的 LLM 供应商列表
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

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "config_id": "cfg_temp_09",
      "games_played": 50,
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
GET    /api/v1/prompts/ab-stats              # A/B 统计
PUT    /api/v1/prompts/ab-config             # A/B 配置
```

### 2.10 AI 决策追踪

```
GET    /api/v1/traces                        # 追踪列表（支持 game_id、experiment_id、player_id 筛选）
GET    /api/v1/traces/{trace_id}             # 追踪详情（含子操作 spans）
GET    /api/v1/traces/metrics                # 聚合性能指标
GET    /api/v1/traces/compare                # Prompt 版本对比
```

#### GET /api/v1/traces — 追踪列表

**Query Parameters**:
```
?game_id=game_xxx
&experiment_id=exp_xxx
&player_id=cfg_temp_09
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
          "used_langchain_parser": true
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
      "used_langchain_parser": true
    },
    "spans": [],
    "created_at": "2024-01-01T10:00:00Z"
  }
}
```

#### GET /api/v1/traces/metrics — 聚合指标

**Query Parameters**:
```
?game_id=game_xxx
&model=gpt-4o
&start_time=2024-01-01
&end_time=2024-01-31
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_traces": 150,
    "avg_response_time_ms": 1234.56,
    "min_response_time_ms": 500,
    "max_response_time_ms": 3000,
    "langchain_success_count": 145
  }
}
```

#### GET /api/v1/traces/compare — 版本对比

**Query Parameters**:
```
?version1=v1
&version2=v2
```

**Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "version1": {
      "version": "v1",
      "total_traces": 50,
      "avg_response_time_ms": 1500,
      "langchain_success_count": 45,
      "success_rate": 90.0
    },
    "version2": {
      "version": "v2",
      "total_traces": 50,
      "avg_response_time_ms": 1200,
      "langchain_success_count": 48,
      "success_rate": 96.0
    },
    "response_time_diff": -300,
    "success_rate_diff": 6.0
  }
}
```

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
    "used_langchain_parser": true,
    "win_probability": {"probability": 0.62, "confidence": "中", "reasoning": "局势均衡"}
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
```

#### GET /api/v1/decision-points — 决策点列表

**Query Parameters**:
```
?game_id=game_xxx
&experiment_id=exp_xxx
&player_id=cfg_temp_09
&min_quality=0.7
&max_quality=1.0
&game_phase=endgame
&outcome=win
&train_usable=true
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
        "quality_score": 0.8,
        "parser_ok": true,
        "win_probability": {"probability": 0.62, "confidence": "中"}
        "train_usable": true,
        "train_usable_reason": "ok",
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
    "avg_quality": 0.65,
    "min_quality": 0.3,
    "max_quality": 0.8,
    "outcome_counts": {"win": 50, "lose": 80, "draw": 20},
    "phase_counts": {"early": 30, "mid": 70, "endgame": 50},
    "train_usable_count": 120,
    "not_usable_count": 30,
    "usable_rate": 0.8,
    "not_usable_reason_counts": {
      "chosen_not_in_legal_actions": 12,
      "llm_fallback_action": 10,
      "thinking_pass_action_play": 8
    }
  }
}
```

#### POST /api/v1/decision-points/export — 导出 ChatML

**Request**:
```json
{
  "experiment_id": "exp_xxx",
  "min_quality": 0.7,
  "outcome": "win",
  "train_usable_only": true,
  "include_thinking": false
}
```

**Response**:
```json
{
  "code": 0,
  "message": "Exported 50 decision points to data/datasets/decision_points_20240101_100000.jsonl",
  "data": {
    "filepath": "data/datasets/decision_points_20240101_100000.jsonl",
    "count": 50
  }
```

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
    "quality_score": 0.8
  }
}
```
