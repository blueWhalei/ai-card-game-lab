# UI/UX 设计规格：Ink Lab 双壳 + 通用观战 + Headless

- 状态：已实现  
- 日期：2026-08-28  
- 产品：AI Card Game Lab  
- 前提：**按全新项目对待**，不考虑与旧 Apple/Element 界面的兼容或双轨开关
---

## 1. 背景与目标

### 1.1 产品定位（约束 UI）

- 独立开发者用的**开源工具链**：大模型采集 → 清洗 → SFT → 本地部署  
- 护城河是**全链路体验与数据管道**，不是单游戏精美客户端，也不是中后台管理系统  
- 观战是管道上的**通用可观测层**，不是每游戏一套 UI  

### 1.2 本规格要解决的问题

1. 顶栏 8 入口扁平、主线不清  
2. 视觉像通用 Apple/Element 后台，气质不符  
3. 观战与工作台共用同一套壳，两边都不够好  
4. 文档曾要求每游戏一个 Board，与「工具优先」冲突  

### 1.3 成功标准

- 新人 1 分钟内理解「实验室 / 管道 / 调参」  
- 任意遵守协议的引擎，**零前端改动**即可观战  
- 工作台**完全不像** Element/Ant 默认后台  
- 观战默认通用列表棋盘，无游戏专用桌面  

---

## 2. 产品 UX 原则

1. **管道优先**：界面服务「采集 → 数据 → 训练 → 部署」  
2. **观战 = 可观测**：调试 Prompt/解析、演示数据从哪来；非第二套游戏 UI  
3. **工具，非平台市场**：v1 不做插件商店、游戏注册中心 UI  
4. **双壳、一套语言**：Observer 沉浸；Workbench 密、快、可扫读  
5. **无兼容包袱**：旧顶栏、旧 GameTable、Element Plus 一律移除替换  

---

## 3. 信息架构

### 3.1 Workbench 导航（三组）

| 组 | 入口 | 路由（建议） |
|----|------|----------------|
| **实验室** | 对局、AI 角色 | `/game`、`/ai-players`；观战 `/game/:id` 用 Observer 壳 |
| **管道** | 总览、数据、决策点、训练 | `/` 或 `/pipeline`、`/data`、`/decisions`、`/training` |
| **调参** | 提示词、追踪、设置 | `/prompt`、`/traces`、`/settings` |

进站默认：**管道总览**（非对局列表）。

### 3.2 页面一句话 UX

| 页面 | UX |
|------|-----|
| 管道总览 | 四段状态：采集 / 数据 / 训练 / 部署 + 下一步 CTA + e2e 指引 |
| 对局 | 创建/批量为主；列表次要 |
| 观战 | 全屏；通用列表棋盘；默认「思考」Tab |
| AI 角色 | 配置表，强调 provider/model |
| 数据 | 指标 + 数据集；归档/存储为次级 Tab |
| 决策点 | `train_usable` 筛选与 ChatML 导出为一等操作 |
| 训练 | 任务流 + 模型；导出部署包 / 验证挂在模型上 |
| 提示词 / 追踪 | 高密度调参，少装饰 |
| 设置 | 系统信息与路径，非营销页 |

---

## 4. 双壳布局

### 4.1 Shell — Observer（全屏）

```
┌──────────────────────────────────────────────┐
│ ← 工作台   game_id   连接状态   回放/暂停     │
├────────────────────────────┬─────────────────┤
│ phase · round · table.slots│  动作 | 思考    │
│ GenericBoard（玩家行列表）  │  ThinkingPanel  │
└────────────────────────────┴─────────────────┘
```

- **无**工作台侧栏  
- **唯一**棋盘：`GenericBoard`（方案 A 列表式）  
- **不保留**斗地主三角精美桌面，不做布局切换  

### 4.2 Shell — Workbench

```
┌──────┬───────────────────────────────────────┐
│ Brand│  标题 + 一句管道语境                    │
│ 分组 │  主内容（表/图/表单，少装饰卡片）        │
│ 导航 │                                         │
└──────┴───────────────────────────────────────┘
```

- 桌面：左侧分组导航；窄屏：顶栏 + 抽屉  
- 卡片**仅**用于可交互块（任务卡、模型卡、表单分组）；禁止为「好看」堆白卡片  

### 4.3 工作台密度与字号（修订）

工作台是**工具**，不是博客。内容必须铺满主栏，字号必须可扫读。

| 项 | 规定 |
|----|------|
| 内容宽度 | `.page-container`：`w-full`，上限 `1680px`；**禁止** `max-w-6xl` / 整页 `mx-auto` 居中岛 |
| 根字号 | `html` = **16px**。禁止 14px root（会让 `text-sm` 变成约 12px） |
| 侧栏 | 宽 `256px`（`w-64`）；导航与品牌 **16px**；分组标签 14px |
| 正文 / 表格 / 按钮 | 16px 为默认；`text-sm`（14px）仅用于次级说明、徽章、表单 label |
| `text-xs`（12px） | 仅 ID、时间戳、代码路径等元数据；**不得**用于导航和卡片标题 |

超宽屏（主栏 > 1680px）时内容左对齐铺到上限，不把表格拉成报纸栏。

---

## 5. 通用观战协议

前端 **只消费** 下列快照（由 `get_public_info(..., is_observer=True)` 或等价适配层输出）。

