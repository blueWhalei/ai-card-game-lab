# 端到端闭环指南（M4）

> 目标：熟悉开发者约 **1 小时内**从空仓库跑到「可训数据 + 训练任务 +（可选）本地模型验证」。  
> 护城河是体验，不是胜率。

## 前置

| 项 | 说明 |
|----|------|
| Python 3.11+ / Poetry / Node 20.19+ 或 22.12+ | 必选 |
| `.env` | 从 `.env.example` 复制并填 API Key，或配 Ollama |
| `config/experiment_configs.yaml` | 仅 **seed**：首次启动写入 SQLite；运行时在「实验配置」页维护 |
| 后端 | `start-backend.bat` 或 `cd server && poetry run uvicorn ...` |

可选：

```bash
cd server && poetry install --with training   # PEFT LoRA（必选才能训练）
```

## 一键脚本

在仓库根目录：

```powershell
# Windows
.\scripts\e2e_pipeline.ps1 guide
.\scripts\e2e_pipeline.ps1 check
.\scripts\e2e_pipeline.ps1 all -Count 1          # 采集→导出→真训（需 training 依赖）
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
poetry run python scripts/e2e_pipeline.py all --count 1
```

### 子命令

| 命令 | 作用 |
|------|------|
| `guide` | 打印清单（不调 API） |
| `check` | 健康检查 + AI 玩家是否齐全 |
| `collect` | 批量开斗地主并等待结束 |
| `export` | 导出 `train_usable` 决策点 ChatML（默认不含思考） |
| `train` | 建数据集 + 训练任务（PEFT LoRA / CPU 冒烟） |
| `deploy-hints` | 打印最新模型的 GGUF / Ollama 步骤 |
| `all` | check → collect → export → train → deploy-hints |

**推荐 UI 路径（实验工作台）：**

1. 首页 **实验** → 新建实验（按引擎槽位选配置 + 目标局数）→ 详情「开始采集」
2. 可训决策就绪后，详情点 **登记并开训**（或到「决策点」带 `?experiment_id=` 登记）
3. 「训练」→ 模型仓库：**推送到 Ollama**（需 `.env` 中 `LLAMA_CPP_DIR` + 本机 Ollama；可选勾选同时登记）→ 或手跑「导出部署包」
4. 实验详情 **开对照实验**（新选手 + 与引擎人数相同的基线）→ 继续采集；首页或详情进 **对比实验** 看胜率 CI

**脚本 / 决策点备用路径：**

1. 对局结束后打开「决策点」（默认已筛「可训练」；可加 `experiment_id`）
2. 点主按钮 **登记为训练数据集**（不是「仅导出文件」）
3. 「训练」页选用刚登记的 ChatML 数据集创建任务

「仅导出文件 / 导出 ChatML」只写磁盘 JSONL，**不会**自动出现在训练台。

## 人工观战（可选）

1. `start-frontend.bat` → http://localhost:5173  
2. 首页「加载演示对局」或从实验详情进入观战看思考链  
3. 「决策点」→ **登记为训练数据集**（或实验详情「登记并开训」）  
4. 「训练」模型仓库：**推送到 Ollama**（或导出部署包手转）→ 登记为选手 → 实验详情开对照  

## 验收对照（v1.0）

| 环节 | 可验证输出 |
|------|------------|
| 采集 | JSONL + 决策点列表 |
| 观察 | Web 观战 / 回放 |
| 清洗导出 | ChatML（可关 thinking） |
| 训练 | LoRA adapter |
| 导出 / 推送 | `models/<id>/deploy/`；或一键 merge→GGUF→`ollama create` |
| 部署验证 | Ollama 决策冒烟 / 测一局 |

## 常见问题

- **`check` 失败**：先起后端；确认 `.env` 与端口 8000。  
- **`collect` 卡住**：看 API Key / Ollama；观战页是否报错。  
- **导出 count=0**：等对局 `completed`；确认决策点已写入。  
- **创建任务 400 / 训练依赖缺失**：`cd server && poetry install --with training`。  
- **验证找不到 tag**：训练台点「推送到 Ollama」（需 `LLAMA_CPP_DIR`），或手转 GGUF 再 `ollama create`。
- **推送报 DEPLOY_LLAMA_CPP_MISSING**：在 `.env` 设置 `LLAMA_CPP_DIR` 指向含 `convert_hf_to_gguf.py` 的 llama.cpp 目录。

## CPU Smoke（无 GPU）

在无 CUDA 的本机上验证「真 LoRA → 导出」路径，**不为牌力**，墙钟目标 **≤ 5 分钟**。

### 准备

```bash
cd server && poetry install --with training
```

### 前端步骤

1. **训练台** → 创建任务（默认 `Qwen/Qwen2.5-0.5B`）
2. 若未装 training 依赖 → 页面阻断并提示 `poetry install --with training`
3. 确认对话框后开始；观察 **现场面板**（CPU / 内存 / 进度）；可随时 **取消**
4. 完成后 **模型仓库** → **推送到 Ollama**（`.env` 配 `LLAMA_CPP_DIR`）→ 可选同时登记 → 实验详情开对照
5. **验证决策** 或 **测一局**

默认基座 `Qwen/Qwen2.5-0.5B`、`max_steps=20`，样本截断，避免 OOM。

**不建议**在无 GPU CI 中拉 HF 权重做全量 e2e。
