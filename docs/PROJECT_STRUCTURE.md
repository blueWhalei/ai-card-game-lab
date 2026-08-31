# 目录结构说明

> 本文档定义项目的完整目录规划，说明每个目录和关键文件的职责。开发时严格遵循此结构。

## 完整目录树

```
ai-card-game-lab/
│
├── server/                              # ===== Python 后端 (FastAPI) =====
│   ├── pyproject.toml                   # 项目元数据 + 依赖声明 (Poetry)
│   ├── poetry.lock                      # 锁文件（自动生成）
│   │
│   ├── app/                             # 应用主包
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI 应用实例创建与中间件注册
│   │   ├── config.py                    # Pydantic Settings 配置管理
│   │   ├── database.py                  # SQLite 连接管理 (aiosqlite)
│   │   ├── dependencies.py              # FastAPI 依赖注入容器
│   │   │
│   │   ├── api/                         # ---------- API 层 ----------
│   │   │   ├── __init__.py
│   │   │   ├── router.py               # 总路由聚合（include 所有子路由）
│   │   │   └── v1/                      # API v1 版本
│   │   │       ├── __init__.py
│   │   │       ├── game.py             # 对局 CRUD + 控制
│   │   │       ├── experiment.py               # 实验（run）CRUD / 采集
│   │   │       ├── experiment_config.py        # 实验配置管理
│   │   │       ├── experiment_config_stats.py  # 实验配置统计 API
│   │   │       ├── data.py             # 数据统计 + 数据集管理
│   │   │       ├── training.py         # 训练任务 + 模型仓库
│   │   │       ├── prompt.py           # 提示词模板管理
│   │   │       ├── trace.py            # AI 决策追踪 API
│   │   │       ├── decision.py         # 决策点数据 API (SFT 训练样本)
│   │   │       ├── player_stats.py     # （已合并至 experiment_config_stats）
│   │   │       ├── migration.py        # 数据库迁移工具 API
│   │   │       └── system.py           # 系统健康检查 + 配置 + 归档管理
│   │   │
│   │   ├── schemas/                     # ---------- Pydantic 模型 ----------
│   │   │   ├── __init__.py
│   │   │   ├── common.py              # 通用响应包装 (ApiResponse, PaginatedData)
│   │   │   ├── game.py                # 对局请求/响应模型
│   │   │   ├── experiment_config.py   # 实验配置请求/响应模型
│   │   │   ├── data.py                # 数据/数据集请求/响应模型
│   │   │   ├── training.py            # 训练任务请求/响应模型
│   │   │   ├── archive.py             # 归档/清理请求/响应模型
│   │   │   └── system.py              # 系统配置请求/响应模型
│   │   │
│   │   ├── services/                    # ---------- Service 层 ----------
│   │   │   ├── __init__.py
│   │   │   ├── game_service.py        # 对局业务编排
│   │   │   ├── game_orchestration_service.py # 对局执行编排（引擎调用 + AI 调度）
│   │   │   ├── game_replay_service.py # 对局回放服务
│   │   │   ├── ai_service.py          # AI 调用业务编排（重试 + 解析）
│   │   │   ├── experiment_service.py          # 实验（run）编排 / 采集 / summary
│   │   │   ├── experiment_config_service.py   # 实验配置 CRUD（SQLite + YAML seed）
│   │   │   ├── experiment_config_stats_service.py  # 实验配置战绩统计
│   │   │   ├── data_service.py        # 数据统计 + 数据集导出
│   │   │   ├── training_service.py    # 训练任务编排（状态机 + mock 训练）
│   │   │   ├── prompt_service.py      # 提示词模板管理
│   │   │   ├── trace_service.py       # AI 决策追踪服务
│   │   │   ├── decision_service.py    # 决策点采集服务 (SFT 训练样本)
│   │   │   ├── archive_service.py     # 数据归档与清理服务
│   │   │   └── system_service.py      # 系统配置服务
│   │   │
│   │   ├── repositories/               # ---------- 数据访问层 ----------
│   │   │   ├── __init__.py
│   │   │   ├── game_repo.py           # 对局数据访问 (SQLite)
│   │   │   ├── round_repo.py          # 轮次数据访问 (SQLite)
│   │   │   ├── dataset_repo.py        # 数据集元数据访问 (SQLite)
│   │   │   ├── training_repo.py       # 训练任务数据访问 (SQLite)
│   │   │   ├── prompt_repo.py         # 提示词模板数据访问 (SQLite)
│   │   │   ├── experiment_repo.py             # 实验（run）数据访问
│   │   │   ├── experiment_config_repo.py       # 实验配置数据访问 (SQLite)
│   │   │   └── experiment_config_stats_repo.py # 实验配置战绩统计 (SQLite)
│   │   │
│   │   ├── core/                        # ---------- 核心领域层 ----------
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── engine/                 # 游戏引擎
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # GameEngine ABC + GameState/GameAction 基类
│   │   │   │   ├── registry.py        # GameEngineRegistry 注册中心
│   │   │   │   └── doudizhu/          # 斗地主引擎（独立子包）
│   │   │   │       ├── __init__.py
│   │   │   │       ├── engine.py      # DoudizhuEngine 实现
│   │   │   │       ├── cards.py       # 牌面常量、花色、ActionType 定义
│   │   │   │       └── hand_evaluator.py # 手牌分类与合法出牌枚举
│   │   │   │
│   │   │   ├── ai/                     # AI 调用模块
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # LLMClient ABC + ChatResponse
│   │   │   │   ├── factory.py         # LLMClientFactory
│   │   │   │   ├── stream_chunk.py     # StreamChunk (流式输出块, 含可选 usage)
│   │   │   │   ├── prompt.py          # PromptBuilder 提示词构建
│   │   │   │   ├── provider_config.py  # LLMProviderConfig 配置驱动
│   │   │   │   ├── providers/         # LLM 供应商实现
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── openai_client.py  # OpenAI 兼容 (DeepSeek/Kimi/MiniMax/ZhipuAI/Yi/Baichuan)
│   │   │   │   │   ├── ollama_client.py
│   │   │   │   │   └── dashscope_client.py
│   │   │   │   ├── parsers/            # AI 响应解析
│   │   │   │   │   ├── action_parser.py  # 出牌动作解析
│   │   │   │   │   └── bid_parser.py     # 叫分解析
│   │   │   │   ├── prompts/            # 提示词模板
│   │   │   │   │   └── registry.py      # 模板注册中心
│   │   │   │   ├── tools/              # AI 工具
│   │   │   │   └── memory/             # AI 记忆模块
│   │   │   │
│   │   │   ├── collector/              # 数据采集
│   │   │   │   ├── __init__.py
│   │   │   │   └── jsonl_writer.py    # JSONL 文件写入器
│   │   │   │
│   │   │   ├── database/               # 数据库抽象层（预留迁移接口）
│   │   │   │   ├── __init__.py
│   │   │   │   ├── backend.py         # DatabaseBackend ABC + SQLiteBackend
│   │   │   │   └── migration.py       # 迁移工具（分析/导出/生成 schema）
│   │   │   │
│   │   │   └── training/              # 训练模块
│   │   │       ├── __init__.py
│   │   │       ├── sft.py             # PEFT LoRA SFT（缺依赖则拒绝）
│   │   │       └── exporter.py        # JSONL → ChatML SFT 格式导出
│   │   │
│   │   ├── websocket/                   # ---------- WebSocket ----------
│   │   │   ├── __init__.py
│   │   │   ├── manager.py            # ConnectionManager 连接管理
│   │   │   └── handlers.py           # WebSocket 消息处理器（game_websocket 逻辑）
│   │   │
│   │   └── utils/                       # ---------- 工具层 ----------
│   │       ├── __init__.py
│   │       ├── logger.py              # structlog 配置
│   │       ├── exceptions.py          # 自定义异常体系
│   │       └── id_generator.py        # 唯一 ID 生成
│   │
│   └── tests/                           # 测试目录（镜像 app/ 结构）
│       ├── conftest.py                 # pytest 全局 fixture
│       ├── test_api/
│       │   ├── test_system.py
│       │   ├── test_game.py
│       │   └── test_data.py
│       ├── test_services/
│       │   ├── test_ai_service.py
│       │   └── test_training_service.py
│       └── test_core/
│           ├── test_engine/
│           │   └── test_doudizhu.py
│           └── test_ai/
│
├── web/                                 # ===== Vue 3 前端 =====
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── eslint.config.ts               # ESLint Flat Config
│   ├── index.html
│   │
│   ├── public/                          # 静态资源（不经过构建）
│   │   └── favicon.ico
│   │
│   ├── src/
│   │   ├── main.ts                     # 应用入口
│   │   ├── App.vue                     # 根组件
│   │   │
│   │   ├── router/                     # Vue Router
│   │   │   └── index.ts
│   │   │
│   │   ├── stores/                     # Pinia 状态管理
│   │   │   ├── useGameStore.ts
│   │   │   ├── useDataStore.ts
│   │   │   └── useTrainingStore.ts
│   │   │
│   │   ├── api/                        # API 请求封装
│   │   │   ├── client.ts              # Axios 实例 + 拦截器
│   │   │   ├── types.ts               # API 类型定义（对齐后端 Schema）
│   │   │   ├── gameApi.ts
│   │   │   ├── experimentApi.ts           # 实验（run）API
│   │   │   ├── experimentConfigApi.ts
│   │   │   ├── dataApi.ts
│   │   │   ├── trainingApi.ts
│   │   │   ├── prompts.ts             # 提示词模板 API
│   │   │   ├── traces.ts              # AI 决策追踪 API
│   │   │   ├── decision.ts            # 决策点数据 API
│   │   │   └── archive.ts             # 归档/清理 API
│   │   │
│   │   ├── composables/                # 可复用组合式函数
│   │   │   ├── useWebSocket.ts        # WebSocket 连接管理
│   │   │   └── usePagination.ts       # 分页逻辑
│   │   │
│   │   ├── utils/                      # 前端工具函数
│   │   │   ├── error.ts               # API 错误消息映射与统一展示入口
│   │   │   └── format.ts              # 时间/字节/百分比格式化工具
│   │   │
│   │   ├── components/                 # 组件
│   │   │   ├── common/                # 通用/共享组件
│   │   │   │   ├── AppHeader.vue
│   │   │   │   ├── AppSidebar.vue
│   │   │   │   ├── LoadingSpinner.vue
│   │   │   │   └── EmptyState.vue
│   │   │   │
│   │   │   ├── experiment/            # 实验详情拆出的 Tab / 对话框
│   │   │   │   ├── ExperimentGamesTab.vue
│   │   │   │   ├── ExperimentPlayersTab.vue
│   │   │   │   ├── ExperimentTrainingTab.vue
│   │   │   │   └── ExperimentControlDialog.vue
│   │   │   │
│   │   │   ├── training/              # 训练台任务 / 模型 / 实时日志
│   │   │   ├── prompt/                # 提示词编辑 / 列表 / 版本对比
│   │   │   │
│   │   │   ├── game/                  # 对局相关组件
│   │   │   │   ├── PlayerCard.vue    # 玩家卡片（角色/手牌/思考状态/耗时）
│   │   │   │   └── ThinkingPanel.vue # AI 思考历史面板（可折叠）
│   │   │   │
│   │   │   ├── data/                  # 数据相关组件
│   │   │   │   ├── StatCards.vue     # 统计卡片 + ECharts 图表（含 Token/对局/AI表现/响应时间 5 大板块）
│   │   │   │   ├── DatasetList.vue   # 数据集表格 + 创建对话框
│   │   │   │   ├── StorageMonitor.vue # 存储空间监控卡片
│   │   │   │   ├── ArchiveManager.vue # 数据归档与清理管理
│   │   │   │   └── tabs/                # 数据页签标签组件
│   │   │   │       ├── OverviewTab.vue  # 总览（加载 StatCards）
│   │   │   │       ├── DatasetTab.vue   # 数据集管理
│   │   │   │       ├── StorageTab.vue   # 存储管理
│   │   │   │       └── ArchiveTab.vue   # 归档清理
│   │   │   │
│   │   │   └── trace/                # 追踪组件
│   │   │       ├── TraceDetail.vue   # 决策详情展示
│   │   │       ├── TraceMetrics.vue  # 性能指标仪表盘
│   │   │       └── ResponseTimeChart.vue # AI 响应时间趋势图
│   │   │
│   │   ├── views/                      # 页面级组件（路由对应）
│   │   │   ├── GameView.vue           # 对局列表 + 创建
│   │   │   ├── GameObserverView.vue   # 实时观战（Observer 壳 + GenericBoard）
│   │   │   ├── ExperimentListView.vue # 实验列表（默认首页 /；/pipeline 重定向至此）
│   │   │   ├── ExperimentCompareView.vue # 跨实验对比 /experiments/compare
│   │   │   ├── ExperimentDetailView.vue # 实验工作台 /experiments/:id
│   │   │   ├── ExperimentConfigView.vue  # 实验配置 CRUD
│   │   │   ├── DataView.vue           # 数据看板（统计 + 数据集管理）
│   │   │   ├── TrainingView.vue       # 训练控制台（任务列表 + 模型仓库 + 创建对话框）
│   │   │   ├── PromptView.vue         # 提示词管理（模板列表 + 版本控制）
│   │   │   ├── TraceView.vue          # 决策追踪（追踪列表 + 详情 + 指标）
│   │   │   ├── DecisionView.vue       # 决策点数据（SFT 训练样本列表 + 详情）
│   │   │   └── SettingsView.vue       # 系统设置（只读：供应商状态/存储/路径）
│   │   │
│   │   ├── layouts/                    # 双壳布局
│   │   │   ├── WorkbenchLayout.vue    # 侧栏分组导航（实验室/管道/调参）
│   │   │   └── ObserverLayout.vue     # 全屏观战壳
│   │   │
│   │   ├── styles/                     # 全局样式
│   │   │   ├── index.css              # 全局样式入口
│   │   │   ├── tokens.css             # Ink Lab CSS 变量
│   │   │   ├── variables.css          # 兼容入口（转 tokens）
│   │   │   └── components.css         # 共享组件样式
│   │   │
│   │   └── types/                      # 全局 TypeScript 类型
│   │       ├── game.ts                # 游戏领域类型
│   │       ├── observer.ts            # ObserverSnapshot 协议
│   │       ├── websocket.ts           # WebSocket 消息类型
│   │       └── env.d.ts               # 环境变量类型声明
│   │
│   └── src/**/*.spec.ts               # 前端单测（Vitest，与源码同目录）
│
├── config/                              # ===== 运行时配置 =====
│   ├── experiment_configs.yaml         # 实验配置 seed
│   └── README.md                       # 说明：experiment_configs.yaml 仅作 seed；运行时配置见 .env
│
├── data/                                # ===== 运行时数据 (gitignore) =====
│   ├── games/                          # 对局 JSONL 归档
│   │   └── {YYYY-MM-DD}/
│   │       └── {game_id}.jsonl
│   ├── datasets/                       # 导出的训练数据集
│   ├── db/                             # SQLite 数据库文件
│   │   └── app.db
│   └── logs/                           # 运行日志
│
├── models/                              # ===== 训练产出模型 (gitignore) =====
│
├── docs/                                # ===== 项目文档 =====
│   ├── ARCHITECTURE.md                 # 架构设计
│   ├── PROJECT_STRUCTURE.md            # 目录结构（本文档）
│   ├── CODING_STANDARDS.md             # 编码规范
│   └── API_DESIGN.md                   # API 设计
│
├── .gitignore
├── .env.example                        # 环境变量模板
├── LICENSE
├── README.md
└── AI卡牌游戏实验室 - 详细设计说明书.md  # 原始需求设计文档
```

