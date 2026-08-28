# 端到端闭环指南（M4）

> 目标：熟悉开发者约 **1 小时内**从空仓库跑到「可训数据 + 训练任务 +（可选）本地模型验证」。  
> 护城河是体验，不是胜率。

## 前置

| 项 | 说明 |
|----|------|
| Python 3.11+ / Poetry / Node 18+ | 必选 |
| `.env` | 从 `.env.example` 复制并填 API Key，或配 Ollama |
| `config/ai_players.yaml` | 默认三名玩家可用 |
| 后端 | `start-backend.bat` 或 `cd server && poetry run uvicorn ...` |

可选：

```bash
cd server && poetry install --with training   # 真实 LoRA
# .env
TRAINING_USE_MOCK=false
```

## 一键脚本

在仓库根目录：

```powershell
# Windows
.\scripts\e2e_pipeline.ps1 guide
.\scripts\e2e_pipeline.ps1 check
.\scripts\e2e_pipeline.ps1 all -Count 1          # Mock 训练
.\scripts\e2e_pipeline.ps1 all -Count 1 -NoMock  # 需 training 依赖
```

```bash
# macOS / Linux
chmod +x scripts/e2e_pipeline.sh
./scripts/e2e_pipeline.sh guide
./scripts/e2e_pipeline.sh check
./scripts/e2e_pipeline.sh all --count 1
```

或直接：

```bash
cd server
poetry run python scripts/e2e_pipeline.py guide
poetry run python scripts/e2e_pipeline.py all --count 1 --mock
```

### 子命令

| 命令 | 作用 |
|------|------|
| `guide` | 打印清单（不调 API） |
| `check` | 健康检查 + AI 玩家是否齐全 |
| `collect` | 批量开斗地主并等待结束 |
| `export` | 导出 `train_usable` 决策点 ChatML（默认不含思考） |
| `train` | 建数据集 + 训练任务（默认 Mock） |
| `deploy-hints` | 打印最新模型的 GGUF / Ollama 步骤 |
| `all` | check → collect → export → train → deploy-hints |

## 人工观战（可选）

1. `start-frontend.bat` → http://localhost:5173  
2. 「对局」创建 / 进入观战页看思考链  
3. 「决策点」导出（勾选「仅可训练样本」）  
4. 「训练」创建任务 → 「模型仓库」导出部署包 → 验证 / 测一局  

## 验收对照（v1.0）

| 环节 | 可验证输出 |
|------|------------|
| 采集 | JSONL + 决策点列表 |
| 观察 | Web 观战 / 回放 |
| 清洗导出 | ChatML（可关 thinking） |
| 训练 | Mock 或 LoRA adapter |
| 导出 | `models/<id>/deploy/` + GGUF 脚本 |
| 部署验证 | Ollama 决策冒烟 / 测一局 |

## 常见问题

- **`check` 失败**：先起后端；确认 `.env` 与端口 8000。  
- **`collect` 卡住**：看 API Key / Ollama；观战页是否报错。  
- **导出 count=0**：等对局 `completed`；确认决策点已写入。  
- **Mock 无法「导出部署包」**：需 `use_mock=false` 的真实 LoRA。  
- **验证找不到 tag**：先转 GGUF 再 `ollama create`。
