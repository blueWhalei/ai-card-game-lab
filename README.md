# AI Card Game Lab

[English](README.en.md) | 中文

AI 卡牌游戏实验室数据采集与训练平台 —— 面向 AI 研究的本地化工具，用于观察大模型决策过程、采集对局数据、蒸馏专用小模型。

## 核心能力

- **实验工作台**：以「实验」为第一公民——选手人数由游戏引擎 min/max 决定，在详情页采集、观战、登记训练、开对照、跨实验对比
- **通用游戏引擎**：抽象卡牌游戏共性，支持快速接入新游戏（首发：斗地主）
- **实时思考链观察**：通过 WebSocket 实时推送 AI 决策的思考过程，含流式推理输出、Token 用量统计
- **数据采集闭环**：JSONL 全量归档 + SQLite 元数据索引；决策点可按实验过滤导出 ChatML
- **数据看板**：Token 用量、对局质量、AI 表现、响应时间等多维度统计
- **模型蒸馏训练**：PEFT LoRA（无 GPU 走 CPU 冒烟）；训练产物可登记为 Ollama 选手并开对照实验

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端 | Vue 3 + TypeScript + Vite + Tailwind CSS v4 + Reka UI（Ink Lab 双壳） |
| 后端 | Python 3.11+ / FastAPI + WebSocket |
| AI 调用 | OpenAI / Ollama / DashScope / DeepSeek / Kimi / ZhipuAI / Yi / Baichuan / MiniMax 统一适配 |
| 元数据库 | SQLite（索引/查询/统计） |
| 数据归档 | JSONL 本地文件 |
| 训练框架 | `poetry install --with training` 启用 PEFT LoRA（Transformers）；无 GPU 走 CPU 冒烟 |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20.19+ 或 22.12+
- Poetry（Python 依赖管理）
- 可选：Ollama（本地大模型推理，零 Key 路径）

### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab

# 2. 复制环境变量配置
cp .env.example .env          # macOS / Linux
# copy .env.example .env      # Windows cmd
# 编辑 .env：填写至少一个云厂商 Key，或使用本机 Ollama
# 选手配置在前端「实验配置」页创建，仓库不提供 YAML seed

# 3. 安装 Python 依赖
cd server
poetry install

# 4. 启动后端服务
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 安装前端依赖并启动开发服务器（新终端）
cd ../web
npm install
npm run dev
```

### 首次运行检查清单

1. `.env` 已复制，并至少满足其一：云厂商 API Key，或本机 Ollama。
2. 打开「实验配置」页，按引擎槽位数创建选手（斗地主需要 3 个）。首次为空，点空态按钮创建。
3. 后端启动后可访问 http://localhost:8000/api/v1/system/startup-check 查看警告。
4. 采集对局会校验所选配置的 API Key；未配置会被拒绝，而不是开局后静默失败。
5. 训练需 `cd server && poetry install --with training`。缺依赖时无法创建任务；无 GPU 自动走 CPU 冒烟。
6. 无 Key 时可在首页点「加载演示对局」体验观战与回放（演示局不挂实验）。

### 研究者主路径（推荐）

打开 http://localhost:5173 —— 首页即**实验列表**。

1. **创建选手配置**：到「实验配置」页为每个槽位建一份（模型 / 温度等）
2. **新建实验**：按引擎要求选择实验配置 + 目标局数 → 进入详情（**不会**自动开局，避免误打 Key）
3. **开始采集 / 再开 n 局**：在详情页批量开局；进行中可点进观战，结束可回放
4. **登记并开训**：可训决策 > 0 时一键登记 ChatML 并创建训练任务（缺训练依赖则只登记）
5. **训练台 · 模型仓库**：导出部署包 →（本机 GGUF + `ollama create`）→ **登记为选手**
6. **开对照实验**：详情「开对照实验」选新选手 + 与引擎槽位数相同的基线 → 新建实验后继续采集；「对比实验」并排看胜率 CI / 延迟 / Token

**基准测验**：新建实验时可选「基准测验（固定发牌）」模式，使用系统预置的 50 组 `deal_seed`（最多 50 局），便于跨模型在相同牌面下公平对比；对比页会显示「基准测验」标记。

侧栏「对局」仍可用于散局创建。实验详情 Tab 含**对局 / 选手 / 决策点 / 追踪 / 训练**（`?tab=decisions` 等）；侧栏「决策点 / 追踪 / 数据 / 训练」也可用 `?experiment_id=` 深链，工具页顶部有回实验的上下文条。

也可用脚本闭环（不经实验对象）：

```powershell
.\scripts\e2e_pipeline.ps1 guide
.\scripts\e2e_pipeline.ps1 check
.\scripts\e2e_pipeline.ps1 all -Count 1   # 采集→导出→真训（需 training 依赖）
```

完整说明见 [端到端闭环指南](docs/E2E_PIPELINE.md)。

### 访问地址

- 前端界面：http://localhost:5173（开发模式）
  - **Ink Lab 双壳**：默认进实验列表；`/experiments/:id` 为实验工作台；`/game/:id` 为全屏观战（GenericBoard）
- API 文档：http://localhost:8000/docs（Swagger UI）
- API 备选文档：http://localhost:8000/redoc（ReDoc）

### 配置实验参数

选手配置只保存在 **SQLite**，在前端「实验配置」页增删改。仓库没有 YAML seed：首次启动该表为空，必须先在 UI 里创建足够槽位的配置，才能新建实验。

### 配置 API Key

编辑项目根目录的 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 或 OpenAI / 本地 Ollama
OPENAI_API_KEY=sk-your-openai-key
OLLAMA_BASE_URL=http://localhost:11434
```

