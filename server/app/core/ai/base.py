"""抽象 LLM 客户端接口。

定义了与大型语言模型交互的统一接口。所有具体的 LLM 提供商实现
（如 OpenAI、Ollama、DashScope 等）都应继承 LLMClient 并实现
其抽象方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from app.core.ai.stream_chunk import StreamChunk


@dataclass(frozen=True)
class ChatResponse:
    """Unified response from LLM chat completion.

    Attributes:
        content: The text content of the response
        usage: Token usage statistics (prompt_tokens, completion_tokens, total_tokens)
    """

    content: str
    usage: dict[str, int | None]


class LLMClient(ABC):
    """统一的 LLM 调用接口抽象基类。

    为不同的大语言模型提供商提供统一的调用接口。支持多种提供商，
    包括 Chat Completions 接口（OpenAI、DashScope、DeepSeek、Kimi、
    ZhipuAI、Yi、Baichuan、MiniMax）和 Ollama 本地模型。

    子类必须实现：
        - chat：发送聊天请求并获取响应
        - chat_stream：发送聊天请求并流式返回响应（可选）
        - supports：判断是否支持特定提供商

    所有实现都应该是异步的，以支持非阻塞 I/O 操作。

    Example:
        >>> class OpenAIClient(LLMClient):
        ...     async def chat(self, messages, **kwargs):
        ...         # 调用 OpenAI API
        ...         return response
        ...     def supports(self, provider):
        ...         return provider in ["openai", "gpt"]
    """

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        """发送聊天补全请求并返回助手回复。

        向 LLM 发送消息列表，获取模型的回复。支持通过 kwargs
        传递额外的请求参数，如 temperature、max_tokens 等。

        Args:
            messages: 消息列表，每条消息是包含 'role' 和 'content' 的字典。
                role 可以是 'system'、'user' 或 'assistant'。
                例如: [{"role": "user", "content": "你好"}]
            **kwargs: 额外的请求参数，如：
                - temperature: 采样温度 (0.0-2.0)
                - max_tokens: 最大生成 token 数
                - model: 指定模型名称（覆盖默认配置）

        Returns:
            ChatResponse 包含 content 文本和 usage 统计信息。

        Raises:
            LLMError: LLM 调用失败，包括网络错误、API 错误等。
            RateLimitError: 超过 API 调用频率限制。
            InvalidResponseError: LLM 返回了无效的响应格式。

        Example:
            >>> messages = [
            ...     {"role": "system", "content": "你是一个卡牌游戏AI"},
            ...     {"role": "user", "content": "我该出什么牌？"}
            ... ]
            >>> response = await client.chat(messages, temperature=0.7)
            >>> print(response.content)
            "根据当前局势，建议你出对子..."
        """

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        """发送聊天补全请求并流式返回助手回复。

        子类可以重写此方法以支持真正的流式输出。默认实现会调用 chat()
        并一次性返回完整响应。支持 reasoning_content 字段用于思考模型。

        Args:
            messages: 消息列表，每条消息是包含 'role' 和 'content' 的字典。
            **kwargs: 额外的请求参数，如 temperature、max_tokens 等

        Yields:
            StreamChunk 对象，包含 type ("reasoning" 或 "content") 和 text。

        Example:
            >>> async for chunk in client.chat_stream(messages):
            ...     if chunk.type == "reasoning":
            ...         print(f"[思考] {chunk.text}")
            ...     else:
            ...         print(chunk.text, end='', flush=True)
        """
        # 默认实现：调用 chat 并一次性返回
        response = await self.chat(messages, **kwargs)
        yield StreamChunk(type="content", text=response.content)

    @abstractmethod
    def supports(self, provider: str) -> bool:
        """判断此客户端是否支持指定的提供商。

        用于 LLMClientFactory 根据配置选择合适的客户端实现。

        Args:
            provider: 提供商名称，如 'openai'、'ollama'、'dashscope' 等。

        Returns:
            如果此客户端支持该提供商返回 True，否则返回 False。

        Example:
            >>> client.supports("openai")
            True
            >>> client.supports("ollama")
            False
        """
