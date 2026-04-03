# 架构设计文档

> 本文档基于《AI卡牌游戏实验室 - 详细设计说明书》，确定采用 **方案A（去掉 Node.js 中间层，Python FastAPI 统一后端）** 后的最终架构设计。

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
- 与 Element Plus 组件库可良好共存
- 社区生态成熟，文档完善

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + TypeScript)                     │
│                                                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐    │
│  │ 牌局观察器 │ │ 数据看板   │ │ 训练控制台 │    │
│  │ (WebSocket)│ │ (ECharts)  │ │            │    │
│  └────────────┘ └────────────┘ └────────────┘    │
│                                                                   │
│  Tailwind CSS + Element Plus                                      │
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
        ai_player_service: AIPlayerService,
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
| `ai/` | LLM 统一调用，提示词构建 | `LLMClient` (ABC), `LLMClientFactory` |
| `collector/` | 对局数据采集与归档 | `JsonlWriter` |
| `training/` | SFT 数据导出 + Mock 训练器 | `export_sft_dataset`, `run_mock_training` |

### 3.4 基础设施层

| 模块 | 职责 |
|------|------|
| `config.py` | Pydantic Settings 配置管理，从环境变量与项目根目录 `.env` 加载 |
| `database.py` | SQLite 连接管理（aiosqlite），提供 request-scope 与后台任务统一入口 |
| `dependencies.py` | FastAPI 依赖注入容器 |
| `exceptions.py` | 统一异常体系（包含细粒度 AI 错误码） |
| `logger.py` | 结构化日志（structlog） |

## 4. 核心流程

### 4.1 对局执行流程

```
用户点击"开始对局"
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
  GameService.run_game()
       │
       ▼ (循环：直到游戏结束)
  ┌─────────────────────────────────────────────┐
  │  1. engine.get_current_player(state)        │
  │  2. engine.get_legal_actions(state, player) │
  │  3. prompt_builder.build(state)             │
  │  4. llm_client.chat(prompt)                 │
  │  5. engine.parse_action(llm_output)         │
  │  6. collector.record_round(...)             │  ← JSONL + SQLite
  │  7. ws_manager.broadcast(thinking_data)     │  ← WebSocket 推送
  │  8. engine.apply_action(state, action)      │
  └─────────────────────────────────────────────┘
       │
       ▼ (游戏结束)
  GameService.finish_game()
       │── GameRepository.update_result(...)    ← SQLite
       └── JsonlWriter.end_game(...)          ← JSONL
```

### 4.2 数据双写策略

每条对局数据同时写入两个存储：

| 存储 | 写入内容 | 用途 |
|------|----------|------|
| **JSONL** | 完整对局数据（状态、动作、思考链、模型信息） | 归档、训练数据导出 |
| **SQLite** | 元数据索引（game_id, type, players, result, timestamp, round_count） | 列表查询、筛选、统计 |

```
写入时：JSONL（主） + SQLite（索引）同步写入
查询时：SQLite 查索引 → 按需读取 JSONL 详情
导出时：根据 SQLite 筛选条件 → 批量读取 JSONL → 生成训练集
```

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
    """Singleton — holds long-lived game state.
    API handlers pass db into methods; background tasks open own connections.
    """
    settings = get_settings()
    ai_service = AIService(
        llm_factory=get_llm_factory(),
        prompt_builder=get_prompt_builder(),
        ai_player_service=get_ai_player_service(),
    )
    return GameService(
        engine_registry=get_engine_registry(),
        collector=get_jsonl_writer(),
        ai_service=ai_service,
        ai_player_service=get_ai_player_service(),
        sqlite_path=settings.sqlite_path,
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
````

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
| `AIPlayerService` | `get_ai_player_service()` | AI 角色管理 |
| `PromptBuilder` | `get_prompt_builder()` | 提示词构建器 |
| `JsonlWriter` | `get_jsonl_writer()` | JSONL 数据写入器 |
| `GameService` | `get_game_service()` | 对局业务服务 |
| `DataService` | `get_data_service()` | 数据服务 |
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
| `thinking` | AI 开始思考 | `{player_id, player_name}` |
| `thinking_chunk` | AI 思考流式输出 | `{player_id, chunk, chunk_type}` |
| `thinking_complete` | AI 思考完成 | `{player_id, thinking, response_time_ms, action_preview, prompt_preview, raw_response_preview, prompt_tokens, completion_tokens, total_tokens, model_provider, model_name}` |
| `action` | AI 完成出牌 | `{round, player_id, action_type, cards}` |
| `state_update` | 全局状态更新 | `{players, hands, current_player, landlord_cards}` |
| `game_paused` | 对局暂停 | `{}` |
| `game_resumed` | 对局恢复 | `{}` |
| `game_ended` | 对局结束 | `{winner_id, winner_name, winner_role, total_rounds}` |
| `error` | 对局运行错误 | `{message}` |
| `pong` | 心跳响应 | `{type: "pong"}` |

## 9. 数据库设计（SQLite）

### 9.1 games 表

```sql
CREATE TABLE games (
    id            TEXT PRIMARY KEY,
    game_type     TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'created',  -- created/running/paused/finished
    player_ids    TEXT    NOT NULL,                     -- JSON array
    winner_id     TEXT,
    winner_role   TEXT,
    total_rounds  INTEGER DEFAULT 0,
    data_file     TEXT    NOT NULL,                     -- JSONL 文件相对路径
    created_at    TEXT    NOT NULL,
    finished_at   TEXT,
    metadata      TEXT                                  -- JSON, 扩展字段
);

CREATE INDEX idx_games_type ON games(game_type);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_games_created ON games(created_at);
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
    finished_at   TEXT
);
```

### 7.6 prompt_templates 表

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

## 10. 可扩展性设计

### 10.1 新增游戏

1. 在 `core/engine/` 下创建新游戏包（如 `sanguosha/`）
2. 继承 `GameEngine` 抽象基类，实现所有抽象方法
3. 在引擎注册中心注册
4. 前端创建对应的牌桌组件
5. 无需修改 Service 层和 API 层 —— 通过 `game_type` 参数自动路由

### 10.2 新增 LLM 供应商

1. 在 `core/ai/providers/` 下创建新文件
2. 继承 `LLMClient` 抽象基类
3. 在 `LLMClientFactory` 注册
4. 在 `ai_players.yaml` 中配置使用

### 10.3 新增训练算法

1. 在 `core/training/` 下创建新训练器
2. 实现统一的 `Trainer` 接口
3. Service 层通过 `training_type` 参数路由到对应训练器