### 散局创建（可选）

「对局」页仍可创建不挂实验的散局（1–50 局批量），数据同样进入决策点与看板。挂实验请走实验详情采集，便于按实验过滤与对照。

### 观战

- **实时观察**：WebSocket 推送决策与思考链
- **牌桌**：GenericBoard 列表观战；结束后可逐步回放

### 配置实验参数示例

在「实验配置」页填写供应商与模型，例如：

| provider | model_name 示例 |
|----------|-----------------|
| `openai` | `gpt-4o-mini` |
| `deepseek` | `deepseek-v4-flash` |
| `ollama` | `qwen2.5:7b` |
| `dashscope` | `qwen-plus` |

采样用 `temperature`、`top_p`、`max_tokens`；实验意图写在 `notes`（如「高 temperature 对照」）。

## 项目文档

| 文档 | 说明 |
|------|------|
| [README.en.md](README.en.md) | English getting-started |
| [CLAUDE.md](CLAUDE.md) | Agent / 开发入口（英文，与代码同步） |
| [端到端闭环](docs/E2E_PIPELINE.md) | 1 小时采集→训练→部署指南与脚本 |
| [架构设计](docs/ARCHITECTURE.md) | 系统架构、分层设计、核心流程 |
| [目录结构](docs/PROJECT_STRUCTURE.md) | 目录规划与模块职责 |
| [编码规范](docs/CODING_STANDARDS.md) | Python / TypeScript / Vue 编码标准 |
| [API 设计](docs/API_DESIGN.md) | RESTful API + WebSocket 接口规范 |
| [开发示例](docs/EXAMPLES.md) | 新增引擎 / LLM 供应商 / 事件处理器 |

## 开发路线图

### 第一阶段：核心闭环
- [x] 项目骨架搭建（FastAPI + Vue 3）
- [x] 斗地主游戏引擎
- [x] 统一 LLM 客户端（OpenAI + Ollama + 8 家国产供应商）
- [x] 数据采集器（JSONL + SQLite）
- [x] 牌局观察界面（WebSocket 实时推送 + 回放）

### 第二阶段：数据与训练
- [x] 数据统计看板
- [x] 数据集筛选导出
- [x] 决策点 `train_usable` 过滤 + ChatML 导出（默认不含思考链）
- [x] 训练任务管理界面（PEFT LoRA / CPU 冒烟）
- [x] 模型仓库管理
- [x] 接入真实 SFT 训练（可选依赖组 `training`：Transformers + PEFT）
- [x] 模型导出部署包（merge + Modelfile + llama.cpp GGUF 脚本）+ Ollama 验证 / 测一局
- [x] 一键体验脚本串起采集→训练→部署提示（`scripts/e2e_pipeline.*`）

### 第三阶段：实验主线
- [x] 实验列表 / 详情工作台（采集、概要指标、详情内嵌决策/追踪、深链与上下文条）
- [x] 按实验过滤决策导出与「登记并开训」
- [x] 训练产物登记为 Ollama 选手 + 开对照实验
- [x] 工作台密度系统（KPI 条、紧凑列表、对比矩阵）+ 提示词 / 散局 / 选手配置对齐

> **说明**：决策点上的 `quality_score` 是**终局结果分**（胜 0.8 / 负 0.3 / 平 0.5），不是招法质量分。SFT 筛选以 `train_usable` 为准。实验详情可「登记并开训」；决策点页亦可登记。导出默认 `include_thinking=false`。
>
> **真实训练**：`cd server && poetry install --with training`。产物为 `models/<task_id>/adapter/` LoRA 权重。无 GPU 时自动限制步数与样本（CPU 冒烟）。
>
> **本地部署**：
> 1. 训练页对 LoRA 模型点「导出部署包」→ `models/<id>/deploy/`
> 2. 设置 `LLAMA_CPP_DIR` 后运行转换脚本得到 `model.gguf`
> 3. `ollama create <tag> -f Modelfile`（tag 与「登记为选手」约定一致，形如 `acgl-…`）
> 4. 「登记为选手」→ 实验详情「开对照实验」
>
> **脚本闭环**：见 [docs/E2E_PIPELINE.md](docs/E2E_PIPELINE.md)

### 第四阶段：扩展与优化（持续）
- [x] 实验间对比（`/experiments/compare` + `GET /api/v1/experiments/compare`）
- [x] 一键 merge→GGUF→`ollama create`（训练台「推送到 Ollama」，需 `LLAMA_CPP_DIR`）
- [ ] 新增游戏引擎（三国杀等）
- [ ] 强化训练能力（如 PPO 等）

## License

[MIT](LICENSE)
