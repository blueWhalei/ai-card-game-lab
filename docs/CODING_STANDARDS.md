# 编码规范

> 本文档是本项目的工程准则。凡属“规范性要求”，默认对**新增代码与本次修改范围内的代码**强制生效；对存量代码，按“发现即修、逐步收敛”的原则推进，不因历史原因降低标准。

## 1. Python 后端规范

### 1.1 语言与环境

| 项目 | 标准 |
|------|------|
| Python 版本 | 3.11+（使用 `X \| Y` 联合类型语法、`ExceptionGroup` 等新特性） |
| 依赖管理 | Poetry + `pyproject.toml` |
| 虚拟环境 | Poetry 自动管理，禁止全局安装 |

### 1.2 类型提示

**强制要求**：所有新增或修改的函数签名必须有完整类型注解；涉及本次改动的旧代码也应一并补齐。

```python
# 正确 ✓
def get_legal_actions(self, state: GameState, player_id: str) -> list[GameAction]:
    ...

# 正确 ✓ — 使用 Python 3.11+ 内置泛型语法
def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    ...

# 错误 ✗ — 缺少类型注解
def get_legal_actions(self, state, player_id):
    ...

# 错误 ✗ — 使用旧式 typing 导入（3.11+ 不需要）
from typing import List, Dict
def search(self, query: str) -> List[Dict[str, Any]]:
    ...
```

**类型提示要点**：
- 使用 `list[...]`, `dict[...]`, `tuple[...]` 等内置泛型，不再从 `typing` 导入
- 联合类型使用 `X | Y` 语法，不用 `Union[X, Y]`
- 可选参数使用 `X | None`，不用 `Optional[X]`
- 复杂类型使用 `TypeAlias` 或 `type` 语句定义别名
- 回调/函数类型使用 `Callable` 或 `Protocol`

### 1.3 代码格式化与检查

| 工具 | 用途 | 配置位置 |
|------|------|----------|
| **Ruff** | Linter + Formatter（替代 flake8 + black + isort） | `pyproject.toml` |
| **mypy** | 静态类型检查 | `pyproject.toml` |

**规范说明**：相关配置以仓库内实际 `pyproject.toml` 为准；下列片段用于说明目标标准与推荐配置方向。

**Ruff 核心配置**：

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

**mypy 核心配置**：

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 1.4 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `game_service.py`, `vector_store.py` |
| 类 | PascalCase | `GameEngine`, `JsonlWriter` |
| 函数/方法 | snake_case | `get_legal_actions()`, `apply_action()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TEMPERATURE` |
| 私有成员 | 单下划线前缀 | `self._engine`, `self._connections` |
| 受保护方法 | 单下划线前缀 | `def _validate_action()` |
| 类型别名 | PascalCase | `PlayerHand = list[str]` |

### 1.5 模块设计原则

**单一职责**：每个模块/类只负责一个明确的功能域。

```python
# 正确 ✓ — 各司其职
class DoudizhuEngine:    # 只负责游戏规则
    ...

class JsonlWriter:      # 只负责数据写入
    ...

class PromptBuilder:     # 只负责提示词构建
    ...

# 错误 ✗ — 上帝类，职责混杂
class GameManager:
    def play_card(self): ...
    def save_to_file(self): ...
    def call_llm(self): ...
    def build_prompt(self): ...
```

**依赖倒置**：高层模块不依赖低层实现，都依赖抽象接口。

```python
# 正确 ✓ — Service 依赖抽象
class GameService:
    def __init__(self, engine: GameEngine, repo: GameRepository) -> None:
        self._engine = engine   # 抽象基类
        self._repo = repo       # 抽象基类

# 错误 ✗ — Service 直接依赖具体实现
class GameService:
    def __init__(self) -> None:
        self._engine = DoudizhuEngine()  # 硬编码具体类
        self._db = sqlite3.connect("...")  # 直接操作数据库
```

**开闭原则**：对扩展开放，对修改关闭。

