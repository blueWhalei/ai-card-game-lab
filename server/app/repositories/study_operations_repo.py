"""Read current game tasks and saved usage without multiplying joined records."""

from typing import Any

import aiosqlite

TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")
MAX_SAFE_INTEGER = 2**53 - 1

COUNTS = """
WITH counts AS (
 SELECT e.id, e.name, e.target_games, e.updated_at,
   COUNT(g.id) AS game_count,
   COALESCE(SUM(g.status IN ('created','pending')),0) AS waiting,
   COALESCE(SUM(g.status='running'),0) AS running,
   COALESCE(SUM(g.status='paused'),0) AS paused,
   COALESCE(SUM(g.status='finished'),0) AS finished,
   COALESCE(SUM(g.status='failed'),0) AS failed,
   COALESCE(SUM(g.status='interrupted'),0) AS interrupted,
   COALESCE(SUM(g.status='cancelled'),0) AS cancelled,
   COALESCE(SUM(g.id IS NOT NULL AND (g.status IS NULL OR g.status NOT IN
     ('created','pending','running','paused','finished','failed','interrupted','cancelled'))),0) AS unknown,
   COALESCE(SUM(g.status='finished' AND g.winner_role='no_bid'),0) AS no_bid
 FROM experiments e JOIN study_runs sr ON sr.experiment_id=e.id
 LEFT JOIN games g ON g.experiment_id=e.id
 WHERE sr.study_id=? GROUP BY e.id
)
"""


class StudyOperationsRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def runs(self, study_id: str, state: str, page: int) -> tuple[list[dict[str, Any]], int]:
        where = {
            "all": "",
            "active": "WHERE waiting + running + paused > 0",
            "attention": "WHERE failed + interrupted + unknown > 0",
        }[state]
        cursor = await self.db.execute(COUNTS + f"SELECT COUNT(*) FROM counts {where}", (study_id,))
        row = await cursor.fetchone()
        total = int(row[0]) if row else 0
        cursor = await self.db.execute(
            COUNTS
            + f"SELECT * FROM counts {where} ORDER BY updated_at DESC, id DESC LIMIT 20 OFFSET ?",
            (study_id, (page - 1) * 20),
        )
        return [dict(row) for row in await cursor.fetchall()], total

    async def usage(self, run_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not run_ids:
            return {}
        parts = []
        for field in TOKEN_FIELDS:
            value = f"json_extract(body, '$.{field}')"
            kind = f"json_type(body, '$.{field}')"
            valid = f"json_type(body)='object' AND {kind}='integer' AND {value} BETWEEN 0 AND {MAX_SAFE_INTEGER}"
            missing = (
                f"well_formed AND json_type(body)='object' AND ({kind} IS NULL OR {kind}='null')"
            )
            parts.extend(
                [
                    f"SUM(CASE WHEN {valid} THEN 1 ELSE 0 END) AS {field}_count",
                    f"SUM(CASE WHEN {missing} THEN 1 ELSE 0 END) AS {field}_missing",
                    # REAL avoids SQLite integer overflow; the service rejects unsafe totals.
                    f"TOTAL(CASE WHEN {valid} THEN {value} ELSE NULL END) AS {field}_sum",
                ]
            )
        marks = ",".join("?" for _ in run_ids)
        cursor = await self.db.execute(
            f"""WITH records AS (
              SELECT g.experiment_id, json_valid(t.metrics) AS well_formed,
                CASE WHEN json_valid(t.metrics) THEN t.metrics ELSE '{{}}' END AS body
              FROM traces t JOIN games g ON g.id=t.game_id
              WHERE g.experiment_id IN ({marks})
            ) SELECT experiment_id, COUNT(*) AS trace_count, {",".join(parts)}
              FROM records GROUP BY experiment_id""",
            run_ids,
        )
        return {row["experiment_id"]: dict(row) for row in await cursor.fetchall()}
