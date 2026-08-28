# AI Card Game Lab

AI 卡牌游戏实验室数据采集与训练平台 —— 面向 AI 研究的本地化工具，用于观察大模型决策过程、采集对局数据、蒸馏专用小模型。

## 核心能力

- **通用游戏引擎**：抽象卡牌游戏共性，支持快速接入新游戏（首发：斗地主）
- **实时思考链观察**：通过 WebSocket 实时推送 AI 决策的思考过程，含流式推理输出、Token 用量统计
- **数据采集闭环**：JSONL 全量归档 + SQLite 元数据索引，支持多维度筛选导出
- **数据看板**：Token 用量统计、对局质量分析、AI 表现对比、响应时间分析等多维度统计图表
- **模型蒸馏训练**：可选 PEFT LoRA + Mock；一键脚本串起采集→导出→训练→部署提示

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端 | Vue 3 + TypeScript + Vite + Tailwind CSS v4 + Reka UI（Ink Lab 双壳） |
| 后端 | Python 3.11+ / FastAPI + WebSocket |
| AI 调用 | OpenAI / Ollama / DashScope / DeepSeek / Kimi / ZhipuAI / Yi / Baichuan / MiniMax 统一适配 |
| 元数据库 | SQLite（索引/查询/统计） |
| 数据归档 | JSONL 本地文件 |
| 训练框架 | Mock 默认可用；可选 `poetry install --with training` 启用 PEFT LoRA（Transformers） |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Poetry（Python 依赖管理）
- 可选：Ollama（本地大模型推理）

### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab

# 2. 复制环境变量配置
cp .env.example .env
# 编辑 .env 填入你的 API Key

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

### 一小时闭环（推荐）

后端起来后，在仓库根目录：

```powershell
.\scripts\e2e_pipeline.ps1 guide          # 打印清单
.\scripts\e2e_pipeline.ps1 check          # 健康检查
.\scripts\e2e_pipeline.ps1 all -Count 1   # 采集→导出→Mock 训练
```

完整说明见 [端到端闭环指南](docs/E2E_PIPELINE.md)。

### 访问地址

- 前端界面：http://localhost:5173（开发模式）
  - **Ink Lab 双壳**：默认进管道总览；`/game/:id` 为全屏观战（GenericBoard），无工作台侧栏
- API 文档：http://localhost:8000/docs（Swagger UI）
- API 备选文档：http://localhost:8000/redoc（ReDoc）

### 创建第一个 AI 对局

#### 步骤 1：配置 AI 玩家

编辑 `config/ai_players.yaml` 文件，定义 AI 玩家的决策风格：

```yaml
players:
  - id: "aggressive_tiger"
    name: "激进虎"
    description: "偏好主动出击，率先出牌，追求速赢"
    avatar: "🐯"
    model_config:
      provider: "deepseek"           # LLM 供应商
      model_name: "deepseek-v4-flash"
      temperature: 0.9               # 高温度 = 更随机
      top_p: 0.95
      max_tokens: 1024
    game_configs:
      doudizhu:
        style: "aggressive"          # 游戏风格
        bid_threshold: 0.4           # 叫地主阈值
        risk_tolerance: 0.8          # 风险承受度

  - id: "cautious_fox"
    name: "谨慎狐"
    description: "保守出牌，观察对手策略后再做决定"
    avatar: "🦊"
    model_config:
      provider: "deepseek"
      model_name: "deepseek-v4-flash"
      temperature: 0.6               # 低温度 = 更保守
      top_p: 0.9
      max_tokens: 1024
    game_configs:
      doudizhu:
        style: "cautious"
        bid_threshold: 0.7
        risk_tolerance: 0.3
```

#### 步骤 2：配置 API Key

编辑项目根目录的 `.env` 文件，填入你的 LLM API Key：

```bash
# DeepSeek（推荐，性价比高）
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 或使用 OpenAI
OPENAI_API_KEY=sk-your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1

# 或使用本地 Ollama
OLLAMA_BASE_URL=http://localhost:11434
```

#### 步骤 3：创建对局

1. 打开前端界面 http://localhost:5173
2. 进入「对局」页面
3. 点击「创建对局」按钮
4. 选择游戏类型：斗地主
5. 选择 3 个 AI 玩家（如：激进虎、谨慎狐、随机熊猫）
6. 点击「开始」

