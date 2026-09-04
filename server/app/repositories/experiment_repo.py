"""Experiment (run) data access layer (SQLite)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.core.stats.scenarios import SCENARIO_SQL, fill_scenario_scores


class ExperimentRepository:
    """CRUD operations for the ``experiments`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        experiment_id: str,
        name: str,
        notes: str,
        game_type: str,
        player_ids: list[str],
        target_games: int,
        created_at: str,
        updated_at: str,
        protocol: dict[str, Any] | None = None,
        *,
        hypothesis: str = "",
        conclusion: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        tag_list = tags or []
        await self._db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, hypothesis, conclusion, tags, game_type, player_ids,
                target_games, protocol, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                name,
                notes,
                hypothesis,
                conclusion,
                json.dumps(tag_list, ensure_ascii=False),
                game_type,
                json.dumps(player_ids, ensure_ascii=False),
                target_games,
                json.dumps(protocol, ensure_ascii=False) if protocol is not None else None,
                created_at,
                updated_at,
            ),
        )
        await self._db.commit()
        return await self.get_by_id(experiment_id)

    async def update_protocol(
        self,
        experiment_id: str,
        protocol: dict[str, Any],
        *,
        updated_at: str | None = None,
    ) -> None:
        if updated_at is not None:
            await self._db.execute(
                "UPDATE experiments SET protocol = ?, updated_at = ? WHERE id = ?",
                (json.dumps(protocol, ensure_ascii=False), updated_at, experiment_id),
            )
        else:
            await self._db.execute(
                "UPDATE experiments SET protocol = ? WHERE id = ?",
                (json.dumps(protocol, ensure_ascii=False), experiment_id),
            )
        await self._db.commit()

    async def get_by_id(self, experiment_id: str) -> dict[str, Any]:
        cursor = await self._db.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(experiment_id)
        return _row_to_dict(row)

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]

    async def touch_updated_at(self, experiment_id: str, updated_at: str) -> None:
        await self._db.execute(
            "UPDATE experiments SET updated_at = ? WHERE id = ?",
            (updated_at, experiment_id),
        )
        await self._db.commit()

    async def update_fields(
        self,
        experiment_id: str,
        *,
        updated_at: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        if not fields:
            return await self.get_by_id(experiment_id)
        allowed = {"name", "notes", "hypothesis", "conclusion", "tags"}
        parts: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "tags":
                value = json.dumps(list(value), ensure_ascii=False)
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return await self.get_by_id(experiment_id)
        parts.append("updated_at = ?")
        values.append(updated_at)
        values.append(experiment_id)
        await self._db.execute(
            f"UPDATE experiments SET {', '.join(parts)} WHERE id = ?",
            tuple(values),
        )
        await self._db.commit()
        return await self.get_by_id(experiment_id)

    async def list_control_experiments(self, source_experiment_id: str) -> list[dict[str, Any]]:
        """Experiments whose protocol.source_experiment_id points to source."""
        cursor = await self._db.execute(
            "SELECT id, name, created_at, protocol FROM experiments ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            raw_protocol = data.get("protocol")
            protocol: dict[str, Any] = {}
            if isinstance(raw_protocol, str):
                try:
                    parsed = json.loads(raw_protocol)
                    if isinstance(parsed, dict):
                        protocol = parsed
                except json.JSONDecodeError:
                    protocol = {}
            if str(protocol.get("source_experiment_id") or "") == source_experiment_id:
                results.append(
                    {
                        "id": str(data["id"]),
                        "name": str(data["name"]),
                        "created_at": str(data["created_at"]),
                    }
                )
        return results

    async def first_game_timestamps(self, experiment_id: str) -> dict[str, str | None]:
        cursor = await self._db.execute(
            """
            SELECT MIN(created_at) AS first_created,
                   MIN(finished_at) AS first_finished
            FROM games
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return {"first_collect": None, "first_finished": None}
        return {
            "first_collect": row["first_created"],
            "first_finished": row["first_finished"],
        }

    async def first_dataset_at(self, experiment_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT created_at, filters FROM datasets ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        for row in rows:
            raw_filters = row["filters"]
            filters: dict[str, Any] = {}
            if isinstance(raw_filters, str):
                try:
                    parsed = json.loads(raw_filters)
                    if isinstance(parsed, dict):
                        filters = parsed
                except json.JSONDecodeError:
                    filters = {}
            if str(filters.get("experiment_id") or "") == experiment_id:
                return str(row["created_at"])
        return None

    async def first_training_completed_at(self, experiment_id: str) -> str | None:
        cursor = await self._db.execute(
            """
            SELECT finished_at FROM training_tasks
            WHERE experiment_id = ? AND status = 'completed' AND finished_at IS NOT NULL
            ORDER BY finished_at ASC LIMIT 1
            """,
            (experiment_id,),
        )
        row = await cursor.fetchone()
        return str(row["finished_at"]) if row and row["finished_at"] else None

    async def count_decisions_by_usability(self, experiment_id: str) -> dict[str, int]:
        cursor = await self._db.execute(
            """
            SELECT
                SUM(CASE WHEN dp.train_usable = 1 THEN 1 ELSE 0 END) AS usable,
                SUM(CASE WHEN dp.train_usable = 0 THEN 1 ELSE 0 END) AS not_usable,
                COUNT(*) AS total
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return {"usable": 0, "not_usable": 0, "total": 0}
        return {
            "usable": int(row["usable"] or 0),
            "not_usable": int(row["not_usable"] or 0),
            "total": int(row["total"] or 0),
        }

    async def list_games(self, experiment_id: str) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            """
            SELECT * FROM games
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_train_usable_decisions(self, experiment_id: str) -> int:
        cursor = await self._db.execute(
            """
            SELECT COUNT(*) AS total
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ? AND dp.train_usable = 1
            """,
            (experiment_id,),
        )
        row = await cursor.fetchone()
        return int(row["total"] if row else 0)

    async def count_train_usable_by_player(self, experiment_id: str) -> dict[str, int]:
        """Count train_usable decision points per player within an experiment."""
        cursor = await self._db.execute(
            """
            SELECT dp.player_id AS player_id, COUNT(*) AS total
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ? AND dp.train_usable = 1
            GROUP BY dp.player_id
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        return {str(r["player_id"]): int(r["total"]) for r in rows}

    async def avg_response_ms_by_player(
        self,
        experiment_id: str,
    ) -> dict[str, tuple[float, int]]:
        """Average response_time_ms and round count per player (from rounds)."""
        cursor = await self._db.execute(
            """
            SELECT
                r.player_id AS player_id,
                AVG(r.response_time_ms) AS avg_ms,
                COUNT(*) AS total
            FROM rounds r
            INNER JOIN games g ON g.id = r.game_id
            WHERE g.experiment_id = ? AND r.response_time_ms IS NOT NULL
            GROUP BY r.player_id
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        result: dict[str, tuple[float, int]] = {}
        for r in rows:
            avg_raw = r["avg_ms"]
            avg_ms = round(float(avg_raw), 2) if avg_raw is not None else 0.0
            result[str(r["player_id"])] = (avg_ms, int(r["total"]))
        return result

    async def eval_aggregates(self, experiment_id: str) -> dict[str, Any]:
        """Experiment-level evaluation metrics from games / rounds / traces / decisions."""
        decision_cursor = await self._db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN dp.train_usable = 1 THEN 1 ELSE 0 END) AS usable
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        decision_row = await decision_cursor.fetchone()
        decision_count = int(decision_row["total"] if decision_row else 0)
        train_usable_n = int(decision_row["usable"] or 0) if decision_row else 0

        round_cursor = await self._db.execute(
            """
            SELECT
                AVG(r.response_time_ms) AS avg_ms,
                SUM(r.total_tokens) AS tokens,
                AVG(r.total_tokens) AS avg_tokens
            FROM rounds r
            INNER JOIN games g ON g.id = r.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        round_row = await round_cursor.fetchone()
        avg_ms_raw = round_row["avg_ms"] if round_row else None
        tokens_raw = round_row["tokens"] if round_row else None
        avg_tokens_raw = round_row["avg_tokens"] if round_row else None

        pct_cursor = await self._db.execute(
            """
            SELECT r.response_time_ms
            FROM rounds r
            INNER JOIN games g ON g.id = r.game_id
            WHERE g.experiment_id = ? AND r.response_time_ms IS NOT NULL
            ORDER BY r.response_time_ms
            """,
            (experiment_id,),
        )
        pct_rows = await pct_cursor.fetchall()
        p50_ms, p95_ms = 0.0, 0.0
        if pct_rows:
            n = len(pct_rows)
            p50_idx = min(int(n * 0.5), n - 1)
            p95_idx = min(int(n * 0.95), n - 1)
            p50_ms = round(float(pct_rows[p50_idx][0]), 1)
            p95_ms = round(float(pct_rows[p95_idx][0]), 1)

        parser_cursor = await self._db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE WHEN json_extract(t.metrics, '$.used_langchain_parser') = 1
                    THEN 1 ELSE 0 END
                ) AS parser_ok
            FROM traces t
            INNER JOIN games g ON g.id = t.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        parser_row = await parser_cursor.fetchone()
        parser_n = int(parser_row["total"] if parser_row else 0)
        parser_ok = int(parser_row["parser_ok"] or 0) if parser_row else 0

        games_cursor = await self._db.execute(
            """
            SELECT id, status, winner_id, winner_role, metadata
            FROM games
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        )
        game_rows = await games_cursor.fetchall()

        wins_by_role: dict[str, int] = {"landlord": 0, "peasant": 0}
        decisive_games = 0
        finished_games = 0
        status_counts: dict[str, int] = {
            "finished": 0,
            "failed": 0,
            "cancelled": 0,
            "interrupted": 0,
            "no_bid": 0,
        }
        landlord_games: dict[str, int] = {}
        landlord_wins: dict[str, int] = {}

        for g in game_rows:
            status = str(g["status"] or "")
            role = str(g["winner_role"] or "") if g["winner_role"] else ""
            if status == "finished":
                finished_games += 1
                if role == "no_bid":
                    status_counts["no_bid"] += 1
                else:
                    status_counts["finished"] += 1
            elif status in status_counts:
                status_counts[status] = status_counts.get(status, 0) + 1

            if role in ("landlord", "peasant"):
                decisive_games += 1
                wins_by_role[role] = wins_by_role.get(role, 0) + 1

            meta_raw = g["metadata"]
            meta: dict[str, Any] = {}
            if isinstance(meta_raw, str):
                try:
                    parsed = json.loads(meta_raw)
                    if isinstance(parsed, dict):
                        meta = parsed
                except json.JSONDecodeError:
                    meta = {}
            elif isinstance(meta_raw, dict):
                meta = meta_raw

            landlord_id = meta.get("landlord_id")
            if landlord_id and status == "finished" and role in ("landlord", "peasant"):
                lid = str(landlord_id)
                landlord_games[lid] = landlord_games.get(lid, 0) + 1
                if g["winner_id"] and str(g["winner_id"]) == lid:
                    landlord_wins[lid] = landlord_wins.get(lid, 0) + 1

        landlord_role_wins = wins_by_role.get("landlord", 0)
        landlord_win_rate = (
            landlord_role_wins / decisive_games if decisive_games > 0 else 0.0
        )
        tokens_total = int(tokens_raw) if tokens_raw is not None else 0
        tokens_per_game = (
            round(tokens_total / finished_games, 2) if finished_games > 0 else 0.0
        )
        parser_rate = (parser_ok / parser_n) if parser_n else 0.0
        train_rate = (train_usable_n / decision_count) if decision_count else 0.0
        scenario_scores = await self._scenario_aggregates(experiment_id)

        return {
            "decision_count": decision_count,
            "train_usable_n": train_usable_n,
            "train_usable_rate": round(train_rate, 4),
            "scenario_scores": scenario_scores,
            "avg_response_time_ms": (
                round(float(avg_ms_raw), 2) if avg_ms_raw is not None else 0.0
            ),
            "p50_response_ms": p50_ms,
            "p95_response_ms": p95_ms,
            "total_tokens": tokens_total,
            "avg_tokens_per_round": (
                round(float(avg_tokens_raw), 2) if avg_tokens_raw is not None else 0.0
            ),
            "tokens_per_game": tokens_per_game,
            "parser_n": parser_n,
            "parser_ok": parser_ok,
            "parser_success_rate": round(parser_rate, 4),
            "wins_by_role": wins_by_role,
            "decisive_games": decisive_games,
            "landlord_win_rate": round(landlord_win_rate, 4),
            "status_counts": status_counts,
            "landlord_games_by_player": landlord_games,
            "landlord_wins_by_player": landlord_wins,
            "finished_games": finished_games,
        }

    async def _scenario_aggregates(self, experiment_id: str) -> dict[str, dict[str, Any]]:
        """Train-usable / parser rates by bidding, playing, endgame, bomb."""
        cursor = await self._db.execute(
            f"""
            SELECT
              scenario,
              COUNT(*) AS n,
              SUM(usable) AS usable,
              SUM(has_trace) AS parser_n,
              SUM(parser_ok) AS parser_ok
            FROM (
              SELECT
                {SCENARIO_SQL} AS scenario,
                CASE WHEN dp.train_usable = 1 THEN 1 ELSE 0 END AS usable,
                MAX(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) AS has_trace,
                MAX(
                  CASE WHEN json_extract(t.metrics, '$.used_langchain_parser') = 1
                  THEN 1 ELSE 0 END
                ) AS parser_ok
              FROM decision_points dp
              INNER JOIN games g ON g.id = dp.game_id
              LEFT JOIN traces t
                ON t.game_id = dp.game_id
               AND t.round_number = dp.round_number
               AND t.player_id = dp.player_id
              WHERE g.experiment_id = ?
              GROUP BY dp.id
            )
            GROUP BY scenario
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            grouped[str(row["scenario"])] = {
                "n": int(row["n"] or 0),
                "train_usable_n": int(row["usable"] or 0),
                "parser_n": int(row["parser_n"] or 0),
                "parser_ok": int(row["parser_ok"] or 0),
            }
        return fill_scenario_scores(grouped)

    async def compare_aggregates(self, experiment_id: str) -> dict[str, Any]:
        """Backward-compatible alias for eval_aggregates."""
        return await self.eval_aggregates(experiment_id)

def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    data = dict(row)
    raw_players = data.get("player_ids")
    if isinstance(raw_players, str):
        data["player_ids"] = json.loads(raw_players)
    raw_protocol = data.get("protocol")
    if isinstance(raw_protocol, str):
        data["protocol"] = json.loads(raw_protocol)
    raw_tags = data.get("tags")
    if isinstance(raw_tags, str):
        try:
            parsed_tags = json.loads(raw_tags)
            data["tags"] = parsed_tags if isinstance(parsed_tags, list) else []
        except json.JSONDecodeError:
            data["tags"] = []
    elif raw_tags is None:
        data["tags"] = []
    for text_key in ("hypothesis", "conclusion"):
        if data.get(text_key) is None:
            data[text_key] = ""
    return data
