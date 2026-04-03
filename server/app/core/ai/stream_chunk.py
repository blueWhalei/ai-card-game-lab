"""流式输出块的数据结构。"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class StreamChunk:
    """流式输出块，区分推理内容和最终答案。

    用于支持 DeepSeek R1、OpenAI o1 等推理模型，
    这些模型会先输出推理过程 (reasoning_content)，
    再输出最终答案 (content)。

    Attributes:
        type: 块类型，"reasoning" 表示推理过程，"content" 表示最终答案
        text: 文本内容
        usage: Token 用量统计，仅在流式最后一个 chunk 携带
    """

    type: Literal["reasoning", "content"]
    text: str
    usage: dict[str, int | None] | None = None
