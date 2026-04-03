# AI卡牌游戏实验室 - 详细设计说明书

## 1. 引言

### 1.1 项目背景
卡牌类游戏（斗地主、三国杀、英雄杀等）蕴含着丰富的策略与博弈元素，是研究AI决策、推理与模型蒸馏的理想场景。随着大语言模型（LLM）的普及，利用LLM作为游戏实验室，观察其思考过程，并逐步将经验“蒸馏”至专用小模型，成为探索AI能力压缩与迁移的有效路径。本项目旨在构建一个**通用化、可扩展、面向AI研究的卡牌游戏实验室数据采集与训练平台**。

### 1.2 项目目标
- **通用性**：平台不局限于斗地主，而是抽象出卡牌游戏的共性，支持快速接入新游戏。
- **数据采集**：自动采集每轮决策数据（状态、动作、思考链），为训练专用小模型提供高质量数据集。
- **模型蒸馏**：提供数据集导出、训练任务管理、模型版本管理能力，并为后续真实训练器接入预留扩展空间。
- **可观测性**：实时观察AI的思考过程，理解其决策逻辑，为模型优化提供洞察。

### 1.3 核心定位
本项目**不是**社交游戏平台，而是一个**面向AI研究的本地化数据采集与训练工具**。因此功能设计以数据完整性、可观测性、可扩展性和轻量化为首要考虑。**无需用户注册登录系统**，所有数据存储在本地，开箱即用。

## 2. 系统总体架构

### 2.1 核心架构图
```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │牌局观察器│ │数据看板  │ │训练控制台│                   │
│  └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼ (WebSocket + HTTP)
┌─────────────────────────────────────────────────────────────┐
│                    Python 服务层 (FastAPI)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │WebSocket │ │API路由   │ │依赖注入  │ │后台任务  │      │
│  │推送服务  │ │(REST)    │ │/配置管理 │ │(训练触发)│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Python 核心引擎层                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ 游戏引擎     │ │ AI调用器     │ │ 数据采集器   │        │
│  │ (斗地主/...) │ │ (LLM客户端)  │ │ (JSONL写入)  │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │ 数据库抽象层 │ │ 训练任务编排 │                          │
│  │ (预留迁移)   │ │ (Mock SFT)  │                          │
│  └──────────────┘ └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                        数据存储层                            │
│  ┌──────────┐ ┌──────────┐                                 │
│  │本地文件  │ │SQLite    │                                 │
│  │(JSONL)   │ │(元数据)  │                                 │
│  └──────────┘ └──────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心流程
1. **对局流程**：前端创建对局 → FastAPI初始化牌局 → 轮到AI → 构造提示词 → 调用大模型 → 解析动作 → 记录JSONL → 通过WebSocket推送思考链 → 下一AI
2. **数据流水线**：从本地JSONL文件筛选数据 → 清洗 → 生成训练数据集 → 触发训练任务 → 产出模型元数据/文件 → 版本管理

### 2.3 技术栈总览
| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + Tailwind CSS | 现代响应式UI框架 |
| 后端服务 | FastAPI + Uvicorn | 高性能异步Python Web框架 |
| 实时通信 | FastAPI WebSocket | 原生WebSocket支持 |
| Python引擎 | Python 3.11+ | AI调用、游戏逻辑、训练 |
| 大模型适配 | openai / ollama / dashscope SDK | 统一调用接口 |
| 训练框架 | Mock 训练器 + PyTorch / Transformers 扩展位 | 当前已实现训练任务编排与模拟执行，真实训练后续接入 |
| 数据存储 | SQLite + JSONL | SQLite存储元数据，JSONL存储详细对局数据 |
| 依赖管理 | Poetry | Python包管理与依赖锁定 |

## 3. 通用游戏引擎设计（核心扩展性）

### 3.1 游戏抽象层
为了支持所有卡牌类游戏，设计通用游戏引擎接口（Python版本）：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class GameState:
    """游戏状态基类"""
    game_type: str
    round: int
    player_ids: list[str]
    current_player: str
    is_terminal: bool
    winner: str | None = None
    winner_role: str | None = None

@dataclass
class GameAction:
    """游戏动作基类"""
    player_id: str
    action_type: str
    cards: list[str] = field(default_factory=list)
    target: str | None = None

@dataclass
class PlayerState:
    """玩家状态"""
    player_id: str
    hand_cards: list[str]
    alive: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)

class GameEngine(ABC):
    """游戏引擎抽象基类"""
    
    @property
    @abstractmethod
    def game_type(self) -> str:
        """游戏类型标识"""
        pass
    
    @abstractmethod
    def initialize(self, player_ids: list[str], **params: Any) -> GameState:
        """初始化游戏"""
        pass
    
    @abstractmethod
    def get_legal_actions(self, state: GameState, player_id: str) -> list[GameAction]:
        """获取合法动作"""
        pass
    
    @abstractmethod
    def apply_action(self, state: GameState, action: GameAction) -> GameState:
        """应用动作，返回新状态"""
        pass
    
    @abstractmethod
    def is_terminal(self, state: GameState) -> bool:
        """判断游戏是否结束"""
        pass
    
    @abstractmethod
    def get_winner(self, state: GameState) -> str | None:
        """获取获胜者ID"""
        pass
    
    @abstractmethod
    def get_current_player(self, state: GameState) -> str:
        """获取当前应该行动的玩家ID"""
        pass
    
    @abstractmethod
    def format_for_prompt(self, state: GameState, player_id: str) -> str:
        """将状态格式化为提示词文本"""
        pass
    
    @abstractmethod
    def parse_action(self, llm_output: str, legal_actions: list[GameAction]) -> GameAction:
        """解析大模型输出为动作"""
        pass
    
    @abstractmethod
    def get_public_info(self, state: GameState, viewer_id: str) -> dict[str, Any]:
        """获取指定玩家视角的公开信息"""
        pass
```