```python
# 正确 ✓ — 新增游戏只需注册，不修改已有代码
GameEngineRegistry.register(DoudizhuEngine())
GameEngineRegistry.register(SanguoshaEngine())  # 新增

# 错误 ✗ — 新增游戏需要修改 if-else 链
def create_engine(game_type: str):
    if game_type == "doudizhu":
        return DoudizhuEngine()
    elif game_type == "sanguosha":  # 每次新增都要改这里
        return SanguoshaEngine()
```

### 1.6 异步编程规范

- 所有新增或修改范围内的 I/O 操作（LLM 调用、文件读写、数据库操作）应优先使用 `async/await`
- CPU 密集型任务使用 `asyncio.to_thread()` 或 `ProcessPoolExecutor`
- 避免在 async 函数中调用同步阻塞操作

```python
# 正确 ✓
async def call_llm(self, messages: list[dict]) -> str:
    response = await self._client.chat.completions.create(
        model=self._model,
        messages=messages,
    )
    return response.choices[0].message.content

# 正确 ✓ — CPU 密集型任务放到线程池
async def train_model(self, config: TrainingConfig) -> str:
    result = await asyncio.to_thread(self._run_training, config)
    return result
```

### 1.7 错误处理规范

- 使用自定义异常体系，禁止裸 `except`
- 异常应携带足够的上下文信息
- API 层统一捕获并转换为标准错误响应
- 前端展示层应优先复用统一错误处理入口，避免在各页面散落重复错误提示逻辑

```python
# 正确 ✓
try:
    action = engine.parse_action(llm_output, legal_actions)
except InvalidActionError as e:
    logger.warning("LLM produced invalid action", error=str(e), player=player_id)
    action = legal_actions[0]  # fallback 到第一个合法动作

# 错误 ✗ — 裸 except，吞掉所有异常
try:
    action = engine.parse_action(llm_output, legal_actions)
except:
    action = legal_actions[0]
```

### 1.8 日志规范

使用 structlog 进行结构化日志记录：

```python
import structlog

logger = structlog.get_logger()

# 正确 ✓ — 结构化键值对
logger.info("game_created", game_id=game.id, game_type=game.game_type)
logger.warning("llm_parse_failed", raw_output=output[:200], player=player_id)

# 错误 ✗ — f-string 拼接
logger.info(f"Game {game.id} created with type {game.game_type}")
```

### 1.9 Docstring 规范

采用 Google 风格，仅在函数职责不明显时编写：

```python
class GameEngine(ABC):
    """卡牌游戏引擎抽象基类。

    所有具体游戏引擎必须继承此类并实现全部抽象方法。
    引擎实例应是无状态的 —— 游戏状态通过 GameState 对象传递。
    """

    @abstractmethod
    def parse_action(self, llm_output: str, legal_actions: list[GameAction]) -> GameAction:
        """解析 LLM 输出为合法游戏动作。

        Args:
            llm_output: LLM 返回的原始文本。
            legal_actions: 当前状态下的合法动作列表。

        Returns:
            匹配的合法动作。

        Raises:
            InvalidActionError: LLM 输出无法映射到任何合法动作。
        """
```

## 2. Vue / TypeScript 前端规范

### 2.1 TypeScript 配置

项目目标为严格 TypeScript。**新增代码与修改过的代码**禁止随意引入 `any`；存量代码若暂时无法一次性清理，应优先限制范围并在后续迭代中继续收敛。

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

**禁止使用 `any`**：新增代码与本次修改范围内的代码必须有明确类型；存量代码如暂时无法彻底清理，应避免扩散并持续收敛。

```typescript
// 正确 ✓
interface GameState {
  gameId: string
  gameType: string
  currentPlayer: string
  round: number
  isTerminal: boolean
}

function getGame(id: string): Promise<GameState> { ... }

// 错误 ✗
function getGame(id: any): any { ... }
```

### 2.2 Vue 组件规范

| 项目 | 标准 |
|------|------|
| 组件风格 | `<script setup lang="ts">` + Composition API |
| 模板顺序 | `<script>` → `<template>` → `<style>` |
| Props 定义 | `defineProps<{...}>()` 泛型语法 |
| Emits 定义 | `defineEmits<{...}>()` 泛型语法 |
| 样式作用域 | `<style scoped>` 或 Tailwind 行内 |

