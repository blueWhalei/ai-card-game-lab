"""Puzzle extraction and offline answering against self-contained packs.

Orchestrates repositories, deal-seed replay, and ``RolloutEvaluator`` for
extract; pack IO / scoring live in ``core/eval/puzzle``. HTTP is Task 5.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog

from app.core.engine.base import GameAction, GameEngine, LegalAction
from app.core.engine.observation import Observation
from app.core.engine.registry import GameEngineRegistry
from app.core.eval.perturb import (
    PerturbKind,
    ensure_perturb_kinds,
    perturb_puzzle,
)
from app.core.eval.puzzle import (
    Puzzle,
    PuzzleAnswerScore,
    PuzzlePackManifest,
    load_pack,
    save_pack,
    score_answer,
    select_by_spread,
)
from app.core.eval.replay import rebuild_state
from app.core.eval.rollout import EvaluatorParams, RolloutEvaluator
from app.core.policy import (
    ActionChosen,
    Budget,
    FirstActionPolicy,
    HeuristicPolicy,
    Policy,
    PolicyContext,
    RandomPolicy,
)
from app.core.policy.baselines import HeuristicPolicy as HeuristicOpponent
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.round_repo import RoundRepository
from app.utils.exceptions import AppError

logger = structlog.get_logger()

_DEFAULT_EVALUATOR_PARAMS = EvaluatorParams()

BaselineKind = Literal["rule", "first", "random", "heuristic"]
# ``rule`` kept for API compatibility: means FirstActionPolicy, not HeuristicPolicy.


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


def observation_from_dict(data: dict[str, Any]) -> Observation:
    """Rebuild an ``Observation`` from a frozen puzzle snapshot."""
    return Observation(
        game_type=str(data.get("game_type", "")),
        phase=str(data.get("phase", "")),
        round=int(data.get("round", 0)),
        player_id=str(data.get("player_id", "")),
        to_act=bool(data.get("to_act", True)),
        private=dict(data.get("private") or {}),
        public=dict(data.get("public") or {}),
        text=str(data.get("text") or ""),
    )


def legal_actions_from_dicts(
    rows: list[dict[str, Any]], *, player_id: str
) -> list[LegalAction]:
    """Rebuild ``LegalAction`` rows from frozen puzzle JSON."""
    result: list[LegalAction] = []
    for row in rows:
        action_raw = row.get("action") or {}
        action = GameAction(
            player_id=player_id,
            action_type=str(action_raw.get("action_type", "")),
            cards=list(action_raw.get("cards") or []),
            target=action_raw.get("target"),
        )
        result.append(
            LegalAction(
                id=str(row["id"]),
                label=str(row.get("label") or row["id"]),
                action=action,
            )
        )
    return result


def baseline_policy(kind: BaselineKind) -> Policy:
    """Map API baseline names to non-LLM policies.

    ``rule`` ≡ ``first`` (``FirstActionPolicy``). Prefer ``first`` / ``heuristic`` /
    ``random`` in new callers so the name matches the policy class.
    """
    resolved = "first" if kind == "rule" else kind
    if resolved == "first":
        return FirstActionPolicy()
    if resolved == "random":
        return RandomPolicy()
    if resolved == "heuristic":
        return HeuristicPolicy()
    raise AppError(
        message=f"Unknown baseline kind: {kind}",
        code="PUZZLE_INVALID_BASELINE",
        status_code=400,
    )


class PuzzleService:
    """Extract and run static puzzle packs."""

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
        self._opponent = HeuristicOpponent()

    def list_packs(self) -> list[PuzzlePackManifest]:
        """List local pack manifests under ``puzzle_dir``."""
        if not self._puzzle_dir.exists():
            return []
        manifests: list[PuzzlePackManifest] = []
        for child in sorted(self._puzzle_dir.iterdir()):
            if not child.is_dir():
                continue
            if not (child / "manifest.json").exists():
                continue
            try:
                manifest, _puzzles = load_pack(child)
            except ValueError:
                logger.info("puzzle_pack_skip", reason="invalid_pack", path=str(child))
                continue
            manifests.append(manifest)
        return manifests

    def get_pack(
        self, pack_id: str, *, preview: int = 5
    ) -> tuple[PuzzlePackManifest, list[Puzzle]]:
        """Load one pack; ``preview`` limits returned puzzles."""
        root = self._puzzle_dir / pack_id
        if not root.is_dir():
            raise AppError(
                message=f"Puzzle pack not found: {pack_id}",
                code="PUZZLE_PACK_NOT_FOUND",
                status_code=404,
            )
        try:
            manifest, puzzles = load_pack(root)
        except ValueError as error:
            raise AppError(
                message=str(error),
                code="PUZZLE_PACK_INVALID",
                status_code=400,
            ) from error
        if preview < 0:
            preview = 0
        return manifest, puzzles[:preview]

    async def run(
        self,
        pack_id: str,
        *,
        baseline_kind: BaselineKind = "heuristic",
        seed: int = 0,
    ) -> dict[str, Any]:
        """Score a baseline policy against a frozen pack (no rollout, no API)."""
        root = self._puzzle_dir / pack_id
        if not root.is_dir():
            raise AppError(
                message=f"Puzzle pack not found: {pack_id}",
                code="PUZZLE_PACK_NOT_FOUND",
                status_code=404,
            )
        try:
            manifest, puzzles = load_pack(root)
        except ValueError as error:
            raise AppError(
                message=str(error),
                code="PUZZLE_PACK_INVALID",
                status_code=400,
            ) from error

        policy = baseline_policy(baseline_kind)
        engine = self._engine_registry.get(manifest.game_type)
        ctx = PolicyContext(advisor=engine, rng=random.Random(seed))
        budget = Budget()

        rows: list[dict[str, Any]] = []
        scores: list[PuzzleAnswerScore] = []
        for puzzle in puzzles:
            observation = observation_from_dict(puzzle.observation)
            legal = legal_actions_from_dicts(
                puzzle.legal_actions, player_id=observation.player_id
            )
            chosen_id = await self._decide_action_id(
                policy, observation, legal, budget, ctx
            )
            answer = score_answer(puzzle.best_action_id, puzzle.action_values, chosen_id)
            scores.append(answer)
            rows.append(
                {
                    "puzzle_id": puzzle.puzzle_id,
                    "chosen_action_id": answer.chosen_action_id,
                    "best_action_id": puzzle.best_action_id,
                    "hit": answer.hit,
                    "ev_loss": answer.ev_loss,
                    "truncated": puzzle.truncated,
                }
            )

        summary = self._summarize(scores, puzzles)
        run_id = f"run_{secrets.token_hex(4)}"
        report = {
            "run_id": run_id,
            "pack_id": pack_id,
            "baseline_kind": baseline_kind,
            "seed": seed,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "summary": summary,
            "puzzles": rows,
        }
        runs_dir = root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / f"{run_id}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "puzzle_run_done",
            pack_id=pack_id,
            run_id=run_id,
            baseline_kind=baseline_kind,
            **summary,
        )
        return report

    async def probe(
        self,
        pack_id: str,
        *,
        baseline_kind: BaselineKind = "heuristic",
        seed: int = 0,
        n_trials: int = 3,
        kinds: list[PerturbKind] | None = None,
    ) -> dict[str, Any]:
        """Measure action-id consistency under safe presentation shuffles."""
        if n_trials < 1:
            raise AppError(
                message="n_trials must be >= 1",
                code="PUZZLE_INVALID_N_TRIALS",
                status_code=400,
            )
        root = self._puzzle_dir / pack_id
        if not root.is_dir():
            raise AppError(
                message=f"Puzzle pack not found: {pack_id}",
                code="PUZZLE_PACK_NOT_FOUND",
                status_code=404,
            )
        try:
            manifest, puzzles = load_pack(root)
        except ValueError as error:
            raise AppError(
                message=str(error),
                code="PUZZLE_PACK_INVALID",
                status_code=400,
            ) from error

        try:
            active_kinds = ensure_perturb_kinds(kinds)
        except ValueError as error:
            raise AppError(
                message=str(error),
                code="PUZZLE_INVALID_PERTURB",
                status_code=400,
            ) from error

        policy = baseline_policy(baseline_kind)
        engine = self._engine_registry.get(manifest.game_type)
        budget = Budget()

        puzzle_rows: list[dict[str, Any]] = []
        consistent_flags: list[bool] = []
        base_scores: list[PuzzleAnswerScore] = []
        pert_scores: list[PuzzleAnswerScore] = []

        for puzzle in puzzles:
            base_rng = random.Random(self._probe_seed(seed, puzzle.puzzle_id, -1))
            base_ctx = PolicyContext(advisor=engine, rng=base_rng)
            observation = observation_from_dict(puzzle.observation)
            legal = legal_actions_from_dicts(
                puzzle.legal_actions, player_id=observation.player_id
            )
            base_chosen = await self._decide_action_id(
                policy, observation, legal, budget, base_ctx
            )
            base_answer = score_answer(
                puzzle.best_action_id, puzzle.action_values, base_chosen
            )
            base_scores.append(base_answer)

            trials: list[dict[str, Any]] = []
            for trial in range(n_trials):
                trial_rng = random.Random(
                    self._probe_seed(seed, puzzle.puzzle_id, trial)
                )
                pert = perturb_puzzle(puzzle, active_kinds, trial_rng)
                pert_obs = observation_from_dict(pert.observation)
                pert_legal = legal_actions_from_dicts(
                    pert.legal_actions, player_id=pert_obs.player_id
                )
                decide_rng = random.Random(
                    self._probe_seed(seed, puzzle.puzzle_id, trial + 10_000)
                )
                pert_ctx = PolicyContext(advisor=engine, rng=decide_rng)
                pert_chosen = await self._decide_action_id(
                    policy, pert_obs, pert_legal, budget, pert_ctx
                )
                consistent = pert_chosen == base_chosen
                consistent_flags.append(consistent)
                pert_answer = score_answer(
                    puzzle.best_action_id, puzzle.action_values, pert_chosen
                )
                pert_scores.append(pert_answer)
                trials.append(
                    {
                        "trial": trial,
                        "chosen_action_id": pert_chosen,
                        "consistent": consistent,
                        "hit": pert_answer.hit,
                        "ev_loss": pert_answer.ev_loss,
                    }
                )

            puzzle_rows.append(
                {
                    "puzzle_id": puzzle.puzzle_id,
                    "base_chosen_action_id": base_chosen,
                    "best_action_id": puzzle.best_action_id,
                    "base_hit": base_answer.hit,
                    "base_ev_loss": base_answer.ev_loss,
                    "trials": trials,
                }
            )

        n = len(puzzles)
        n_flags = len(consistent_flags)
        summary = {
            "n": n,
            "n_trials": n_trials,
            "kinds": active_kinds,
            "consistency": (
                round(sum(1 for flag in consistent_flags if flag) / n_flags, 4)
                if n_flags
                else 0.0
            ),
            "base_accuracy": (
                round(sum(1 for s in base_scores if s.hit) / n, 4) if n else 0.0
            ),
            "pert_accuracy": (
                round(sum(1 for s in pert_scores if s.hit) / len(pert_scores), 4)
                if pert_scores
                else 0.0
            ),
            "base_mean_ev_loss": (
                round(sum(s.ev_loss for s in base_scores) / n, 4) if n else 0.0
            ),
            "pert_mean_ev_loss": (
                round(sum(s.ev_loss for s in pert_scores) / len(pert_scores), 4)
                if pert_scores
                else 0.0
            ),
        }
        run_id = f"probe_{secrets.token_hex(4)}"
        report = {
            "run_id": run_id,
            "pack_id": pack_id,
            "baseline_kind": baseline_kind,
            "seed": seed,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "summary": summary,
            "puzzles": puzzle_rows,
        }
        runs_dir = root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / f"{run_id}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "puzzle_probe_done",
            pack_id=pack_id,
            run_id=run_id,
            baseline_kind=baseline_kind,
            consistency=summary["consistency"],
            n=n,
            n_trials=n_trials,
        )
        return report

    @staticmethod
    def _probe_seed(seed: int, puzzle_id: str, trial: int) -> int:
        digest = hashlib.sha256(f"{seed}|{puzzle_id}|{trial}".encode()).hexdigest()
        return int(digest[:16], 16)

    @staticmethod
    async def _decide_action_id(
        policy: Policy,
        observation: Observation,
        legal: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> str:
        chosen: ActionChosen | None = None
        async for event in policy.decide(observation, legal, budget, ctx):
            if isinstance(event, ActionChosen):
                chosen = event
        if chosen is None:
            raise AppError(
                message="Policy finished without ActionChosen",
                code="PUZZLE_POLICY_NO_ACTION",
                status_code=500,
            )
        return chosen.action_id

    @staticmethod
    def _summarize(
        results: list[PuzzleAnswerScore], puzzles: list[Puzzle]
    ) -> dict[str, Any]:
        n = len(results)
        hits = sum(1 for result in results if result.hit)
        return {
            "n": n,
            "accuracy": round(hits / n, 4) if n else 0.0,
            "mean_ev_loss": (
                round(sum(result.ev_loss for result in results) / n, 4) if n else 0.0
            ),
            "truncated_n": sum(1 for puzzle in puzzles if puzzle.truncated),
        }

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


__all__ = [
    "PuzzleService",
    "baseline_policy",
    "legal_actions_from_dicts",
    "match_recorded_action",
    "observation_from_dict",
]
