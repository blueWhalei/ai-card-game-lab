# 目录结构说明

> 目录地图。与代码冲突时以仓库实际文件和 `CLAUDE.md` 为准。

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
│   │   │       ├── experiment_config.py        # 选手配置 API（路径 experiment-configs）
│   │   │       ├── experiment_config_stats.py  # 选手配置统计 API
│   │   │       ├── data.py             # 数据统计 + 数据集管理
│   │   │       ├── training.py         # 训练任务 + 模型仓库
│   │   │       ├── prompt.py           # 提示词模板管理
│   │   │       ├── trace.py            # AI 决策追踪 API
│   │   │       ├── decision.py         # 决策点数据 API (SFT 训练样本)
│   │   │       └── system.py           # 健康检查 / startup-check / seed-demo / 归档
│   │   │
│   │   ├── schemas/                     # ---------- Pydantic 模型 ----------
│   │   │   ├── __init__.py
│   │   │   ├── common.py              # 通用响应包装 (ApiResponse, PaginatedData)
│   │   │   ├── game.py                # 对局请求/响应模型
│   │   │   ├── experiment.py          # 实验（run）请求/响应模型
│   │   │   ├── experiment_config.py   # 选手配置请求/响应模型
│   │   │   ├── data.py                # 数据/数据集请求/响应模型
│   │   │   ├── training.py            # 训练任务请求/响应模型
│   │   │   ├── prompt.py              # 提示词模板请求/响应模型
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
│   │   │   ├── experiment_config_service.py   # 选手配置 CRUD（SQLite，UI 创建）
│   │   │   ├── experiment_config_stats_service.py  # 选手配置战绩统计
│   │   │   ├── data_service.py        # 数据统计 + 数据集导出
│   │   │   ├── training_service.py    # 训练任务编排（PEFT LoRA / CPU 快速验证）
│   │   │   ├── prompt_service.py      # 提示词模板管理
│   │   │   ├── trace_service.py       # AI 决策追踪服务
│   │   │   ├── decision_service.py    # 决策点采集服务 (SFT 训练样本)
│   │   │   ├── archive_service.py     # 数据归档与清理服务
│   │   │   ├── demo_seed_service.py   # 演示对局种子
│   │   │   ├── startup_recovery.py    # 启动恢复
│   │   │   └── system_service.py      # 系统配置 / 供应商状态
│   │   │
│   │   ├── repositories/               # ---------- 数据访问层 ----------
│   │   │   ├── __init__.py
│   │   │   ├── game_repo.py           # 对局数据访问 (SQLite)
│   │   │   ├── round_repo.py          # 轮次数据访问 (SQLite)
│   │   │   ├── dataset_repo.py        # 数据集元数据访问 (SQLite)
│   │   │   ├── training_repo.py       # 训练任务数据访问 (SQLite)
│   │   │   ├── prompt_repo.py         # 提示词模板数据访问 (SQLite)
│   │   │   ├── experiment_repo.py             # 实验（run）数据访问
│   │   │   ├── experiment_config_repo.py       # 选手配置数据访问 (SQLite)
│   │   │   ├── experiment_config_stats_repo.py # 选手配置战绩统计 (SQLite)
│   │   │   ├── decision_repo.py       # 决策点
│   │   │   ├── trace_repo.py          # 追踪
│   │   │   ├── archive_repo.py        # 归档
│   │   │   └── stats_repo.py          # 聚合统计
│   │   │
│   │   ├── core/                        # ---------- 核心领域层 ----------
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── engine/                 # 游戏引擎
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # GameEngine ABC + GameState/GameAction 基类
│   │   │   │   ├── registry.py        # GameEngineRegistry 注册中心
│   │   │   │   ├── observer_types.py  # ObserverSnapshot 协议
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
│   │   │   │   │   ├── openai_client.py  # OpenAICompatibleClient（含 DashScope 等兼容厂商）
│   │   │   │   │   └── ollama_client.py
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
│   │   │   │   └── backend.py         # DatabaseBackend ABC + SQLiteBackend
│   │   │   │
│   │   │   ├── training/              # 训练模块
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sft.py             # PEFT LoRA SFT（缺依赖则拒绝）
│   │   │   │   ├── exporter.py        # JSONL → ChatML SFT 格式导出
│   │   │   │   ├── deploy.py          # merge / GGUF / Ollama 辅助
│   │   │   │   └── cpu_smoke.py       # 无 GPU 步数/样本钳制
│   │   │   │
│   │   │   └── events/                # 领域事件（EventBus + game lifecycle）
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
│   │   │   ├── systemApi.ts           # 健康检查 / 供应商 / seed-demo
│   │   │   └── archive.ts             # 归档/清理 API
│   │   │
│   │   ├── composables/                # 可复用组合式函数
│   │   │   ├── useWebSocket.ts        # WebSocket 连接管理
│   │   │   ├── useGameWebSocket.ts    # 观战专用 WS
│   │   │   ├── usePagination.ts       # 分页逻辑
│   │   │   ├── useTweenNumber.ts      # 数字滚动
│   │   │   ├── useTheme.ts / useLocale.ts / useFieldWidth.ts
│   │   │
│   │   ├── utils/                      # 前端工具函数
│   │   │   ├── error.ts               # API 错误消息映射与统一展示入口
│   │   │   ├── format.ts              # 时间/字节/百分比格式化工具
│   │   │   ├── pagination.ts          # 列表页默认 page_size=20
│   │   │   └── compareMatrix.ts       # 实验对比转置矩阵
│   │   │
│   │   ├── i18n/                        # vue-i18n（zh-CN + en）
│   │   │
│   │   ├── components/                 # 组件
│   │   │   ├── ui/                    # Reka UI + Ink Lab 控件（含 compact Table）
│   │   │   ├── common/                # 通用/共享组件
│   │   │   │   ├── HeaderToggles.vue      # 主题 / 语言 / 使用说明（/guide）
│   │   │   │   ├── WorkbenchFilterBar.vue  # 决策/追踪筛选（可锁定 experiment）
│   │   │   │   ├── ExperimentContextBar.vue # Pipeline 页回实验上下文条
│   │   │   │   ├── KpiStrip.vue / NameChips.vue / CompactRecordList.vue
│   │   │   │   ├── LoadingSpinner.vue
│   │   │   │   └── EmptyState.vue
│   │   │   │
│   │   │   ├── experiment/            # 实验详情：顶栏 / 结果摘要 / Tab / 档案
│   │   │   │   ├── ExperimentDetailContextBar.vue
│   │   │   │   ├── ExperimentResultsStrip.vue
│   │   │   │   ├── ExperimentMetaPanel.vue       # 实验档案（⋯ 对话框）
│   │   │   │   ├── ExperimentNotebookPanel.vue
│   │   │   │   ├── ExperimentGamesTab.vue
│   │   │   │   ├── ExperimentPlayersTab.vue
│   │   │   │   ├── ExperimentTrainingTab.vue     # 遗留组件，详情页未引用
│   │   │   │   └── ExperimentControlDialog.vue
│   │   │   │
│   │   │   ├── guide/                 # 使用说明 /guide
│   │   │   │   ├── GuideModuleSection.vue
│   │   │   │   └── GuideFlowDiagram.vue
│   │   │   │
│   │   │   ├── decision/              # 决策点面板（侧栏独立页；可带 experiment_id）
│   │   │   │   └── DecisionWorkbenchPanel.vue
│   │   │   │
│   │   │   ├── training/              # 训练页：任务 / 模型仓库 / 实时日志
│   │   │   ├── prompt/                # 提示词编辑 / 列表 / 版本对比
│   │   │   │
│   │   │   ├── game/                  # 对局相关组件
│   │   │   │   ├── GenericBoard.vue   # 唯一观战牌桌（列表）
│   │   │   │   ├── ThinkingPanel.vue # AI 思考历史面板
│   │   │   │   └── GameReplayControls.vue
│   │   │   │
│   │   │   ├── data/                  # 数据相关组件
│   │   │   │   ├── StatCards.vue     # 总览 KPI / 角色胜负饼图（不含按模型柱状图）
│   │   │   │   ├── DatasetList.vue
│   │   │   │   ├── StorageMonitor.vue
│   │   │   │   ├── ArchiveManager.vue
│   │   │   │   └── tabs/
│   │   │   │       ├── OverviewTab.vue
│   │   │   │       ├── AIPerformanceTab.vue  # 按模型对比（各图只出现一次）
│   │   │   │       ├── DatasetTab.vue
│   │   │   │       ├── StorageTab.vue
│   │   │   │       └── ArchiveTab.vue
│   │   │   │
│   │   │   └── trace/                # 追踪组件
│   │   │       ├── TraceWorkbenchPanel.vue # 追踪面板（侧栏独立页；可带 experiment_id）
│   │   │       ├── TraceDetail.vue   # 决策详情展示
│   │   │       ├── TraceMetrics.vue  # 性能指标仪表盘
│   │   │       └── ResponseTimeChart.vue # AI 响应时间趋势图
│   │   │
│   │   ├── views/                      # 页面级组件（路由对应）
│   │   │   ├── GameView.vue           # 试玩对局列表 + 创建
│   │   │   ├── GameObserverView.vue   # 实时观战（Observer 壳 + GenericBoard）
│   │   │   ├── ExperimentListView.vue # 实验列表（默认首页 /；/pipeline 重定向至此）
│   │   │   ├── ExperimentCompareView.vue # 跨实验对比 /experiments/compare
│   │   │   ├── ExperimentDetailView.vue # 实验详情 /experiments/:id（Tab：对局 / 选手表现）
│   │   │   ├── ExperimentConfigView.vue  # 选手配置 CRUD
│   │   │   ├── GuideView.vue          # 使用说明 /guide（桌面端目录在右侧）
│   │   │   ├── DataView.vue           # 数据看板（统计 + 数据集管理）
│   │   │   ├── TrainingView.vue       # 训练页（任务列表 + 模型仓库 + 创建对话框）
│   │   │   ├── PromptView.vue         # 提示词管理（模板列表 + 版本控制）
│   │   │   ├── TraceView.vue          # 决策追踪（薄壳 → TraceWorkbenchPanel）
│   │   │   ├── DecisionView.vue       # 决策点（薄壳 → DecisionWorkbenchPanel）
│   │   │   └── SettingsView.vue       # 系统设置（只读：供应商状态/存储/路径）
│   │   │
│   │   ├── layouts/                    # 双壳布局
│   │   │   ├── WorkbenchLayout.vue    # 侧栏：研究 / 数据与训练 / 调试
│   │   │   └── ObserverLayout.vue     # 全屏观战壳
│   │   │
│   │   ├── styles/                     # 全局样式
│   │   │   ├── index.css
│   │   │   ├── tokens.css             # Ink Lab CSS 变量
│   │   │   ├── motion.css             # 进出场 / 骨架 / 观战光晕
│   │   │   ├── variables.css          # 兼容入口（转 tokens）
│   │   │   └── components.css
│   │   │
│   │   └── types/                      # 全局 TypeScript 类型
│   │       ├── game.ts                # 游戏领域类型
│   │       ├── observer.ts            # ObserverSnapshot 协议
│   │       ├── websocket.ts           # WebSocket 消息类型
│   │       └── env.d.ts               # 环境变量类型声明
│   │
│   └── src/**/*.spec.ts               # 前端单测（Vitest，与源码同目录）
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
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── CODING_STANDARDS.md
│   ├── API_DESIGN.md
│   ├── E2E_PIPELINE.md
│   ├── EXAMPLES.md
│   └── 欢乐斗地主经典玩法规则.md
│
├── CLAUDE.md                            # Agent 入口（英文）
├── .gitignore
├── .env.example
├── LICENSE
└── README.md
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
