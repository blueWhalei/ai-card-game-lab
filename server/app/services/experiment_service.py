"""Experiment (run) service — one researcher session spanning collect → review."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.core.engine.base import EngineCapability
from app.core.eval.evaluator_protocol import freeze_evaluator_snapshot
from app.core.eval.scorer import ScorerRegistry
from app.core.eval.scorers import build_scorer_registry
from app.core.pack import (
    KIND_EXPERIMENT_PACK,
    KIND_PLAYER_PACK,
    build_experiment_pack,
    parse_pack,
)
from app.core.stats.benchmark import build_benchmark_coverage
from app.database import open_db_connection
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_collect import ExperimentCollectMixin
from app.services.experiment_delta import (
    ExperimentDeltaMixin,
    _games_with_progress,
    _normalize_game_row,
    _slim_list_delta,
)
from app.services.experiment_errors import (
    ExperimentNotFoundError,
    ExperimentValidationError,
)
from app.services.experiment_protocol import (
    build_protocol,
    protocol_collect_mode,
    protocol_deal_seeds,
    protocol_game_type,
    protocol_pair_deals,
    protocol_players,
    protocol_prompt_version,
    protocol_prompts,
)
from app.services.game_service import GameService
from app.utils.id_generator import generate_id
from app.utils.providers import unconfigured_providers_from_players

logger = structlog.get_logger()

__all__ = [
    "ExperimentNotFoundError",
    "ExperimentService",
    "ExperimentValidationError",
]


class ExperimentService(ExperimentCollectMixin, ExperimentDeltaMixin):
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

    def _prompt_version(self, override: str | None = None) -> str:
        from app.core.ai.prompts.registry import DEFAULT_TEMPLATE_VERSION

        raw = (override or "").strip()
        return raw or DEFAULT_TEMPLATE_VERSION

    async def _snapshot_prompts(
        self,
        *,
        game_type: str,
        prompt_version: str,
    ) -> dict[str, dict[str, Any]]:
        """Freeze template bodies for every engine prompt key at *prompt_version*."""
        from app.core.ai.prompt import get_prompt_registry
        from app.core.task_protocol import prompt_content_hash
        from app.database import open_db_connection

        capability = self._engine_capability(game_type)
        registry = get_prompt_registry()
        engine = self._game_service._engine_registry.get(game_type)
        keys = list(dict.fromkeys(capability.prompt_keys.values()))
        out: dict[str, dict[str, Any]] = {}

        conn = await open_db_connection(self._sqlite_path)
        try:
            for template_key in keys:
                content: str | None = None
                try:
                    content = await registry.get_template(
                        template_key,
                        db=conn,
                        version=prompt_version,
                        require_active=False,
                    )
                except ValueError:
                    phase = next(
                        (p for p, k in capability.prompt_keys.items() if k == template_key),
                        "playing",
                    )
                    content = engine.default_system_template(phase)
                if not content:
                    continue
                out[template_key] = {
                    "version": prompt_version,
                    "content": content,
                    "content_hash": prompt_content_hash(content),
                }
        finally:
            await conn.close()
        return out

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
        prompt_version: str | None = None,
        prompts: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from app.config import Settings

        settings = Settings()
        evaluator = freeze_evaluator_snapshot(
            determinizations=settings.ev_loss_determinizations,
            max_candidates=settings.ev_loss_max_candidates,
        )
        version = self._prompt_version(prompt_version)
        return build_protocol(
            players=self._snapshot_players(player_ids),
            source_experiment_id=source_experiment_id,
            pair_deals=pair_deals,
            deal_seeds=deal_seeds,
            frozen_at=frozen_at,
            prompt_version=version,
            collect_mode=collect_mode,
            protocol_fingerprint=self._engine_capability(game_type).protocol_fingerprint(),
            evaluator=evaluator,
            prompts=prompts,
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
        prompt_version: str | None = None,
        frozen_prompts: dict[str, dict[str, Any]] | None = None,
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
        source_protocol: dict[str, Any] | None = None
        if pair_deals:
            if not source_experiment_id:
                raise ExperimentValidationError("配对发牌需要指定源实验")
            source = await self.get_experiment(source_experiment_id, include_games=False)
            if str(source["game_type"]) != game_type:
                raise ExperimentValidationError("对照实验的游戏类型必须与源实验一致")
            if len(source.get("player_ids") or []) != n_players:
                raise ExperimentValidationError("对照实验的座位数必须与源实验一致")
            source_id = str(source["id"])
            raw_source_protocol = source.get("protocol") or {}
            if isinstance(raw_source_protocol, dict):
                source_protocol = raw_source_protocol
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

        version = self._prompt_version(prompt_version)
        prompts = frozen_prompts
        if prompts is None and source_protocol is not None and pair_deals:
            # Control runs keep the source's frozen prompt bodies for a fair Δ.
            prompts = protocol_prompts(source_protocol) or None
            if not prompt_version:
                version = self._prompt_version(protocol_prompt_version(source_protocol))
        if prompts is None:
            prompts = await self._snapshot_prompts(game_type=game_type, prompt_version=version)

        protocol = self._build_protocol(
            player_ids=player_ids,
            source_experiment_id=source_id,
            pair_deals=bool(pair_deals and source_id),
            deal_seeds=deal_seeds,
            frozen_at=now,
            collect_mode=effective_mode,
            game_type=game_type,
            prompt_version=version,
            prompts=prompts,
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
        collect_mode = protocol_collect_mode(protocol) if isinstance(protocol, dict) else "free"
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
            prompt_version=(
                protocol_prompt_version(protocol) if isinstance(protocol, dict) else None
            ),
            frozen_prompts=(protocol_prompts(protocol) if isinstance(protocol, dict) else None)
            or None,
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
        pack_protocol = pack.get("protocol") if isinstance(pack.get("protocol"), dict) else None

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
            prompt_version=(
                str(spec.get("prompt_version") or "")
                or (protocol_prompt_version(pack_protocol) if pack_protocol else None)
            )
            or None,
            frozen_prompts=protocol_prompts(pack_protocol) or None,
        )
        payload["experiment"] = created
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
            payload["delta"] = await self._build_delta(repo, row, summary, payload["validation"])
            return payload
        finally:
            await conn.close()
