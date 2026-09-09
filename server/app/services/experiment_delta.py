"""Summary / delta / compare helpers for ExperimentService."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite
import structlog

from app.core.eval.scorer import (
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.stats.game_progress import build_game_progress
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
    protocol_deal_seeds,
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

    async def compare_experiments(self, experiment_ids: list[str]) -> dict[str, Any]:
        """Side-by-side metrics for 2–5 experiments, including Wilson CIs."""
        unique_ids = list(dict.fromkeys(experiment_ids))
        if len(unique_ids) < 2 or len(unique_ids) > 5:
            raise ExperimentValidationError("对比需要 2 到 5 个不重复的实验 ID")

        rows: list[dict[str, Any]] = []
        games_by_exp: dict[str, list[dict[str, Any]]] = {}
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            for experiment_id in unique_ids:
                try:
                    row = await repo.get_by_id(experiment_id)
                except KeyError as exc:
                    raise ExperimentNotFoundError(experiment_id) from exc
                summary = await self._build_summary(repo, row)
                extras = await repo.eval_aggregates(experiment_id)
                protocol = row.get("protocol")
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
                rows.append(self._attach_compare_metrics(row, summary, extras))
        finally:
            await conn.close()

        self._attach_paired_compare_metrics(rows, games_by_exp)
        payload: dict[str, Any] = {"experiments": rows}
        paired_summary = self._build_paired_summary(rows, games_by_exp)
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
                wid = str(winner)
                if wid in wins_by_config:
                    wins_by_config[wid] += 1

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
        landlord_games_map = eval_metrics.get("landlord_games_by_player") or {}
        landlord_wins_map = eval_metrics.get("landlord_wins_by_player") or {}
        player_stats: list[dict[str, Any]] = []
        for pid in player_ids:
            wins = wins_by_config.get(pid, 0)
            avg_ms, round_count = response_by_player.get(pid, (0.0, 0))
            win_rate = (wins / with_winner) if with_winner > 0 else 0.0
            low, high = wilson_interval(wins, with_winner)
            games_as_landlord = int(landlord_games_map.get(pid, 0))
            wins_as_landlord = int(landlord_wins_map.get(pid, 0))
            landlord_rate = wins_as_landlord / games_as_landlord if games_as_landlord > 0 else 0.0
            player_stats.append(
                {
                    "player_id": pid,
                    "wins": wins,
                    "win_rate": round(win_rate, 4),
                    "win_rate_ci": [round(low, 4), round(high, 4)],
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
            "credibility": build_credibility(decisive_n=decisive, landlord_win_rate_ci=landlord_ci),
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
        if control_ids:
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
        paired = self._build_paired_summary(
            [
                {"id": this_id, "protocol": experiment.get("protocol")},
                {"id": peer_id, "protocol": peer_row.get("protocol")},
            ],
            {this_id: this_games, peer_id: peer_games},
        )

        paired_n = 0
        paired_diff: float | None = None
        paired_low_power = False
        paired_p: float | None = None
        paired_ci: list[float] | None = None
        if paired is not None:
            from app.core.stats.paired import mcnemar_exact_p, paired_bootstrap_ci

            paired_n = int(paired.get("shared_seeds") or 0)
            raw_diff = paired.get("landlord_win_rate_diff")
            if raw_diff is not None:
                ctl_minus_src = float(raw_diff)
                if relation == "vs_source":
                    paired_diff = round(ctl_minus_src, 4)
                else:
                    paired_diff = round(-ctl_minus_src, 4)
            paired_low_power = bool(paired.get("low_power"))
            b = int(paired.get("mcnemar_b") or 0)
            c = int(paired.get("mcnemar_c") or 0)
            if relation == "vs_control":
                # Flip discordant counts so "this vs peer" matches delta sign.
                b, c = c, b
            if paired_n > 0:
                paired_p = round(mcnemar_exact_p(b, c), 4)
                seed_diffs = list(paired.get("seed_diffs") or [])
                if relation == "vs_control":
                    seed_diffs = [-float(x) for x in seed_diffs]
                elif relation == "vs_source":
                    seed_diffs = [float(x) for x in seed_diffs]
                lo, hi = paired_bootstrap_ci(seed_diffs, n_boot=2000, seed=0)
                paired_ci = [lo, hi]

        this_cred = summary.get("credibility") or {}
        peer_cred = peer_summary.get("credibility") or {}
        return build_experiment_delta(
            peer_id=peer_id,
            peer_name=str(peer_row.get("name") or peer_id),
            relation=relation,
            peer_ready=peer_ready,
            this_landlord_win_rate=float(summary.get("landlord_win_rate") or 0.0),
            peer_landlord_win_rate=float(peer_summary.get("landlord_win_rate") or 0.0),
            this_landlord_win_rate_ci=ci_pair(summary.get("landlord_win_rate_ci")),
            peer_landlord_win_rate_ci=ci_pair(peer_summary.get("landlord_win_rate_ci")),
            this_decisive_n=int(summary.get("decisive_games") or 0),
            peer_decisive_n=int(peer_summary.get("decisive_games") or 0),
            this_low_power=bool(this_cred.get("low_power")),
            peer_low_power=bool(peer_cred.get("low_power")),
            paired_n=paired_n,
            paired_landlord_win_rate_diff=paired_diff,
            paired_low_power=paired_low_power,
            paired_p=paired_p,
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

    @staticmethod
    def _build_next_step(
        experiment: dict[str, Any],
        summary: dict[str, Any],
        validation: dict[str, Any],
        *,
        training_completed: bool = False,
    ) -> dict[str, Any]:
        status = str(summary.get("status") or "pending_collect")
        usable = int(summary.get("train_usable_decisions") or 0)
        decision_count = int(summary.get("decision_count") or 0)
        not_usable = decision_count - usable
        control_ids = list(validation.get("control_experiment_ids") or [])
        control_progress = list(validation.get("control_progress") or [])

        if status == "pending_collect":
            return {"id": "collect", "action": "collect"}
        if status == "collecting":
            return {"id": "watch", "action": "games"}
        if usable > 0 and decision_count > 0 and not_usable / decision_count > 0.2:
            return {"id": "review_decisions", "action": "decisions"}
        if usable > 0 and not control_ids:
            if training_completed:
                return {"id": "open_control", "action": "control"}
            return {"id": "register_train", "action": "train"}
        if usable > 0 and control_ids and validation.get("validation_ready"):
            return {"id": "review", "action": "stay"}
        if usable > 0 and control_ids:
            pending = next((c for c in control_progress if not c.get("ready")), None)
            target_control = pending or (control_progress[0] if control_progress else None)
            ref_id = str(target_control["id"]) if target_control else control_ids[0]
            return {
                "id": "collect_control",
                "action": "control_collect",
                "ref_id": ref_id,
            }
        if status in ("ready_review", "ready_more") and usable == 0:
            return {"id": "decisions", "action": "decisions"}
        if status == "ready_more":
            return {"id": "collect_more", "action": "collect"}
        return {"id": "review", "action": "games"}

    @staticmethod
    def _attach_compare_metrics(
        row: dict[str, Any],
        summary: dict[str, Any],
        extras: dict[str, Any],
    ) -> dict[str, Any]:
        with_winner = int(summary.get("games_with_winner") or 0)
        player_stats: list[dict[str, Any]] = []
        for stat in summary.get("player_stats") or []:
            wins = int(stat.get("wins") or 0)
            low, high = wilson_interval(wins, with_winner)
            player_stats.append(
                {
                    **stat,
                    "win_rate_ci": list(stat.get("win_rate_ci") or [round(low, 4), round(high, 4)]),
                    "paired_wins": 0,
                }
            )
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
            "credibility": build_credibility(decisive_n=decisive, landlord_win_rate_ci=landlord_ci),
            "status_counts": extras.get("status_counts") or {},
            "player_stats": player_stats,
            "paired_n": 0,
            "paired_seat_wins": [0] * len(row.get("player_ids") or []),
            "paired_landlord_win_rate": 0.0,
            "scenario_scores": extras.get("scenario_scores") or fill_scenario_scores({}),
        }

    @staticmethod
    def _attach_paired_compare_metrics(
        rows: list[dict[str, Any]],
        games_by_exp: dict[str, list[dict[str, Any]]],
    ) -> None:
        seed_sets: list[set[int]] = []
        for row in rows:
            protocol = row.get("protocol") or {}
            seeds = set(protocol_deal_seeds(protocol)) if isinstance(protocol, dict) else set()
            seed_sets.append(seeds)
        if not seed_sets:
            return
        common = set.intersection(*seed_sets) if seed_sets else set()
        if not common:
            for row in rows:
                row["paired_n"] = 0
                row["paired_landlord_win_rate"] = 0.0
            return

        for row in rows:
            player_ids: list[str] = list(row.get("player_ids") or [])
            seat_wins = [0] * len(player_ids)
            wins_by_player = {pid: 0 for pid in player_ids}
            games = games_by_exp.get(str(row["id"]), [])
            by_seed: dict[int, dict[str, Any]] = {}
            for game in games:
                meta = game.get("metadata") or {}
                if not isinstance(meta, dict):
                    continue
                raw_seed = meta.get("deal_seed")
                if raw_seed is None:
                    continue
                by_seed[int(raw_seed)] = game

            paired_n = 0
            paired_landlord_wins = 0
            paired_decisive = 0
            for seed in common:
                seed_game = by_seed.get(seed)
                if seed_game is None:
                    continue
                winner = seed_game.get("winner_id")
                if not winner:
                    continue
                paired_n += 1
                wid = str(winner)
                if wid in wins_by_player:
                    wins_by_player[wid] += 1
                try:
                    seat = player_ids.index(wid)
                    seat_wins[seat] += 1
                except ValueError:
                    pass
                role = str(seed_game.get("winner_role") or "")
                if role in ("landlord", "peasant"):
                    paired_decisive += 1
                    if role == "landlord":
                        paired_landlord_wins += 1

            row["paired_n"] = paired_n
            row["paired_seat_wins"] = seat_wins
            row["paired_landlord_win_rate"] = (
                round(paired_landlord_wins / paired_decisive, 4) if paired_decisive > 0 else 0.0
            )
            for stat in row.get("player_stats") or []:
                pid = str(stat.get("player_id") or "")
                stat["paired_wins"] = wins_by_player.get(pid, 0)

    @staticmethod
    def _build_paired_summary(
        rows: list[dict[str, Any]],
        games_by_exp: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any] | None:
        if len(rows) != 2:
            return None

        by_id = {str(row["id"]): row for row in rows}
        source_id: str | None = None
        control_id: str | None = None
        for row in rows:
            protocol = row.get("protocol") or {}
            src = protocol_source_experiment_id(protocol) if isinstance(protocol, dict) else None
            if src and str(src) in by_id:
                control_id = str(row["id"])
                source_id = str(src)
                break
        if source_id is None or control_id is None:
            return None

        seed_sets: list[set[int]] = []
        for row in rows:
            protocol = row.get("protocol") or {}
            seed_sets.append(
                set(protocol_deal_seeds(protocol)) if isinstance(protocol, dict) else set()
            )
        common = set.intersection(*seed_sets) if seed_sets else set()
        if not common:
            return {
                "shared_seeds": 0,
                "source_id": source_id,
                "control_id": control_id,
                "landlord_win_rate_diff": None,
                "low_power": True,
            }

        def landlord_wins_on_common(exp_id: str) -> tuple[int, int]:
            """Return (landlord_wins, decisive) on seeds where this experiment finished."""
            games = games_by_exp.get(exp_id, [])
            by_seed: dict[int, dict[str, Any]] = {}
            for game in games:
                meta = game.get("metadata") or {}
                if not isinstance(meta, dict):
                    continue
                raw_seed = meta.get("deal_seed")
                if raw_seed is None:
                    continue
                by_seed[int(raw_seed)] = game

            landlord_wins = 0
            decisive = 0
            for seed in common:
                seed_game = by_seed.get(seed)
                if seed_game is None:
                    continue
                winner = seed_game.get("winner_id")
                if not winner:
                    continue
                role = str(seed_game.get("winner_role") or "")
                if role in ("landlord", "peasant"):
                    decisive += 1
                    if role == "landlord":
                        landlord_wins += 1
            return landlord_wins, decisive

        src_ll_wins, src_dec = landlord_wins_on_common(source_id)
        ctl_ll_wins, ctl_dec = landlord_wins_on_common(control_id)

        def landlord_on_seed(exp_id: str, seed: int) -> int | None:
            """1 landlord win, 0 peasant win, None if missing/undecisive."""
            for game in games_by_exp.get(exp_id, []):
                meta = game.get("metadata") or {}
                if not isinstance(meta, dict):
                    continue
                raw_seed = meta.get("deal_seed")
                if raw_seed is None:
                    continue
                if int(raw_seed) != int(seed):
                    continue
                if not game.get("winner_id"):
                    return None
                role = str(game.get("winner_role") or "")
                if role == "landlord":
                    return 1
                if role == "peasant":
                    return 0
                return None
            return None

        shared_played = 0
        mcnemar_b = 0  # control landlord, source peasant
        mcnemar_c = 0  # control peasant, source landlord
        seed_diffs: list[float] = []
        for seed in common:
            src_ll = landlord_on_seed(source_id, seed)
            ctl_ll = landlord_on_seed(control_id, seed)
            if src_ll is None or ctl_ll is None:
                continue
            shared_played += 1
            seed_diffs.append(float(ctl_ll - src_ll))
            if ctl_ll == 1 and src_ll == 0:
                mcnemar_b += 1
            elif ctl_ll == 0 and src_ll == 1:
                mcnemar_c += 1

        if shared_played <= 0:
            return {
                "shared_seeds": len(common),
                "source_id": source_id,
                "control_id": control_id,
                "landlord_win_rate_diff": None,
                "low_power": True,
                "mcnemar_b": 0,
                "mcnemar_c": 0,
                "seed_diffs": [],
            }

        src_rate = src_ll_wins / src_dec if src_dec else 0.0
        ctl_rate = ctl_ll_wins / ctl_dec if ctl_dec else 0.0
        diff = round(ctl_rate - src_rate, 4)
        return {
            "shared_seeds": shared_played,
            "source_id": source_id,
            "control_id": control_id,
            "landlord_win_rate_diff": diff,
            "low_power": shared_played < CREDIBILITY_MIN_DECISIVE_N,
            "mcnemar_b": mcnemar_b,
            "mcnemar_c": mcnemar_c,
            "seed_diffs": seed_diffs,
        }


def _slim_list_delta(delta: dict[str, Any] | None) -> dict[str, Any] | None:
    """Home-list delta: direction + confidence, no scenario bars."""
    if delta is None:
        return None
    return {
        "peer_id": delta.get("peer_id"),
        "peer_name": delta.get("peer_name"),
        "relation": delta.get("relation"),
        "landlord_win_rate_diff": delta.get("landlord_win_rate_diff"),
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