### 3.2 游戏引擎注册中心

```python
class GameEngineRegistry:
    """游戏引擎注册中心"""
    _engines: dict[str, GameEngine] = {}
    
    @classmethod
    def register(cls, engine: GameEngine):
        cls._engines[engine.game_type] = engine
    
    @classmethod
    def get(cls, game_type: str) -> GameEngine:
        if game_type not in cls._engines:
            raise ValueError(f"Unsupported game type: {game_type}")
        return cls._engines[game_type]
    
    @classmethod
    def list_games(cls) -> list[str]:
        return list(cls._engines.keys())
```

### 3.3 斗地主引擎实现（已实现）

项目已完整实现斗地主游戏引擎，位于 `server/app/core/engine/doudizhu/` 目录：

- **engine.py**: 核心游戏逻辑，实现 `DoudizhuEngine` 类
- **cards.py**: 扑克牌定义与工具函数
- **hand_evaluator.py**: 牌型识别与合法出牌计算

主要特性：
- 支持3人对战（1地主 vs 2农民）
- 自动发牌与地主随机分配
- 完整的牌型识别（单张、对子、顺子、炸弹等）
- 智能的LLM输出解析（支持JSON和文本格式）
- 中文提示词格式化

> 说明：本项目当前实现聚焦“随机分配地主 + 出牌阶段对局”，未单独实现经典规则中的“叫地主/叫分”流程。

## 4. 功能模块详细说明

### 4.1 AI角色配置（无需用户系统）

**设计理念**：由于无需用户注册，AI角色配置直接存储在本地配置文件中，开箱即用。每个AI角色专注于最佳策略输出，不设置性格描述，确保数据的一致性和训练效果。

**配置文件格式** (`config/ai_players.yaml`):
```yaml
ai_players:
  - id: "ai_gpt4"
    name: "GPT-4 玩家"
    avatar: "gpt4.png"
    model_config:
      provider: "openai"
      model_name: "gpt-4"
      api_key: "${OPENAI_API_KEY}"  # 从环境变量读取
      temperature: 0.7
      top_p: 0.95
      max_tokens: 1024

  - id: "ai_qwen"
    name: "通义千问玩家"
    avatar: "qwen.png"
    model_config:
      provider: "dashscope"
      model_name: "qwen-plus"
      api_key: "${DASHSCOPE_API_KEY}"
      temperature: 0.7

  - id: "ai_deepseek"
    name: "DeepSeek 玩家"
    avatar: "deepseek.png"
    model_config:
      provider: "deepseek"
      model_name: "deepseek-reasoner"
      api_key: "${DEEPSEEK_API_KEY}"
      temperature: 0.7
```

**前端界面**：提供简单的AI角色管理界面，支持增删改查配置。

### 4.2 牌局控制与观察