```ts
type ObserverSnapshot = {
  game_type: string
  phase: string
  round: number
  current_player_id: string | null
  players: Array<{
    id: string
    name?: string
    role?: string
    is_active: boolean
    hand_count: number
    hand_cards?: string[]
    badges?: string[]
    last_action?: { type: string; cards?: string[]; label?: string }
  }>
  table?: {
    slots?: Array<{ key: string; label: string; cards?: string[] }>
  }
  extras?: Record<string, unknown> // 壳忽略；可选皮肤才读（v1 无皮肤）
}
```

现有 WS 事件类型可保留：`thinking` / `thinking_chunk` / `thinking_complete` / `action` / `state_update` / `game_ended`。  
`state_update` / `game_started` 的 `data` 必须可映射为 `ObserverSnapshot`。

### 5.1 接入新游戏（目标态）

1. 引擎实现 + Registry  
2. `get_public_info` 输出上述协议  
3. 可选：Prompt / Parser  

**禁止**要求新建 `XxxBoard.vue` 或修改 `GameObserverView` 业务分支。

### 5.2 GenericBoard（A）

每位玩家一行：名称 + badges · 手牌或「剩余 N」· 思考/行动态 · 最近动作。  
顶部：`phase` / `round` / `table.slots`。  
人数 2–N 均为纵向列表。

---

## 6. 视觉系统：Ink Lab

| Token | 意图 |
|-------|------|
| Workbench 背景 | 冷青石灰（非暖奶油纸、非 terracotta）；语义 token，可切 `data-theme` |
| Observer 背景 | 深炭/墨绿桌面感，高对比文字 |
| 主色 | 墨绿 / 青石（实验室信号）；**禁用** `#0071e3` 作为品牌主色 |
| 强调色 | 冷钢青：进行中 / 需注意（不用琥珀作品牌脸） |
| 字体 | 中文 Noto Sans SC（或等价）；西文 IBM Plex Sans / Source Sans 3；**禁用**以 Inter/SF Pro 为品牌脸 |
| 圆角 | 6–10px；少用全胶囊 pill 堆砌 |
| 阴影 | 单层轻阴影或分割线；禁止多层 glow / 霓虹 |

### 6.1 动效（至少 2–3 个有意动效）

1. 侧栏激活指示滑动  
2. 观战「思考中」行轻脉冲  
3. 管道总览阶段完成过渡  

---

## 7. 前端技术选型（定稿）

### 7.1 决定

| 项 | 决定 |
|----|------|
| Element Plus | **移除**，不再使用 |
| 中后台替代库（Ant / Naive 作整站） | **不采用**（仍偏后台脸） |
| 样式 | **Tailwind CSS v4** 为唯一样式主轴 |
| 交互零件 | **Headless**（Reka UI / Radix Vue 等）+ 项目自研样式，类 shadcn-vue 模式 |
| 观战 / 双壳 / 管道首页 | **纯自研** Vue SFC + Tailwind |
| 表格 | 自研简单表或 TanStack Table + 自研外观；按需加复杂度 |
| 图表 | 保留 ECharts / vue-echarts |
| 图标 | 单一图标方案（如 Iconify），风格统一 |

### 7.2 原则

- 摆脱的是「后台组件库脸」，不是「表单与表能力」  
- 差异化在 IA、双壳、通用观战、令牌；不在自造 Checkbox  
- 全库禁止 `import ... from 'element-plus'`（实现期清依赖）  

### 7.3 建议基础零件清单（Workbench）

Button、Input、Textarea、Select、Checkbox、Dialog、Dropdown、Toast、Tabs、简单 Table、Empty、Spinner。  
均以 headless + Ink Lab class 封装在 `web/src/components/ui/`。

---

## 8. 明确不做

- 每游戏精美牌桌 / Board 插件市场  
- 经典桌面与通用列表双轨切换  
- 整站深色（仅 Observer 壳深色）  
- 为兼容保留旧导航或 Element 主题层  
- 平台型：游戏商店、社区贡献中心 UI（v1）  

---

## 9. 实现顺序（设计之后）

1. Design tokens（CSS 变量）+ 移除 Element 依赖策略  
2. `components/ui/*` headless 基础零件  
3. Workbench 壳 + 分组导航 + 管道总览  
4. Observer 壳 + GenericBoard + 后端 ObserverSnapshot 适配  
5. 业务页迁入新壳（对局 → 数据/决策 → 训练 → 调参）  
6. 删除 `GameTable` 旧桌面、旧 `apple-*` 后台皮肤、更新 CLAUDE.md / 接入文档  

实现前另出 **implementation plan**（writing-plans），按上序拆 PR。

---

## 10. 文档影响

实现完成后需更新：

- `CLAUDE.md` / `docs/PROJECT_STRUCTURE.md`：删除「必做 Board」；改为 ObserverSnapshot + GenericBoard  
- `README.md`：补充 UI 为 Ink Lab 双壳说明（简短）  

---

## 11. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-28 | 初稿定稿：双壳 IA、通用列表观战、Ink Lab、Headless（无 Element） |
| 2026-08-28 | 实现完成：tokens + ui + 双壳 + ObserverSnapshot/GenericBoard + 卸 Element |
| 2026-08-28 | 工作台密度修订：取消 max-w-6xl 居中岛；根字号 16px；侧栏/正文加大一号 |
