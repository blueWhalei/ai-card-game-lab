# 端到端闭环指南（M4）

> 目标：熟悉开发者约 **1 小时内**从空仓库跑到「可训数据 + 训练任务 +（可选）本地模型验证」。  
> 产品价值在于完整的研究体验闭环，而不是胜率排行榜。

## 前置

| 项 | 说明 |
|----|------|
| Python 3.11+ / Poetry / Node 20.19+ 或 22.12+ | 必选 |
| `.env` | 从 `.env.example` 复制并填 API Key，或配 Ollama |
| 选手配置 | 在前端「选手配置」页创建至少 3 份选手（斗地主需要 3 个槽位）；无仓库级 YAML seed |
| 后端 | `scripts/start-backend.bat` / `./scripts/start-backend.sh`，或 `cd server && poetry run uvicorn ...` |

可选：

```bash
cd server && poetry install --with training   # PEFT LoRA（必选才能训练）
# 可选：4-bit QLoRA 需自行 pip install bitsandbytes（不要写进 poetry training extra）
```

## 一键脚本

在仓库根目录：

```powershell
# Windows
.\scripts\start-backend.bat       # 另开终端
.\scripts\start-frontend.bat      # 可选观战
.\scripts\e2e_pipeline.ps1 guide
.\scripts\e2e_pipeline.ps1 check
.\scripts\e2e_pipeline.ps1 all -Count 1          # 采集→导出→真训（需 training 依赖）
```

```bash
# macOS / Linux（首次需 chmod）
chmod +x scripts/*.sh
./scripts/start-backend.sh      # 另开终端
./scripts/start-frontend.sh     # 可选观战
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
| `train` | 建数据集 + 训练任务（PEFT LoRA / CPU 快速验证） |
| `deploy-hints` | 打印最新模型的 GGUF / Ollama 步骤 |
| `all` | check → collect → export → train → deploy-hints |

**推荐 UI 路径（实验详情页）：**

1. 首页 **实验** → 新建实验（按引擎槽位选选手配置 + 目标局数）→ 详情页「开始实验」
2. 可训决策就绪后，详情点 **开始训练**；或从更多菜单 / 侧栏「分析」进入 **决策点**（`?experiment_id=` 自动筛选）
3. 「训练」→ 模型仓库：**推送到 Ollama**（需 `.env` 中 `LLAMA_CPP_DIR` + 本机 Ollama；可选勾选同时登记）→ 或手跑「导出部署包」
4. 实验详情 **开始对照实验**（挑战选手 + 与引擎人数相同的基线）→ 继续对局；首页或详情进 **对比实验** 看胜率 CI

**脚本 / 决策点备用路径：**

1. 对局结束后，侧栏「分析」→「决策点」打开（默认已筛「可训练」；加 `experiment_id` 限定实验）
2. 点主按钮 **登记为训练数据集**（不是「仅导出文件」）
3. 「训练」页选用刚登记的 ChatML 数据集创建任务

「仅导出文件 / 导出 ChatML」只写磁盘 JSONL，**不会**自动出现在训练页。

## 人工观战（可选）

1. `scripts/start-frontend.bat` 或 `./scripts/start-frontend.sh` → http://localhost:5173  
2. 首页「加载演示对局」或从实验详情进入观战看思考链  
3. 侧栏「分析」→「决策点」或详情「开始训练」→ **登记为训练数据集**  
4. 「训练」模型仓库：**推送到 Ollama**（或导出部署包手转）→ 登记为选手 → 实验详情开始对照实验  

## 验收对照（v1.0）

| 环节 | 可验证输出 |
|------|------------|
| 采集 | JSONL + 决策点列表 |
| 观察 | Web 观战 / 回放 |
| 清洗导出 | ChatML（可关 thinking） |
| 训练 | LoRA adapter |
| 导出 / 推送 | `models/<id>/deploy/`；或一键 merge→GGUF→`ollama create` |
| 部署验证 | Ollama 决策快速验证 / 测一局 |

## 常见问题

- **`check` 失败**：先起后端；确认 `.env` 与端口 8000。  
- **`collect` 卡住**：看 API Key / Ollama；观战页是否报错。  
- **导出 count=0**：等对局 `completed`；确认决策点已写入。  
- **创建任务 400 / 训练依赖缺失**：`cd server && poetry install --with training`。  
- **验证找不到 tag**：训练页点「推送到 Ollama」（需 `LLAMA_CPP_DIR`），或手转 GGUF 再 `ollama create`。
- **推送报 DEPLOY_LLAMA_CPP_MISSING**：在 `.env` 设置 `LLAMA_CPP_DIR` 指向含 `convert_hf_to_gguf.py` 的 llama.cpp 目录。

## CPU 快速验证（无 GPU）

在无 CUDA 的本机上验证「真 LoRA → 导出」路径，**不为牌力**，墙钟目标 **≤ 5 分钟**。

### 准备

```bash
cd server && poetry install --with training
```

### 前端步骤

1. **训练** 页 → 创建任务（默认 `Qwen/Qwen2.5-0.5B`）
2. 若未装 training 依赖 → 页面阻断并提示 `poetry install --with training`
3. 确认对话框后开始；观察 **现场面板**（CPU / 内存 / 进度）；可随时 **取消**
4. 完成后 **模型仓库** → **推送到 Ollama**（`.env` 配 `LLAMA_CPP_DIR`）→ 可选同时登记 → 实验详情开始对照实验
5. **验证决策** 或 **测一局**

默认基座 `Qwen/Qwen2.5-0.5B`、`max_steps=20`，样本截断，避免 OOM。

**不建议**在无 GPU CI 中拉 HF 权重做全量 e2e。

## 基准测验（固定发牌）

创建实验时选择 **基准测验** 采集模式（`collect_mode: benchmark`）。系统从 `GET /api/v1/system/benchmark-seeds` 返回的 50 个固定发牌种子中按目标局数截取，采集时按局序使用同一 seed，不再随机发牌。

适用场景：两个或多个模型在相同牌面条件下对比胜率 / 延迟，无需搭建排行榜平台。实验详情会给出相对对照的 Δ 与是否可下结论，以及叫分 / 出牌 / 残局 / 炸弹子分；详情与对比页会显示「基准测验」徽章。
