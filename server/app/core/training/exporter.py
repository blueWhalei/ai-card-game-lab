"""Training dataset exporter — converts game JSONL to SFT-ready ChatML format.

Each training sample is a three-turn conversation:
  system: game rules + strategy guidelines
  user:   game state description (from the round's raw_response context)
  assistant: the actual JSON decision (action + thinking)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

_SFT_SYSTEM = (
    "你是一个 AI 卡牌游戏玩家。根据当前局面选择最佳动作，"
    '按照 JSON 格式输出：{"thinking": "...", "action": {"type": "...", "cards": [...]}}'
)


def export_sft_dataset(
    source_jsonl: str,
    output_path: str,
    game_type: str | None = None,
    include_thinking: bool = False,
) -> int:
    """Convert a raw game dataset JSONL into ChatML SFT training format.

    Returns the number of training samples written.
    """
    src = Path(source_jsonl)
    if not src.exists():
        logger.warning("export_source_not_found", path=source_jsonl)
        return 0

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with src.open("r", encoding="utf-8") as fin, \
         out.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only process round records with thinking + action
            if record.get("type") != "round":
                continue
            if game_type and record.get("game_type") and record["game_type"] != game_type:
                continue

            sample = _build_sft_sample(record, include_thinking=include_thinking)
            if sample is None:
                continue

            fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
            count += 1

    logger.info(
        "sft_export_done",
        source=source_jsonl,
        output=output_path,
        count=count,
        include_thinking=include_thinking,
    )
    return count


def _build_sft_sample(
    record: dict[str, Any],
    *,
    include_thinking: bool = False,
) -> dict[str, Any] | None:
    """Build a single ChatML training sample from a round record."""
    thinking = record.get("thinking", "")
    action_type = record.get("action_type", "")
    cards = record.get("cards", [])
    player_id = record.get("player_id", "")

    if not action_type:
        return None

    # Build the user message (game context)
    user_parts = [
        f"玩家: {player_id}",
        f"轮次: {record.get('round_num', '?')}",
    ]
    user_content = "\n".join(user_parts)

    # Build the assistant response (what the model should learn to output)
    action_payload: dict[str, Any] = {
        "type": action_type,
        "cards": cards,
    }
    if include_thinking:
        assistant_obj: dict[str, Any] = {
            "thinking": thinking or "无",
            "action": action_payload,
        }
    else:
        assistant_obj = {"action": action_payload}
    assistant_content = json.dumps(assistant_obj, ensure_ascii=False)

    system = _SFT_SYSTEM
    if not include_thinking:
        system = (
            "你是一个 AI 卡牌游戏玩家。根据当前局面选择最佳动作，"
            '按照 JSON 格式输出：{"action": {"type": "...", "cards": [...]}}'
        )

    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
    }
