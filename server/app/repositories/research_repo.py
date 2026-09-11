"""Append-only conclusions and decision evidence scoped to a comparison."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.repositories.decision_repo import DecisionRepository


class ResearchRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def candidates(
        self, game_ids: list[str], cutoff: str, limit: int, offset: int
    ) -> dict[str, Any]:
        predicate = "game_id IN (SELECT value FROM json_each(?)) AND created_at <= ?"
        params = (json.dumps(game_ids), cutoff)
        async with self.db.execute(
            f"SELECT COUNT(*) FROM decision_points WHERE {predicate}", params
        ) as cursor:
            count = await cursor.fetchone()
        async with self.db.execute(
            f"SELECT id, game_id, player_id, round_number, action_id, ev_loss, annotation FROM decision_points WHERE {predicate} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return {
            "total": count[0] if count else 0,
            "items": [
                dict(
                    zip(
                        (
                            "id",
                            "game_id",
                            "player_id",
                            "round_number",
                            "action_id",
                            "ev_loss",
                            "annotation",
                        ),
                        row,
                        strict=True,
                    )
                )
                for row in rows
            ],
        }

    async def latest(self, comparison_id: str) -> int:
        async with self.db.execute(
            "SELECT COALESCE(MAX(revision), 0) FROM research_revisions WHERE comparison_id = ?",
            (comparison_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def create(self, record: dict[str, Any]) -> None:
        await self.db.execute(
            "INSERT INTO research_revisions (id, comparison_id, revision, created_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                record["id"],
                record["comparison_id"],
                record["revision"],
                record["created_at"],
                json.dumps(record, ensure_ascii=False, allow_nan=False),
            ),
        )

    async def get(self, revision_id: str) -> dict[str, Any]:
        async with self.db.execute(
            "SELECT payload FROM research_revisions WHERE id = ?", (revision_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(revision_id)
        return json.loads(row[0])  # type: ignore[no-any-return]

    async def list_versions(
        self, comparison_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        async with self.db.execute(
            "SELECT id, revision, created_at FROM research_revisions WHERE comparison_id = ? ORDER BY revision DESC LIMIT ? OFFSET ?",
            (comparison_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"id": r[0], "revision": r[1], "created_at": r[2]} for r in rows]

    async def evidence_status(self, evidence: list[dict[str, Any]]) -> dict[str, str]:
        statuses = {}
        decisions = DecisionRepository(self.db)
        for item in evidence:
            saved = item["decision"]
            current = await decisions.get_by_id(saved["id"])
            if current is None:
                statuses[saved["id"]] = "missing"
            elif any(
                current.get(key) != saved.get(key)
                for key in ("game_id", "player_id", "round_number", "created_at")
            ):
                statuses[saved["id"]] = "identity_mismatch"
            elif any(current.get(key) != val for key, val in saved.items()):
                statuses[saved["id"]] = "changed"
            else:
                statuses[saved["id"]] = "available"
        return statuses
