# 架构设计文档

> FastAPI 统一后端（无 Node 中间层）。与代码冲突时以 `server/app/` 和 `CLAUDE.md` 为准。

## 1. 架构决策记录

### 1.1 去掉 Node.js 中间层，采用 FastAPI 统一后端

**背景**：原设计采用 Vue → Node.js(Express) → Python 子进程的三层架构，Node 层仅做透传代理。

**决策**：去掉 Node.js 层，由 FastAPI 直接承担 Web 服务职责。

**理由**：
- FastAPI 原生支持 async/await、WebSocket、自动 OpenAPI 文档生成
- 消除 Node → Python 子进程通信的序列化开销与错误处理复杂度
- 减少一层技术栈，降低维护成本
- Pydantic 模型提供请求/响应类型安全，与前端 TypeScript 形成类型闭环

### 1.2 引入 SQLite 作为元数据索引

**背景**：原设计仅用 JSONL 文件存储所有数据，列表查询/筛选/统计需要遍历全部文件。

**决策**：SQLite 存储对局元数据与索引，JSONL 保留为完整数据归档。

**理由**：
- 对局列表、多条件筛选、聚合统计等场景需要高效查询
- SQLite 零部署、单文件，与"本地化轻量工具"的定位完全一致
- JSONL 继续作为完整对局数据的归档载体，保证数据完整性与可移植性

### 1.3 Python 依赖管理采用 Poetry + pyproject.toml

**理由**：
- `pyproject.toml` 是 Python 社区标准（PEP 621）
- Poetry 提供锁文件、虚拟环境管理、依赖分组（dev/prod）
- 比 requirements.txt 更可靠的依赖解析

### 1.4 前端 CSS 方案采用 Tailwind CSS

**理由**：
- 原子化 CSS，开发效率高，bundle 体积小
- 与现有组件体系（Reka UI + Ink Lab）可良好共存
- 社区生态成熟，文档完善

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + TypeScript)                     │
│                                                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ 实验详情页 │ │ 牌局观察器 │ │ 分析       │ │ 设置       │   │
│  │ (实验阶段) │ │ (WebSocket)│ │ 四工具     │ │ 提示词     │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘   │
│                                                                   │
│  Tailwind CSS + Reka UI（Ink Lab tokens；双壳 Workbench/Observer） │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼  HTTP (REST) + WebSocket
┌───────────────────────────────────────────────────────────────────┐
│                   Python 后端 (FastAPI)                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      API 层 (api/)                           │   │
│  │  路由定义 · 请求校验 · 响应序列化 · WebSocket 端点            │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                   Service 层 (services/)                     │   │
│  │  业务编排 · 流程控制 · 跨模块协调                              │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                    Core 层 (core/)                            │   │
│  │                                                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│  │  │ 游戏引擎 │ │ AI 调用  │ │ 数据采集 │       │   │
│  │  │ engine/  │ │ ai/      │ │collector/│       │   │
│  │  └──────────┘ └──────────┘ └──────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                    基础设施层                                  │   │
│  │  config · logger · exceptions · database                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                         数据存储层                                  │
│                                                                     │
│  ┌────────────┐  ┌────────────┐                   │
│  │  SQLite    │  │  JSONL     │                   │
│  │ 元数据索引 │  │ 完整归档   │                   │
│  │ 查询/统计  │  │ 对局全量   │                   │
│  └────────────┘  └────────────┘                   │
└───────────────────────────────────────────────────────────────────┘
```

## 3. 分层架构详细说明

### 3.1 API 层（Thin Controller）

**职责边界**：
- 定义 HTTP 路由和 WebSocket 端点
- 使用 Pydantic Schema 校验请求参数
- 调用 Service 层获取结果
- 序列化响应数据

**禁止**：
- 包含任何业务逻辑
- 直接操作数据库或文件系统
- 直接实例化 Core 层对象

```python
# 正确示例
@router.post("/games", response_model=GameResponse)
async def create_game(
    request: CreateGameRequest,
    game_service: GameService = Depends(get_game_service),
) -> GameResponse:
    game = await game_service.create_game(
        game_type=request.game_type,
        player_ids=request.player_ids,
    )
    return GameResponse.from_domain(game)
