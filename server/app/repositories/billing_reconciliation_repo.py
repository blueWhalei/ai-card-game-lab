"""Append-only comparison evidence and review events. Callers own transactions."""

from typing import Any

import aiosqlite

RECORD_SELECT = """SELECT r.*,COALESCE(e.revision,0) AS review_revision,
    e.action AS review_action,e.reason AS review_reason,e.created_at AS reviewed_at
    FROM billing_reconciliations r LEFT JOIN billing_reconciliation_reviews e
    ON e.record_id=r.id AND e.revision=(SELECT MAX(v.revision)
    FROM billing_reconciliation_reviews v WHERE v.record_id=r.id) """


class BillingReconciliationRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def policy(self, study_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM billing_reconciliation_policies WHERE study_id=? "
            "ORDER BY revision DESC LIMIT 1",
            (study_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def policy_history(self, study_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM billing_reconciliation_policies WHERE study_id=? "
            "ORDER BY revision DESC LIMIT 10",
            (study_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def set_policy(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            "INSERT INTO billing_reconciliation_policies VALUES "
            "(:study_id,:revision,:enabled,:reason,:created_at)",
            row,
        )

    async def pending_count(self, study_id: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM (" + RECORD_SELECT + ") WHERE study_id=? "
            "AND result!='matched' AND (review_action IS NULL OR review_action='reopen')",
            (study_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def record(self, study_id: str, record_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            RECORD_SELECT + "WHERE r.study_id=? AND r.id=?", (study_id, record_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def request(self, study_id: str, request_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            RECORD_SELECT + "WHERE r.study_id=? AND r.request_id=?", (study_id, request_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def records(self, study_id: str, page: int) -> tuple[list[dict[str, Any]], int]:
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM billing_reconciliations WHERE study_id=?", (study_id,)
        )
        count = await cursor.fetchone()
        cursor = await self.db.execute(
            RECORD_SELECT
            + "WHERE r.study_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 10 OFFSET ?",
            (study_id, (page - 1) * 10),
        )
        return [dict(row) for row in await cursor.fetchall()], int(count[0]) if count else 0

    async def save(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            "INSERT INTO billing_reconciliations VALUES "
            "(:id,:study_id,:attempt_id,:request_id,:request_hash,:result,:comparison_json,:created_at)",
            row,
        )

    async def review(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            "INSERT INTO billing_reconciliation_reviews VALUES "
            "(:record_id,:revision,:action,:reason,:created_at)",
            row,
        )

    async def reviews(self, record_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM billing_reconciliation_reviews WHERE record_id=? ORDER BY revision",
            (record_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
