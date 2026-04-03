# 开发示例文档

本文档提供常见开发场景的完整代码示例，帮助开发者快速扩展系统功能。

## 目录

1. [如何添加新游戏引擎](#1-如何添加新游戏引擎)
2. [如何添加新 LLM 供应商](#2-如何添加新-llm-供应商)
3. [如何创建自定义事件处理器](#3-如何创建自定义事件处理器)

---

## 1. 如何添加新游戏引擎

本示例演示如何添加一个简单的"猜数字"游戏引擎。

### 1.1 创建游戏引擎目录

```bash
mkdir -p server/app/core/engine/guess_number
```

### 1.2 实现游戏状态类

创建 `server/app/core/engine/guess_number/__init__.py`：

```python
"""猜数字游戏引擎"""

from app.core.engine.guess_number.engine import GuessNumberEngine
from app.core.engine.guess_number.state import GuessNumberState

__all__ = ["GuessNumberEngine", "GuessNumberState"]
```

创建 `server/app/core/engine/guess_number/state.py`：

```python
from dataclasses import dataclass, field
from typing import Any

from app.core.engine.base import GameState


@dataclass
class GuessNumberState(GameState):
    """猜数字游戏状态"""

    game_type: str = "guess_number"
    target_number: int = 0
    guesses: list[dict[str, Any]] = field(default_factory=list)
    current_range: tuple[int, int] = (1, 100)
    max_attempts: int = 10
```

### 1.3 实现游戏引擎

创建 `server/app/core/engine/guess_number/engine.py`：

```python
import random
import re
from typing import Any

from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.engine.guess_number.state import GuessNumberState
from app.utils.exceptions import InvalidActionError


class GuessNumberEngine(GameEngine):
    """猜数字游戏引擎"""

    @property
    def game_type(self) -> str:
        return "guess_number"

    def initialize(self, player_ids: list[str], **params: Any) -> GameState:
        target = random.randint(1, 100)
        return GuessNumberState(
            game_type="guess_number",
            round=1,
            player_ids=player_ids,
            current_player=player_ids[0],
            is_terminal=False,
            target_number=target,
            guesses=[],
            current_range=(1, 100),
            max_attempts=params.get("max_attempts", 10),
        )

    def get_legal_actions(self, state: GuessNumberState, player_id: str) -> list[GameAction]:
        if state.is_terminal or player_id != state.current_player:
            return []
        return [GameAction(player_id=player_id, action_type="guess")]

    def apply_action(self, state: GuessNumberState, action: GameAction) -> GameState:
        if action.action_type != "guess":
            raise InvalidActionError(action.action_type, "只能执行 guess 动作")

        guess = action.target
        if guess is None:
            raise InvalidActionError(action.action_type, "必须指定猜测的数字")

        new_guesses = state.guesses.copy()
        new_guesses.append({
            "player": action.player_id,
            "guess": guess,
            "result": "correct" if guess == state.target_number
            else "higher" if guess < state.target_number
            else "lower",
        })

        is_correct = guess == state.target_number
        is_over = is_correct or len(new_guesses) >= state.max_attempts

        new_range = state.current_range
        if not is_correct:
            if guess < state.target_number:
                new_range = (max(state.current_range[0], guess + 1), state.current_range[1])
            else:
                new_range = (state.current_range[0], min(state.current_range[1], guess - 1))

        next_player_idx = (state.player_ids.index(state.current_player) + 1) % len(state.player_ids)

        return GuessNumberState(
            game_type=state.game_type,
            round=state.round + 1,
            player_ids=state.player_ids,
            current_player=state.player_ids[next_player_idx] if not is_over else state.current_player,
            is_terminal=is_over,
            winner=action.player_id if is_correct else None,
            target_number=state.target_number,
            guesses=new_guesses,
            current_range=new_range,
            max_attempts=state.max_attempts,
        )

    def is_terminal(self, state: GameState) -> bool:
        return state.is_terminal

    def get_winner(self, state: GameState) -> str | None:
        return state.winner

    def get_current_player(self, state: GameState) -> str:
        return state.current_player

    def format_for_prompt(self, state: GuessNumberState, player_id: str) -> str:
        return f"""你正在玩猜数字游戏。

当前范围: {state.current_range[0]} - {state.current_range[1]}
剩余尝试次数: {state.max_attempts - len(state.guesses)}

历史猜测:
{self._format_guesses(state.guesses)}

请猜一个 {state.current_range[0]} 到 {state.current_range[1]} 之间的数字。
回复格式: 我猜 XX"""

    def _format_guesses(self, guesses: list[dict[str, Any]]) -> str:
        if not guesses:
            return "暂无"
        lines = []
        for g in guesses:
            lines.append(f"  - {g['player']}: {g['guess']} ({g['result']})")
        return "\n".join(lines)

    def parse_action(self, llm_output: str, legal_actions: list[GameAction]) -> GameAction:
        match = re.search(r"(\d+)", llm_output)
        if not match:
            raise InvalidActionError("parse", f"无法从输出中解析数字: {llm_output}")

        guess = int(match.group(1))
        if legal_actions:
            return GameAction(
                player_id=legal_actions[0].player_id,
                action_type="guess",
                target=guess,
            )
        raise InvalidActionError("parse", "没有合法动作")

    def get_public_info(self, state: GuessNumberState, viewer_id: str) -> dict[str, Any]:
        return {
            "game_type": state.game_type,
            "round": state.round,
            "current_player": state.current_player,
            "current_range": state.current_range,
            "guesses": state.guesses,
            "remaining_attempts": state.max_attempts - len(state.guesses),
            "is_terminal": state.is_terminal,
            "winner": state.winner,
        }
```

### 1.4 注册游戏引擎

修改 `server/app/dependencies.py`：

```python
from app.core.engine.guess_number import GuessNumberEngine

@lru_cache
def get_engine_registry() -> GameEngineRegistry:
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    registry.register(GuessNumberEngine())  # 添加新引擎
    return registry
```

### 1.5 创建前端牌桌组件

创建 `web/src/components/game/boards/GuessNumberBoard.vue`：

```vue
<template>
  <div class="guess-number-board">
    <div class="range-display">
      当前范围: {{ gameState.current_range[0] }} - {{ gameState.current_range[1] }}
    </div>
    <div class="guesses-history">
      <h3>猜测历史</h3>
      <ul>
        <li v-for="guess in gameState.guesses" :key="guess.guess">
          {{ guess.player }}: {{ guess.guess }} ({{ guess.result }})
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  gameState: {
    current_range: [number, number]
    guesses: Array<{ player: string; guess: number; result: string }>
  }
}>()
</script>
```

---

## 2. 如何添加新 LLM 供应商

本示例演示如何添加一个新的 LLM 供应商（以 Claude 为例）。

### 2.1 创建客户端实现

创建 `server/app/core/ai/providers/claude_client.py`：

```python
"""Anthropic Claude LLM 客户端实现"""

from typing import Any

import httpx

from app.core.ai.base import LLMClient
from app.utils.exceptions import LLMError


class ClaudeClient(LLMClient):
    """Anthropic Claude API 客户端"""

    def __init__(
        self,
        provider_name: str = "claude",
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
        model: str = "claude-3-sonnet-20240229",
    ) -> None:
        self._provider_name = provider_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        model = kwargs.get("model", self._model)
        max_tokens = kwargs.get("max_tokens", 1024)
        temperature = kwargs.get("temperature", 0.7)

        claude_messages = self._convert_messages(messages)

        try:
            response = await self._client.post(
                f"{self._base_url}/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": claude_messages,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Claude API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise LLMError(f"Claude request failed: {e}")

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                continue
            converted.append({
                "role": "user" if role == "user" else "assistant",
                "content": msg["content"],
            })
        return converted

    def supports(self, provider: str) -> bool:
        return provider.lower() in ["claude", "anthropic"]
```

### 2.2 注册供应商

修改 `server/app/dependencies.py`：

```python
from app.core.ai.providers.claude_client import ClaudeClient

@lru_cache
def get_llm_factory() -> LLMClientFactory:
    settings = get_settings()
    factory = LLMClientFactory()

    # ... 其他供应商 ...

    # 添加 Claude 支持
    if settings.claude_api_key:
        factory.register(type(
            "Configured_claude",
            (ClaudeClient,),
            {
                "__init__": lambda self, **kw: ClaudeClient.__init__(
                    self,
                    provider_name="claude",
                    api_key=settings.claude_api_key,
                    base_url=settings.claude_base_url,
                    model="claude-3-sonnet-20240229",
                    **kw,
                )
            },
        ))

    return factory
```

### 2.3 添加配置项

修改 `server/app/config.py`：

```python
class Settings(BaseSettings):
    # ... 其他配置 ...

    # Claude 配置
    claude_api_key: str = ""
    claude_base_url: str = "https://api.anthropic.com/v1"
```

修改 `.env.example`：

```bash
# ===== Anthropic Claude =====
CLAUDE_API_KEY=your-key-here
CLAUDE_BASE_URL=https://api.anthropic.com/v1
```

### 2.4 在 AI 玩家配置中使用

修改 `config/ai_players.yaml`：

```yaml
players:
  - id: "claude_thinker"
    name: "Claude 思考者"
    description: "使用 Claude 模型的策略玩家"
    avatar: "🤖"
    model_config:
      provider: "claude"
      model_name: "claude-3-sonnet-20240229"
      temperature: 0.7
      max_tokens: 1024
    game_configs:
      doudizhu:
        style: "cautious"
        bid_threshold: 0.6
        risk_tolerance: 0.4
```

---

## 3. 如何创建自定义事件处理器

本示例演示如何创建一个事件处理器，在对局结束后自动发送通知。

### 3.1 创建事件处理器

创建 `server/app/core/events/handlers/notification_handler.py`：

```python
"""对局结束通知处理器"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.core.events import AsyncEventHandler, GameEndedEvent

if TYPE_CHECKING:
    from app.core.events.base import DomainEvent

logger = structlog.get_logger()


class GameEndNotificationHandler(AsyncEventHandler):
    """对局结束后发送通知的处理器"""

    def __init__(
        self,
        webhook_url: str | None = None,
        notify_on_win: bool = True,
        notify_on_loss: bool = False,
    ) -> None:
        self._webhook_url = webhook_url
        self._notify_on_win = notify_on_win
        self._notify_on_loss = notify_on_loss

    @property
    def event_types(self) -> list[type["DomainEvent"]]:
        return [GameEndedEvent]

    async def handle(self, event: GameEndedEvent) -> None:
        logger.info(
            "game_ended_notification_start",
            game_id=event.game_id,
            winner_id=event.winner_id,
            total_rounds=event.total_rounds,
        )

        if self._webhook_url:
            await self._send_webhook(event)

        await self._log_summary(event)

    async def _send_webhook(self, event: GameEndedEvent) -> None:
        """发送 Webhook 通知"""
        import httpx

        payload = {
            "game_id": event.game_id,
            "game_type": event.game_type,
            "winner_id": event.winner_id,
            "winner_role": event.winner_role,
            "total_rounds": event.total_rounds,
            "duration_seconds": event.duration_seconds,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info("webhook_sent", game_id=event.game_id)
        except Exception as e:
            logger.error("webhook_failed", game_id=event.game_id, error=str(e))

    async def _log_summary(self, event: GameEndedEvent) -> None:
        """记录对局摘要"""
        summary = f"""
对局结束摘要:
  游戏ID: {event.game_id}
  游戏类型: {event.game_type}
  获胜者: {event.winner_id} ({event.winner_role})
  总回合数: {event.total_rounds}
  持续时间: {event.duration_seconds:.1f}秒
"""
        logger.info("game_summary", summary=summary)
```

### 3.2 注册事件处理器

修改 `server/app/main.py`：

```python
from app.core.events import get_event_bus
from app.core.events.handlers.notification_handler import GameEndNotificationHandler


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_time = datetime.utcnow()
    app.state.settings = Settings()
    app.state.startup_time = startup_time

    # 注册事件处理器
    event_bus = get_event_bus()
    settings = app.state.settings

    if settings.notification_webhook_url:
        event_bus.subscribe(
            GameEndNotificationHandler(
                webhook_url=settings.notification_webhook_url,
            )
        )

    logger.info("application_started", startup_time=startup_time.isoformat())

    yield

    logger.info("application_shutdown")


app = FastAPI(lifespan=lifespan)
```

### 3.3 添加配置项

修改 `server/app/config.py`：

```python
class Settings(BaseSettings):
    # ... 其他配置 ...

    # 通知配置
    notification_webhook_url: str = ""
```

### 3.4 在业务代码中发布事件

在 `server/app/services/game_service.py` 中：

```python
from app.core.events import GameEndedEvent, get_event_bus


class GameService:
    async def finish_game(self, game_id: str, ...) -> None:
        # ... 结束对局逻辑 ...

        # 发布对局结束事件
        event = GameEndedEvent(
            game_id=game_id,
            game_type=game_type,
            winner_id=winner_id,
            winner_role=winner_role,
            total_rounds=total_rounds,
            duration_seconds=duration,
            player_stats=player_stats,
        )

        event_bus = get_event_bus()
        await event_bus.publish(event)
```

---

## 总结

以上示例展示了系统的主要扩展点：

1. **游戏引擎**：继承 `GameEngine` 实现新游戏
2. **LLM 供应商**：继承 `LLMClient` 添加新模型支持
3. **事件处理器**：实现 `AsyncEventHandler` 或 `SyncEventHandler` 响应领域事件

所有扩展都遵循系统的分层架构和依赖注入模式，确保代码的可维护性和可测试性。