#### 4.2.1 创建对局流程
1. 用户从AI角色列表中选择3个AI（可重复选择同一AI）
2. 选择游戏类型（斗地主/三国杀/英雄杀）
3. 设置对局模式：
   - **实时模式**：AI轮流决策，前端实时推送思考过程，适合观察
   - **批量模式**：连续运行多局，仅记录数据，用于快速积累样本
4. 点击"开始对局"

#### 4.2.2 对局状态管理
服务端维护完整游戏状态机，每轮决策流程：

```python
async def run_round(game_engine, state, ai_players, data_collector, websocket):
    """执行一轮决策"""
    current_player = game_engine.get_current_player(state)
    ai = ai_players[current_player]

    # 1. 获取合法动作
    legal_actions = game_engine.get_legal_actions(state, current_player)

    # 2. 构建提示词
    prompt = build_prompt(state, legal_actions, ai)

    # 3. 调用大模型
    start_time = time.time()
    llm_response = await ai_client.chat(prompt, ai.model_config)
    response_time = int((time.time() - start_time) * 1000)

    # 4. 解析动作
    action = game_engine.parse_action(llm_response, legal_actions)

    # 5. 记录数据
    data_collector.record_round(
        game_id=state.game_id,
        round_num=state.round,
        player_id=current_player,
        state=state,
        action=action,
        chain_of_thought=llm_response,
        response_time_ms=response_time,
        model_info=ai.model_config
    )

    # 6. 推送思考链到前端
    await websocket.emit("thinking", {
        "player": ai.name,
        "thinking": llm_response,
        "action": action.action_type,
        "cards": action.cards
    })

    # 7. 应用动作
    new_state = game_engine.apply_action(state, action)
    return new_state
```

#### 4.2.3 观察者视图
前端提供以下核心组件：
- **牌桌区域**：展示各玩家手牌（仅当前用户AI可见）、已出牌堆、剩余牌数
- **思考气泡**：实时显示当前AI的思考链，支持打字机效果
- **时间轴**：可回溯任意轮次的思考过程
- **控制栏**：暂停/继续、加速、手动干预（替AI出牌，用于对比实验）
- **对局记录**：保存完整对局日志，支持回放

### 4.3 数据采集与存储

#### 4.4.1 数据存储格式（JSONL）
所有对局数据以JSONL格式存储在本地文件系统中：

```
data/
├── games/
│   ├── 2024-01-01/
│   │   ├── game_001.jsonl
│   │   └── game_002.jsonl
│   └── 2024-01-02/
│       └── game_003.jsonl
├── datasets/
│   └── doudizhu_sft_v1.jsonl
├── archives/                    # 归档文件目录
│   └── archive_20240201_120000.jsonl.gz
└── migration_exports/           # 迁移导出目录
    └── games.jsonl
```

#### 4.4.2 单条数据格式
每行JSONL记录包含以下字段：

```json
{
  "type": "round",
  "game_id": "game_001",
  "game_type": "doudizhu",
  "round": 5,
  "player_id": "ai_001",
  "state": {
    "hand_cards": ["3","4","5","6","7"],
    "role": "peasant",
    "public_info": {
      "last_move": {"player": "ai_002", "action": "SINGLE_4", "cards": ["4"]},
      "cards_left": {"ai_002": 10, "ai_003": 5}
    }
  },
  "legal_actions": [
    {"type": "SINGLE", "cards": ["3"]},
    {"type": "PASS", "cards": []}
  ],
  "action": {
    "type": "SINGLE",
    "cards": ["3"]
  },
  "chain_of_thought": "对方出了4，我手上有3，但我想保留大牌，所以过。",
  "response_time_ms": 1250,
  "model_info": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.8
  },
  "result": "win",
  "timestamp": "2024-01-01T10:30:00Z"
}
```

### 4.5 数据看板

提供本地Web界面，展示以下统计信息：
- **总对局数**：累计完成的对局数量
- **总样本数**：累计采集的决策轮次数量
- **各游戏分布**：不同游戏类型的对局占比
- **各模型调用次数**：不同大模型的调用统计
- **平均决策耗时**：各模型的平均响应时间
- **数据质量评分**：基于思考链长度、决策合法性的综合评分

### 4.6 数据集管理

#### 4.6.1 数据集创建
用户可在界面上设置筛选条件，生成训练数据集：

