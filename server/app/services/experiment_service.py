"""Experiment (run) service — one researcher session spanning collect → review."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.core.engine.base import EngineCapability
from app.core.eval.scorer import (
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.eval.scorers import build_scorer_registry
from app.core.pack import (
    KIND_EXPERIMENT_PACK,
    KIND_PLAYER_PACK,
    build_experiment_pack,
    parse_pack,
)
from app.core.stats.benchmark import build_benchmark_coverage
from app.core.stats.game_progress import build_game_progress
from app.core.stats.proportion import wilson_interval
from app.core.stats.scenarios import fill_scenario_scores, scenario_rate_diffs
from app.database import open_db_connection
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_eval import (
    CREDIBILITY_MIN_DECISIVE_N,
    build_credibility,
    build_experiment_delta,
    ci_pair,
    derive_experiment_status,
    resolve_delta_peer,
)
from app.services.experiment_protocol import (
    build_protocol,
    clamp_benchmark_collect_count,
    pick_collect_seed,
    protocol_collect_mode,
    protocol_deal_seeds,
    protocol_eval_metric_ids,
    protocol_game_type,
    protocol_pair_deals,
    protocol_players,
    protocol_source_experiment_id,
    set_protocol_deal_seeds,
    set_protocol_pair_deals,
    validate_protocol,
)
from app.services.game_service import GameService
from app.utils.exceptions import AppError, ProviderNotConfiguredError
from app.utils.id_generator import generate_id
from app.utils.providers import unconfigured_providers_from_players

logger = structlog.get_logger()

_ACTIVE_STATUSES = frozenset({"created", "running", "paused", "pending"})
_VALIDATION_MIN_PAIRED_N = 5


def _control_experiment_ready(summary: dict[str, Any]) -> bool:
    paired_n = int(summary.get("paired_games") or 0)
    finished = int(summary.get("finished_games") or 0)
    target = int(summary.get("target_games") or 0)
    return paired_n >= _VALIDATION_MIN_PAIRED_N or finished >= target


class ExperimentNotFoundError(AppError):
    def __init__(self, experiment_id: str) -> None:
        super().__init__(
            message=f"Experiment not found: {experiment_id}",
            code="EXPERIMENT_NOT_FOUND",
            status_code=404,
        )


class ExperimentValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="EXPERIMENT_VALIDATION_FAILED",
            status_code=400,
        )


class ExperimentService:
    """Manages experiment runs and collection against GameService."""

    def __init__(
        self,
        sqlite_path: str,
        game_service: GameService,
        scorer_registry: ScorerRegistry | None = None,
    ) -> None:
        self._sqlite_path = sqlite_path
        self._game_service = game_service
        # When injected (tests), always use that registry. Otherwise build per game_type.
        self._scorer_registry = scorer_registry

    def _registry_for(self, protocol: dict[str, Any] | None, game_type: str) -> ScorerRegistry:
        if self._scorer_registry is not None:
            return self._scorer_registry
        resolved = protocol_game_type(protocol) if isinstance(protocol, dict) else None
        return build_scorer_registry(game_type=resolved or game_type)

    async def _conn(self) -> aiosqlite.Connection:
        return await open_db_connection(self._sqlite_path)

    def _prompt_version(self) -> str:
        from app.core.ai.prompts.registry import DEFAULT_TEMPLATE_VERSION

        return DEFAULT_TEMPLATE_VERSION

    def _snapshot_players(self, player_ids: list[str]) -> list[dict[str, Any]]:
        cfg_svc = self._game_service._experiment_config_service
        players: list[dict[str, Any]] = []
        for pid in player_ids:
            cfg = cfg_svc.get_config(pid)
            if cfg is None:
                continue
            players.append(
                {
                    "id": cfg["id"],
                    "name": cfg["name"],
                    "notes": cfg.get("notes") or "",
                    "policy_kind": cfg.get("policy_kind") or "llm",
                    "model_config": deepcopy(cfg.get("model_config") or {}),
                }
            )
        return players

    def _engine_capability(self, game_type: str) -> EngineCapability:
        return self._game_service._engine_registry.get_capability(game_type)

    def _benchmark_seeds(self, game_type: str) -> list[int]:
        return list(self._engine_capability(game_type).benchmark_seeds)

    def _build_protocol(
        self,
        *,
        player_ids: list[str],
        source_experiment_id: str | None,
        pair_deals: bool,
        deal_seeds: list[int],
        frozen_at: str,
        game_type: str,
        collect_mode: str = "free",
    ) -> dict[str, Any]:
        return build_protocol(
            players=self._snapshot_players(player_ids),
            source_experiment_id=source_experiment_id,
            pair_deals=pair_deals,
            deal_seeds=deal_seeds,
            frozen_at=frozen_at,
            prompt_version=self._prompt_version(),
            collect_mode=collect_mode,
            protocol_fingerprint=self._engine_capability(game_type).protocol_fingerprint(),
        )
    async def create_experiment(
        self,
        *,
        name: str,
        notes: str,
        game_type: str,
        player_ids: list[str],
        target_games: int,
        source_experiment_id: str | None = None,
        pair_deals: bool = False,
        hypothesis: str = "",
        tags: list[str] | None = None,
        collect_mode: str = "free",
        preset_deal_seeds: list[int] | None = None,
    ) -> dict[str, Any]:
        min_players, max_players = self._game_service.player_slots(game_type)
        n_players = len(player_ids)
        if n_players < min_players or n_players > max_players:
            if min_players == max_players:
                raise ExperimentValidationError(
                    f"{game_type} 实验需要恰好 {min_players} 个选手配置"
                )
            raise ExperimentValidationError(
                f"{game_type} 实验需要 {min_players}-{max_players} 个选手配置"
            )
        if len(set(player_ids)) != n_players:
            raise ExperimentValidationError("选手配置不能重复")

        missing = [
            pid
            for pid in player_ids
            if self._game_service._experiment_config_service.get_config(pid) is None
        ]
        if missing:
            from app.utils.exceptions import InvalidPlayerIdsError

            raise InvalidPlayerIdsError(missing)

        deal_seeds: list[int] = []
        source_id: str | None = None
        if pair_deals:
            if not source_experiment_id:
                raise ExperimentValidationError("配对发牌需要指定源实验")
            source = await self.get_experiment(source_experiment_id, include_games=False)
            if str(source["game_type"]) != game_type:
                raise ExperimentValidationError("对照实验的游戏类型必须与源实验一致")
            if len(source.get("player_ids") or []) != n_players:
                raise ExperimentValidationError("对照实验的座位数必须与源实验一致")
            source_id = str(source["id"])
            source_protocol = source.get("protocol") or {}
            if isinstance(source_protocol, dict):
                deal_seeds = protocol_deal_seeds(source_protocol)
            else:
                deal_seeds = []

        if preset_deal_seeds is not None:
            deal_seeds = list(preset_deal_seeds)
        elif collect_mode == "benchmark" and not pair_deals:
            seeds = self._benchmark_seeds(game_type)
            if not seeds:
                raise ExperimentValidationError(
                    f"{game_type} 不支持基准测试（引擎未声明 benchmark_seeds）"
                )
            deal_seeds = seeds[:target_games]

        experiment_id = generate_id("exp")
        now = datetime.now(tz=UTC).isoformat()
        effective_mode = "benchmark" if collect_mode == "benchmark" and not pair_deals else "free"
        protocol = self._build_protocol(
            player_ids=player_ids,
            source_experiment_id=source_id,
            pair_deals=bool(pair_deals and source_id),
            deal_seeds=deal_seeds,
            frozen_at=now,
            collect_mode=effective_mode,
            game_type=game_type,
        )

        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            await repo.create(
                experiment_id=experiment_id,
                name=name.strip(),
                notes=notes.strip(),
                hypothesis=hypothesis.strip(),
                tags=tags or [],
                game_type=game_type,
                player_ids=player_ids,
                target_games=target_games,
                created_at=now,
                updated_at=now,
                protocol=protocol,
            )
        finally:
            await conn.close()
        logger.info(
            "experiment_created",
            experiment_id=experiment_id,
            pair_deals=protocol_pair_deals(protocol),
            deal_seed_count=len(deal_seeds),
        )
        return await self.get_experiment(experiment_id, include_games=False)

    async def update_experiment(
        self,
        experiment_id: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        hypothesis: str | None = None,
        conclusion: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            try:
                await repo.get_by_id(experiment_id)
            except KeyError as exc:
                raise ExperimentNotFoundError(experiment_id) from exc
            fields: dict[str, Any] = {}
            if name is not None:
                fields["name"] = name.strip()
            if notes is not None:
                fields["notes"] = notes.strip()
            if hypothesis is not None:
                fields["hypothesis"] = hypothesis.strip()
            if conclusion is not None:
                fields["conclusion"] = conclusion.strip()
            if tags is not None:
                cleaned = [t.strip() for t in tags if t.strip()][:20]
                fields["tags"] = cleaned
            now = datetime.now(tz=UTC).isoformat()
            await repo.update_fields(experiment_id, updated_at=now, fields=fields)
        finally:
            await conn.close()
        return await self.get_experiment(experiment_id, include_games=False)

    async def draft_conclusion(
        self,
        experiment_id: str,
        *,
        locale: str = "zh-CN",
    ) -> dict[str, Any]:
        """Build a conclusion draft from delta + high EV-loss moves (does not write)."""
        from app.core.research.conclusion_draft import build_conclusion_draft
        from app.core.stats.highlights import BLUNDER_EV_LOSS

        detail = await self.get_experiment(experiment_id, include_games=False)
        delta = detail.get("delta")
        if delta is not None and not isinstance(delta, dict):
            delta = None

        blunders = await self._top_blunders(experiment_id, limit=3, min_loss=BLUNDER_EV_LOSS)
        draft = build_conclusion_draft(
            experiment=detail,
            delta=delta,
            blunders=blunders,
            locale=locale,
        )
        return {
            "text": draft.text,
            "locale": draft.locale,
            "verdict_key": draft.verdict_key,
            "can_conclude": draft.can_conclude,
            "blunder_ids": draft.blunder_ids,
            "blunders": [
                {
                    "id": str(row.get("id") or ""),
                    "game_id": str(row.get("game_id") or ""),
                    "round_number": row.get("round_number"),
                    "action_id": str(row.get("action_id") or ""),
                    "ev_loss": row.get("ev_loss"),
                }
                for row in blunders
                if str(row.get("id") or "")
            ],
        }

    async def _top_blunders(
        self,
        experiment_id: str,
        *,
        limit: int = 3,
        min_loss: float,
    ) -> list[dict[str, Any]]:
        """Highest EV-loss decisions for this experiment (evaluated only)."""
        conn = await self._conn()
        try:
            repo = DecisionRepository(conn)
            items, _total = await repo.list_decision_points(
                experiment_id=experiment_id,
                limit=500,
                offset=0,
            )
        finally:
            await conn.close()

        scored: list[dict[str, Any]] = []
        for item in items:
            raw = item.get("ev_loss")
            if raw is None:
                continue
            try:
                loss = float(raw)
            except (TypeError, ValueError):
                continue
            if loss < min_loss:
                continue
            scored.append(item)
        scored.sort(key=lambda row: float(row["ev_loss"]), reverse=True)
        return scored[:limit]

    async def clone_experiment(
        self,
        experiment_id: str,
        *,
        name: str | None = None,
        copy_deal_seeds: bool = True,
        copy_hypothesis: bool = True,
    ) -> dict[str, Any]:
        source = await self.get_experiment(experiment_id, include_games=False)
        protocol = source.get("protocol") or {}
        deal_seeds: list[int] | None = None
        if copy_deal_seeds and isinstance(protocol, dict):
            deal_seeds = protocol_deal_seeds(protocol)
        clone_name = (name or f"{source['name']} (copy)").strip()
        collect_mode = (
            protocol_collect_mode(protocol) if isinstance(protocol, dict) else "free"
        )
        return await self.create_experiment(
            name=clone_name,
            notes=str(source.get("notes") or ""),
            hypothesis=str(source.get("hypothesis") or "") if copy_hypothesis else "",
            tags=list(source.get("tags") or []),
            game_type=str(source["game_type"]),
            player_ids=list(source["player_ids"]),
            target_games=int(source["target_games"]),
            collect_mode=collect_mode,
            preset_deal_seeds=deal_seeds,
        )

    async def export_pack(self, experiment_id: str) -> dict[str, Any]:
        experiment = await self.get_experiment(experiment_id, include_games=False)
        raw_protocol = experiment.get("protocol")
        protocol = raw_protocol if isinstance(raw_protocol, dict) else {}
        cfg_svc = self._game_service._experiment_config_service
        players: list[dict[str, Any]] = []
        frozen = protocol_players(protocol) if isinstance(protocol, dict) else []
        frozen_by_id = {
            str(item.get("id")): item
            for item in frozen
            if isinstance(item, dict) and item.get("id")
        }
        for pid in list(experiment.get("player_ids") or []):
            live = cfg_svc.get_config(str(pid))
            if live is not None:
                players.append(live)
            elif str(pid) in frozen_by_id:
                players.append(frozen_by_id[str(pid)])
        if not players:
            players = [item for item in frozen if isinstance(item, dict)]
        return build_experiment_pack(
            experiment=experiment,
            protocol=protocol if isinstance(protocol, dict) else None,
            players=players,
            exported_at=datetime.now(tz=UTC).isoformat(),
        )

    async def import_pack(
        self,
        raw: dict[str, Any],
        *,
        include_experiment: bool,
    ) -> dict[str, Any]:
        try:
            pack = parse_pack(raw)
        except ValueError as exc:
            raise ExperimentValidationError(str(exc)) from exc

        cfg_svc = self._game_service._experiment_config_service
        player_result = await cfg_svc.import_players(list(pack.get("players") or []))
        requirements = pack.get("requirements") or {}
        settings = getattr(self._game_service, "_settings", None)
        unconfigured: list[str] = []
        if settings is not None:
            unconfigured = unconfigured_providers_from_players(
                settings, list(pack.get("players") or [])
            )

        payload: dict[str, Any] = {
            "kind": pack["kind"],
            "experiment": None,
            "players_created": player_result["created"],
            "players_reused": player_result["reused"],
            "requirements": requirements,
            "unconfigured_providers": unconfigured,
        }
        if pack["kind"] != KIND_EXPERIMENT_PACK or not include_experiment:
            payload["kind"] = KIND_PLAYER_PACK if not include_experiment else pack["kind"]
            return payload

        spec = pack["experiment"]
        collect_mode = str(spec.get("collect_mode") or "free")
        if collect_mode not in ("free", "benchmark"):
            collect_mode = "free"
        deal_seeds = [int(s) for s in (pack.get("deal_seeds") or [])]
        created = await self.create_experiment(
            name=str(spec.get("name") or "imported"),
            notes=str(spec.get("notes") or ""),
            hypothesis=str(spec.get("hypothesis") or ""),
            tags=list(spec.get("tags") or []),
            game_type=str(spec.get("game_type") or "doudizhu"),
            player_ids=list(spec.get("player_ids") or []),
            target_games=int(spec.get("target_games") or 1),
            collect_mode=collect_mode,
            preset_deal_seeds=deal_seeds or None,
        )
        payload["experiment"] = created
        return payload

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
                metric_ids = (
                    protocol_eval_metric_ids(protocol_dict) if protocol_dict else []
                )
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

    async def list_experiments(self) -> list[dict[str, Any]]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            rows = await repo.list_all()
            results: list[dict[str, Any]] = []
            for row in rows:
                summary = await self._build_summary(repo, row)
                validation = await self._build_validation(repo, row, summary)
                experiment_id = str(row["id"])
                training_at = await repo.first_training_completed_at(experiment_id)
                next_step = self._build_next_step(
                    row,
                    summary,
                    validation,
                    training_completed=training_at is not None,
                )
                delta = await self._build_delta(repo, row, summary, validation)
                slim_delta = _slim_list_delta(delta)
                results.append(
                    {
                        **row,
                        "summary": summary,
                        "next_step": next_step,
                        "delta": slim_delta,
                    }
                )
            return results
        finally:
            await conn.close()

    async def get_experiment(
        self,
        experiment_id: str,
        *,
        include_games: bool = True,
    ) -> dict[str, Any]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            try:
                row = await repo.get_by_id(experiment_id)
            except KeyError as exc:
                raise ExperimentNotFoundError(experiment_id) from exc
            summary = await self._build_summary(repo, row)
            payload: dict[str, Any] = {**row, "summary": summary}
            games = await repo.list_games(experiment_id)
            normalized_games = [_normalize_game_row(game) for game in games]
            if include_games:
                payload["games"] = await _games_with_progress(conn, games)
            payload["benchmark"] = build_benchmark_coverage(
                protocol=row.get("protocol") if isinstance(row.get("protocol"), dict) else None,
                games=normalized_games,
            )
            payload["timeline"] = await self._build_timeline(repo, row)
            payload["validation"] = await self._build_validation(repo, row, summary)
            training_completed = any(
                event.get("id") == "training_completed" for event in payload["timeline"]
            )
            payload["next_step"] = self._build_next_step(
                row,
                summary,
                payload["validation"],
                training_completed=training_completed,
            )
            payload["delta"] = await self._build_delta(
                repo, row, summary, payload["validation"]
            )
            return payload
        finally:
            await conn.close()

    async def collect(
        self,
        experiment_id: str,
        *,
        count: int,
        db: aiosqlite.Connection,
    ) -> dict[str, Any]:
        experiment = await self.get_experiment(experiment_id, include_games=True)
        player_ids = list(experiment["player_ids"])
        game_type = str(experiment["game_type"])
        existing_games = list(experiment.get("games") or [])
        start_index = len(existing_games)

        now = datetime.now(tz=UTC).isoformat()
        try:
            protocol = validate_protocol(experiment.get("protocol"))
        except ValueError as exc:
            raise ExperimentValidationError(str(exc)) from exc
        protocol = deepcopy(protocol)

        from app.config import Settings

        settings = getattr(self._game_service, "_settings", None)
        frozen_players = protocol_players(protocol)
        if isinstance(settings, Settings):
            missing = unconfigured_providers_from_players(settings, frozen_players)
            if missing:
                raise ProviderNotConfiguredError(missing)

        deal_seeds = protocol_deal_seeds(protocol)
        pair_deals = protocol_pair_deals(protocol)
        collect_mode = protocol_collect_mode(protocol)

        if collect_mode == "benchmark" and not pair_deals:
            try:
                count = clamp_benchmark_collect_count(
                    deal_seeds=deal_seeds,
                    start_index=start_index,
                    count=count,
                )
            except ValueError as exc:
                raise ExperimentValidationError(str(exc)) from exc

        game_ids: list[str] = []
        for offset in range(count):
            index = start_index + offset
            seed, paired = pick_collect_seed(
                index=index,
                deal_seeds=deal_seeds,
                pair_deals=pair_deals,
                collect_mode=collect_mode,
            )

            game = await self._game_service.create_game(
                game_type=game_type,
                player_ids=player_ids,
                mode="batch",
                db=db,
                experiment_id=experiment_id,
                deal_seed=seed,
                paired=paired,
                frozen_players=frozen_players,
            )
            await self._game_service.start_game(game["id"], db=db)
            game_ids.append(game["id"])

        set_protocol_deal_seeds(protocol, deal_seeds)
        set_protocol_pair_deals(protocol, pair_deals)
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            await repo.update_protocol(experiment_id, protocol, updated_at=now)
        finally:
            await conn.close()

        logger.info(
            "experiment_collect_started",
            experiment_id=experiment_id,
            count=len(game_ids),
            deal_seed_count=len(deal_seeds),
        )
        return {"game_ids": game_ids, "count": len(game_ids)}

    async def cancel_collect(self, experiment_id: str) -> dict[str, Any]:
        """Cancel all active games for an experiment (stop an in-flight collect)."""
        experiment = await self.get_experiment(experiment_id, include_games=True)
        cancelled: list[str] = []
        needs_db: list[str] = []
        for game in experiment.get("games") or []:
            status = str(game.get("status") or "")
            if status not in _ACTIVE_STATUSES:
                continue
            game_id = str(game["id"])
            if await self._game_service.cancel_game(game_id):
                cancelled.append(game_id)
            else:
                needs_db.append(game_id)

        if needs_db:
            from app.repositories.game_repo import GameRepository

            conn = await self._conn()
            try:
                repo = GameRepository(conn)
                for game_id in needs_db:
                    await repo.update_status(game_id, "cancelled")
                    cancelled.append(game_id)
            finally:
                await conn.close()

        logger.info(
            "experiment_collect_cancelled",
            experiment_id=experiment_id,
            cancelled_count=len(cancelled),
        )
        return {"cancelled_game_ids": cancelled, "count": len(cancelled)}

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
        wins_by_config: dict[str, int] = {
            pid: 0 for pid in experiment.get("player_ids") or []
        }
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
                import json

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
            landlord_rate = (
                wins_as_landlord / games_as_landlord if games_as_landlord > 0 else 0.0
            )
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
            "credibility": build_credibility(
                decisive_n=decisive, landlord_win_rate_ci=landlord_ci
            ),
            "scenario_scores": eval_metrics.get("scenario_scores")
            or fill_scenario_scores({}),
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
        if paired is not None:
            paired_n = int(paired.get("shared_seeds") or 0)
            raw_diff = paired.get("landlord_win_rate_diff")
            if raw_diff is not None:
                ctl_minus_src = float(raw_diff)
                if relation == "vs_source":
                    paired_diff = round(ctl_minus_src, 4)
                else:
                    paired_diff = round(-ctl_minus_src, 4)
            paired_low_power = bool(paired.get("low_power"))

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
            "credibility": build_credibility(
                decisive_n=decisive, landlord_win_rate_ci=landlord_ci
            ),
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
            seeds = (
                set(protocol_deal_seeds(protocol))
                if isinstance(protocol, dict)
                else set()
            )
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
                game = by_seed.get(seed)
                if game is None:
                    continue
                winner = game.get("winner_id")
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
                role = str(game.get("winner_role") or "")
                if role in ("landlord", "peasant"):
                    paired_decisive += 1
                    if role == "landlord":
                        paired_landlord_wins += 1

            row["paired_n"] = paired_n
            row["paired_seat_wins"] = seat_wins
            row["paired_landlord_win_rate"] = (
                round(paired_landlord_wins / paired_decisive, 4)
                if paired_decisive > 0
                else 0.0
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
            src = (
                protocol_source_experiment_id(protocol)
                if isinstance(protocol, dict)
                else None
            )
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
                set(protocol_deal_seeds(protocol))
                if isinstance(protocol, dict)
                else set()
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
                game = by_seed.get(seed)
                if game is None:
                    continue
                winner = game.get("winner_id")
                if not winner:
                    continue
                role = str(game.get("winner_role") or "")
                if role in ("landlord", "peasant"):
                    decisive += 1
                    if role == "landlord":
                        landlord_wins += 1
            return landlord_wins, decisive

        src_ll_wins, src_dec = landlord_wins_on_common(source_id)
        ctl_ll_wins, ctl_dec = landlord_wins_on_common(control_id)
        shared_played = 0
        for seed in common:
            has_src = has_ctl = False
            for exp_id in (source_id, control_id):
                games = games_by_exp.get(exp_id, [])
                for game in games:
                    meta = game.get("metadata") or {}
                    if not isinstance(meta, dict):
                        continue
                    if meta.get("deal_seed") != seed:
                        continue
                    if game.get("winner_id") and str(game.get("winner_role") or "") in (
                        "landlord",
                        "peasant",
                    ):
                        if exp_id == source_id:
                            has_src = True
                        else:
                            has_ctl = True
            if has_src and has_ctl:
                shared_played += 1

        if shared_played <= 0:
            return {
                "shared_seeds": len(common),
                "source_id": source_id,
                "control_id": control_id,
                "landlord_win_rate_diff": None,
                "low_power": True,
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
    import json

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
