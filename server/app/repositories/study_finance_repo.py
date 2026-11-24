"""Append-only budget versions and expenses with retained void records."""

from typing import Any

import aiosqlite


class StudyFinanceRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def budget(self, study_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM study_budget_revisions WHERE study_id=? ORDER BY revision DESC LIMIT 1",
            (study_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def history(self, study_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM study_budget_revisions WHERE study_id=? ORDER BY revision DESC LIMIT 20",
            (study_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def add_budget(self, data: dict[str, Any]) -> None:
        await self.db.execute(
            """INSERT INTO study_budget_revisions
            (study_id,revision,currency,limit_units,enforcement_enabled,reason,created_at)
            VALUES (:study_id,:revision,:currency,:limit_units,:enforcement_enabled,:reason,:created_at)
            """,
            data,
        )

    async def totals(self, study_id: str) -> tuple[int, int, int]:
        # Python integers avoid SQLite SUM overflow. No floating point is used.
        cursor = await self.db.execute(
            "SELECT amount_units,voided_at FROM study_expenses WHERE study_id=?", (study_id,)
        )
        total = count = voided = 0
        async for row in cursor:
            if row["voided_at"] is None:
                total += row["amount_units"]
                count += 1
            else:
                voided += 1
        return total, count, voided

    async def expenses(self, study_id: str, page: int) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM study_expenses WHERE study_id=? "
            "ORDER BY created_at DESC,id DESC LIMIT 20 OFFSET ?",
            (study_id, (page - 1) * 20),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def by_request(self, study_id: str, request_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM study_expenses WHERE study_id=? AND request_id=?",
            (study_id, request_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def expense(self, study_id: str, entry_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM study_expenses WHERE study_id=? AND id=?", (study_id, entry_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def add_expense(self, data: dict[str, Any]) -> None:
        await self.db.execute(
            """INSERT INTO study_expenses
            (id,study_id,request_id,currency,amount_units,incurred_on,source_type,
             source_reference,scope_description,created_at)
            VALUES (:id,:study_id,:request_id,:currency,:amount_units,:incurred_on,:source_type,
             :source_reference,:scope_description,:created_at)""",
            data,
        )

    async def void(self, study_id: str, entry_id: str, reason: str, now: str) -> None:
        await self.db.execute(
            "UPDATE study_expenses SET voided_at=?,void_reason=? WHERE study_id=? AND id=?",
            (now, reason, study_id, entry_id),
        )