| 筛选条件 | 说明 |
|----------|------|
| 游戏类型 | 斗地主 / 三国杀 / ... |
| 时间范围 | 起始日期 - 结束日期 |
| AI角色 | 指定特定AI角色的数据 |
| 胜负结果 | 仅获胜 / 仅失败 / 全部 |
| 数据质量分 | 最低质量分数阈值 |
| 包含思考链 | 是否包含chain_of_thought字段 |

#### 4.6.2 导出格式
数据集导出为JSONL格式，每行包含一个训练样本：

```json
{
  "input": "【状态描述】你是农民，手牌：3,4,5,6,7...",
  "output": "SINGLE_3",
  "instruction": "请根据当前牌局状态，选择最合适的出牌动作。",
  "chain_of_thought": "对方出了4，我手上有3，但我想保留大牌，所以过。"
}
```

### 4.7 训练任务管理

#### 4.7.1 训练任务配置
用户在界面上配置训练参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| 任务名称 | 唯一标识 | doudizhu_sft_v1 |
| 游戏类型 | 选择游戏 | 斗地主 |
| 训练类型 | 当前以 SFT 为主，预留扩展位 | SFT |
| 基础模型 | 预训练模型 | Qwen/Qwen2.5-1.5B |
| 数据集 | 选择已创建的数据集 | doudizhu_sft_v1.jsonl |
| 学习率 | 优化器学习率 | 2e-5 |
| Batch Size | 批次大小 | 8 |
| 训练轮数 | Epochs | 3 |
| 输出格式 | ONNX / PyTorch | ONNX |

#### 4.7.2 训练任务执行
- 点击“开始训练”后，由 FastAPI 后端编排训练任务流程
- 当前实现以 Mock 训练器模拟进度推进，并向前端暴露任务状态
- 训练完成后，模型文件与结果元数据写入 `models/` 目录及数据库记录

### 4.8 模型仓库

| 模型版本 | 基础模型 | 训练数据量 | 测试胜率 | 文件大小 | 操作 |
|----------|----------|------------|----------|----------|------|
| doudizhu_sft_v1 | Qwen-1.5B | 5k样本 | 52.3% | 1.2GB | 下载｜部署｜测试 |
| doudizhu_sft_v2 | Qwen-1.5B | 12k样本 | 58.7% | 1.2GB | 下载｜部署｜测试 |

**模型部署**：选择模型版本后，可将其作为AI角色的决策引擎，替换大模型调用。

## 5. 数据模型定义

### 5.1 SQLite数据库结构

#### 5.1.1 games表（对局元数据）
```sql
CREATE TABLE games (
    id TEXT PRIMARY KEY,           -- 对局ID
    game_type TEXT NOT NULL,       -- 游戏类型
    player_ids TEXT NOT NULL,      -- 玩家ID列表（JSON数组）
    status TEXT NOT NULL,          -- 状态：created/running/paused/finished
    data_file TEXT,                -- JSONL数据文件路径
    winner_id TEXT,                -- 获胜者ID
    winner_role TEXT,              -- 获胜者角色
    total_rounds INTEGER,          -- 总轮次
    metadata TEXT,                 -- 扩展元数据（JSON）
    created_at TEXT NOT NULL,      -- 创建时间
    finished_at TEXT               -- 结束时间
);
```

#### 5.1.2 rounds表（决策轮次）
```sql
CREATE TABLE rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,         -- 关联对局ID
    round_num INTEGER NOT NULL,    -- 轮次编号
    player_id TEXT NOT NULL,       -- 行动玩家ID
    action_type TEXT NOT NULL,     -- 动作类型
    response_time_ms INTEGER,      -- 响应时间（毫秒）
    model_provider TEXT,           -- 模型供应商
    model_name TEXT,               -- 模型名称
    created_at TEXT NOT NULL,      -- 创建时间
    FOREIGN KEY (game_id) REFERENCES games(id)
);
```

### 5.2 本地文件存储结构

#### 5.2.1 对局数据文件 (`data/games/{date}/{game_id}.jsonl`)
每行一个JSON对象，包含三种类型记录：

```json
// 对局开始记录
{"type": "game_start", "game_id": "xxx", "game_type": "doudizhu", "players": [...], "timestamp": "..."}

// 决策轮次记录
{"type": "round", "game_id": "xxx", "round_num": 1, "player_id": "ai_001", "action_type": "SINGLE", "cards": ["S3"], "thinking": "...", "raw_response": "...", "response_time_ms": 1250, "timestamp": "..."}

// 对局结束记录
{"type": "game_end", "game_id": "xxx", "winner_id": "ai_001", "winner_role": "landlord", "total_rounds": 45, "timestamp": "..."}
```

