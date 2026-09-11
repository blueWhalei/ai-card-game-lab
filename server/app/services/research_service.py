"""Freeze cited decisions with an append-only conclusion revision."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.decision_repo import DecisionRepository
from app.repositories.research_repo import ResearchRepository
from app.utils.id_generator import generate_id

EVIDENCE_FIELDS = (
    "id",
    "game_id",
    "player_id",
    "round_number",
    "created_at",
    "game_phase",
    "hand_cards",
    "opponent_hands",
    "last_action",
    "legal_actions",
    "action_id",
    "chosen_action",
    "train_usable",
    "train_usable_reason",
    "parse_fallback",
    "ev_loss",
    "evaluator_params",
    "policy_kind",
    "annotation",
    "outcome",
    "quality_score",
)


class ResearchConflictError(Exception):
    """A conclusion changed while the user was editing."""


class ResearchValidationError(ValueError):
    """Evidence does not belong to the frozen comparison scope."""


class ResearchMixin:
    async def _conn(self) -> aiosqlite.Connection:
        raise NotImplementedError

    @staticmethod
    def _scope(snapshot: dict[str, Any]) -> tuple[list[str], str]:
        result = snapshot["result"]
        return [gid for row in result["experiments"] for gid in row["game_ids"]], result[
            "computed_at"
        ]

    async def research_candidates(
        self, comparison_id: str, limit: int, offset: int
    ) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            game_ids, cutoff = self._scope(snapshot)
            return await ResearchRepository(db).candidates(game_ids, cutoff, limit, offset)
        finally:
            await db.close()

    async def research_versions(
        self, comparison_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        db = await self._conn()
        try:
            await ComparisonRepository(db).get(comparison_id)
            return await ResearchRepository(db).list_versions(comparison_id, limit, offset)
        finally:
            await db.close()

    async def save_research(
        self,
        comparison_id: str,
        expected_revision: int,
        observations: str,
        interpretation: str,
        limitations: str,
        evidence: list[dict[str, str]],
    ) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN IMMEDIATE")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            game_ids, cutoff = self._scope(snapshot)
            repo = ResearchRepository(db)
            latest = await repo.latest(comparison_id)
            if latest != expected_revision:
                raise ResearchConflictError("结论已有新版本，请刷新版本列表后再保存")
            ids = [item["decision_id"] for item in evidence]
            if len(ids) != len(set(ids)):
                raise ResearchValidationError("同一决策只能引用一次")
            frozen = []
            for item in evidence:
                decision = await DecisionRepository(db).get_by_id(item["decision_id"])
                if (
                    decision is None
                    or decision["game_id"] not in game_ids
                    or decision["created_at"] > cutoff
                ):
                    raise ResearchValidationError("证据已不存在或不属于比较快照的数据范围")
                frozen.append(
                    {
                        "note": item["note"].strip(),
                        "decision": {key: decision.get(key) for key in EVIDENCE_FIELDS},
                    }
                )
            record = {
                "id": generate_id("rev"),
                "comparison_id": comparison_id,
                "revision": latest + 1,
                "created_at": datetime.now(UTC).isoformat(),
                "observations": observations.strip(),
                "interpretation": interpretation.strip(),
                "limitations": limitations.strip(),
                "evidence": frozen,
            }
            await repo.create(record)
            await db.commit()
            return {"record": record, "evidence_status": {d: "available" for d in ids}}
        finally:
            await db.close()

    async def get_research(self, revision_id: str, export: bool = False) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            repo = ResearchRepository(db)
            record = await repo.get(revision_id)
            status = await repo.evidence_status(record["evidence"])
            response: dict[str, Any] = {"record": record, "evidence_status": status}
            if export:
                response.update(
                    {
                        "kind": "cardlab.research_report",
                        "exported_at": datetime.now(UTC).isoformat(),
                        "comparison": await ComparisonRepository(db).get(record["comparison_id"]),
                        "scope": "Frozen comparison and selected decision evidence; not a runnable environment or a full game archive.",
                    }
                )
            return response
        finally:
            await db.close()
