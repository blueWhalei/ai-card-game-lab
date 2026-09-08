"""Puzzle extraction: experiment games → self-contained puzzle packs.

Orchestrates repositories, deal-seed replay, and ``RolloutEvaluator``; pack IO
and selection live in ``core/eval/puzzle``. Answering packs is Task 4.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.core.engine.base import GameAction, GameEngine, LegalAction
from app.core.engine.registry import GameEngineRegistry
from app.core.eval.puzzle import (
    Puzzle,
    PuzzlePackManifest,
    save_pack,
    select_by_spread,
)
from app.core.eval.replay import rebuild_state
from app.core.eval.rollout import EvaluatorParams, RolloutEvaluator
from app.core.policy.baselines import HeuristicPolicy
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.round_repo import RoundRepository
from app.utils.exceptions import AppError

logger = structlog.get_logger()

_DEFAULT_EVALUATOR_PARAMS = EvaluatorParams()


def match_recorded_action(
    engine: GameEngine,
    state: Any,
    *,
    player_id: str,
    action_type: str,
    cards: list[str] | None,
    dp_action_id: str = "",
) -> GameAction | None:
    """Recover the ``GameAction`` that was played from legal actions at ``state``.

    Prefer an exact ``action_id`` match from the decision point (needed for Dou
    Dizhu ``BID``, where ``rounds`` does not store ``target``). Otherwise match
    ``action_type`` + ``cards`` when that pair is unique among legal actions.
    """
    legal = engine.legal_actions(state, player_id)
    if dp_action_id:
        for entry in legal:
            if entry.id == dp_action_id:
                return entry.action

    card_list = list(cards or [])
    matches = [
        entry.action
        for entry in legal
        if str(entry.action.action_type) == action_type
        and list(entry.action.cards or []) == card_list
    ]
    if len(matches) == 1:
        return matches[0]
    return None


class PuzzleService:
    """Extract static puzzle packs from finished experiment games."""

    def __init__(
        self,
        *,
        sqlite_path: str,
        puzzle_dir: str,
        engine_registry: GameEngineRegistry,
    ) -> None:
        self._sqlite_path = sqlite_path
        self._puzzle_dir = Path(puzzle_dir)
        self._engine_registry = engine_registry
        self._evaluators: dict[str, RolloutEvaluator] = {}
        self._opponent = HeuristicPolicy()

    async def extract(
        self,
        experiment_id: str,
        *,
        min_spread: float = 0.15,
        max_per_game: int = 3,
        max_total: int = 200,
        evaluator_params: EvaluatorParams | None = None,
    ) -> PuzzlePackManifest:
        """Replay finished games, re-score decisions, freeze high-spread puzzles."""
        params = evaluator_params or _DEFAULT_EVALUATOR_PARAMS

        async with connect_sqlite(self._sqlite_path) as db:
            experiment = await self._load_experiment(db, experiment_id)
            game_type = str(experiment["game_type"])
            engine = self._engine_registry.get(game_type)
            if not engine.capability.supports_hidden_state_sampling:
                logger.info(
                    "puzzle_extract_skip",
                    reason="engine_no_sampling",
                    game_type=game_type,
                    experiment_id=experiment_id,
                )
                return self._write_empty(
                    experiment_id, game_type, params, min_spread, max_per_game, max_total
                )

            games = [
                g
                for g in await ExperimentRepository(db).list_games(experiment_id)
                if str(g.get("status")) == "finished"
            ]
            rounds_by_game = {
                str(g["id"]): await RoundRepository(db).list_by_game(str(g["id"]))
                for g in games
            }
            dp_by_game = {
                str(g["id"]): await self._decision_lookups(db, str(g["id"]))
                for g in games
            }

        candidates: list[Puzzle] = []
        for game in games:
            game_id = str(game["id"])
            game_candidates = await self._extract_game(
                engine=engine,
                experiment_id=experiment_id,
                game=game,
                rounds=rounds_by_game[game_id],
                dp_ids=dp_by_game[game_id][0],
                dp_action_ids=dp_by_game[game_id][1],
                params=params,
            )
            candidates.extend(game_candidates)

        picked = select_by_spread(
            candidates,
            min_spread=min_spread,
            max_per_game=max_per_game,
            max_total=max_total,
        )
        manifest = self._build_manifest(
            experiment_id=experiment_id,
            game_type=game_type,
            params=params,
            min_spread=min_spread,
            max_per_game=max_per_game,
            max_total=max_total,
            count=len(picked),
        )
        save_pack(self._puzzle_dir / manifest.pack_id, manifest, picked)
        logger.info(
            "puzzle_extract_done",
            experiment_id=experiment_id,
            pack_id=manifest.pack_id,
            game_count=len(games),
            candidate_count=len(candidates),
            puzzle_count=len(picked),
        )
        return manifest

    async def _load_experiment(self, db: Any, experiment_id: str) -> dict[str, Any]:
        try:
            return await ExperimentRepository(db).get_by_id(experiment_id)
        except KeyError as error:
            raise AppError(
                message=f"Experiment not found: {experiment_id}",
                code="EXPERIMENT_NOT_FOUND",
                status_code=404,
            ) from error

    async def _decision_lookups(
        self, db: Any, game_id: str
    ) -> tuple[dict[tuple[int, str], str], dict[tuple[int, str], str]]:
        """Maps ``(pre_action_round, player_id)`` → decision_point id / action_id."""
        items, _total = await DecisionRepository(db).list_decision_points(
            game_id=game_id, limit=10_000
        )
        ids: dict[tuple[int, str], str] = {}
        action_ids: dict[tuple[int, str], str] = {}
        for item in items:
            key = (int(item["round_number"]), str(item["player_id"]))
            ids[key] = str(item["id"])
            action_ids[key] = str(item.get("action_id") or "")
        return ids, action_ids

    async def _extract_game(
        self,
        *,
        engine: GameEngine,
        experiment_id: str,
        game: dict[str, Any],
        rounds: list[dict[str, Any]],
        dp_ids: dict[tuple[int, str], str],
        dp_action_ids: dict[tuple[int, str], str],
        params: EvaluatorParams,
    ) -> list[Puzzle]:
        game_id = str(game["id"])
        deal_seed = self._deal_seed(game)
        if deal_seed is None:
            logger.info("puzzle_extract_skip", reason="no_deal_seed", game_id=game_id)
            return []
        player_ids = self._player_ids(game)
        if not player_ids:
            logger.info("puzzle_extract_skip", reason="no_player_ids", game_id=game_id)
            return []

        evaluator = self._evaluator_for(engine, params)
        try:
            state = await asyncio.to_thread(
                rebuild_state, engine, player_ids, deal_seed, []
            )
        except Exception as error:
            logger.info(
                "puzzle_extract_skip",
                reason="rebuild_failed",
                game_id=game_id,
                error=str(error),
            )
            return []

        candidates: list[Puzzle] = []
        for row in rounds:
            round_num = int(row["round_num"])
            actor = str(row["player_id"])
            pre_round = int(getattr(state, "round", 0))
            try:
                puzzle = await self._maybe_candidate(
                    engine=engine,
                    evaluator=evaluator,
                    state=state,
                    experiment_id=experiment_id,
                    game_id=game_id,
                    deal_seed=deal_seed,
                    round_num=round_num,
                    actor=actor,
                    decision_point_id=dp_ids.get((pre_round, actor)),
                )
                if puzzle is not None:
                    candidates.append(puzzle)
            except Exception as error:
                logger.info(
                    "puzzle_point_skip",
                    game_id=game_id,
                    round_num=round_num,
                    player_id=actor,
                    error=str(error),
                )

            cards_raw = row.get("cards")
            cards = (
                json.loads(cards_raw) if isinstance(cards_raw, str) else (cards_raw or [])
            )
            action = match_recorded_action(
                engine,
                state,
                player_id=actor,
                action_type=str(row["action_type"]),
                cards=cards if isinstance(cards, list) else [],
                dp_action_id=dp_action_ids.get((pre_round, actor), ""),
            )
            if action is None:
                logger.info(
                    "puzzle_extract_skip",
                    reason="action_not_recoverable",
                    game_id=game_id,
                    round_num=round_num,
                    action_type=str(row["action_type"]),
                )
                return candidates
            try:
                state = await asyncio.to_thread(engine.apply_action, state, action)
            except Exception as error:
                logger.info(
                    "puzzle_extract_skip",
                    reason="apply_failed",
                    game_id=game_id,
                    round_num=round_num,
                    error=str(error),
                )
                return candidates

        return candidates

    async def _maybe_candidate(
        self,
        *,
        engine: GameEngine,
        evaluator: RolloutEvaluator,
        state: Any,
        experiment_id: str,
        game_id: str,
        deal_seed: int,
        round_num: int,
        actor: str,
        decision_point_id: str | None,
    ) -> Puzzle | None:
        if engine.get_current_player(state) != actor:
            return None
        legal = engine.legal_actions(state, actor)
        if len(legal) < 2:
            return None
        observation = engine.observe(state, actor)
        values = await asyncio.to_thread(evaluator.action_values, observation, legal)
        if not values:
            return None
        best_id = max(values, key=lambda aid: values[aid])
        spread = max(values.values()) - min(values.values())
        return Puzzle(
            puzzle_id=self._puzzle_id(game_id, round_num, actor),
            game_type=engine.game_type,
            source={
                "experiment_id": experiment_id,
                "game_id": game_id,
                "deal_seed": deal_seed,
                "round_num": round_num,
                "player_id": actor,
                "decision_point_id": decision_point_id,
            },
            observation=asdict(observation),
            legal_actions=self._legal_actions_json(legal),
            action_values={aid: round(float(v), 6) for aid, v in values.items()},
            best_action_id=best_id,
            spread=round(float(spread), 6),
            candidates_evaluated=len(values),
            legal_action_count=len(legal),
            truncated=len(values) < len(legal),
            evaluator_params=evaluator.params.to_dict(),
        )

    def _evaluator_for(
        self, engine: GameEngine, params: EvaluatorParams
    ) -> RolloutEvaluator:
        key = f"{engine.game_type}:{json.dumps(params.to_dict(), sort_keys=True)}"
        cached = self._evaluators.get(key)
        if cached is None:
            cached = RolloutEvaluator(engine, self._opponent, params)
            self._evaluators[key] = cached
        return cached

    @staticmethod
    def _deal_seed(game: dict[str, Any]) -> int | None:
        raw = game.get("metadata")
        meta: dict[str, Any] = {}
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    meta = parsed
            except json.JSONDecodeError:
                meta = {}
        elif isinstance(raw, dict):
            meta = raw
        seed = meta.get("deal_seed")
        if seed is None:
            return None
        try:
            return int(seed)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _player_ids(game: dict[str, Any]) -> list[str]:
        raw = game.get("player_ids")
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(p) for p in parsed]
            except json.JSONDecodeError:
                return []
        if isinstance(raw, list):
            return [str(p) for p in raw]
        return []

    @staticmethod
    def _legal_actions_json(legal: list[LegalAction]) -> list[dict[str, Any]]:
        return [
            {
                "id": entry.id,
                "label": entry.label,
                "action": {
                    "action_type": str(entry.action.action_type),
                    "cards": list(entry.action.cards or []),
                    "target": entry.action.target,
                },
            }
            for entry in legal
        ]

    @staticmethod
    def _puzzle_id(game_id: str, round_num: int, actor: str) -> str:
        digest = hashlib.sha256(f"{game_id}|{round_num}|{actor}".encode()).hexdigest()
        return f"pz_{digest[:8]}"

    def _build_manifest(
        self,
        *,
        experiment_id: str,
        game_type: str,
        params: EvaluatorParams,
        min_spread: float,
        max_per_game: int,
        max_total: int,
        count: int,
    ) -> PuzzlePackManifest:
        return PuzzlePackManifest(
            pack_id=self._pack_id(experiment_id),
            created_at=datetime.now(tz=UTC).isoformat(),
            game_type=game_type,
            source_experiment_id=experiment_id,
            puzzle_count=count,
            extract={
                "min_spread": min_spread,
                "max_per_game": max_per_game,
                "max_total": max_total,
                "evaluator_params": params.to_dict(),
            },
        )

    def _write_empty(
        self,
        experiment_id: str,
        game_type: str,
        params: EvaluatorParams,
        min_spread: float,
        max_per_game: int,
        max_total: int,
    ) -> PuzzlePackManifest:
        manifest = self._build_manifest(
            experiment_id=experiment_id,
            game_type=game_type,
            params=params,
            min_spread=min_spread,
            max_per_game=max_per_game,
            max_total=max_total,
            count=0,
        )
        save_pack(self._puzzle_dir / manifest.pack_id, manifest, [])
        return manifest

    @staticmethod
    def _pack_id(experiment_id: str) -> str:
        short_exp = experiment_id[:8] if experiment_id else "unknown"
        yyyymmdd = datetime.now(tz=UTC).strftime("%Y%m%d")
        return f"exp_{short_exp}_{yyyymmdd}_{secrets.token_hex(4)}"


__all__ = ["PuzzleService", "match_recorded_action"]