#### 5.2.2 AI角色配置 (`config/ai_players.yaml`)
见4.1节。

#### 5.2.3 系统配置（环境变量）
通过 `.env` 文件配置敏感信息和模型API：

```bash
# 数据存储路径
DATA_DIR=./data
SQLITE_PATH=./data/db/app.db
MODELS_DIR=./models

# OpenAI 配置
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# DeepSeek 配置
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-reasoner

# DashScope（阿里通义）配置
DASHSCOPE_API_KEY=xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Ollama 配置
OLLAMA_BASE_URL=http://localhost:11434

# 服务器配置
APP_HOST=0.0.0.0
APP_PORT=8000
```

## 6. 技术栈完整清单

### 6.1 服务端（Python）

| 组件 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| Python运行环境 | Python | 3.11+ | 核心引擎语言 |
| Web框架 | FastAPI | 0.115+ | 高性能异步Web框架 |
| ASGI服务器 | Uvicorn | 0.34+ | 异步HTTP服务器 |
| 数据验证 | Pydantic | 2.7+ | 数据模型与验证 |
| 数据库 | SQLite + aiosqlite | 0.20+ | 异步SQLite驱动 |
| 配置管理 | pydantic-settings | 2.7+ | 类型安全的配置 |
| 日志 | structlog | 24.0+ | 结构化日志 |
| YAML解析 | PyYAML | 6.0+ | 配置文件解析 |
| 大模型调用 | openai | 1.0+ | OpenAI SDK |
| | ollama | 0.1+ | Ollama Python客户端 |
| | dashscope | 1.14+ | 阿里通义SDK |
| 游戏引擎 | 自研 | - | Python实现 |
| 训练框架 | PyTorch + Transformers（预留） | 真实训练能力后续接入 |
| 模型库 | Transformers | 4.35+ | HuggingFace |
| 测试框架 | pytest + pytest-asyncio | 8.0+ | 异步测试支持 |
| 代码质量 | ruff + mypy | 最新 | Linting与类型检查 |
| 依赖管理 | Poetry | 最新 | 包管理与依赖锁定 |

### 6.2 前端

| 组件 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| 核心框架 | Vue 3 | 3.5+ | 组合式API |
| 构建工具 | Vite | 7.3+ | 快速构建 |
| 类型支持 | TypeScript | 5.9+ | 类型安全 |
| UI组件库 | Element Plus | 2.13+ | 中后台组件 |
| CSS框架 | Tailwind CSS | 4.2+ | 原子化CSS |
| 状态管理 | Pinia | 3.0+ | Vue状态管理 |
| HTTP客户端 | Axios | 1.13+ | API调用 |
| WebSocket | 原生WebSocket | - | 实时通信 |
| 图表 | ECharts + vue-echarts | 6.0+ | 数据可视化 |
| 路由 | Vue Router | 5.0+ | 前端路由 |
| 代码质量 | oxlint + ESLint + Prettier | 最新 | Linting与格式化 |

## 7. 模块化设计详细说明

### 7.1 目录结构