```

### 3.2 Service 层（Business Orchestration）

**职责边界**：
- 编排业务流程（如：创建对局 → 初始化引擎 → 写入数据库）
- 跨模块协调（如：对局结束 → 触发数据采集)
- 事务控制与错误处理

**禁止**：
- 包含游戏规则等领域逻辑（属于 Core 层）
- 直接处理 HTTP 请求/响应格式

```python
# 正确示例
class GameService:
    def __init__(
        self,
        engine_registry: GameEngineRegistry,
        collector: JsonlWriter,
        ai_service: AIService,
        experiment_config_service: ExperimentConfigService,
        sqlite_path: str,
    ) -> None:
        self._engine_registry = engine_registry
        self._collector = collector
        self._ai_service = ai_service
        ...

    async def create_game(self, game_type: str, player_ids: list[str], db=None) -> dict:
        engine = self._engine_registry.get(game_type)
        data_file = self._collector.start_game(game_id, game_type, player_ids)
        game_repo = GameRepository(db)
        game = await game_repo.create(...)
        return game
```

### 3.3 Core 层（Domain Logic）

**职责边界**:
- 纯领域逻辑实现: 游戏规则、AI 调用、数据采集
- 不依赖任何 Web 框架（FastAPI）
- 可独立实例化与测试

**子模块划分**:

| 子模块 | 职责 | 关键类 |
|--------|------|--------|
| `engine/` | 游戏引擎，含规则、状态管理 | `GameEngine` (ABC), `DoudizhuEngine` |
| `ai/` | LLM 统一调用，提示词构建 | `LLMClient` (ABC), `OpenAICompatibleClient`, `OllamaClient`, `LLMClientFactory` |
| `collector/` | 对局数据采集与归档 | `JsonlWriter` |
| `training/` | SFT 导出 + PEFT LoRA + 部署辅助 | `data_quality.py`, `sft.py`, `deploy.py`（无项目级 `Trainer` ABC） |

### 3.4 基础设施层

| 模块 | 职责 |
|------|------|
| `config.py` | Pydantic Settings 配置管理，从环境变量与项目根目录 `.env` 加载 |
| `database.py` | SQLite 连接管理（aiosqlite），提供 request-scope 与后台任务统一入口；`_SCHEMA_SQL` 负责建库 |
| `migrations.py` | `PRAGMA user_version` + 编号迁移列表，负责改库；库版本高于程序时拒绝启动 |
| `dependencies.py` | FastAPI 依赖注入容器 |
| `exceptions.py` | 统一异常体系（包含细粒度 AI 错误码） |
| `logger.py` | 结构化日志（structlog） |

## 4. 核心流程

### 4.1 对局执行流程

```
用户创建对局
       │
       ▼
  POST /api/v1/games
       │
       ▼
  GameService.create_game()
       │── GameEngineRegistry.get("doudizhu")
       │── DoudizhuEngine.initialize(player_ids)
       │── GameRepository.create(...)        ← SQLite 写入元数据
       └── JsonlWriter.start_game(...)     ← JSONL 写入 game_start
       │
       ▼
  POST /api/v1/games/{id}/start
       │
       ▼
  GameService.start_game() → GameOrchestrationService._run_game_loop()
       │
       ▼ (循环：直到游戏结束)
  1. engine.observe() + present_legal_actions()：生成选手视角与合法动作菜单
  2. AIService → Policy.decide()：构建提示词、调用模型或基线策略
  3. Policy 返回事件流，以 ActionChosen(action_id) 结束
  4. engine.resolve_action()：验证并解析动作；保存决策点与 EV 评估
  5. engine.apply_action()：推进状态
  6. 广播回合事件，保存 rounds、JSONL 与 traces/spans
       │
       ▼ (游戏结束)
  GameOrchestrationService._finish_game()
       │── GameRepository.update_result(...)    ← SQLite
       └── JsonlWriter.end_game(...)          ← JSONL
