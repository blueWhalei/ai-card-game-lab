# 设计规格：管道打磨 + CPU Smoke 真训 + 训练可视化

- 状态：已实现（2026-08-28，`feat/pipeline-polish-cpu-smoke` 已合并 develop）
- 日期：2026-08-28
- 产品：AI Card Game Lab
- 前置：Mock e2e 已通；本机无可用训练 GPU（i5-8400 / 32GB / GT 710 不可作现代 CUDA 训练）

---

## 1. 背景与目标

### 1.1 问题

- Mock 闭环可用，但「关 Mock」后的真实 LoRA 路径对独立开发者仍不友好：依赖、失败原因、导出限制说不清。
- 本机只有 CPU，真训若按默认大模型/多 epoch 跑，容易内存打满、系统卡死。
- 训练过程可视化偏弱：多为任务进度百分比，看不到机器是否在「安全区」。

### 1.2 目标

在本机把闭环打磨成：

**采集 → 导出 →（可选）CPU Smoke 真训（≤5 分钟）→ 部署包导出 → Ollama 验证入口可用且失败可诊断**

并在真训进行时提供**轻量、可读的机器状态可视化**（CPU / 内存 / 训练进度），不做成运维监控平台。

### 1.3 成功标准

| 项 | 标准 |
|----|------|
| Mock 演示 | 与现有 e2e 一致，默认路径不变 |
| CPU Smoke | 显式关 Mock 后 ≤5 分钟产出真实 LoRA adapter；浏览器仍可操作 |
| 安全 | 可用内存不足则拒绝开训；可取消；进程低优先级 |
| 导出 | Mock 导出给出明确原因；真训导出生成 `models/<id>/deploy/` |
| 验证 | 有 Ollama 则决策冒烟；无则可读提示，不假装成功 |
| 可视化 | 训练进行中可看到进度 + CPU% + 内存占用/可用，约 1–2s 刷新 |

---

## 2. 约束与非目标

### 2.1 硬件约束（本机）

- 真训走 **CPU**；不依赖 GT 710 / CUDA。
- 墙钟上限：**≤ 5 分钟**（Smoke，不为牌力）。

### 2.2 明确不做

- 本机追求可打牌的模型质量
- 完整 APM / 历史指标库 / Grafana 式监控
- GPU 利用率面板（无可用训练 GPU 时不假装有）
- 新游戏、精美牌桌、大规模 Prompt A/B UI

---

## 3. 产品行为

### 3.1 默认仍是 Mock

- `TRAINING_USE_MOCK=true` / 创建任务默认勾选 Mock。
- 管道总览「训练」段：Mock 完成也算「已就绪（演示）」；真 adapter 用不同徽标区分。

### 3.2 关 Mock → CPU Smoke 档

当用户取消「使用 Mock」时：

1. 检测 `training_deps_available()`；缺失则阻止提交，提示 `poetry install --with training`。
2. 检测 CUDA：无则进入 **CPU Smoke** 预设，并二次确认文案说明「仅冒烟、≤约 5 分钟、不为牌力」。
3. 应用硬上限（见 §4）；用户改大超限项时警告或钳制。
4. 启动前内存体检：可用物理内存 &lt; **8GB** → HTTP 友好错误，拒绝启动。

### 3.3 取消

- 训练任务支持取消；后端须能中断 CPU 训练循环（协作式 cancel flag / Trainer interrupt），避免「点了取消仍吃满内存」。

### 3.4 导出与验证

- Mock 产物：导出 API 返回明确错误（已有方向，统一文案）。
- 真 adapter：导出 `deploy/`（merged 视依赖与 merge 开关；至少 Modelfile + 脚本 + meta）。
- 验证：调用现有 verify；UI 展示成功/失败步骤清单。

---

## 4. CPU Smoke 硬预设