```
ai-card-game-lab/
├── server/                      # Python 后端服务
│   ├── app/                     # 应用主目录
│   │   ├── api/                 # API路由层
│   │   │   ├── router.py        # 路由汇总
│   │   │   └── v1/              # v1版本API
│   │   │       ├── game.py      # 对局管理API
│   │   │       ├── ai_player.py # AI角色管理API
│   │   │       ├── data.py      # 数据查询API
│   │   │       ├── training.py  # 训练任务API
│   │   │       └── system.py    # 系统状态API
│   │   ├── core/                # 核心业务逻辑
│   │   │   ├── engine/          # 游戏引擎
│   │   │   │   ├── base.py      # 抽象基类
│   │   │   │   ├── registry.py  # 引擎注册中心
│   │   │   │   └── doudizhu/    # 斗地主实现
│   │   │   │       ├── engine.py
│   │   │   │       ├── cards.py
│   │   │   │       └── hand_evaluator.py
│   │   │   ├── ai/              # AI调用模块
│   │   │   │   ├── base.py      # 统一LLM客户端接口
│   │   │   │   ├── factory.py   # 客户端工厂
│   │   │   │   ├── prompt.py    # 提示词构建
│   │   │   │   └── providers/   # 各厂商适配
│   │   │   │       ├── openai_client.py
│   │   │   │       ├── ollama_client.py
│   │   │   │       └── dashscope_client.py
│   │   │   ├── collector/       # 数据采集模块
│   │   │   │   └── jsonl_writer.py
│   │   │   └── training/        # 训练模块
│   │   │       ├── sft.py
│   │   │       └── exporter.py
│   │   ├── repositories/        # 数据访问层
│   │   │   ├── game_repo.py
│   │   │   ├── round_repo.py
│   │   │   ├── dataset_repo.py
│   │   │   └── training_repo.py
│   │   ├── schemas/             # Pydantic数据模型
│   │   │   ├── game.py
│   │   │   ├── ai_player.py
│   │   │   ├── data.py
│   │   │   └── training.py
│   │   ├── services/            # 业务服务层
│   │   │   ├── game_service.py
│   │   │   ├── ai_service.py
│   │   │   ├── ai_player_service.py
│   │   │   ├── data_service.py
│   │   │   └── training_service.py
│   │   ├── websocket/           # WebSocket管理
│   │   │   ├── manager.py
│   │   │   └── handlers.py
│   │   ├── utils/               # 工具函数
│   │   │   ├── exceptions.py
│   │   │   ├── id_generator.py
│   │   │   └── logger.py
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库初始化
│   │   ├── dependencies.py      # FastAPI依赖注入
│   │   └── main.py              # FastAPI应用入口
│   ├── tests/                   # 测试目录
│   │   ├── test_api/
│   │   ├── test_core/
│   │   └── test_services/
│   ├── pyproject.toml           # Poetry配置
│   └── poetry.lock
│
├── web/                         # Vue前端
│   ├── src/
│   │   ├── api/                 # API调用封装
│   │   │   ├── client.ts        # Axios实例
│   │   │   ├── gameApi.ts
│   │   │   ├── aiPlayerApi.ts
│   │   │   ├── dataApi.ts
│   │   │   ├── trainingApi.ts
│   │   │   └── types.ts         # TypeScript类型定义
│   │   ├── components/          # 组件
│   │   │   ├── common/          # 通用组件
│   │   │   │   ├── AppHeader.vue
│   │   │   │   ├── AppSidebar.vue
│   │   │   │   ├── EmptyState.vue
│   │   │   │   └── LoadingSpinner.vue
│   │   │   └── game/            # 游戏组件
│   │   │       └── PlayerCard.vue
│   │   ├── composables/         # 组合式函数
│   │   │   ├── useWebSocket.ts
│   │   │   └── usePagination.ts
│   │   ├── router/              # 路由配置
│   │   │   └── index.ts
│   │   ├── stores/              # Pinia状态管理
│   │   │   ├── useGameStore.ts
│   │   │   ├── useDataStore.ts
│   │   │   └── useTrainingStore.ts
│   │   ├── styles/              # 样式文件
│   │   │   ├── variables.css
│   │   │   ├── components.css
│   │   │   └── index.css
│   │   ├── types/               # 类型定义
│   │   │   ├── game.ts
│   │   │   └── websocket.ts
│   │   ├── views/               # 页面视图
│   │   │   ├── GameView.vue
│   │   │   ├── GameObserverView.vue
│   │   │   ├── AIPlayerView.vue
│   │   │   ├── DataView.vue
│   │   │   ├── TrainingView.vue
│   │   │   └── SettingsView.vue
│   │   ├── App.vue
│   │   └── main.ts
│   ├── dist/                    # 构建产物
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── config/                      # 配置文件
│   └── ai_players.yaml          # AI角色配置
│
├── data/                        # 数据存储（运行时生成）
│   ├── db/                      # SQLite数据库
│   │   └── app.db
│   ├── games/                   # 原始对局数据
│   │   └── 2026-03-25/
│   └── datasets/                # 导出的训练集
│
├── docs/                        # 文档
│   ├── API_DESIGN.md
│   ├── ARCHITECTURE.md
│   ├── CODING_STANDARDS.md
│   └── PROJECT_STRUCTURE.md
│
├── models/                      # 训练产出的模型
│
├── .env.example                 # 环境变量示例
├── README.md
└── LICENSE
```

### 7.2 模块依赖关系