```

### 4.2 数据双写策略

每条对局数据同时写入两个存储：

| 存储 | 写入内容 | 用途 |
|------|----------|------|
| **JSONL** | 对局事件与回合记录 | 对局归档、回放 |
| **SQLite** | 实验、对局、回合、决策点、提示词、traces/spans | 查询、统计、决策分析及训练数据导出 |

```
写入时：保存 JSONL 事件与 SQLite 结构化记录（两个存储不共享事务）
查询时：SQLite 查索引 → 按需读取 JSONL 详情
训练导出：筛选 SQLite decision_points → 提取记录的 prompt_messages/action_id → ChatML
```

JSONL 路径在创建时选定，执行时从 `games.data_file` 恢复，跨 UTC 日期不重新选目录。回放兼容旧版本拆到多个日期目录的文件，按日期顺序合并。

实验采集先在 SQLite 写事务中预留 games、发牌种子和 `experiment_collect_requests`（迁移 6），再启动后台任务。`GameService.start_game()` 使用带 `status='created'` 条件的原子更新领取任务。相同幂等键只复用原批次；已取消或已结束的对局不会自动重跑。后台进程重启后仍按现有恢复策略将运行中的对局标为 `interrupted`，重试仅继续未启动的对局。

模型接口仅在 400/422 明确拒绝 `response_format` 或 `stream_options` 时去掉对应字段。其他 4xx 不降级；429 单独映射限流错误。策略层直接传播不可重试错误，保留正常的瞬时故障重试与解析补救逻辑。

### 4.3 归档与清理

归档/清理仅选取 `finished`、`failed`、`cancelled` 的对局，保留期按结束时间计算（旧记录缺失结束时间时使用创建时间）。`days_old` 范围为 1–36500 天。

归档在同一 SQLite 写事务中读取 games、rounds、traces、spans 和 decision_points，先完整写入临时压缩文件，再以唯一文件名原子发布，最后提交删除。文件发布失败时保留数据库记录。归档使用同目录硬链接发布，文件系统不支持时操作失败且保留原始数据。现有 `.jsonl.gz` 扩展名继续兼容，但内容是一个包含上述数组的 JSON 对象。

永久清理使用删除前保存的 `games.data_file` 路径清理 JSONL，仅允许 `data/games/` 内的文件。删除归档仅接受本目录的 `.jsonl.gz` 文件名，拒绝路径穿越和符号链接。

## 5. 依赖注入设计

采用 FastAPI 原生依赖注入机制，所有 Service 和 Core 组件通过 `Depends()` 注入：

```python
# dependencies.py

from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

async def get_db(settings: Settings = Depends(get_settings)) -> AsyncGenerator[aiosqlite.Connection, None]:
    async for db in get_db_connection(settings.sqlite_path):
        yield db

@lru_cache
def get_engine_registry() -> GameEngineRegistry:
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    return registry

@lru_cache
def get_game_service() -> GameService:
    """Singleton game service."""
    settings = get_settings()
    return GameService(
        engine_registry=get_engine_registry(),
        collector=get_jsonl_writer(),
        sqlite_path=settings.sqlite_path,
        orchestration_service=get_game_orchestration_service(),
        replay_service=get_game_replay_service(),
    )
```

## 6. 领域事件机制

系统采用发布-订阅模式实现领域事件，实现模块间的松耦合通信。

### 6.1 EventBus 核心设计

```python
from app.core.events import EventBus, get_event_bus

bus = get_event_bus()

# 订阅事件
bus.subscribe(my_handler)

