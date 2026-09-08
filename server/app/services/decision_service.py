"""Decision point service for SFT training data collection."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.core.stats.highlights import BLUNDER_EV_LOSS, pick_game_highlights
from app.core.training.data_quality import evaluate_train_usable
from app.core.training.preference import DEFAULT_MIN_EV_GAP, build_preference_pair
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
        hand_cards: list[str],
        opponent_hands: dict[str, int] | None,
        last_action: dict[str, Any] | None,
        game_phase: str,
        legal_actions: list[dict[str, Any]],
        chosen_action: dict[str, Any],
        action_id: str = "",
        prompt_messages: list[dict[str, str]] | None = None,
        thinking: str | None = None,
        ev_loss: float | None = None,
        evaluator_params: dict[str, Any] | None = None,
        parse_fallback: bool = False,
        policy_kind: str = "llm",
    ) -> str:
        """Create a new decision point record with train_usable evaluated.

        ``ev_loss`` is optional: the caller computes it when it has a live state
        and an engine that can sample hidden state, and passes ``None`` otherwise.
        ``parse_fallback`` says the model did not pick this move -- a rescue action
        is never training data.
        """
        decision_id = generate_id("dp")
        now = datetime.now(tz=UTC).isoformat()
        train_usable, reason = evaluate_train_usable(
            action_id=action_id,
            legal_action_ids=_legal_ids(legal_actions),
            prompt_messages=prompt_messages,
            parse_fallback=parse_fallback,
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
                action_id=action_id,
                prompt_messages=prompt_messages,
                thinking=thinking,
                created_at=now,
                train_usable=train_usable,
                train_usable_reason=reason,
                parse_fallback=parse_fallback,
                ev_loss=ev_loss,
                evaluator_params=evaluator_params,
                policy_kind=policy_kind,
            )

        logger.info(
            "decision_point_created",
            decision_id=decision_id,
            game_id=game_id,
            round_number=round_number,
            player_id=player_id,
            train_usable=train_usable,
            train_usable_reason=reason,
            ev_loss=ev_loss,
            policy_kind=policy_kind,
        )

        return decision_id

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
        max_ev_loss: float | None = None,
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
                max_ev_loss=max_ev_loss,
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
            ev_stats = await repo.get_ev_loss_stats(
                experiment_id, blunder_threshold=BLUNDER_EV_LOSS
            )
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
            **ev_stats,
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
        max_ev_loss: float | None = None,
        include_thinking: bool = False,
        output_path: str | None = None,
        eval_ratio: float = 0.0,
    ) -> tuple[str, int, dict[str, Any]]:
        """Export decision points to ChatML format JSONL.

        ``train_usable`` filters on structural validity, ``max_ev_loss`` on move
        quality. They answer different questions, so they stay separate knobs:
        a legal but weak move is still a well-formed sample.

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
            max_ev_loss=max_ev_loss,
            limit=10000,
        )

        if not items:
            logger.warning(
                "export_chatml_no_data",
                game_id=game_id,
                experiment_id=experiment_id,
                min_quality=min_quality,
                train_usable=train_usable_filter,
                max_ev_loss=max_ev_loss,
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

    async def export_preferences(
        self,
        game_id: str | None = None,
        experiment_id: str | None = None,
        player_id: str | None = None,
        min_quality: float | None = None,
        outcome: str | None = None,
        game_phase: str | None = None,
        train_usable: bool | None = None,
        train_usable_only: bool = True,
        max_ev_loss: float | None = None,
        min_ev_gap: float = DEFAULT_MIN_EV_GAP,
        include_thinking: bool = False,
        output_path: str | None = None,
    ) -> tuple[str, int, dict[str, Any]]:
        """Export EV preference pairs (DPO JSONL) from scored decision points.

        Chosen = rollout ``best_action_id``; rejected = model ``action_id``.
        Rows without ``best_action_id`` in ``evaluator_params`` are skipped.

        Returns ``(filepath, count, meta)``. Empty filepath when no pairs written.
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
            max_ev_loss=max_ev_loss,
            limit=10000,
        )

        meta: dict[str, Any] = {
            "skipped_missing_best": 0,
            "skipped_gap": 0,
            "skipped_tie": 0,
            "skipped_missing_prompt": 0,
            "skipped_missing_action": 0,
            "min_ev_gap": min_ev_gap,
        }

        if not items:
            logger.warning(
                "export_preferences_no_data",
                game_id=game_id,
                experiment_id=experiment_id,
                min_ev_gap=min_ev_gap,
            )
            return "", 0, meta

        records: list[dict[str, Any]] = []
        for item in items:
            record, skip = build_preference_pair(
                item,
                min_ev_gap=min_ev_gap,
                include_thinking=include_thinking,
            )
            if record is not None:
                records.append(record)
                continue
            key = f"skipped_{skip}" if skip else "skipped_other"
            if key in meta:
                meta[key] = int(meta[key]) + 1

        if not records:
            logger.warning(
                "export_preferences_no_pairs",
                candidates=len(items),
                **{k: v for k, v in meta.items() if k.startswith("skipped_")},
            )
            return "", 0, meta

        if output_path:
            filepath = Path(output_path)
        else:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            filepath = self._data_dir / "datasets" / f"preferences_{timestamp}.jsonl"

        filepath.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(record, ensure_ascii=False) for record in records]
        await asyncio.to_thread(_write_lines, filepath, lines)

        logger.info(
            "export_preferences_completed",
            filepath=str(filepath),
            count=len(records),
            candidates=len(items),
            min_ev_gap=min_ev_gap,
            experiment_id=experiment_id,
        )
        return str(filepath), len(records), meta


def _legal_ids(legal_actions: list[dict[str, Any]]) -> list[str]:
    return [str(entry["id"]) for entry in legal_actions if entry.get("id")]


def _write_lines(filepath: Path, lines: list[str]) -> None:
    """Write lines to file synchronously (called via asyncio.to_thread)."""
    with filepath.open("w", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines)


def _to_chatml(item: dict[str, Any], *, include_thinking: bool = False) -> dict[str, Any]:
    """Replay one stored turn as a ChatML sample.

    The prompt is the one the model actually received and the reply is the one it
    should have produced, so a fine-tuned model is trained on the protocol it will
    be asked to speak. Re-rendering the state here instead would be a second
    implementation of the prompt, free to drift away from the first.
    """
    reply: dict[str, str] = {}
    if include_thinking:
        reply["thinking"] = str(item.get("thinking") or "")
    reply["action_id"] = str(item["action_id"])

    return {
        "messages": [
            *item["prompt_messages"],
            {"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)},
        ],
        "metadata": {
            "decision_id": item["id"],
            "game_id": item["game_id"],
            "round_number": item["round_number"],
            "player_id": item["player_id"],
            "quality_score": item.get("quality_score", 0.5),
            "train_usable": item.get("train_usable", True),
            "ev_loss": item.get("ev_loss"),
        },
    }