## 各层职责速查

### 后端分层

| 层 | 目录 | 职责 | 依赖方向 |
|----|------|------|----------|
| **API** | `app/api/` | 路由 + 请求校验 + 响应序列化 | → Service |
| **Schema** | `app/schemas/` | Pydantic 请求/响应模型 | 被 API 层引用 |
| **Service** | `app/services/` | 业务编排 + 跨模块协调 | → Repository + Core |
| **Repository** | `app/repositories/` | SQLite 数据访问 | → database |
| **Core** | `app/core/` | 纯领域逻辑（引擎/AI/采集/训练） | 不依赖 Web 框架 |
| **WebSocket** | `app/websocket/` | WS 连接管理 + 消息处理 | → Service |
| **Utils** | `app/utils/` | 日志/异常/ID生成 | 被所有层引用 |

**依赖规则**（严格单向）：

```
API → Service → Repository → database
                Service → Core
```

- Core 层不得依赖 API、Service、Repository
- API 层不得直接调用 Core 或 Repository
- Repository 不得调用 Service 或 API

### 前端分层

| 层 | 目录 | 职责 |
|----|------|------|
| **Views** | `src/views/` | 页面级组件，路由对应，编排子组件 |
| **Components** | `src/components/` | UI 组件，接收 props，发射 events |
| **Stores** | `src/stores/` | Pinia 全局状态，调用 API |
| **API** | `src/api/` | Axios 封装，类型化请求函数 |
| **Composables** | `src/composables/` | 可复用逻辑（WebSocket、分页等） |
| **Utils** | `src/utils/` | 错误展示等轻量共享工具 |

## 新增游戏时需要修改的文件清单

以添加「三国杀」为例：

| 位置 | 操作 |
|------|------|
| `server/app/core/engine/sanguosha/` | 新建目录，实现引擎 |
| `server/app/core/engine/__init__.py` | 注册新引擎 |
| `get_public_info(..., is_observer=True)` | 输出 ObserverSnapshot（`players[]` / `table.slots` / `extras`） |

**禁止**新建 `web/src/components/game/boards/<GameName>Board.vue` 或修改 `GameObserverView` 按游戏分支。观战统一走 `GenericBoard`。

无需修改 API 层、Service 层、数据层 —— 通过 `game_type` 参数自动路由。
