"""Decision point data access layer (SQLite)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.core.stats.scenarios import SCENARIO_SQL

_TRACE_EXPLAIN_SQL = """
json_extract((
    SELECT t.input_snapshot FROM traces t
    WHERE t.game_id = decision_points.game_id
      AND t.round_number = decision_points.round_number
      AND t.player_id = decision_points.player_id
    ORDER BY t.created_at DESC LIMIT 1
), '$.hand_analysis') AS hand_analysis_json
"""


class DecisionRepository:
    """CRUD operations for the ``decision_points`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def scenario_records(
        self,
        experiment_id: str,
        scenario: str | None,
        game_id: str | None,
        game_page: int,
        page: int,
    ) -> dict[str, Any]:
        """One run's current records, with the canonical mutually exclusive buckets."""
        scope = (
            "FROM decision_points dp JOIN games g ON g.id = dp.game_id WHERE g.experiment_id = ?"
        )
        counts = "COUNT(*) AS decision_n, COUNT(dp.ev_loss) AS evaluated_n"
        cursor = await self._db.execute(
            f"SELECT {SCENARIO_SQL} AS scenario, {counts}, COUNT(DISTINCT dp.game_id) AS game_n "
            f"{scope} GROUP BY scenario",
            (experiment_id,),
        )
        groups = [dict(row) for row in await cursor.fetchall()]
        cursor = await self._db.execute(
            f"SELECT {counts}, COUNT(DISTINCT dp.game_id) AS game_n {scope}", (experiment_id,)
        )
        totals_row = await cursor.fetchone()
        assert totals_row is not None  # An aggregate without GROUP BY always returns one row.
        totals = dict(totals_row)
        total_games = int(
            await self._scalar(
                "SELECT COUNT(*) FROM games WHERE experiment_id = ?", [experiment_id]
            )
        )
        totals["unrecorded_game_n"] = total_games - totals["game_n"]
        params: list[Any] = [experiment_id]
        if scenario is not None:
            scope += f" AND ({SCENARIO_SQL}) = ?"
            params.append(scenario)
        game_total = int(await self._scalar(f"SELECT COUNT(DISTINCT dp.game_id) {scope}", params))
        game_fields = f"g.id, g.status, g.created_at, {counts}"
        cursor = await self._db.execute(
            f"SELECT {game_fields} {scope} GROUP BY g.id "
            "ORDER BY g.created_at DESC, g.id LIMIT 20 OFFSET ?",
            [*params, (game_page - 1) * 20],
        )
        games = [dict(row) for row in await cursor.fetchall()]
        selected_game = None
        points: list[dict[str, Any]] = []
        if game_id is not None:
            selected_scope = scope + " AND g.id = ?"
            cursor = await self._db.execute(
                f"SELECT {game_fields} {selected_scope} GROUP BY g.id", [*params, game_id]
            )
            row = await cursor.fetchone()
            selected_game = dict(row) if row else None
            if selected_game:
                cursor = await self._db.execute(
                    f"SELECT dp.* {selected_scope} "
                    "ORDER BY dp.round_number, dp.created_at, dp.id LIMIT 20 OFFSET ?",
                    [*params, game_id, (page - 1) * 20],
                )
                fields = (
                    "id",
                    "game_id",
                    "round_number",
                    "player_id",
                    "game_phase",
                    "hand_cards",
                    "chosen_action",
                    "action_id",
                    "ev_loss",
                    "evaluator_params",
                    "created_at",
                )
                points = [
                    {key: value for key, value in _row_to_dict(row).items() if key in fields}
                    for row in await cursor.fetchall()
                ]
        return {
            "totals": totals,
            "groups": groups,
            "games": {"items": games, "total": game_total, "page": game_page, "page_size": 20},
            "selected_game": selected_game,
            "decisions": {
                "items": points,
                "total": selected_game["decision_n"] if selected_game else 0,
                "page": page,
                "page_size": 20,
            },
        }

    async def create(
        self,
        decision_id: str,
        game_id: str,
        round_number: int,
        player_id: str,
        hand_cards: list[str],
        opponent_hands: dict[str, int] | None,
        last_action: dict[str, Any] | None,
        game_phase: str,
        legal_actions: list[dict[str, Any]],
        chosen_action: dict[str, Any],
        action_id: str,
        prompt_messages: list[dict[str, str]] | None,
        thinking: str | None,
        created_at: str,
        train_usable: bool = True,
        train_usable_reason: str = "",
        parse_fallback: bool = False,
        ev_loss: float | None = None,
        evaluator_params: dict[str, Any] | None = None,
        policy_kind: str = "llm",
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Insert a new decision point record.

        ``ev_loss`` stays NULL when the move was not evaluated, which downstream
        must not confuse with a loss of 0.0 (the move was the best candidate).
        """
        await self._db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards,
                opponent_hands, last_action, game_phase, legal_actions,
                chosen_action, action_id, prompt_messages, thinking,
                train_usable, train_usable_reason, parse_fallback,
                ev_loss, evaluator_params, policy_kind, tool_calls, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                action_id,
                json.dumps(prompt_messages, ensure_ascii=False) if prompt_messages else None,
                thinking,
                1 if train_usable else 0,
                train_usable_reason,
                1 if parse_fallback else 0,
                ev_loss,
                json.dumps(evaluator_params, ensure_ascii=False) if evaluator_params else None,
                policy_kind or "llm",
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                created_at,
            ),
        )
        await self._db.commit()

    async def list_decision_points(
        self,
        *,
        game_id: str | None = None,
        experiment_id: str | None = None,
        player_id: str | None = None,
        game_phase: str | None = None,
        outcome: str | None = None,
        train_usable: bool | None = None,
        max_ev_loss: float | None = None,
        annotation: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List decision points with filters and pagination.

        ``max_ev_loss`` keeps unevaluated points (``ev_loss IS NULL``): those moves
        were never scored, which is not the same as a loss of zero.

        ``annotation`` filters by exact label; pass ``""`` to keep only unlabeled rows.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if experiment_id:
            conditions.append("game_id IN (SELECT id FROM games WHERE experiment_id = ?)")
            params.append(experiment_id)
        if game_id:
            conditions.append("game_id = ?")
            params.append(game_id)
        if player_id:
            conditions.append("player_id = ?")
            params.append(player_id)
        if game_phase:
            conditions.append("game_phase = ?")
            params.append(game_phase)
        if outcome:
            conditions.append("outcome = ?")
            params.append(outcome)
        if train_usable is not None:
            conditions.append("train_usable = ?")
            params.append(1 if train_usable else 0)
        if max_ev_loss is not None:
            conditions.append("(ev_loss IS NULL OR ev_loss <= ?)")
            params.append(max_ev_loss)
        if annotation is not None:
            if annotation == "":
                conditions.append("annotation IS NULL")
            else:
                conditions.append("annotation = ?")
                params.append(annotation)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) as total FROM decision_points {where_clause}",
            params,
        )
        count_row = await count_cursor.fetchone()
        total = count_row["total"] if count_row else 0

        cursor = await self._db.execute(
            f"""
            SELECT decision_points.*, {_TRACE_EXPLAIN_SQL}
            FROM decision_points
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
            f"""
            SELECT decision_points.*, {_TRACE_EXPLAIN_SQL}
            FROM decision_points
            WHERE id = ?
            """,
            (decision_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def evidence_sequence(self, game_id: str, cutoff: str) -> list[dict[str, Any]]:
        """Bound one game's records at the comparison's frozen cutoff."""
        async with self._db.execute(
            f"SELECT dp.*, {SCENARIO_SQL} AS scenario FROM decision_points dp "
            "WHERE game_id = ? AND created_at <= ? "
            "ORDER BY round_number, id LIMIT 2001",
            (game_id, cutoff),
        ) as cursor:
            return [
                {**_row_to_dict(row), "scenario": row["scenario"]}
                for row in await cursor.fetchall()
            ]

    async def evidence_scenario_counts(
        self, game_ids: list[str], cutoff: str
    ) -> list[dict[str, Any]]:
        """Current records inside frozen membership and the snapshot cutoff."""
        async with self._db.execute(
            f"SELECT dp.game_id, {SCENARIO_SQL} AS scenario, COUNT(*) AS n "
            "FROM decision_points dp "
            "WHERE dp.game_id IN (SELECT value FROM json_each(?)) AND dp.created_at <= ? "
            "GROUP BY dp.game_id, scenario",
            (json.dumps(game_ids), cutoff),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def update_annotation(self, decision_id: str, annotation: str | None) -> bool:
        """Set or clear human annotation. Returns False if the row is missing."""
        cursor = await self._db.execute(
            "UPDATE decision_points SET annotation = ? WHERE id = ?",
            (annotation, decision_id),
        )
        await self._db.commit()
        return (cursor.rowcount or 0) > 0

    async def count_total(self, experiment_id: str | None = None) -> int:
        """Count total decision points, optionally scoped to an experiment."""
        where, params = self._experiment_where(experiment_id)
        return int(await self._scalar(f"SELECT COUNT(*) FROM decision_points{where}", params))

    async def count_usability(self, experiment_id: str | None = None) -> dict[str, int]:
        where, params = self._experiment_where(experiment_id)
        cursor = await self._db.execute(
            f"""
            SELECT
                SUM(CASE WHEN train_usable = 1 THEN 1 ELSE 0 END) AS usable,
                SUM(CASE WHEN train_usable = 0 THEN 1 ELSE 0 END) AS not_usable,
                COUNT(*) AS total
            FROM decision_points
            {where}
            """,
            params,
        )
        row = await cursor.fetchone()
        if row is None:
            return {"usable": 0, "not_usable": 0, "total": 0}
        return {
            "usable": int(row["usable"] or 0),
            "not_usable": int(row["not_usable"] or 0),
            "total": int(row["total"] or 0),
        }

    async def get_ev_loss_stats(
        self,
        experiment_id: str | None = None,
        *,
        blunder_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """EV loss aggregates over evaluated decisions only.

        ``evaluated_count`` is reported next to the averages so a small average
        over three decisions is not mistaken for a claim about the whole run.
        """
        where, params = self._experiment_where(experiment_id, extra="ev_loss IS NOT NULL")
        cursor = await self._db.execute(
            f"""
            SELECT
                COUNT(*) AS evaluated_count,
                AVG(ev_loss) AS avg_ev_loss,
                MAX(ev_loss) AS max_ev_loss,
                SUM(CASE WHEN ev_loss >= ? THEN 1 ELSE 0 END) AS blunder_count
            FROM decision_points
            {where}
            """,
            [blunder_threshold, *params],
        )
        row = await cursor.fetchone()
        if row is None or not row["evaluated_count"]:
            return {
                "evaluated_count": 0,
                "avg_ev_loss": None,
                "max_ev_loss": None,
                "blunder_count": 0,
            }
        return {
            "evaluated_count": int(row["evaluated_count"]),
            "avg_ev_loss": float(row["avg_ev_loss"]),
            "max_ev_loss": float(row["max_ev_loss"]),
            "blunder_count": int(row["blunder_count"] or 0),
        }

    async def get_outcome_counts(self, experiment_id: str | None = None) -> dict[str, int]:
        """Return counts grouped by outcome."""
        where, params = self._experiment_where(experiment_id, extra="outcome IS NOT NULL")
        cursor = await self._db.execute(
            f"""
            SELECT outcome, COUNT(*) as count
            FROM decision_points
            {where}
            GROUP BY outcome
            """,
            params,
        )
        rows = await cursor.fetchall()
        return {row["outcome"]: row["count"] for row in rows}

    async def latest_progress_by_game_ids(
        self,
        game_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Latest decision snapshot per game (phase / round / player)."""
        if not game_ids:
            return {}
        placeholders = ",".join("?" * len(game_ids))
        cursor = await self._db.execute(
            f"""
            SELECT game_id, game_phase, player_id, round_number
            FROM (
                SELECT
                    game_id,
                    game_phase,
                    player_id,
                    round_number,
                    ROW_NUMBER() OVER (
                        PARTITION BY game_id
                        ORDER BY created_at DESC, round_number DESC
                    ) AS rn
                FROM decision_points
                WHERE game_id IN ({placeholders})
            )
            WHERE rn = 1
            """,
            game_ids,
        )
        rows = await cursor.fetchall()
        return {
            str(row["game_id"]): {
                "game_phase": row["game_phase"],
                "player_id": row["player_id"],
                "round_number": int(row["round_number"]),
            }
            for row in rows
        }

    async def get_phase_counts(self, experiment_id: str | None = None) -> dict[str, int]:
        """Return counts grouped by game_phase."""
        where, params = self._experiment_where(experiment_id)
        cursor = await self._db.execute(
            f"""
            SELECT game_phase, COUNT(*) as count
            FROM decision_points
            {where}
            GROUP BY game_phase
            """,
            params,
        )
        rows = await cursor.fetchall()
        return {row["game_phase"]: row["count"] for row in rows}

    async def count_not_usable_by_reason(
        self,
        experiment_id: str | None = None,
    ) -> dict[str, int]:
        """Return counts grouped by train_usable_reason for not-usable samples."""
        where, params = self._experiment_where(
            experiment_id,
            extra="train_usable = 0",
        )
        cursor = await self._db.execute(
            f"""
            SELECT train_usable_reason AS reason, COUNT(*) AS count
            FROM decision_points
            {where}
            GROUP BY train_usable_reason
            ORDER BY count DESC
            """,
            params,
        )
        rows = await cursor.fetchall()
        return {str(row["reason"]): int(row["count"]) for row in rows}

    def _experiment_where(
        self,
        experiment_id: str | None,
        *,
        extra: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if experiment_id:
            clauses.append("game_id IN (SELECT id FROM games WHERE experiment_id = ?)")
            params.append(experiment_id)
        if extra:
            clauses.append(extra)
        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    async def _scalar(self, sql: str, params: list[Any] | None = None) -> int | float:
        cursor = await self._db.execute(sql, params or [])
        row = await cursor.fetchone()
        value = row[0] if row else 0
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return float(value)


def _parse_json_object(raw: Any) -> dict[str, Any] | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _parse_json_list(raw: Any) -> list[Any] | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a decision_points row to a dictionary with JSON fields parsed.

    The tool columns are optional because only the detail queries join the trace
    that carries them; every ``decision_points`` column is always present.
    """
    keys = set(row.keys())
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
        "action_id": row["action_id"],
        "prompt_messages": json.loads(row["prompt_messages"]) if row["prompt_messages"] else None,
        "thinking": row["thinking"],
        "outcome": row["outcome"],
        "train_usable": bool(row["train_usable"]),
        "train_usable_reason": row["train_usable_reason"],
        "parse_fallback": bool(row["parse_fallback"]),
        "parser_ok": not row["parse_fallback"],
        "ev_loss": row["ev_loss"],
        "evaluator_params": _parse_json_object(row["evaluator_params"]),
        "policy_kind": row["policy_kind"] if "policy_kind" in keys else "llm",
        "tool_calls": _parse_json_list(row["tool_calls"] if "tool_calls" in keys else None),
        "annotation": row["annotation"] if "annotation" in keys else None,
        "created_at": row["created_at"],
        "hand_analysis": _parse_json_object(
            row["hand_analysis_json"] if "hand_analysis_json" in keys else None
        ),
    }