```vue
<script setup lang="ts">
interface Props {
  gameId: string
  isObserving?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isObserving: false,
})

const emit = defineEmits<{
  pause: []
  resume: []
}>()
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 模板内容 -->
  </div>
</template>
```

### 2.3 文件命名规范

| 类别 | 命名规范 | 示例 |
|------|----------|------|
| Vue 组件 | PascalCase | `GameObserver.vue`, `DataDashboard.vue` |
| Composable | camelCase + use 前缀 | `useGameState.ts`, `useWebSocket.ts` |
| Store | camelCase + use 前缀 | `useGameStore.ts`, `useDataStore.ts` |
| API 模块 | camelCase | `gameApi.ts`, `trainingApi.ts` |
| 类型定义 | camelCase + .types 后缀或 types/ 目录 | `game.types.ts` |
| 工具函数 | camelCase | `formatCard.ts`, `parseAction.ts` |

### 2.4 状态管理规范

Pinia Store 按功能域拆分，保持单一职责：

```typescript
// stores/useGameStore.ts
export const useGameStore = defineStore('game', () => {
  const currentGame = ref<GameState | null>(null)
  const games = ref<GameListItem[]>([])
  const isLoading = ref(false)

  async function fetchGames(): Promise<void> {
    isLoading.value = true
    try {
      games.value = await gameApi.listGames()
    } finally {
      isLoading.value = false
    }
  }

  return { currentGame, games, isLoading, fetchGames }
})
```

### 2.5 API 层封装规范

统一的 Axios 实例 + 类型化请求函数：

```typescript
// api/client.ts
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const apiError: ApiError = error.response?.data ?? {
      code: 'NETWORK_ERROR',
      message: error.message,
    }
    return Promise.reject(apiError)
  },
)

// api/gameApi.ts
import { apiClient } from './client'
import type { CreateGameRequest, GameResponse, GameListResponse } from './types'

export const gameApi = {
  list: () => apiClient.get<never, GameListResponse>('/api/v1/games'),
  create: (data: CreateGameRequest) => apiClient.post<never, GameResponse>('/api/v1/games', data),
  get: (id: string) => apiClient.get<never, GameResponse>(`/api/v1/games/${id}`),
}
```

### 2.6 Tailwind CSS 规范

- 优先使用 Tailwind 原子类，减少自定义 CSS
- 重复出现的样式组合通过 `@apply` 提取为组件类
- 颜色、间距等设计 Token 统一在 `tailwind.config.ts` 中定义
- Element Plus 组件的定制通过 CSS 变量覆盖，不修改 Tailwind 配置

```css
/* styles/components.css */
@layer components {
  .card-container {
    @apply rounded-lg border border-gray-200 bg-white p-4 shadow-sm;
  }

  .btn-primary {
    @apply rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700;
  }
}
```

## 3. 通用规范

### 3.1 Git 提交规范

采用 Conventional Commits：

```
<type>(<scope>): <subject>

feat(engine): implement doudizhu game rules
fix(ai): handle empty LLM response gracefully
refactor(service): extract game orchestration logic
docs(arch): update architecture decision records
chore(deps): upgrade FastAPI to 0.110
```

**类型列表**：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `refactor` | 重构（不改变功能） |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖 |
| `perf` | 性能优化 |

### 3.2 分支策略

| 分支 | 用途 |
|------|------|
| `master` | 稳定版本（`origin/HEAD`） |
| `develop` | 开发主线 |
| `feat/<name>` | 功能开发（仅在明确要求时新建） |
| `fix/<name>` | Bug 修复 |

### 3.3 禁止事项清单

- **禁止** 在代码中硬编码密钥、API Key、密码
- **禁止** 使用 `print()` 调试，必须使用 logger
- **禁止** 捕获异常后不处理（空 except 块）
- **禁止** 使用全局可变状态
- **禁止** 在 API 层编写业务逻辑
- **禁止** 跨层直接调用（如 API 层直接调用 Core 层，跳过 Service）
- **禁止** 在新增或修改的前端代码中引入 `any` 类型
- **禁止** 在新增 Vue 组件中使用 Options API
