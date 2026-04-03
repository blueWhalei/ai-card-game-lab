"""Decision point service for SFT training data collection."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from app.repositories.decision_repo import DecisionRepository
from app.utils.id_generator import generate_id

logger = structlog.get_logger()


class DecisionService:
    """Service for recording and querying decision points for SFT training."""

    def __init__(self, sqlite_path: str, data_dir: str = "data") -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = Path(data_dir)

    async def create_decision_point(
        self,
        game_id: str,
        round_number: int,
        player_id: str,
        hand_cards: list[int],
        opponent_hands: dict[str, int] | None,
        last_action: dict[str, Any] | None,
        game_phase: str,
        legal_actions: list[dict[str, Any]],
        chosen_action: dict[str, Any],
        thinking: str | None = None,
    ) -> str:
        """Create a new decision point record."""
        decision_id = generate_id("dp")
        now = datetime.now(tz=UTC).isoformat()

        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DecisionRepository(db)
            await repo.create(
                decision_id=decision_id,
                game_id=game_id,
                round_number=round_number,
                player_id=player_id,
                hand_cards=hand_cards,
                opponent_hands=opponent_hands,
                last_action=last_action,
                game_phase=game_phase,
                legal_actions=legal_actions,
                chosen_action=chosen_action,
                thinking=thinking,
                created_at=now,
            )

        logger.info(
            "decision_point_created",
            decision_id=decision_id,
            game_id=game_id,
            round_number=round_number,
            player_id=player_id,
        )

        return decision_id

    async def update_outcome(
        self,
        game_id: str,
        winner_id: str | None,
    ) -> int:
        """Update outcome and quality score for all decision points in a game."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DecisionRepository(db)
            if winner_id:
                updated = await repo.update_outcome_by_winner(game_id, winner_id)
            else:
                updated = await repo.update_outcome_draw(game_id)

        logger.info(
            "decision_outcome_updated",
            game_id=game_id,
            winner_id=winner_id,
            updated_count=updated,
        )

        return updated

    async def list_decision_points(
        self,
        game_id: str | None = None,
        player_id: str | None = None,
        min_quality: float | None = None,
        max_quality: float | None = None,
        game_phase: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List decision points with filters and pagination."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DecisionRepository(db)
            return await repo.list_decision_points(
                game_id=game_id,
                player_id=player_id,
                min_quality=min_quality,
                max_quality=max_quality,
                game_phase=game_phase,
                outcome=outcome,
                limit=limit,
                offset=offset,
            )

    async def get_decision_point(self, decision_id: str) -> dict[str, Any] | None:
        """Get a single decision point by ID."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DecisionRepository(db)
            return await repo.get_by_id(decision_id)

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics for decision points."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = DecisionRepository(db)

            total = await repo.count_total()
            quality = await repo.get_quality_stats()
            outcome_counts = await repo.get_outcome_counts()
            phase_counts = await repo.get_phase_counts()

        return {
            "total": total,
            **quality,
            "outcome_counts": outcome_counts,
            "phase_counts": phase_counts,
        }

    async def export_chatml(
        self,
        game_id: str | None = None,
        min_quality: float | None = None,
        outcome: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """Export decision points to ChatML format JSONL."""
        items, _ = await self.list_decision_points(
            game_id=game_id,
            min_quality=min_quality,
            outcome=outcome,
            limit=10000,
        )

        if not items:
            logger.warning("export_chatml_no_data", game_id=game_id, min_quality=min_quality)
            return ""

        self._data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"decision_points_{timestamp}.jsonl"
        filepath = self._data_dir / "datasets" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = [json.dumps(_to_chatml(item), ensure_ascii=False) for item in items]
        await asyncio.to_thread(_write_lines, filepath, lines)

        logger.info(
            "export_chatml_completed",
            filepath=str(filepath),
            count=len(items),
        )

        return str(filepath)


def _write_lines(filepath: Path, lines: list[str]) -> None:
    """Write lines to file synchronously (called via asyncio.to_thread)."""
    with filepath.open("w", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines)


def _to_chatml(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a decision point to ChatML format."""
    hand_str = _format_hand(item["hand_cards"])
    opponent_str = _format_opponent_hands(item["opponent_hands"])
    last_action_str = _format_action(item["last_action"])
    legal_actions_str = _format_legal_actions(item["legal_actions"])
    chosen_action_str = _format_chosen_action(item["chosen_action"])

    user_content = f"""手牌: {hand_str}
对手剩余: {opponent_str}
上家出牌: {last_action_str}
游戏阶段: {item["game_phase"]}
可选动作: {legal_actions_str}"""

    assistant_content = f"{chosen_action_str}"
    if item.get("thinking"):
        assistant_content += f"\n\n原因: {item['thinking']}"

    return {
        "messages": [
            {"role": "system", "content": "你是斗地主AI,根据当前状态选择最优出牌。"},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": {
            "decision_id": item["id"],
            "game_id": item["game_id"],
            "round_number": item["round_number"],
            "player_id": item["player_id"],
            "quality_score": item.get("quality_score", 0.5),
        },
    }


def _format_hand(hand_cards: list[int]) -> str:
    if not hand_cards:
        return "无"
    return str(hand_cards)


def _format_opponent_hands(opponent_hands: dict[str, int] | None) -> str:
    if not opponent_hands:
        return "未知"
    return ", ".join(f"{k}({v}张)" for k, v in opponent_hands.items())


def _format_action(action: dict[str, Any] | None) -> str:
    if not action:
        return "无"
    action_type = action.get("action_type", action.get("type", "UNKNOWN"))
    if action_type == "PASS":
        return "过"
    cards = action.get("cards", [])
    if cards:
        return f"{action_type} {cards}"
    return str(action_type)


def _format_legal_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "无"
    formatted = []
    for action in actions:
        action_type = action.get("action_type", action.get("type", "UNKNOWN"))
        if action_type == "PASS":
            formatted.append("过")
        else:
            cards = action.get("cards", [])
            formatted.append(str(cards) if cards else str(action_type))
    return ", ".join(formatted)


def _format_chosen_action(action: dict[str, Any]) -> str:
    if not action:
        return "未知"
    action_type = action.get("action_type", action.get("type", "UNKNOWN"))
    if action_type == "PASS":
        return "过"
    cards = action.get("cards", [])
    if cards:
        return f"出 {cards}"
    return str(action_type)