#### 步骤 4：观战对局

创建对局后，系统自动跳转到观战页面：

- **实时观察**：通过 WebSocket 实时推送 AI 决策过程
- **思考链展示**：查看 AI 的完整推理过程，含每轮 Token 用量统计
- **牌桌可视化**：直观展示手牌、出牌历史、角色手牌（观察者模式透明）
- **回放功能**：对局结束后可逐步回放

#### 步骤 5：批量创建对局

用于数据采集场景：

1. 在创建对局时设置「批量数量」（1-50 局）
2. 系统自动依次执行所有对局
3. 对局数据自动保存到 `data/games/` 目录
4. 可在「数据」页面查看统计和导出数据集

### 配置 AI 玩家示例

#### 使用不同 LLM 供应商

```yaml
# OpenAI GPT-4
model_config:
  provider: "openai"
  model_name: "gpt-4o-mini"
  temperature: 0.8

# DeepSeek（推荐）
model_config:
  provider: "deepseek"
  model_name: "deepseek-v4-flash"
  temperature: 0.7

# 本地 Ollama
model_config:
  provider: "ollama"
  model_name: "qwen2.5:7b"
  temperature: 0.8

# 阿里通义千问
model_config:
  provider: "dashscope"
  model_name: "qwen-plus"
  temperature: 0.7
```

#### 调整决策风格

```yaml
game_configs:
  doudizhu:
    style: "aggressive"      # aggressive | cautious | random
    bid_threshold: 0.5       # 叫地主阈值 (0-1)
    risk_tolerance: 0.6      # 风险承受度 (0-1)
```

## 项目文档

| 文档 | 说明 |
|------|------|
| [端到端闭环](docs/E2E_PIPELINE.md) | 1 小时采集→训练→部署指南与脚本 |
| [架构设计](docs/ARCHITECTURE.md) | 系统架构、分层设计、核心流程 |
| [目录结构](docs/PROJECT_STRUCTURE.md) | 目录规划与模块职责 |
| [编码规范](docs/CODING_STANDARDS.md) | Python / TypeScript / Vue 编码标准 |
| [API 设计](docs/API_DESIGN.md) | RESTful API + WebSocket 接口规范 |
| [详细设计说明书](AI卡牌游戏实验室%20-%20详细设计说明书.md) | 完整的功能设计文档 |

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
- [x] 训练任务管理界面（Mock 默认 + 可选 PEFT LoRA）
- [x] 模型仓库管理
- [x] 接入真实 SFT 训练（可选依赖组 `training`：Transformers + PEFT）
- [x] 模型导出部署包（merge + Modelfile + llama.cpp GGUF 脚本）+ Ollama 验证 / 测一局
- [x] 一键体验脚本串起采集→训练→部署提示（`scripts/e2e_pipeline.*`）

> **说明**：决策点上的 `quality_score` 仅为终局胜负代理（胜 0.8 / 负 0.3 / 平 0.5），**不是**推理质量分。SFT 样本筛选以 `train_usable` 为准；导出默认 `include_thinking=false`，避免伪思考链污染训练集。
>
> **真实训练**：`cd server && poetry install --with training`，设置 `TRAINING_USE_MOCK=false`（或创建任务时取消「使用 Mock」）。产物为 `models/<task_id>/adapter/` LoRA 权重。
>
> **本地部署（M3）**：
> 1. 训练页对 LoRA 模型点「导出部署包」→ `models/<id>/deploy/`（含 `merged/`、`Modelfile`、`convert_gguf.ps1`）
> 2. 设置 `LLAMA_CPP_DIR` 后运行转换脚本得到 `model.gguf`
> 3. `ollama create <tag> -f Modelfile`
> 4. 点「验证决策」或「测一局」
>
> **一键闭环（M4）**：见 [docs/E2E_PIPELINE.md](docs/E2E_PIPELINE.md)，`.\scripts\e2e_pipeline.ps1 all -Count 1`

### 第四阶段：扩展与优化（持续）
- [ ] 新增游戏引擎（三国杀等）
- [ ] 强化训练能力（如 PPO 等）
- [ ] A/B 测试与模型评估

## License

[MIT](LICENSE)
