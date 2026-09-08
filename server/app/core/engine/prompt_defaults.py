"""Shared built-in system prompt skeleton (game-agnostic)."""

# Format keys: game_type_cn, rules, format_instructions.
SYSTEM_TEMPLATE = """\
你是{game_type_cn} AI 玩家。你的玩家ID会在每轮提示中明确标注。

## 核心规则
{rules}

{format_instructions}
"""