```
web/ (Vue前端)
    └── HTTP/WebSocket ──→ server/app/main.py (FastAPI)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
    api/v1/                 services/              repositories/
    (路由处理)              (业务逻辑)              (数据访问)
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                            core/
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼
    engine/      ai/      collector/    training/
    (游戏逻辑)  (LLM调用)  (数据采集)  (模型训练)
```

### 7.3 核心接口定义

#### 7.3.1 统一LLM客户端接口

```python
from abc import ABC, abstractmethod
from typing import Any

class LLMClient(ABC):
    """大模型统一接口"""
    
    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送对话请求，返回文本"""
        pass
    
    @abstractmethod
    def supports(self, provider: str) -> bool:
        """判断是否支持该供应商"""
        pass
```

#### 7.3.2 数据采集器接口

```python
class JsonlWriter:
    """数据采集器，负责写入JSONL文件"""
    
    def start_game(self, game_id: str, game_type: str, player_ids: list[str]) -> str:
        """开始新对局，返回数据文件路径"""
        pass
    
    def record_round(self, game_id: str, data: dict) -> None:
        """记录一轮决策"""
        pass
    
    def end_game(self, game_id: str, summary: dict) -> None:
        """结束对局"""
        pass
```

#### 7.3.3 WebSocket连接管理器

```python
class ConnectionManager:
    """WebSocket连接管理器"""
    
    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        """接受并注册新的WebSocket连接"""
        pass
    
    async def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        """移除WebSocket连接"""
        pass
    
    async def broadcast(self, game_id: str, message: dict[str, Any]) -> None:
        """向所有观察该对局的连接广播消息"""
        pass
```

## 8. 可扩展性详细设计

### 8.1 添加新游戏的步骤

#### 8.1.1 服务端扩展
1. 在 `server/game_engines/` 下创建新文件 `newgame.py`
2. 定义游戏特定的状态类和动作枚举：

```python
# server/game_engines/newgame.py
from dataclasses import dataclass
from .base import GameEngine, GameState, GameAction

@dataclass
class NewGameState(GameState):
    """新游戏状态"""
    deck: List[str] = field(default_factory=list)
    health: Dict[str, int] = field(default_factory=dict)
    # 游戏特有属性

class NewGameAction:
    """新游戏动作"""
    DRAW_CARD = "draw_card"
    USE_SKILL = "use_skill"
    ATTACK = "attack"

class NewGameEngine(GameEngine):
    @property
    def game_type(self) -> str:
        return "newgame"
    
    # 实现所有抽象方法...
```

3. 在引擎注册中心注册：

```python
# server/game_engines/__init__.py
from .newgame import NewGameEngine
from .registry import GameEngineRegistry

GameEngineRegistry.register(NewGameEngine())
```

#### 8.1.2 前端扩展
1. 创建游戏牌桌组件：`web/src/components/games/NewGameBoard.vue`
2. 实现牌桌渲染逻辑，接收通用props：

```vue
<template>
  <div class="newgame-board">
    <!-- 游戏特定渲染逻辑 -->
  </div>
</template>

<script setup>
defineProps({
  gameState: Object,
  currentPlayer: Object,
  isObserving: Boolean
})
</script>
```

3. 在游戏路由中注册：

```javascript
// web/src/router/index.js
const gameComponents = {
  'doudizhu': () => import('@/components/games/DouDiZhuBoard.vue'),
  'newgame': () => import('@/components/games/NewGameBoard.vue')
}
```

### 8.2 添加新模型供应商

1. 在 `server/ai/providers/` 下创建新文件 `newprovider.py`
2. 实现 `LLMClient` 接口：

```python
# server/ai/providers/newprovider.py
from ..client import LLMClient

class NewProviderClient(LLMClient):
    def __init__(self, api_key: str, model: str = "default-model"):
        self.api_key = api_key
        self.model = model
    
    def supports(self, provider: str) -> bool:
        return provider == "newprovider"
    
    async def chat(self, messages: List[Dict], **kwargs) -> str:
        # 调用新供应商API
        pass
```

3. 在工厂中注册：

```python
# server/ai/client.py
from .providers.newprovider import NewProviderClient

LLMClientFactory._clients.append(NewProviderClient)
```

### 8.3 添加新训练算法

1. 在 `server/training/` 下创建新文件 `new_algorithm.py`
2. 实现训练器：

