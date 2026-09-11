# CardLab

[English](README.en.md) | 中文

本地 AI 卡牌研究工具：以「实验」为主线，提出假设、审查模型决策、比较对局结果并记录结论；LoRA 微调是可选的改进路径。

保存比较快照后，可引用具体决策并按版本记录观察、解释与局限，导出包含快照和所选证据的研究报告。原始决策变化或删除不会改写已保存证据。

> **关于模型**：本项目是**调用**第三方 LLM API（或本地 Ollama）进行卡牌决策，而非对任何大模型进行蒸馏或复制。LoRA 微调使用的是对局行为轨迹数据（用户自己的对局记录），不涉及将第三方 API 输出用于训练竞品模型。所有 API 调用均按各供应商服务条款合规使用。项目本身**不内置任何模型权重**，用户自行配置 API Key 或本地模型。

## 技术栈

| 层级 | 选型 |
|------|------|
| 前端 | Vue 3 · TypeScript · Vite · Tailwind v4 · Reka UI |
| 后端 | Python 3.11+ · FastAPI · WebSocket |
| LLM | OpenAI · Ollama · DashScope · DeepSeek · Kimi · Zhipu · Yi · Baichuan · MiniMax |
| 存储 | SQLite 索引 + JSONL 归档 |
| 训练 | PEFT LoRA（`poetry install --with training`；无 GPU 走 CPU 快速验证；可选 4-bit QLoRA 需自行安装 bitsandbytes） |

## 快速开始

**环境**：Python 3.11+ · Node 20.19+ / 22.12+ · Poetry ·（可选）Ollama

```bash
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab
cp .env.example .env    # Windows: copy .env.example .env
```

两个终端分别启动：

| 平台 | 后端（:8000） | 前端（:5173） |
|------|---------------|---------------|
| Windows | `scripts\start-backend.bat` | `scripts\start-frontend.bat` |
| macOS / Linux | `chmod +x scripts/*.sh` 后 `./scripts/start-backend.sh` | `./scripts/start-frontend.sh` |

也可手动：`cd server && poetry install && poetry run uvicorn ...` · `cd web && npm install && npm run dev`。

打开 http://localhost:5173 。首页会按「密钥 → 选手 → 实验」引导到第一局。首次请在「选手配置」页创建选手（斗地主需 3 个），`.env` 至少配置一个 API 密钥或本机 Ollama。无密钥可首页「加载演示实验」——会写入主实验 + 对照并直接进入 **verdict** 阶段。仓库 [`examples/`](examples/) 提供可导入的实验包（基线对比、Prompt A/B 骨架、微调前基线）。

## 主路径

1. **配置选手** — 选择模型、策略与采样参数。
2. **设计实验** — 选择选手，记录研究假设与判断标准。创建不会自动开局。
3. **运行与审查** — 观战、回放，审查全部决策，包括失败和不符合训练格式要求的记录。“可训练”仅表示结构有效，不代表决策质量。
4. **比较结果** — 比较已有实验，或用已有选手与源实验发牌种子创建对照；解读结果前核对协议差异和有效样本量。
5. **记录结论** — 在详情记录工作笔记；保存比较快照后，在「结论与证据」中引用决策、追加结论版本并导出研究报告。

**可选训练：** 从「分析 → 训练」进入数据集登记、微调与选手注册。审查、比较和创建对照均不要求先训练。通过 `?collect=1` 打开对照只显示开始确认，明确提交后才会运行对局。

比较页现可审查冻结协议差异与共同有效种子，重复运行产生的歧义会被排除并列出。声明允许变化的 Solver 字段后重新比较，可保存具名快照，之后重开或导出冻结结果。当前声明属于事后审查；研究报告可附所选证据，完整可运行复现包仍待实现。

基准测试模式使用固定发牌种子（最多 50 局）；详情页阶段下方给出**本实验**的指标（地主胜率、解析、可训练、延迟、每局 Token）。试玩对局在侧栏 `/game`，不计入实验。决策点、追踪、数据、训练在侧栏「分析」（`/pipeline/…`，支持 `?experiment_id=`）。实验详情可导出 JSON 实验包（包内不含 API 密钥），首页可导入以在另一台机器复现。使用说明：顶栏书本图标 `/guide`。

脚本闭环：`.\scripts\e2e_pipeline.ps1 all -Count 1` — 详见 [E2E 指南](docs/E2E_PIPELINE.md)。

## 界面

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/zh/experiment-configs.png" alt="选手配置：模型、采样与胜率">
      <p><strong>选手配置</strong> — 为每个座位指定模型与采样；可导入 / 导出选手包，包内不含 API 密钥。</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/zh/games.png" alt="试玩对局列表">
      <p><strong>试玩对局</strong> — 不计入实验的单局；也可加载演示对局先看观战。</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/zh/data.png" alt="分析 · 数据总览：对局、轮次、Token 与阵营胜负">
      <p><strong>分析 · 数据</strong> — 语料规模、完成情况、地主 / 农民胜负分布。</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/zh/decisions.png" alt="分析 · 决策点：手牌、合法行动与思考">
      <p><strong>分析 · 决策点</strong> — 每步状态、合法行动、思考与是否可训练；可导出 ChatML。</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/zh/training.png" alt="分析 · 训练任务列表">
      <p><strong>分析 · 训练</strong> — PEFT LoRA 任务与模型仓库；完成后可登记为选手。</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/zh/traces.png" alt="分析 · 追踪：解析成功率与模型思考">
      <p><strong>分析 · 追踪</strong> — 延迟、解析成功率、工具调用与原始 JSON。</p>
    </td>
  </tr>
</table>

## 配置

`.env` 示例（项目根目录）：

```bash
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# 或 OPENAI_API_KEY / OLLAMA_BASE_URL=http://localhost:11434
```

| provider | model 示例 |
|----------|-------------|
| `openai` | `gpt-4o-mini` |
| `deepseek` | `deepseek-v4-flash` |
| `ollama` | `qwen2.5:7b` |
| `dashscope` | `qwen-plus` |

## 链接

| 地址 | 说明 |
|------|------|
| https://blueWhalei.github.io/ai-card-game-lab/ | 项目页 |
| http://localhost:5173 | 前端 |
| http://localhost:8000/docs | API 文档 |
| http://localhost:8000/api/v1/system/preflight | 开始前检查 |

## 文档

| 文档 | 说明 |
|------|------|
| [E2E 闭环](docs/E2E_PIPELINE.md) | 采集 → 训练 → 部署 |
| [架构](docs/ARCHITECTURE.md) | 分层与核心流程 |
| [API](docs/API_DESIGN.md) | REST + WebSocket |
| [目录结构](docs/PROJECT_STRUCTURE.md) | 模块地图 |
| [编码规范](docs/CODING_STANDARDS.md) | Python / Vue / i18n |
| [开发示例](docs/EXAMPLES.md) | 新引擎 / 供应商 |
| [CLAUDE.md](CLAUDE.md) | Agent 开发入口 |

## License

[MIT](LICENSE)