# 发布事件
await bus.publish(event)
```

**EventBus 特性**：
- 支持同步处理器（`SyncEventHandler`）和异步处理器（`AsyncEventHandler`）
- 异步处理器并发执行，同步处理器在线程池中执行避免阻塞
- 处理器错误不影响其他处理器执行，错误会被捕获并记录日志
- 单例模式，全局共享一个 EventBus 实例

### 6.2 已定义的事件类型

| 事件类 | 事件类型标识 | 触发时机 | 关键字段 |
|--------|-------------|----------|----------|
| `GameStartedEvent` | `game.started` | 对局开始 | `game_id`, `game_type`, `player_ids` |
| `GameEndedEvent` | `game.ended` | 对局结束 | `winner_id`, `total_rounds`, `duration_seconds` |
| `RoundCompletedEvent` | `round.completed` | 回合完成 | `round_number`, `player_id`, `action_type` |
| `PlayerActionEvent` | `player.action` | 玩家出牌前 | `thinking`, `response_time_ms` |
| `GameErrorEvent` | `game.error` | 对局错误 | `error_type`, `error_message`, `recoverable` |

### 6.3 创建新事件

```python
from dataclasses import dataclass
from typing import Any
from app.core.events.base import DomainEvent


@dataclass
class DatasetCreatedEvent(DomainEvent):
    """数据集创建完成事件"""

    dataset_id: str = ""
    name: str = ""
    sample_count: int = 0
    filters: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "dataset.created"
```

### 6.4 创建事件处理器

**异步处理器**（推荐用于 I/O 操作）：

```python
from app.core.events import AsyncEventHandler, GameEndedEvent


class DataExportHandler(AsyncEventHandler):
    """赛后数据导出处理器"""

    @property
    def event_types(self) -> list[type[DomainEvent]]:
        return [GameEndedEvent]

    async def handle(self, event: GameEndedEvent) -> None:
        # 异步执行数据导出逻辑
        await self._export_game_data(event.game_id)
```

**同步处理器**（适用于 CPU 密集型操作）：

```python
from app.core.events import SyncEventHandler, RoundCompletedEvent


class StatisticsHandler(SyncEventHandler):
    """回合统计处理器"""

    @property
    def event_types(self) -> list[type[DomainEvent]]:
        return [RoundCompletedEvent]

    def handle(self, event: RoundCompletedEvent) -> None:
        # 同步执行统计计算
        self._update_statistics(event)
```

**注册处理器**：

```python
from app.core.events import get_event_bus

bus = get_event_bus()
bus.subscribe(DataExportHandler())
bus.subscribe(StatisticsHandler())
```

## 7. 依赖注入生命周期

系统采用 FastAPI 原生依赖注入机制，服务实例的生命周期分为**单例**和**请求作用域**两种。

### 7.1 单例服务（@lru_cache）

使用 `@lru_cache` 装饰器实现单例，整个应用生命周期内只创建一个实例：

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

@lru_cache
def get_engine_registry() -> GameEngineRegistry:
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    return registry

@lru_cache
def get_game_service() -> GameService:
    return GameService(
        engine_registry=get_engine_registry(),
        collector=get_jsonl_writer(),
        ...
    )
```

**单例服务列表**：

| 服务 | 获取函数 | 说明 |
|------|----------|------|
| `Settings` | `get_settings()` | 应用配置 |
| `GameEngineRegistry` | `get_engine_registry()` | 游戏引擎注册中心 |
| `LLMClientFactory` | `get_llm_factory()` | LLM 客户端工厂 |
| `ExperimentConfigService` | `get_experiment_config_service()` | 选手配置管理 |
| `ExperimentService` | `get_experiment_service()` | 实验（run）CRUD / 采集 / 跨实验对比 |
| `PromptBuilder` | `get_prompt_builder()` | 提示词构建器 |
| `JsonlWriter` | `get_jsonl_writer()` | JSONL 数据写入器 |
| `GameService` | `get_game_service()` | 对局业务服务 |
| `DataService` | `get_data_service()` | 数据服务 |
| `TrainingService` | `get_training_service()` | 训练服务 |
| `SystemService` | `get_system_service()` | 系统服务 |
| `TraceService` | `get_trace_service()` | 追踪服务 |
| `DecisionService` | `get_decision_service()` | 决策点服务 |

### 7.2 请求作用域服务

每次 HTTP 请求创建新实例，请求结束后自动释放：

```python
async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aiosqlite.Connection, None]:
    async for db in get_db_connection(settings.sqlite_path):
        yield db

async def get_prompt_service(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[PromptService, None]:
    async for db in get_db_connection(settings.sqlite_path):
        yield PromptService(db=db, registry=get_registry())
```

