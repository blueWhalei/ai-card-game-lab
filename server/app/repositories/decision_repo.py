"""Decision point data access layer (SQLite)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite


class DecisionRepository:
    """CRUD operations for the ``decision_points`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        decision_id: str,
        game_id: str,
        round_number: int,
        player_id: str,
        hand_cards: list[int],
        opponent_hands: dict[str, int] | None,
        last_action: dict[str, Any] | None,
        game_phase: str,
        legal_actions: list[dict[str, Any]],
        chosen_action: dict[str, Any],
        thinking: str | None,
        created_at: str,
    ) -> None:
        """Insert a new decision point record."""
        await self._db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards,
                opponent_hands, last_action, game_phase, legal_actions,
                chosen_action, thinking, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                game_id,
                round_number,
                player_id,
                json.dumps(hand_cards, ensure_ascii=False),
                json.dumps(opponent_hands, ensure_ascii=False) if opponent_hands else None,
                json.dumps(last_action, ensure_ascii=False) if last_action else None,
                game_phase,
                json.dumps(legal_actions, ensure_ascii=False),
                json.dumps(chosen_action, ensure_ascii=False),
                thinking,
                created_at,
            ),
        )
        await self._db.commit()

    async def update_outcome_by_winner(
        self,
        game_id: str,
        winner_id: str,
    ) -> int:
        """Set outcome='win' for winner, 'lose' for the rest. Returns total updated count."""
        cursor = await self._db.execute(
            """
            UPDATE decision_points
            SET outcome = 'win', quality_score = 0.8
            WHERE game_id = ? AND player_id = ?
            """,
            (game_id, winner_id),
        )
        updated = cursor.rowcount or 0

        cursor = await self._db.execute(
            """
            UPDATE decision_points
            SET outcome = 'lose', quality_score = 0.3
            WHERE game_id = ? AND player_id != ?
            """,
            (game_id, winner_id),
        )
        updated += cursor.rowcount or 0
        await self._db.commit()
        return updated

    async def update_outcome_draw(self, game_id: str) -> int:
        """Set outcome='draw' for all decision points in a game. Returns updated count."""
        cursor = await self._db.execute(
            """
            UPDATE decision_points
            SET outcome = 'draw', quality_score = 0.5
            WHERE game_id = ?
            """,
            (game_id,),
        )
        count = cursor.rowcount or 0
        await self._db.commit()
        return count

    async def list_decision_points(
        self,
        *,
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
        conditions: list[str] = []
        params: list[Any] = []

        if game_id:
            conditions.append("game_id = ?")
            params.append(game_id)
        if player_id:
            conditions.append("player_id = ?")
            params.append(player_id)
        if min_quality is not None:
            conditions.append("quality_score >= ?")
            params.append(min_quality)
        if max_quality is not None:
            conditions.append("quality_score <= ?")
            params.append(max_quality)
        if game_phase:
            conditions.append("game_phase = ?")
            params.append(game_phase)
        if outcome:
            conditions.append("outcome = ?")
            params.append(outcome)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) as total FROM decision_points {where_clause}",
            params,
        )
        count_row = await count_cursor.fetchone()
        total = count_row["total"] if count_row else 0

        cursor = await self._db.execute(
            f"""
            SELECT * FROM decision_points
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows], total

    async def get_by_id(self, decision_id: str) -> dict[str, Any] | None:
        """Get a single decision point by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM decision_points WHERE id = ?",
            (decision_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def count_total(self) -> int:
        """Count total decision points."""
        return await self._scalar("SELECT COUNT(*) FROM decision_points")

    async def get_quality_stats(self) -> dict[str, Any]:
        """Return avg/min/max quality scores."""
        cursor = await self._db.execute(
            """
            SELECT
                AVG(quality_score) as avg_quality,
                MIN(quality_score) as min_quality,
                MAX(quality_score) as max_quality
            FROM decision_points
            WHERE quality_score IS NOT NULL
            """
        )
        row = await cursor.fetchone()
        return {
            "avg_quality": row["avg_quality"] if row and row["avg_quality"] else 0,
            "min_quality": row["min_quality"] if row and row["min_quality"] else 0,
            "max_quality": row["max_quality"] if row and row["max_quality"] else 0,
        }

    async def get_outcome_counts(self) -> dict[str, int]:
        """Return counts grouped by outcome."""
        cursor = await self._db.execute(
            """
            SELECT outcome, COUNT(*) as count
            FROM decision_points
            WHERE outcome IS NOT NULL
            GROUP BY outcome
            """
        )
        rows = await cursor.fetchall()
        return {row["outcome"]: row["count"] for row in rows}

    async def get_phase_counts(self) -> dict[str, int]:
        """Return counts grouped by game_phase."""
        cursor = await self._db.execute(
            """
            SELECT game_phase, COUNT(*) as count
            FROM decision_points
            GROUP BY game_phase
            """
        )
        rows = await cursor.fetchall()
        return {row["game_phase"]: row["count"] for row in rows}

    async def _scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        cursor = await self._db.execute(sql, params or [])
        row = await cursor.fetchone()
        return row[0] if row else 0


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a decision_points row to a dictionary with JSON fields parsed."""
    return {
        "id": row["id"],
        "game_id": row["game_id"],
        "round_number": row["round_number"],
        "player_id": row["player_id"],
        "hand_cards": json.loads(row["hand_cards"]) if row["hand_cards"] else [],
        "opponent_hands": json.loads(row["opponent_hands"]) if row["opponent_hands"] else None,
        "last_action": json.loads(row["last_action"]) if row["last_action"] else None,
        "game_phase": row["game_phase"],
        "legal_actions": json.loads(row["legal_actions"]) if row["legal_actions"] else [],
        "chosen_action": json.loads(row["chosen_action"]) if row["chosen_action"] else {},
        "thinking": row["thinking"],
        "outcome": row["outcome"],
        "quality_score": row["quality_score"],
        "created_at": row["created_at"],
    }
