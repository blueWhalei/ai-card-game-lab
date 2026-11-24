"""Freeze cited decisions with an append-only conclusion revision."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.core.engine.base import GameEngine
from app.core.research.decision_alignment import align_decisions, comparison_members
from app.core.stats.scenarios import ENDGAME_MAX_HAND, SCENARIO_IDS
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.decision_repo import DecisionRepository
from app.repositories.game_repo import GameRepository
from app.repositories.research_repo import ResearchRepository
from app.repositories.round_repo import RoundRepository
from app.services.decision_replay import comparison_boards
from app.services.puzzle_service import PuzzleService
from app.services.research_puzzles import (
    check_puzzle_scope,
    checked_puzzle,
    freeze_puzzles,
    preview_puzzle,
    puzzle_statuses,
)
from app.services.research_traces import (
    check_trace_scope,
    checked_trace,
    freeze_traces,
    preview_trace,
    trace_statuses,
)
from app.utils.exceptions import AppError
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
)


class ResearchConflictError(Exception):
    """A conclusion changed while the user was editing."""


class ResearchValidationError(ValueError):
    """Evidence does not belong to the frozen comparison scope."""


class ResearchMixin:
    def _research_engine(self, game_type: str) -> GameEngine:
        raise NotImplementedError

    def _puzzles(self) -> PuzzleService:
        raise NotImplementedError

    async def _conn(self) -> aiosqlite.Connection:
        raise NotImplementedError

    @staticmethod
    def _scope(snapshot: dict[str, Any]) -> tuple[list[str], str]:
        result = snapshot["result"]
        try:
            members = comparison_members(result)
            return [gid for member in members for gid in member["game_ids"].values()], result[
                "computed_at"
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ResearchValidationError("比较缺少有效的冻结共同样本范围") from exc

    @staticmethod
    def _pair_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = snapshot["result"]["experiments"]
        if len(rows) != 2 or any(row.get("game_type") != "doudizhu" for row in rows):
            raise ResearchValidationError("记录对照需要两组斗地主运行")
        engines = [(row.get("protocol") or {}).get("engine") for row in rows]
        if (
            not all(isinstance(engine, dict) and engine.get("engine_version") for engine in engines)
            or engines[0] != engines[1]
        ):
            raise ResearchValidationError("冻结引擎条件不同或缺失，无法确认记录对照")
        if any(
            len(row.get("player_ids", [])) != 3 or len(set(row["player_ids"])) != 3 for row in rows
        ):
            raise ResearchValidationError("冻结席位信息不完整")
        return rows

    @staticmethod
    async def _pair_game(
        db: aiosqlite.Connection, row: dict[str, Any], gid: str, seed: int, cutoff: str
    ) -> dict[str, Any]:
        try:
            game = await GameRepository(db).get_by_id(gid)
        except KeyError as exc:
            raise ResearchValidationError("快照引用的对局已不存在") from exc
        try:
            metadata = json.loads(game["metadata"])
            players = json.loads(game["player_ids"])
        except (TypeError, ValueError) as exc:
            raise ResearchValidationError("对局身份信息不完整") from exc
        if (
            not isinstance(metadata, dict)
            or type(metadata.get("deal_seed")) is not int
            or metadata["deal_seed"] != seed
            or players != row["player_ids"]
            or game["experiment_id"] != row["id"]
            or game["game_type"] != row["game_type"]
            or game["status"] != "finished"
            or game["created_at"] > cutoff
        ):
            raise ResearchValidationError("对局身份或状态与冻结样本不符")
        return game

    async def research_pairs(
        self, comparison_id: str, scenario: str | None = None
    ) -> dict[str, Any]:
        if scenario is not None and scenario not in SCENARIO_IDS:
            raise ResearchValidationError("未知场景分类")
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            game_ids, cutoff = self._scope(snapshot)
            rows = self._pair_rows(snapshot)
            members = comparison_members(snapshot["result"])
            for member in members:
                for row in rows:
                    await self._pair_game(
                        db, row, member["game_ids"][row["id"]], member["seed"], cutoff
                    )
            counts = await DecisionRepository(db).evidence_scenario_counts(game_ids, cutoff)
            by_game: dict[str, dict[str, int]] = {}
            for count in counts:
                by_game.setdefault(count["game_id"], {})[count["scenario"]] = count["n"]
            groups = []
            items = []
            for sid in (None, *SCENARIO_IDS):
                group: dict[str, Any] = dict(
                    scenario=sid, left_n=0, right_n=0, left_game_n=0, right_game_n=0, pair_n=0
                )
                for member in members:
                    gids = [member["game_ids"][row["id"]] for row in rows]
                    ns = [
                        sum(by_game.get(gid, {}).values())
                        if sid is None
                        else by_game.get(gid, {}).get(sid, 0)
                        for gid in gids
                    ]
                    group["left_n"] += ns[0]
                    group["right_n"] += ns[1]
                    group["left_game_n"] += int(ns[0] > 0)
                    group["right_game_n"] += int(ns[1] > 0)
                    group["pair_n"] += int(any(ns))
                    if sid == scenario and (sid is None or any(ns)):
                        items.append(
                            dict(
                                seed=member["seed"],
                                left_game_id=gids[0],
                                right_game_id=gids[1],
                                left_n=ns[0],
                                right_n=ns[1],
                            )
                        )
                groups.append(group)
            return {
                "comparison_id": comparison_id,
                "scenario": scenario,
                "cutoff": cutoff,
                "read_at": datetime.now(UTC).isoformat(),
                "endgame_max_hand": ENDGAME_MAX_HAND,
                "cohort_n": len(members),
                "groups": groups,
                "runs": [{"id": row["id"], "name": row["name"]} for row in rows],
                "items": items,
            }
        finally:
            await db.close()

    async def research_pair(
        self, comparison_id: str, seed: int, scenario: str | None = None
    ) -> dict[str, Any]:
        if scenario is not None and scenario not in SCENARIO_IDS:
            raise ResearchValidationError("未知场景分类")
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            _, cutoff = self._scope(snapshot)
            rows = self._pair_rows(snapshot)
            member = next(
                (item for item in comparison_members(snapshot["result"]) if item["seed"] == seed),
                None,
            )
            if member is None:
                raise ResearchValidationError("该发牌不属于快照的共同有效样本")
            sequences = []
            sides = []
            totals = []
            boards = []
            for row in rows:
                gid = member["game_ids"][row["id"]]
                game = await self._pair_game(db, row, gid, seed, cutoff)
                records = await DecisionRepository(db).evidence_sequence(gid, cutoff)
                total = game["total_rounds"]
                if type(total) is not int or not 1 <= total <= 2000 or len(records) > 2000:
                    raise ResearchValidationError("单局决策数量缺失或超过对照范围")
                if any(
                    type(record["round_number"]) is not int
                    or not 0 <= record["round_number"] < total
                    for record in records
                ):
                    raise ResearchValidationError("决策轮次不属于该对局的记录范围")
                sequences.append(records)
                totals.append(total)
                sides.append({"experiment_id": row["id"], "name": row["name"], "game_id": gid})
                rounds = await RoundRepository(db).list_by_game(gid, cutoff)
                boards.append(
                    await asyncio.to_thread(
                        comparison_boards,
                        self._research_engine(row["game_type"]),
                        row["player_ids"],
                        seed,
                        records,
                        rounds,
                        total,
                        row["protocol"]["engine"]["engine_version"],
                    )
                )
            aligned = align_decisions(
                sequences[0], sequences[1], [row["player_ids"] for row in rows], totals
            )
            record_groups = {point["id"]: point["scenario"] for seq in sequences for point in seq}
            matching_turns = []
            for frame in aligned["frames"]:
                for side in ("left", "right"):
                    point = frame[side]
                    frame[f"{side}_scenario"] = record_groups.get(point["id"]) if point else None
                if scenario is None or scenario in (
                    frame["left_scenario"],
                    frame["right_scenario"],
                ):
                    matching_turns.append(frame["turn"])
            if scenario is not None and not matching_turns:
                raise ResearchValidationError("所选对局没有可定位的该场景决策，记录可能缺失或重复")
            return {
                "scenario": scenario,
                "matching_turns": matching_turns,
                "seed": seed,
                "left": sides[0],
                "right": sides[1],
                "boards": {
                    "left": boards[0],
                    "right": boards[1],
                    "cutoff": cutoff,
                    "read_at": datetime.now(UTC).isoformat(),
                    "engine_version": self._research_engine(
                        rows[0]["game_type"]
                    ).capability.engine_version,
                },
                **aligned,
            }
        finally:
            await db.close()

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

    @classmethod
    def _decision_in_scope(cls, snapshot: dict[str, Any], point: dict[str, Any] | None) -> int:
        game_ids, cutoff = cls._scope(snapshot)
        if point is None or point["game_id"] not in game_ids or point["created_at"] > cutoff:
            raise ResearchValidationError("证据已不存在或不属于比较快照的数据范围")
        return int(
            next(
                member["seed"]
                for member in comparison_members(snapshot["result"])
                if point["game_id"] in member["game_ids"].values()
            )
        )

    async def research_decision(self, comparison_id: str, decision_id: str) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            point = await DecisionRepository(db).get_by_id(decision_id)
            seed = self._decision_in_scope(snapshot, point)
            assert point is not None
            return {
                "comparison_id": comparison_id,
                "seed": seed,
                "decision": {key: point.get(key) for key in EVIDENCE_FIELDS},
            }
        finally:
            await db.close()

    async def research_decision_targets(self, decision_id: str, offset: int) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            point = await DecisionRepository(db).get_by_id(decision_id)
            if point is None:
                raise KeyError(decision_id)
            snapshots = await ComparisonRepository(db).for_source(
                point["game_id"], point["created_at"], 20, offset
            )
            items = []
            for snapshot in snapshots:
                try:
                    seed = self._decision_in_scope(snapshot, point)
                except ResearchValidationError:
                    continue
                items.append(
                    {key: snapshot[key] for key in ("id", "title", "created_at")} | {"seed": seed}
                )
            return {
                "decision_id": decision_id,
                "items": items,
                "next_offset": offset + 20 if len(snapshots) == 20 else None,
            }
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

    async def research_puzzle_packs(self, comparison_id: str) -> list[dict[str, Any]]:
        db = await self._conn()
        try:
            snapshot = await ComparisonRepository(db).get(comparison_id)
            self._scope(snapshot)
            owners = {row["id"] for row in snapshot["result"]["experiments"]}
            packs = await asyncio.to_thread(self._puzzles().list_packs)
            return [
                pack.to_dict()
                for pack in packs
                if pack.source_experiment_id in owners
                and pack.extract.get("method") in ("decision_record", "rollout_spread")
            ]
        finally:
            await db.close()

    async def research_puzzle_preview(
        self, comparison_id: str, pack_id: str, run_id: str
    ) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            self._scope(snapshot)
            return await preview_puzzle(
                db, self._puzzles(), snapshot, pack_id, run_id, EVIDENCE_FIELDS
            )
        finally:
            await db.close()

    async def research_puzzle_targets(
        self, pack_id: str, run_id: str, offset: int
    ) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            preview = await checked_puzzle(db, self._puzzles(), pack_id, run_id, EVIDENCE_FIELDS)
            # A first-source membership narrows candidates; every source is checked below.
            first = preview["sources"][0]["decision"]
            snapshots = await ComparisonRepository(db).for_source(
                first["game_id"], first["created_at"], 20, offset
            )
            items = []
            for snapshot in snapshots:
                try:
                    check_puzzle_scope(preview, snapshot)
                except AppError:
                    continue
                items.append({key: snapshot[key] for key in ("id", "title", "created_at")})
            return {
                "pack_id": pack_id,
                "run_id": run_id,
                "report_hash": preview["result"]["report_hash"],
                "read_at": preview["result"]["read_at"],
                "items": items,
                "next_offset": offset + 20 if len(snapshots) == 20 else None,
            }
        finally:
            await db.close()

    async def research_trace_preview(self, comparison_id: str, trace_id: str) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            return await preview_trace(db, snapshot, trace_id)
        finally:
            await db.close()

    async def research_trace_targets(self, trace_id: str, offset: int) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN")
            preview = await checked_trace(db, trace_id)
            snapshots = await ComparisonRepository(db).for_source(
                preview["trace"]["game_id"], preview["trace"]["created_at"], 20, offset
            )
            items = []
            for snapshot in snapshots:
                try:
                    check_trace_scope(preview, snapshot)
                except AppError:
                    continue
                items.append({key: snapshot[key] for key in ("id", "title", "created_at")})
            return {
                "trace_id": trace_id,
                "source_hash": preview["source_hash"],
                "items": items,
                "next_offset": offset + 20 if len(snapshots) == 20 else None,
            }
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
        puzzle_evidence: list[dict[str, str]] | None = None,
        trace_evidence: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        db = await self._conn()
        try:
            await db.execute("BEGIN IMMEDIATE")
            snapshot = await ComparisonRepository(db).get(comparison_id)
            self._scope(snapshot)
            repo = ResearchRepository(db)
            latest = await repo.latest(comparison_id)
            if latest != expected_revision:
                raise ResearchConflictError("结论已有新版本，请刷新版本列表后再保存")
            frozen_puzzles = (
                await freeze_puzzles(
                    db, self._puzzles(), snapshot, puzzle_evidence, EVIDENCE_FIELDS
                )
                if puzzle_evidence
                else []
            )
            frozen_traces = await freeze_traces(db, snapshot, trace_evidence or [])
            ids = [item["decision_id"] for item in evidence]
            if len(ids) != len(set(ids)):
                raise ResearchValidationError("同一决策只能引用一次")
            frozen = []
            for item in evidence:
                decision = await DecisionRepository(db).get_by_id(item["decision_id"])
                self._decision_in_scope(snapshot, decision)
                assert decision is not None
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
                "puzzle_evidence": frozen_puzzles,
                "trace_evidence": frozen_traces,
            }
            await repo.create(record)
            await db.commit()
            return {
                "record": record,
                "evidence_status": {d: "available" for d in ids},
                "trace_evidence_status": {
                    item["trace"]["id"]: "available" for item in frozen_traces
                },
                "puzzle_evidence_status": [
                    {
                        "record_status": "available",
                        "source_status": "matched",
                        "decisions": {
                            source["decision"]["id"]: "available" for source in item["sources"]
                        },
                    }
                    for item in frozen_puzzles
                ],
            }
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
            citations = record.get("puzzle_evidence", [])
            response["puzzle_evidence_status"] = (
                await puzzle_statuses(db, self._puzzles(), citations) if citations else []
            )
            response["trace_evidence_status"] = await trace_statuses(
                db, record.get("trace_evidence", [])
            )
            if export:
                response.update(
                    {
                        "kind": "cardlab.research_report",
                        "exported_at": datetime.now(UTC).isoformat(),
                        "comparison": await ComparisonRepository(db).get(record["comparison_id"]),
                        "scope": "Frozen comparison, cited decisions, recorded invocations and exploratory position tests; not a runnable environment or a full game archive.",
                    }
                )
            return response
        finally:
            await db.close()