**请求作用域服务列表**：

| 服务 | 获取函数 | 说明 |
|------|----------|------|
| `aiosqlite.Connection` | `get_db()` | 数据库连接 |
| `PromptService` | `get_prompt_service()` | 提示词服务（需要 DB 连接） |

### 7.3 服务依赖关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                        API 层 (路由处理)                          │
│                                                                 │
│  Depends(get_game_service)  Depends(get_db)  Depends(...)       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service 层 (单例)                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ GameService  │  │ DataService │  │TrainingService│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                  │                   │
│         ▼                 ▼                  ▼                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Core 层组件 (单例)                        │      │
│  │                                                      │      │
│  │  GameEngineRegistry ←── DoudizhuEngine              │      │
│  │  LLMClientFactory   ←── OpenAI/Ollama/DashScope...  │      │
│  │  JsonlWriter        ←── Settings.data_dir           │      │
│  │  DataService         ←── Settings.sqlite_path      │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    请求作用域 (每次请求新建)                       │
│                                                                 │
│  aiosqlite.Connection ←── get_db_connection()                  │
│  PromptService        ←── db + registry                         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 后台任务中的数据库连接

单例服务**不持有**数据库连接。后台任务需要自行创建连接：

```python
class GameService:
    def __init__(self, sqlite_path: str, ...) -> None:
        self._sqlite_path = sqlite_path  # 只存储路径

    async def _background_task(self) -> None:
        # 后台任务自行创建连接
        async with aiosqlite.connect(self._sqlite_path) as db:
            repo = GameRepository(db)
            await repo.update(...)
```

## 8. WebSocket 通信设计

```python
class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self._active: dict[str, list[WebSocket]] = {}  # game_id → connections

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.setdefault(game_id, []).append(websocket)

    async def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        self._active.get(game_id, []).remove(websocket)

    async def broadcast(self, game_id: str, message: dict) -> None:
        for ws in self._active.get(game_id, []):
            await ws.send_json(message)
```

**推送消息类型**：

| type | 说明 | payload |
|------|------|---------|
| `game_started` | 对局开始 | `{players, current_player, landlord_cards}` |
| `thinking` | AI 开始思考 | `{player_id, player_name, legal_actions}` |
| `thinking_chunk` | AI 思考流式输出 | `{player_id, chunk, chunk_type}` |
| `thinking_complete` | AI 思考完成 | `{player_id, thinking, response_time_ms, action_preview, prompt_preview, raw_response_preview, prompt_tokens, completion_tokens, total_tokens, model_provider, model_name, legal_actions, parser_ok, win_probability, hand_analysis}` |
| `action` | AI 完成出牌 | `{round, player_id, action_type, cards}` |
| `state_update` | 全局状态更新 | `{players, hands, current_player, landlord_cards}` |
| `game_paused` | 对局暂停 | `{}` |
| `game_resumed` | 对局恢复 | `{}` |
| `game_ended` | 对局结束 | `{winner_id, winner_name, winner_role, total_rounds}` |
| `error` | 对局运行错误 | `{message}` |
| `pong` | 心跳响应 | `{type: "pong"}` |

## 9. 数据库设计（SQLite）

权威 schema 以 `server/app/database.py` 为准。

**改动 schema 的规则**：`_SCHEMA_SQL`（`CREATE TABLE IF NOT EXISTS`）只负责建新库，
`app/migrations.py` 的编号迁移只负责改已有库，版本号记在 `PRAGMA user_version`。
新增一列要同时改两处：`_SCHEMA_SQL` 的列定义（新库直接建全）+ 一条新迁移（老库补上）。
索引若引用迁移新增的列，必须写在迁移里而不是 `_SCHEMA_SQL`——建库脚本也会对老库执行，
那时列还不存在。库版本高于程序支持的版本时抛 `SchemaVersionError` 拒绝启动，不做静默降级。

### 9.0 experiments 表