```python
# server/training/new_algorithm.py
class NewAlgorithmTrainer:
    def __init__(self, dataset_path: str, config: Dict):
        self.dataset_path = dataset_path
        self.config = config
    
    def train(self, output_dir: str) -> str:
        """执行训练，返回模型路径"""
        # 实现新训练算法
        pass
```

3. 在训练任务配置中支持新算法：

```json
{
  "training_type": "new_algorithm",
  ...
}
```

## 9. 部署与运维

### 9.1 本地开发环境

#### 9.1.1 环境要求
- Python 3.11+
- Node.js 20.19+ 或 22.12+
- 可选：Ollama（用于本地大模型）

#### 9.1.2 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab

# 2. 安装Python依赖（使用Poetry）
cd server
poetry install

# 3. 安装前端依赖
cd ../web
npm install

# 4. 构建前端
npm run build

# 5. 启动后端服务
cd ../server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或同时启动前端开发服务器
cd ../web
npm run dev
```

#### 9.1.3 访问地址
- 前端界面：http://localhost:5173（开发模式）或 http://localhost:8000（生产模式）
- API文档：http://localhost:8000/docs
- ReDoc文档：http://localhost:8000/redoc

### 9.2 配置文件说明

#### 9.2.1 环境变量
可通过 `.env` 文件配置敏感信息：

```bash
# .env
OPENAI_API_KEY=sk-xxx
DASHSCOPE_API_KEY=xxx
OLLAMA_BASE_URL=http://localhost:11434
```

#### 9.2.2 系统配置 (`config/settings.yaml`)
见5.2.3节。

### 9.3 数据备份

| 数据类型 | 存储位置 | 备份建议 |
|----------|----------|----------|
| 对局元数据 | `data/db/app.db` | 定期备份SQLite文件 |
| 对局详细数据 | `data/games/` | 定期压缩归档 |
| 训练数据集 | `data/datasets/` | 重要数据集单独备份 |
| 模型文件 | `models/` | 保留重要版本 |

### 9.4 性能优化建议
- 批量模式下，可设置连续对局数量，一次性运行多局
- 大模型调用可设置并发数，提高数据采集效率
- 训练任务建议在GPU环境下运行，CPU训练较慢
- 使用 `--workers` 参数启动多个Uvicorn worker提高并发

## 10. 开发路线图

### 第一阶段：核心闭环 ✅ 已完成
- [x] 斗地主游戏引擎实现（DoudizhuEngine）
- [x] 统一LLM客户端（OpenAI + Ollama + Dashscope）
- [x] 数据采集器（JSONL写入）
- [x] FastAPI后端框架搭建
- [x] Vue 3 + TypeScript前端框架搭建
- [x] WebSocket实时推送（思考链、动作）
- [x] 基础牌局观察界面
- [x] SQLite元数据存储
- [x] AI角色配置管理

### 第二阶段：数据与训练 🚧 进行中
- [x] 数据看板（统计图表）
- [x] 数据集导出功能
- [x] Mock SFT 训练任务编排
- [x] 训练任务管理界面
- [x] 模型仓库管理
- [ ] 接入真实 SFT 训练
- [ ] 模型部署为 AI 角色

### 第四阶段：扩展与优化 📋 待开始
- [ ] 添加三国杀游戏引擎
- [ ] 强化训练能力（如 PPO 等）
- [ ] A/B测试功能
- [ ] 模型性能评估报告

## 11. 总结

本说明书定义了AI卡牌游戏实验室平台的完整设计，核心特点如下：

1. **纯Python架构**：FastAPI + Uvicorn，无需Node.js中间层，简化部署
2. **通用游戏引擎**：通过抽象接口支持任意卡牌游戏，已实现斗地主引擎
3. **完整数据闭环**：从对局采集、数据清洗到模型训练，全流程Python实现
4. **双存储设计**：SQLite存储元数据便于查询，JSONL存储详细数据便于训练
5. **可观测性优先**：WebSocket实时推送思考链，支持回放和人工干预
6. **本地化部署**：所有数据存储在本地，无需网络服务，保护隐私
7. **可扩展性**：新游戏、新模型、新算法均可无缝接入

**当前进度**：第一阶段（核心闭环）已完成，第二阶段（数据与训练）进行中。

该平台是一个**纯粹的AI研究工具**，专注于数据采集和模型训练，为探索卡牌游戏AI的决策能力和模型蒸馏提供基础设施。