"""Decision point service for SFT training data collection."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.core.stats.highlights import pick_game_highlights
from app.core.training.data_quality import evaluate_train_usable
from app.database import connect_or_reuse
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
        """Create a new decision point record with train_usable evaluated."""
        decision_id = generate_id("dp")
        now = datetime.now(tz=UTC).isoformat()
        train_usable, reason = evaluate_train_usable(
            chosen_action=chosen_action,
            legal_actions=legal_actions,
            thinking=thinking,
        )

        async with connect_or_reuse(self._sqlite_path) as db:
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
                train_usable=train_usable,
                train_usable_reason=reason,
            )

        logger.info(
            "decision_point_created",
            decision_id=decision_id,
            game_id=game_id,
            round_number=round_number,
            player_id=player_id,
            train_usable=train_usable,
            train_usable_reason=reason,
        )

        return decision_id

    async def recompute_train_usable(self, game_id: str | None = None) -> int:
        """Re-evaluate and persist train_usable for existing decision points."""
        async with connect_or_reuse(self._sqlite_path) as db:
            repo = DecisionRepository(db)
            items = await repo.list_for_recompute(game_id=game_id)
            updated = 0
            for item in items:
                usable, reason = evaluate_train_usable(
                    chosen_action=item.get("chosen_action"),
                    legal_actions=item.get("legal_actions"),
                    thinking=item.get("thinking"),
                )
                if item.get("train_usable") != usable or item.get("train_usable_reason") != reason:
                    await repo.update_train_usable(item["id"], usable, reason)
                    updated += 1
                    logger.debug(
                        "train_usable_recomputed",
                        decision_id=item["id"],
                        train_usable=usable,
                        reason=reason,
                    )

        logger.info(
            "train_usable_recompute_done",
            game_id=game_id,
            scanned=len(items),
            updated=updated,
        )
        return updated

    async def update_outcome(
        self,
        game_id: str,
        winner_id: str | None,
    ) -> int:
        """Update outcome and quality score for all decision points in a game.

        quality_score is an end-game outcome proxy only (not reasoning quality).
        """
        async with connect_or_reuse(self._sqlite_path) as db:
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
        experiment_id: str | None = None,
        player_id: str | None = None,
        min_quality: float | None = None,
        max_quality: float | None = None,
        game_phase: str | None = None,
        outcome: str | None = None,
        train_usable: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List decision points with filters and pagination."""
        async with connect_or_reuse(self._sqlite_path) as db:
            repo = DecisionRepository(db)
            return await repo.list_decision_points(
                game_id=game_id,
                experiment_id=experiment_id,
                player_id=player_id,
                min_quality=min_quality,
                max_quality=max_quality,
                game_phase=game_phase,
                outcome=outcome,
                train_usable=train_usable,
                limit=limit,
                offset=offset,
            )

    async def get_decision_point(self, decision_id: str) -> dict[str, Any] | None:
        """Get a single decision point by ID."""
        async with connect_or_reuse(self._sqlite_path) as db:
            repo = DecisionRepository(db)
            return await repo.get_by_id(decision_id)

    async def highlights_for_game(
        self,
        game_id: str,
        winner_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pick 3–5 post-game highlight moves from stored decision points."""
        items, _total = await self.list_decision_points(
            game_id=game_id,
            limit=500,
            offset=0,
        )
        return pick_game_highlights(items, winner_id=winner_id)

    async def get_stats(self, experiment_id: str | None = None) -> dict[str, Any]:
        """Get aggregate statistics for decision points."""
        async with connect_or_reuse(self._sqlite_path) as db:
            repo = DecisionRepository(db)

            total = await repo.count_total(experiment_id)
            usability = await repo.count_usability(experiment_id)
            reason_counts = await repo.count_not_usable_by_reason(experiment_id)
            quality = await repo.get_quality_stats(experiment_id)
            outcome_counts = await repo.get_outcome_counts(experiment_id)
            phase_counts = await repo.get_phase_counts(experiment_id)

        usable = usability["usable"]
        not_usable = usability["not_usable"]
        total_all = usability["total"]
        usable_rate = (usable / total_all) if total_all else 0.0
        return {
            "total": total,
            "train_usable_count": usable,
            "not_usable_count": not_usable,
            "usable_rate": round(usable_rate, 4),
            "not_usable_reason_counts": reason_counts,
            **quality,
            "outcome_counts": outcome_counts,
            "phase_counts": phase_counts,
        }

    async def export_chatml(
        self,
        game_id: str | None = None,
        experiment_id: str | None = None,
        player_id: str | None = None,
        min_quality: float | None = None,
        outcome: str | None = None,
        game_phase: str | None = None,
        train_usable: bool | None = None,
        train_usable_only: bool = True,
        include_thinking: bool = False,
        output_path: str | None = None,
        eval_ratio: float = 0.0,
    ) -> tuple[str, int, dict[str, Any]]:
        """Export decision points to ChatML format JSONL.

        Returns (train_filepath, train_count, split_meta). Empty filepath when nothing to export.
        """
        train_usable_filter: bool | None
        if train_usable is not None:
            train_usable_filter = train_usable
        else:
            train_usable_filter = True if train_usable_only else None
        items, _ = await self.list_decision_points(
            game_id=game_id,
            experiment_id=experiment_id,
            player_id=player_id,
            min_quality=min_quality,
            outcome=outcome,
            game_phase=game_phase,
            train_usable=train_usable_filter,
            limit=10000,
        )

        if not items:
            logger.warning(
                "export_chatml_no_data",
                game_id=game_id,
                experiment_id=experiment_id,
                min_quality=min_quality,
                train_usable=train_usable_filter,
            )
            return "", 0, {}

        if output_path:
            filepath = Path(output_path)
        else:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"decision_points_{timestamp}.jsonl"
            filepath = self._data_dir / "datasets" / filename

        filepath.parent.mkdir(parents=True, exist_ok=True)

        split_meta: dict[str, Any] = {
            "eval_ratio": eval_ratio,
            "eval_sample_count": 0,
            "eval_file_path": None,
            "eval_game_ids": [],
        }

        train_items = items
        eval_items: list[dict[str, Any]] = []
        if eval_ratio > 0 and items:
            game_ids = sorted({str(item["game_id"]) for item in items})
            eval_count = max(1, int(len(game_ids) * eval_ratio))
            eval_game_ids = set(game_ids[:eval_count])
            train_items = [i for i in items if str(i["game_id"]) not in eval_game_ids]
            eval_items = [i for i in items if str(i["game_id"]) in eval_game_ids]
            split_meta["eval_game_ids"] = sorted(eval_game_ids)
            split_meta["eval_sample_count"] = len(eval_items)

        if not train_items:
            return "", 0, split_meta

        lines = [
            json.dumps(_to_chatml(item, include_thinking=include_thinking), ensure_ascii=False)
            for item in train_items
        ]
        await asyncio.to_thread(_write_lines, filepath, lines)

        if eval_items:
            eval_path = filepath.with_name(f"{filepath.stem}_eval{filepath.suffix}")
            eval_lines = [
                json.dumps(_to_chatml(item, include_thinking=include_thinking), ensure_ascii=False)
                for item in eval_items
            ]
            await asyncio.to_thread(_write_lines, eval_path, eval_lines)
            split_meta["eval_file_path"] = str(eval_path)

        logger.info(
            "export_chatml_completed",
            filepath=str(filepath),
            count=len(train_items),
            eval_count=len(eval_items),
            include_thinking=include_thinking,
            train_usable_only=train_usable_only,
            experiment_id=experiment_id,
        )

        return str(filepath), len(train_items), split_meta


def _write_lines(filepath: Path, lines: list[str]) -> None:
    """Write lines to file synchronously (called via asyncio.to_thread)."""
    with filepath.open("w", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines)


def _to_chatml(item: dict[str, Any], *, include_thinking: bool = False) -> dict[str, Any]:
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
    if include_thinking and item.get("thinking"):
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
            "train_usable": item.get("train_usable", True),
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
