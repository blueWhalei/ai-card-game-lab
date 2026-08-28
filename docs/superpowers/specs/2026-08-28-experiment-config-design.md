# 实验配置（Experiment Config）设计

> 状态：已实现（实现计划见 `docs/superpowers/plans/2026-08-28-experiment-config.md`）  
> 日期：2026-08-28  
> 替代概念：原「AI 角色 / AI Player」人格化配置

## 1. 背景与问题

当前「AI 角色」以 emoji + 风格化描述（激进虎 / 谨慎狐）呈现，暗示牌风/人格；但实际影响 LLM 行为的是 **provider、model、temperature、top_p、max_tokens** 以及全局提示词，而非文案人格。

另：对局数/胜率显示为 0——`player_ids LIKE` 查询把 id 中的 `_` 当通配符转义（如 `aggressive_tiger`），导致对局数恒为 0；`winner_id` 精确匹配仍可统计胜场。

## 2. 目标

将实体从「角色」彻底改为 **实验配置档**：可复用的 LLM 采样配置；对局时选择配置档入座；提示词仍在「提示词」页全局管理。

### 非目标（本期不做）

- 配置档绑定提示词版本
- 观战壳随工作台深浅色切换
- 将 `games.player_ids` 重命名为 `config_ids`（引擎与历史数据面大，下期再议）

## 3. 产品定位

| 项 | 决定 |
|----|------|
| 实体名 | 实验配置（Experiment Config） |
| 导航 | 「实验室」→ 实验配置 |
| 提示词 | 配置档**不含**提示词绑定；全局提示词页管理 |
| 备注 | 可选 `notes`，写实验意图（如「高 temperature 对照」），不做人格文案 |
| 头像 | **删除** emoji / avatar |
| 对局席位 | 请求仍用 `player_ids: string[]`，值为配置 `id` |

## 4. 命名对照

| 层 | 旧 | 新 |
|----|----|-----|
| 导航 / 文案 | AI 角色 | 实验配置 |
| 前端路由 | `/ai-players` | `/experiment-configs`（旧路径重定向） |
| REST | `/api/v1/ai-players` | `/api/v1/experiment-configs` |
| SQLite 表 | `ai_players` | `experiment_configs` |
| 字段 | `description` | `notes` |
| 字段 | `avatar` | 删除 |
| 种子 YAML | `config/ai_players.yaml` | `config/experiment_configs.yaml` |
| 代码符号 | `AIPlayer*` / `ai_player_*` | `ExperimentConfig*` / `experiment_config_*` |
| 统计 | `PlayerStats*` + `/ai-players/.../stats` | `ExperimentConfigStats*`（或同等命名）挂到 `/experiment-configs/.../stats`；查询必须精确匹配 |

## 5. 数据模型

```sql
CREATE TABLE IF NOT EXISTS experiment_configs (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    model_config  TEXT    NOT NULL,  -- JSON
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
```

`model_config` JSON：`provider`, `model_name`, `temperature`, `top_p`, `max_tokens`。

`games.player_ids` / `winner_id` / decision·trace 的 `player_id`：**继续存配置 id**（语义 = 席位上的实验配置）。

### 启动迁移

1. 确保存在 `experiment_configs`。
2. 若存在旧表 `ai_players`：将行迁入（`description` → `notes`，不拷贝 `avatar`）；成功后 `DROP TABLE ai_players`。
3. 若 `experiment_configs` 为空：从 `config/experiment_configs.yaml` 种子。
4. 已有库迁移后**保留旧 id**（如 `aggressive_tiger`），不改写历史 `player_ids`。仅**新空库**使用中性种子 id。

## 6. 统计修复

- 对局数 / 最近对局：使用 `json_each(player_ids)` 且 `json_each.value = ?`（或等价精确匹配），**禁止**对 id 做 `LIKE '%…%'`。
- 胜场：`winner_id = ?`。
- 列表统计：以**已登记的实验配置**为轴；无对局时返回 `games_played=0, win_rate=0`，前端始终展示战绩区。

## 7. API 契约

| 方法 | 路径 |
|------|------|
| GET、POST | `/api/v1/experiment-configs` |
| GET、PUT、DELETE | `/api/v1/experiment-configs/{id}` |
| GET | `/api/v1/experiment-configs/stats` |
| GET | `/api/v1/experiment-configs/{id}/stats` |

- 请求/响应：`notes` 替代 `description`；无 `avatar`。
- 采样字段请求体继续用 `model_config_data`（避免与 Pydantic `model_config` 冲突）。
- 本期直接切换新前缀；旧 `/api/v1/ai-players` 可移除（前端同步改完）。
- 路由注册顺序：`/stats` 必须在 `/{id}` 之前，避免被路径参数吞掉。
- 创建对局：仍 `player_ids`；服务端校验 id 存在于 `experiment_configs`。

## 8. 前端

- 视图：`AIPlayerView` → `ExperimentConfigView`；API 模块同步改名。
- 侧栏图标建议：`lucide:flask-conical`。
- 页眉副标题：采样参数配置档；提示词在「提示词」页统一管理。
- 卡片：名称 + id → provider/model/T/top_p/max_tokens → 可选备注 → 对局/胜率/胜场 → 编辑/删除。
- 表单：无 avatar；文案不用「角色/风格」。
- 创建对局：`选择实验配置（x/3）`；选项 `名称（provider/model · T=…）`。
- 观战：只显示 `name`，无 emoji。

## 9. 种子（仅空库）

`config/experiment_configs.yaml` 示例：

| id | name | notes | temperature |
|----|------|-------|-------------|
| `cfg_temp_09` | Temp 0.9 | 较高 temperature 对照 | 0.9 |
| `cfg_temp_06` | Temp 0.6 | 较低 temperature 对照 | 0.6 |
| `cfg_temp_12` | Temp 1.2 | 高 temperature 基线 | 1.2 |

provider/model 默认与现网一致（如 deepseek / deepseek-v4-flash），可在 YAML 调整。

## 10. 文档与兼容

- 更新 README、E2E_PIPELINE、ARCHITECTURE、PROJECT_STRUCTURE：实体名、路径、YAML 文件名；示例改为 Temp 配置。
- 删除或归档 `config/ai_players.yaml`。
- 训练 verify 等内部引用改为 experiment config 服务；临时配置不写 emoji。

## 11. 验收

1. 空库启动 → 三份 Temp 种子；侧栏为「实验配置」。
2. 旧库启动 → 数据迁到 `experiment_configs`，无 `ai_players` 表；历史对局战绩按配置 id 正确显示（对局数 > 0）。
3. 创建对局可选 3 个配置并开局；观战无 emoji。
4. CRUD 备注与采样参数生效；无 avatar 字段。
5. `GET .../experiment-configs/stats` 对局数与胜场一致、胜率合理。
6. `npm run type-check` 与相关 pytest 通过。

## 12. 决议记录

- 定位：实验配置档（非人格角色）
- 提示词：仅全局，本期不绑定配置档
- 导航名：实验配置
- 备注：可选 notes
- 实现深度：方案 3 全链路重命名（表 / API / 前端 / YAML）