| 项 | 上限 / 默认 |
|----|-------------|
| 基座模型 | 默认 `Qwen/Qwen2.5-0.5B`；UI 可选列表仅含「CPU 安全」白名单 |
| `batch_size` | 1 |
| `max_steps` | ≤ 20（优先用 max_steps 掐死墙钟，而不是满 epoch） |
| `num_epochs` | 1（若仍设 epoch，以 max_steps 为准先停） |
| 样本数 | 截断最多 32 条 ChatML |
| 序列长度 | 短截断（实现时定具体 token 上限，目标降低内存） |
| 其它 | `gradient_checkpointing=true`；CPU；进程优先级低于正常 |

白名单外模型：允许填，但必须再次确认「可能导致卡顿/OOM」。

---

## 5. 训练可视化（轻量）

### 5.1 要解决的问题

用户关 Mock 后需要安全感：**机器忙到什么程度、还剩多少内存、训练是否在推进、能否取消。**

### 5.2 UI 位置

- **训练台**「训练任务」：运行中任务行或详情抽屉内展示「现场」面板。
- 不做独立「系统监控」导航页（v1）。

### 5.3 展示指标（v1）

| 指标 | 来源 | 刷新 |
|------|------|------|
| 任务 progress / step | 现有训练进度回调 | 随任务轮询（现有） |
| 进程 CPU% | 后端读训练相关进程或主机 CPU | 1–2s |
| 内存：已用 / 总计 / 可用 | 后端读主机内存 | 1–2s |
| 可选：本任务 RSS | 若能定位训练子进程则显示 | 1–2s |

**不做 v1：** GPU、磁盘 I/O 历史曲线、多机、告警订阅。

### 5.4 API（建议）

- `GET /api/v1/system/runtime-stats`  
  返回：`cpu_percent`, `memory_total_mb`, `memory_used_mb`, `memory_available_mb`, `training_active`（可选附带当前任务 id）。
- 前端仅在「存在 running/exporting/training 任务」或用户打开训练台时轮询，离开页面停止。

### 5.5 视觉

- 符合 Ink Lab：进度条 + 两枚简洁数字/条（CPU、内存），内存可用过低时用琥珀强调（非红闪霓虹）。
- 文案示例：「CPU 冒烟训练中 · 预计数分钟内结束 · 可取消」。

---

## 6. 管道总览对齐

- **训练**：区分 `mock_ready` / `lora_ready` / `running` / `blocked`（缺依赖）。
- **部署**：有真 adapter 时 CTA「导出部署包」；仅 Mock 时 CTA 解释需先 CPU Smoke 或有卡真训。
- 保留 e2e 脚本；增加文档说明 `smoke` / CPU 路径（具体子命令在实现计划里定）。

---

## 7. 技术方案要点

| 层 | 要点 |
|----|------|
| Core `sft.py` | CPU Smoke 钳制；`max_steps`；cancel；可选 `psutil` 或 stdlib 取内存（优先少依赖，不足再加） |
| Service | 开训前 `check_cpu_smoke_guards()`；导出/验证错误码稳定 |
| API | runtime-stats；训练创建校验 |
| Web | TrainingView 现场面板；创建任务确认对话框；PipelineView 状态文案 |
| 进程 | Windows 上降低训练线程/进程优先级，避免拖死交互 |

---

## 8. 验收清单

1. Mock `e2e all` 仍绿。  
2. 未装 training 依赖时关 Mock → 清晰阻断。  
3. 已装依赖 + 关 Mock + 确认 → ≤5min 出 adapter；期间页面可见 CPU/内存与进度；取消后 CPU/内存回落。  
4. 可用内存人为压到阈值下 → 拒绝开训。  
5. 真训模型可导出 deploy；Mock 导出失败文案正确。  
6. 无 Ollama 时验证失败可读。

---

## 9. 实现顺序（概要）

1. 安全护栏 + CPU Smoke 钳制 + 取消  
2. runtime-stats API + 训练台可视化  
3. 导出/验证/管道总览文案与状态  
4. 文档 + e2e/smoke 说明  
5. （可选）有 GPU 机器上的 `--no-mock` 文档路径，不阻塞本机验收  

详细任务拆解见后续 implementation plan。

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-28 | 初稿：CPU Smoke ≤5min、安全护栏、训练现场 CPU/内存可视化；用户确认方向 A（墙钟）与同意设计并追加可视化诉求 |
