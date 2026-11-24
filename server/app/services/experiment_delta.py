"""Summary / delta / compare helpers for ExperimentService."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.core.eval.scorer import (
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.research.prompt_design import paired_design
from app.core.stats.comparison import change_allowed, paired_cohort, protocol_review
from app.core.stats.game_progress import build_game_progress
from app.core.stats.paired import summarize_paired_outcomes
from app.core.stats.proportion import wilson_interval
from app.core.stats.scenarios import fill_scenario_scores, scenario_rate_diffs
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_collect import ACTIVE_GAME_STATUSES
from app.services.experiment_errors import (
    ExperimentNotFoundError,
    ExperimentValidationError,
)
from app.services.experiment_eval import (
    CREDIBILITY_MIN_DECISIVE_N,
    build_credibility,
    build_experiment_delta,
    ci_pair,
    derive_experiment_status,
    resolve_delta_peer,
)
from app.services.experiment_protocol import (
    protocol_eval_metric_ids,
    protocol_source_experiment_id,
)

_ACTIVE_STATUSES = ACTIVE_GAME_STATUSES
_VALIDATION_MIN_PAIRED_N = 5

logger = structlog.get_logger()


def _control_experiment_ready(summary: dict[str, Any]) -> bool:
    paired_n = int(summary.get("paired_games") or 0)
    finished = int(summary.get("finished_games") or 0)
    target = int(summary.get("target_games") or 0)
    return paired_n >= _VALIDATION_MIN_PAIRED_N or finished >= target


class ExperimentDeltaMixin:
    """Metrics, validation, delta, and compare assembly.

    Host methods are provided by ``ExperimentService``; stubs below exist only
    so mypy can type-check the mixin in isolation.
    """

    async def _conn(self) -> aiosqlite.Connection:
        raise NotImplementedError

    def _registry_for(self, protocol: dict[str, Any] | None, game_type: str) -> ScorerRegistry:
        raise NotImplementedError

    async def compare_experiments(
        self, experiment_ids: list[str], allowed_changes: list[str] | None = None
    ) -> dict[str, Any]:
        """Side-by-side metrics for 2–5 experiments, including Wilson CIs."""
        unique_ids = list(dict.fromkeys(experiment_ids))
        if len(unique_ids) < 2 or len(unique_ids) > 5:
            raise ExperimentValidationError("对比需要 2 到 5 个不重复的实验 ID")

        allowed = allowed_changes or []
        if len(allowed) > 32 or any(len(p) > 240 or not change_allowed(p) for p in allowed):
            raise ExperimentValidationError(
                "允许变化字段必须是精确的 Solver 参数路径（最多 32 个）"
            )
        computed_at = datetime.now(UTC).isoformat()
        rows: list[dict[str, Any]] = []
        games_by_exp: dict[str, list[dict[str, Any]]] = {}
        seat_winners: dict[str, set[str]] = {}
        conn = await self._conn()
        try:
            await conn.execute("BEGIN")
            repo = ExperimentRepository(conn)
            for experiment_id in unique_ids:
                try:
                    row = await repo.get_by_id(experiment_id)
                except KeyError as exc:
                    raise ExperimentNotFoundError(experiment_id) from exc
                summary = await self._build_summary(repo, row)
                extras = await repo.eval_aggregates(experiment_id)
                protocol = row.get("protocol")
                if not isinstance(protocol, dict) or protocol.get("schema_version") != 2:
                    raise ExperimentValidationError(
                        "实验协议必须使用当前 Task 结构，请重新创建实验"
                    )
                game_type = str(row.get("game_type") or "doudizhu")
                protocol_dict = protocol if isinstance(protocol, dict) else None
                registry = self._registry_for(protocol_dict, game_type)
                metric_ids = protocol_eval_metric_ids(protocol_dict) if protocol_dict else []
                if not metric_ids:
                    metric_ids = registry.list_ids()
                scored = registry.score_many(
                    metric_ids,
                    score_bundle_from_aggregates(extras),
                )
                extras = apply_scorer_results(extras, scored)
                games = await repo.list_games(experiment_id)
                games_by_exp[experiment_id] = [_normalize_game_row(g) for g in games]
                seat_winners.update(await repo.seat_winners(experiment_id))
                compared = self._attach_compare_metrics(row, summary, extras)
                compared["game_ids"] = [str(g["id"]) for g in games]
                rows.append(compared)
        finally:
            await conn.close()

        coverage, paired_summary = self._paired_analysis(rows, games_by_exp, seat_winners)
        payload: dict[str, Any] = {
            "experiments": rows,
            "coverage": coverage,
            "protocol_review": protocol_review(rows, allowed),
            "computed_at": computed_at,
            "metric_version": "paired-cohort-v5",
        }
        if paired_summary is not None:
            payload["paired_summary"] = paired_summary
        return payload

    async def _build_summary(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
    ) -> dict[str, Any]:
        experiment_id = str(experiment["id"])
        target = int(experiment["target_games"])
        games = await repo.list_games(experiment_id)
        eval_metrics = await repo.eval_aggregates(experiment_id)
        game_type = str(experiment.get("game_type") or "doudizhu")
        protocol = experiment.get("protocol")
        protocol_dict = protocol if isinstance(protocol, dict) else None
        registry = self._registry_for(protocol_dict, game_type)
        metric_ids = protocol_eval_metric_ids(protocol_dict) if protocol_dict else []
        if not metric_ids:
            metric_ids = registry.list_ids()
        scored = registry.score_many(
            metric_ids,
            score_bundle_from_aggregates(eval_metrics),
        )
        eval_metrics = apply_scorer_results(eval_metrics, scored)

        active = 0
        finished = 0
        with_winner = 0
        rounds_sum = 0
        rounds_n = 0
        wins_by_config: dict[str, int] = {pid: 0 for pid in experiment.get("player_ids") or []}
        latest_game_id: str | None = None
        latest_created: str | None = None
        paired_games = 0

        for g in games:
            status = str(g.get("status") or "")
            created = str(g.get("created_at") or "")
            if latest_created is None or created > latest_created:
                latest_created = created
                latest_game_id = str(g["id"])

            if status in _ACTIVE_STATUSES:
                active += 1
            else:
                finished += 1

            winner = g.get("winner_id")
            if winner:
                with_winner += 1

            total_rounds = g.get("total_rounds")
            if isinstance(total_rounds, int) and total_rounds > 0:
                rounds_sum += total_rounds
                rounds_n += 1

            meta = g.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            if isinstance(meta, dict) and meta.get("paired"):
                paired_games += 1

        train_usable = int(eval_metrics.get("train_usable_n") or 0)
        usability = await repo.count_decisions_by_usability(experiment_id)
        train_by_player = await repo.count_train_usable_by_player(experiment_id)
        response_by_player = await repo.avg_response_ms_by_player(experiment_id)
        avg_rounds = (rounds_sum / rounds_n) if rounds_n else 0.0
        status = derive_experiment_status(
            target_games=target,
            total_games=len(games),
            active_games=active,
            finished_games=finished,
        )
        player_ids: list[str] = list(experiment.get("player_ids") or [])
        player_stats: list[dict[str, Any]] = []
        for pid in player_ids:
            counts = eval_metrics["seat_counts"].get(pid, {})
            wins = int(counts.get("wins", 0))
            n = int(counts.get("n", 0))
            wins_by_config[pid] = wins
            avg_ms, round_count = response_by_player.get(pid, (0.0, 0))
            win_rate = round(wins / n, 4) if n else None
            low, high = wilson_interval(wins, n)
            games_as_landlord = int(counts.get("landlord_n", 0))
            wins_as_landlord = int(counts.get("landlord_wins", 0))
            landlord_rate = wins_as_landlord / games_as_landlord if games_as_landlord > 0 else 0.0
            player_stats.append(
                {
                    "player_id": pid,
                    "wins": wins,
                    "decided_games": n,
                    "win_rate": win_rate,
                    "win_rate_ci": [round(low, 4), round(high, 4)] if n else None,
                    "train_usable_decisions": train_by_player.get(pid, 0),
                    "avg_response_time_ms": avg_ms,
                    "trace_count": round_count,
                    "games_as_landlord": games_as_landlord,
                    "wins_as_landlord": wins_as_landlord,
                    "landlord_win_rate": round(landlord_rate, 4),
                }
            )

        decisive = int(eval_metrics.get("decisive_games") or 0)
        landlord_wins = int((eval_metrics.get("wins_by_role") or {}).get("landlord") or 0)
        l_low, l_high = wilson_interval(landlord_wins, decisive)
        landlord_ci = [round(l_low, 4), round(l_high, 4)]

        return {
            "status": status,
            "target_games": target,
            "total_games": len(games),
            "active_games": active,
            "finished_games": finished,
            "games_with_winner": with_winner,
            "train_usable_decisions": train_usable,
            "not_usable_decisions": usability.get("not_usable", 0),
            "decision_total": usability.get("total", 0),
            "train_usable_rate": eval_metrics.get("train_usable_rate", 0.0),
            "decision_count": eval_metrics.get("decision_count", 0),
            "avg_rounds": round(avg_rounds, 1),
            "wins_by_config": wins_by_config,
            "wins_by_role": eval_metrics.get("wins_by_role") or {"landlord": 0, "peasant": 0},
            "decisive_games": decisive,
            "landlord_win_rate": eval_metrics.get("landlord_win_rate", 0.0),
            "landlord_win_rate_ci": landlord_ci,
            "parser_success_rate": eval_metrics.get("parser_success_rate", 0.0),
            "parser_n": eval_metrics.get("parser_n", 0),
            "avg_response_time_ms": eval_metrics.get("avg_response_time_ms", 0.0),
            "p50_response_ms": eval_metrics.get("p50_response_ms", 0.0),
            "p95_response_ms": eval_metrics.get("p95_response_ms", 0.0),
            "avg_ev_loss": eval_metrics.get("avg_ev_loss"),
            "evaluated_count": eval_metrics.get("evaluated_count", 0),
            "total_tokens": eval_metrics.get("total_tokens", 0),
            "tokens_per_game": eval_metrics.get("tokens_per_game", 0.0),
            "avg_tokens_per_round": eval_metrics.get("avg_tokens_per_round", 0.0),
            "status_counts": eval_metrics.get("status_counts") or {},
            "player_stats": player_stats,
            "latest_game_id": latest_game_id,
            "paired_games": paired_games,
            "credibility": build_credibility(decisive_n=decisive, win_rate_ci=landlord_ci),
            "scenario_scores": eval_metrics.get("scenario_scores") or fill_scenario_scores({}),
        }

    async def _build_timeline(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
    ) -> list[dict[str, Any]]:
        experiment_id = str(experiment["id"])
        events: list[dict[str, Any]] = [
            {
                "id": "created",
                "at": experiment["created_at"],
                "ref_id": experiment_id,
            }
        ]
        stamps = await repo.first_game_timestamps(experiment_id)
        if stamps.get("first_collect"):
            events.append(
                {
                    "id": "first_collect",
                    "at": stamps["first_collect"],
                    "ref_id": None,
                }
            )
        if stamps.get("first_finished"):
            events.append(
                {
                    "id": "first_finished",
                    "at": stamps["first_finished"],
                    "ref_id": None,
                }
            )
        dataset_at = await repo.first_dataset_at(experiment_id)
        if dataset_at:
            events.append({"id": "dataset_registered", "at": dataset_at, "ref_id": None})
        training_at = await repo.first_training_completed_at(experiment_id)
        if training_at:
            events.append({"id": "training_completed", "at": training_at, "ref_id": None})
        controls = await repo.list_control_experiments(experiment_id)
        for ctrl in controls:
            events.append(
                {
                    "id": "control_created",
                    "at": ctrl["created_at"],
                    "ref_id": ctrl["id"],
                }
            )
        events.sort(key=lambda e: str(e["at"]))
        return events

    async def _build_validation(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        experiment_id = str(experiment["id"])
        controls = await repo.list_control_experiments(experiment_id)
        control_ids = [c["id"] for c in controls]
        paired_n = int(summary.get("paired_games") or 0)

        control_progress: list[dict[str, Any]] = []
        for control in controls:
            try:
                control_row = await repo.get_by_id(str(control["id"]))
            except KeyError:
                continue
            control_summary = await self._build_summary(repo, control_row)
            ready = _control_experiment_ready(control_summary)
            control_progress.append(
                {
                    "id": control_row["id"],
                    "name": control_row.get("name") or control_row["id"],
                    "finished_games": int(control_summary.get("finished_games") or 0),
                    "target_games": int(control_summary.get("target_games") or 0),
                    "paired_n": int(control_summary.get("paired_games") or 0),
                    "ready": ready,
                }
            )

        first_ready = bool(control_progress) and control_progress[0]["ready"]
        all_controls_ready = bool(control_progress) and all(
            item["ready"] for item in control_progress
        )
        validation_ready = bool(control_ids) and first_ready

        suggested = [experiment_id]
        source_id = protocol_source_experiment_id(experiment.get("protocol") or {})
        if source_id:
            suggested.append(source_id)
        elif control_ids:
            suggested.append(control_ids[0])
        return {
            "control_experiment_ids": control_ids,
            "validation_ready": validation_ready,
            "suggested_compare_ids": suggested,
            "paired_n": paired_n,
            "control_progress": control_progress,
            "all_controls_ready": all_controls_ready,
        }

    async def _build_delta(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
        summary: dict[str, Any],
        validation: dict[str, Any],
    ) -> dict[str, Any] | None:
        peer_id, relation = resolve_delta_peer(experiment, validation)
        if peer_id is None or relation is None:
            return None
        try:
            peer_row = await repo.get_by_id(peer_id)
        except KeyError:
            return None
        peer_summary = await self._build_summary(repo, peer_row)
        if relation == "vs_control":
            peer_ready = _control_experiment_ready(peer_summary)
        else:
            peer_ready = int(peer_summary.get("finished_games") or 0) > 0

        this_id = str(experiment["id"])
        this_games = [_normalize_game_row(g) for g in await repo.list_games(this_id)]
        peer_games = [_normalize_game_row(g) for g in await repo.list_games(peer_id)]
        rows = [experiment, peer_row]
        design = paired_design(rows)
        seat_winners = {}
        if design and design["primary_metric"]["kind"] == "seat_team_win_rate":
            seat_winners.update(await repo.seat_winners(this_id))
            seat_winners.update(await repo.seat_winners(peer_id))
        coverage, paired = self._paired_analysis(
            rows, {this_id: this_games, peer_id: peer_games}, seat_winners, attach_rows=False
        )
        assert paired is not None  # Exactly two runs.
        metric = paired["primary_metric"]
        this_rate, this_ci, this_n = _run_metric(summary, metric)
        peer_rate, peer_ci, peer_n = _run_metric(peer_summary, metric)
        paired_diff = paired["win_rate_diff"]
        paired_ci = paired["paired_ci"]
        if relation == "vs_control":
            paired_diff = -paired_diff if paired_diff is not None else None
            paired_ci = [-paired_ci[1], -paired_ci[0]] if paired_ci is not None else None

        delta = build_experiment_delta(
            peer_id=peer_id,
            peer_name=str(peer_row.get("name") or peer_id),
            relation=relation,
            peer_ready=peer_ready,
            primary_metric=metric,
            affected_player_ids=paired["affected_player_ids"],
            design_hypothesis=design["hypothesis"] if design else None,
            this_win_rate=this_rate,
            peer_win_rate=peer_rate,
            this_win_rate_ci=this_ci,
            peer_win_rate_ci=peer_ci,
            this_decisive_n=this_n,
            peer_decisive_n=peer_n,
            this_low_power=build_credibility(decisive_n=this_n, win_rate_ci=this_ci)["low_power"],
            peer_low_power=build_credibility(decisive_n=peer_n, win_rate_ci=peer_ci)["low_power"],
            paired_n=paired["shared_seeds"],
            win_rate_diff=paired_diff,
            paired_low_power=paired["low_power"],
            paired_p=paired["paired_p"],
            paired_ci=paired_ci,
            scenario_diffs=scenario_rate_diffs(
                summary.get("scenario_scores")
                if isinstance(summary.get("scenario_scores"), dict)
                else None,
                peer_summary.get("scenario_scores")
                if isinstance(peer_summary.get("scenario_scores"), dict)
                else None,
            ),
        )
        delta.update(
            deal_purpose=coverage["deal_purpose"],
            paired_excluded_n=coverage["excluded_n"],
            outcome_counts=paired["outcome_counts"],
            ci_method=paired["ci_method"],
        )
        review = protocol_review([experiment, peer_row], [])
        if (
            coverage["deal_purpose"] == "holdout"
            and coverage["excluded_n"]
            and delta["can_conclude"]
        ):
            delta["can_conclude"] = False
            delta["inconclusive_reason"] = "incomplete_holdout"
        if not review["controlled"]:
            delta["can_conclude"] = False
            delta["inconclusive_reason"] = "protocol_mismatch"
        return delta

    @staticmethod
    def _build_next_step(
        experiment: dict[str, Any],
        summary: dict[str, Any],
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        status = str(summary.get("status") or "pending_collect")
        # Training is optional; workflow guidance depends on run/control state only.
        control_ids = list(validation.get("control_experiment_ids") or [])
        control_progress = list(validation.get("control_progress") or [])
        if status == "pending_collect":
            return {"id": "collect", "action": "collect"}
        if status == "collecting":
            return {"id": "watch", "action": "games"}
        if protocol_source_experiment_id(experiment.get("protocol") or {}):
            return {"id": "review", "action": "stay"}
        if control_ids and validation.get("validation_ready"):
            return {"id": "review", "action": "stay"}
        if control_ids:
            pending = next((c for c in control_progress if not c.get("ready")), None)
            target_control = pending or (control_progress[0] if control_progress else None)
            ref_id = str(target_control["id"]) if target_control else control_ids[0]
            return {"id": "collect_control", "action": "control_collect", "ref_id": ref_id}
        return {"id": "review_decisions", "action": "decisions"}

    @staticmethod
    def _attach_compare_metrics(
        row: dict[str, Any],
        summary: dict[str, Any],
        extras: dict[str, Any],
    ) -> dict[str, Any]:
        with_winner = int(summary.get("games_with_winner") or 0)
        player_stats = [dict(stat) for stat in summary["player_stats"]]
        total_decisions = int(extras.get("decision_count") or 0)
        usable = int(summary.get("train_usable_decisions") or 0)
        train_rate = (usable / total_decisions) if total_decisions else 0.0
        parser_n = int(extras.get("parser_n") or 0)
        parser_rate = float(extras.get("parser_success_rate") or 0.0)
        decisive = int(extras.get("decisive_games") or 0)
        landlord_wins = int((extras.get("wins_by_role") or {}).get("landlord") or 0)
        l_low, l_high = wilson_interval(landlord_wins, decisive)
        landlord_ci = [round(l_low, 4), round(l_high, 4)]
        return {
            "id": row["id"],
            "name": row["name"],
            "notes": row.get("notes") or "",
            "hypothesis": row.get("hypothesis") or "",
            "game_type": row["game_type"],
            "player_ids": row["player_ids"],
            "protocol": row.get("protocol"),
            "finished_games": summary["finished_games"],
            "games_with_winner": with_winner,
            "avg_rounds": summary["avg_rounds"],
            "avg_response_time_ms": extras.get("avg_response_time_ms", 0.0),
            "p50_response_ms": extras.get("p50_response_ms", 0.0),
            "p95_response_ms": extras.get("p95_response_ms", 0.0),
            "total_tokens": extras.get("total_tokens", 0),
            "tokens_per_game": extras.get("tokens_per_game", 0.0),
            "avg_tokens_per_round": extras.get("avg_tokens_per_round", 0.0),
            "train_usable_rate": round(train_rate, 4),
            "train_usable_n": usable,
            "decision_count": total_decisions,
            "parser_success_rate": round(parser_rate, 4),
            "parser_n": parser_n,
            "wins_by_role": extras.get("wins_by_role") or {"landlord": 0, "peasant": 0},
            "decisive_games": decisive,
            "landlord_win_rate": extras.get("landlord_win_rate", 0.0),
            "landlord_win_rate_ci": landlord_ci,
            "credibility": build_credibility(decisive_n=decisive, win_rate_ci=landlord_ci),
            "status_counts": extras.get("status_counts") or {},
            "player_stats": player_stats,
            "paired_n": 0,
            "paired_seat_wins": [0] * len(row.get("player_ids") or []),
            "paired_landlord_win_rate": 0.0,
            "scenario_scores": extras.get("scenario_scores") or fill_scenario_scores({}),
        }

    @staticmethod
    def _paired_analysis(
        rows: list[dict[str, Any]],
        games_by_exp: dict[str, list[dict[str, Any]]],
        seat_winners: dict[str, set[str]],
        *,
        attach_rows: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        design = paired_design(rows)
        metric = design["primary_metric"] if design else {"kind": "landlord_win_rate"}
        target = metric.get("player_id")
        coverage, indexes = paired_cohort(
            rows, games_by_exp, attributable_games=set(seat_winners) if target else None
        )
        seeds = coverage["effective_seeds"]
        if attach_rows:
            ExperimentDeltaMixin._attach_cohort_counts(rows, indexes, seeds, seat_winners)

        if len(rows) != 2:
            return coverage, None
        source_id, control_id = str(rows[0]["id"]), str(rows[1]["id"])
        for row in rows:
            source = protocol_source_experiment_id(row.get("protocol") or {})
            if source in (source_id, control_id) and source != row["id"]:
                source_id, control_id = str(source), str(row["id"])
                break

        def won(run_id: str, seed: int) -> bool:
            game = indexes[run_id][seed]
            if target:
                return target in seat_winners[game["id"]]
            return bool(game["winner_role"] == "landlord")

        stats = summarize_paired_outcomes(
            (won(source_id, seed), won(control_id, seed)) for seed in seeds
        )
        return coverage, {
            **stats,
            "primary_metric": metric,
            "affected_player_ids": design["affected_player_ids"] if design else [],
            "shared_seeds": len(seeds),
            "source_id": source_id,
            "control_id": control_id,
            "low_power": len(seeds) < CREDIBILITY_MIN_DECISIVE_N,
        }

    @staticmethod
    def _attach_cohort_counts(
        rows: list[dict[str, Any]],
        indexes: dict[str, dict[int, dict[str, Any]]],
        seeds: list[int],
        seat_winners: dict[str, set[str]],
    ) -> None:
        for row in rows:
            players = list(row.get("player_ids") or [])
            wins = {pid: 0 for pid in players}
            selected = [indexes[str(row["id"])][seed] for seed in seeds]
            attributable = bool(seeds) and all(game["id"] in seat_winners for game in selected)
            for game in selected:
                for pid in seat_winners.get(game["id"], set()):
                    wins[pid] += 1
            row["paired_n"] = len(seeds)
            row["paired_seat_wins"] = [wins[pid] for pid in players] if attributable else None
            row["paired_landlord_win_rate"] = (
                round(sum(g["winner_role"] == "landlord" for g in selected) / len(seeds), 4)
                if seeds
                else None
            )
            for stat in row.get("player_stats") or []:
                stat["paired_wins"] = wins[stat["player_id"]] if attributable else None


def _run_metric(
    summary: dict[str, Any], metric: dict[str, Any]
) -> tuple[float | None, list[float] | None, int]:
    if metric["kind"] == "seat_team_win_rate":
        stat = next(s for s in summary["player_stats"] if s["player_id"] == metric["player_id"])
        return stat["win_rate"], ci_pair(stat["win_rate_ci"]), stat["decided_games"]
    n = int(summary["decisive_games"])
    return (
        (summary["landlord_win_rate"], ci_pair(summary["landlord_win_rate_ci"]), n)
        if n
        else (None, None, 0)
    )


def _slim_list_delta(delta: dict[str, Any] | None) -> dict[str, Any] | None:
    """Home-list delta: direction + confidence, no scenario bars."""
    if delta is None:
        return None
    return {
        "peer_id": delta.get("peer_id"),
        "peer_name": delta.get("peer_name"),
        "relation": delta.get("relation"),
        "primary_metric": delta["primary_metric"],
        "affected_player_ids": delta["affected_player_ids"],
        "difference_basis": delta["difference_basis"],
        "win_rate_diff": delta["win_rate_diff"],
        "paired_n": delta.get("paired_n"),
        "can_conclude": delta.get("can_conclude"),
        "inconclusive_reason": delta.get("inconclusive_reason"),
        "verdict_key": delta.get("verdict_key"),
        "this_decisive_n": delta.get("this_decisive_n"),
        "peer_decisive_n": delta.get("peer_decisive_n"),
    }


def _normalize_game_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out.get("player_ids"), str):
        out["player_ids"] = json.loads(out["player_ids"])
    if isinstance(out.get("metadata"), str):
        out["metadata"] = json.loads(out["metadata"])
    return out


async def _games_with_progress(
    conn: aiosqlite.Connection,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    games = [_normalize_game_row(row) for row in rows]
    latest = await DecisionRepository(conn).latest_progress_by_game_ids(
        [str(game["id"]) for game in games]
    )
    for game in games:
        snap = latest.get(str(game["id"]))
        game["progress"] = build_game_progress(
            game_phase=str(snap["game_phase"]) if snap else None,
            round_number=int(snap["round_number"]) if snap else None,
            player_id=str(snap["player_id"]) if snap else None,
        )
    return games