```sql
CREATE TABLE experiments (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    game_type     TEXT    NOT NULL,
    player_ids    TEXT    NOT NULL,
    target_games  INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
```

### 9.1 games 表

```sql
CREATE TABLE games (
    id             TEXT PRIMARY KEY,
    game_type      TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'created',  -- created/running/paused/finished
    player_ids     TEXT    NOT NULL,
    winner_id      TEXT,
    winner_role    TEXT,
    total_rounds   INTEGER DEFAULT 0,
    data_file      TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    finished_at    TEXT,
    metadata       TEXT,
    experiment_id  TEXT    REFERENCES experiments(id)   -- 试玩对局为 NULL
);

CREATE INDEX idx_games_type ON games(game_type);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_created ON games(created_at);
CREATE INDEX idx_games_experiment ON games(experiment_id);
```

### 9.2 rounds 表

```sql
CREATE TABLE rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT    NOT NULL REFERENCES games(id),
    round_num       INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    action_type     TEXT    NOT NULL,
    cards           TEXT,                    -- JSON, 出牌内容
    hand_snapshot   TEXT,                    -- JSON, 手牌快照
    prompt          TEXT,                    -- JSON, 发送给 LLM 的消息
    raw_response    TEXT,                    -- LLM 原始响应
    prompt_tokens   INTEGER,                -- Prompt token 数
    completion_tokens INTEGER,              -- Completion token 数
    total_tokens    INTEGER,                -- 总 token 数
    response_time_ms INTEGER,
    model_provider  TEXT,
    model_name      TEXT,
    created_at      TEXT    NOT NULL,
    all_hands       TEXT                    -- JSON, 所有玩家手牌快照
);

CREATE INDEX idx_rounds_game ON rounds(game_id);
CREATE INDEX idx_rounds_player ON rounds(player_id);
CREATE INDEX idx_rounds_model ON rounds(model_name);
CREATE INDEX idx_rounds_tokens ON rounds(total_tokens);
```

### 9.3 datasets 表

```sql
CREATE TABLE datasets (
    id          TEXT PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    game_type   TEXT    NOT NULL,
    filters     TEXT    NOT NULL,    -- JSON, 筛选条件快照
    sample_count INTEGER NOT NULL,
    file_path   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
```

### 9.4 training_tasks 表

```sql
CREATE TABLE training_tasks (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    dataset_id    TEXT    NOT NULL REFERENCES datasets(id),
    base_model    TEXT    NOT NULL,
    training_type TEXT    NOT NULL,  -- sft/ppo
    config        TEXT    NOT NULL,  -- JSON, 训练超参
    status        TEXT    NOT NULL DEFAULT 'pending',  -- pending/exporting/training/completed/failed/cancelled
    progress      REAL    DEFAULT 0,
    result        TEXT,              -- JSON, 训练结果
    model_path    TEXT,
    created_at    TEXT    NOT NULL,
    finished_at   TEXT,
    experiment_id TEXT    REFERENCES experiments(id)
);
```

### 9.4 prompt_templates 表

```sql
CREATE TABLE prompt_templates (
    id           TEXT PRIMARY KEY,
    template_key TEXT    NOT NULL,  -- e.g., 'doudizhu_playing', 'doudizhu_bidding'
    version      TEXT    NOT NULL,  -- e.g., 'v1', 'v2'
    content      TEXT    NOT NULL,  -- Full prompt template content
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    UNIQUE(template_key, version)
);
```

### 9.5 traces 表

```sql
CREATE TABLE traces (
    id              TEXT PRIMARY KEY,
    game_id         TEXT    NOT NULL,
    round_number    INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    prompt_version  TEXT    NOT NULL,
    input_snapshot  TEXT    NOT NULL,  -- JSON, 游戏状态快照 + 合法动作
    output_data     TEXT    NOT NULL,  -- JSON, 原始响应 + 解析结果
    metrics         TEXT    NOT NULL,  -- JSON, 响应时间 + 解析方式
    created_at      TEXT    NOT NULL
);

CREATE INDEX idx_traces_game ON traces(game_id);
CREATE INDEX idx_traces_player ON traces(player_id);
CREATE INDEX idx_traces_created ON traces(created_at);
```

