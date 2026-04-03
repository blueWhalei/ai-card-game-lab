# AI Card Game Lab

AI 卡牌游戏实验室数据采集与训练平台 —— 面向 AI 研究的本地化工具，用于观察大模型决策过程、采集对局数据、蒸馏专用小模型。

## 核心能力

- **通用游戏引擎**：抽象卡牌游戏共性，支持快速接入新游戏（首发：斗地主）
- **实时思考链观察**：通过 WebSocket 实时推送 AI 决策的思考过程，含流式推理输出、Token 用量统计
- **数据采集闭环**：JSONL 全量归档 + SQLite 元数据索引，支持多维度筛选导出
- **数据看板**：Token 用量统计、对局质量分析、AI 表现对比、响应时间分析等多维度统计图表
- **模型蒸馏训练**：SFT 训练管线 + Mock 训练任务编排，逐步演进到真实训练能力

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端 | Vue 3 + TypeScript + Vite + Tailwind CSS + Element Plus |
| 后端 | Python 3.11+ / FastAPI + WebSocket |
| AI 调用 | OpenAI / Ollama / DashScope / DeepSeek / Kimi / ZhipuAI / Yi / Baichuan / MiniMax 统一适配 |
| 元数据库 | SQLite（索引/查询/统计） |
| 数据归档 | JSONL 本地文件 |
| 训练框架 | Mock 训练器（开发阶段），当前聚焦 SFT 流程，预留 PyTorch + Transformers 接口 |

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

### 访问地址

- 前端界面：http://localhost:5173（开发模式）
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
      model_name: "deepseek-reasoner"
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
      model_name: "deepseek-reasoner"
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
  model_name: "deepseek-chat"
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
- [x] 训练任务管理界面（Mock 训练器）
- [x] 模型仓库管理
- [ ] 接入真实 SFT 训练（PyTorch / Transformers）
- [ ] 模型部署为 AI 角色

### 第四阶段：扩展与优化（持续）
- [ ] 新增游戏引擎（三国杀等）
- [ ] 强化训练能力（如 PPO 等）
- [ ] A/B 测试与模型评估

## License

[MIT](LICENSE)