### 9.6 spans 表

```sql
CREATE TABLE spans (
    id          TEXT PRIMARY KEY,
    trace_id    TEXT    NOT NULL REFERENCES traces(id),
    span_type   TEXT    NOT NULL,  -- e.g., 'tool_call'
    start_time  TEXT    NOT NULL,
    end_time    TEXT,
    status      TEXT    NOT NULL DEFAULT 'pending',  -- pending/completed/failed
    data        TEXT    -- JSON, 子操作数据
);

CREATE INDEX idx_spans_trace ON spans(trace_id);
```

### 9.7 decision_points 表

```sql
CREATE TABLE decision_points (
    id              TEXT PRIMARY KEY,
    game_id         TEXT    NOT NULL,
    round_number    INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    hand_cards      TEXT    NOT NULL,
    opponent_hands  TEXT,
    last_action     TEXT,
    game_phase      TEXT    NOT NULL,
    legal_actions   TEXT    NOT NULL,
    chosen_action   TEXT    NOT NULL,
    thinking        TEXT,
    outcome         TEXT,
    quality_score   REAL    DEFAULT 0.5,  -- 终局结果分，非招法质量
    train_usable    INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL
);
```

### 9.8 experiment_configs 表

```sql
CREATE TABLE experiment_configs (  -- 选手配置（UI 名称；API 路径 experiment-configs）
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    model_config  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
```

## 10. 可扩展性设计

### 10.1 新增游戏

1. 在 `core/engine/` 下创建新游戏包（如 `sanguosha/`）
2. 继承 `GameEngine` 抽象基类，实现所有抽象方法
3. 实现 `get_public_info(..., is_observer=True)` 输出统一 ObserverSnapshot
4. **不要**为每个游戏单独写 Board 组件；观战统一使用 GenericBoard
5. 无需修改 Service 层和 API 层 —— 通过 `game_type` 参数自动路由

### 10.2 新增 LLM 供应商

Chat Completions 协议（`POST /chat/completions` + Bearer）：在 `dependencies.py` 的 provider 列表和 `config.py` / `.env` 增加项即可，**不要**新建 client 类。  
其他协议：新建 `LLMClient` 子类并在 `get_llm_factory()` 注册。运行时在「选手配置」页创建并选用。

### 10.3 新增训练算法

当前实现是 `core/training/sft.py` 的 PEFT LoRA（内部使用 HuggingFace `Trainer`）。仓库**没有**统一的 `Trainer` ABC。新算法应扩展 `training_service` + `core/training/`，并由 `training_type` 路由。

## 比较审查与快照（2026-09-11）

比较沿用 API → ExperimentService/ExperimentDeltaMixin → repositories/core 的依赖方向。`core/stats/comparison.py` 为纯计算模块，负责共同有效种子集合与冻结协议差异；SQLite 读事务固定一次比较的数据截点。`ComparisonRepository` 只负责追加、分页列举与读取 `comparison_snapshots`，不启动对局、不回写实验。记录包含当时的结果、协议、成员 game_id、排除原因、声明和口径版本；无更新/级联删除接口。前端通过 `ComparisonAudit` 展示审查与覆盖，通过比较页保存、重开和导出；后续版本化证据/结论在该快照基础上设计，不复用可变实验文本冒充证据版本。

### 研究记录的一致性

`research_revisions` 关联 `comparison_snapshots`，以 `(comparison_id, revision)` 唯一约束保存追加版本。ResearchMixin 在 `BEGIN IMMEDIATE` 内校验预期版本与证据范围、读取引用内容并写入记录，失败关闭连接回滚。读取报告使用单一读事务，分别返回不可变记录与当前原始证据状态。快照保留计算时的所有对局 ID；配对覆盖中的成员列表仍只含共同有效样本。

只维护当前 Task 协议和当前研究报告结构，不进行平铺协议转换、字段推导或报告升级。研究修订用于保留用户的推理过程，与代码兼容无关。
