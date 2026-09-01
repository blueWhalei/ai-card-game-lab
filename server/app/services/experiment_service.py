"""Experiment (run) service — one researcher session spanning collect → review."""

from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from app.core.stats.proportion import wilson_interval
from app.database import open_db_connection
from app.repositories.experiment_repo import ExperimentRepository
from app.services.game_service import GameService
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()

_ACTIVE_STATUSES = frozenset({"created", "running", "paused", "pending"})
_PROTOCOL_SCHEMA_VERSION = 1


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


def derive_experiment_status(
    *,
    target_games: int,
    total_games: int,
    active_games: int,
    finished_games: int,
) -> str:
    """Derive UI status from game rows (not persisted)."""
    if total_games == 0:
        return "pending_collect"
    if active_games > 0:
        return "collecting"
    if finished_games >= target_games:
        return "ready_review"
    return "ready_more"


class ExperimentService:
    """Manages experiment runs and collection against GameService."""

    def __init__(self, sqlite_path: str, game_service: GameService) -> None:
        self._sqlite_path = sqlite_path
        self._game_service = game_service

    async def _conn(self) -> aiosqlite.Connection:
        return await open_db_connection(self._sqlite_path)

    def _prompt_version(self) -> str:
        settings = getattr(self._game_service, "_settings", None)
        if settings is not None:
            return str(getattr(settings, "prompt_version", "v1") or "v1")
        return "v1"

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
                    "model_config": deepcopy(cfg.get("model_config") or {}),
                }
            )
        return players

    def _build_protocol(
        self,
        *,
        player_ids: list[str],
        source_experiment_id: str | None,
        pair_deals: bool,
        deal_seeds: list[int],
        frozen_at: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": _PROTOCOL_SCHEMA_VERSION,
            "frozen_at": frozen_at,
            "prompt_version": self._prompt_version(),
            "players": self._snapshot_players(player_ids),
            "source_experiment_id": source_experiment_id,
            "pair_deals": pair_deals,
            "deal_seeds": list(deal_seeds),
        }

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
            raw_seeds = source_protocol.get("deal_seeds") or []
            deal_seeds = [int(s) for s in raw_seeds]

        experiment_id = generate_id("exp")
        now = datetime.now(tz=UTC).isoformat()
        protocol = self._build_protocol(
            player_ids=player_ids,
            source_experiment_id=source_id,
            pair_deals=bool(pair_deals and source_id),
            deal_seeds=deal_seeds,
            frozen_at=now,
        )

        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            await repo.create(
                experiment_id=experiment_id,
                name=name.strip(),
                notes=notes.strip(),
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
            pair_deals=protocol["pair_deals"],
            deal_seed_count=len(deal_seeds),
        )
        return await self.get_experiment(experiment_id, include_games=False)

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
                games = await repo.list_games(experiment_id)
                games_by_exp[experiment_id] = [_normalize_game_row(g) for g in games]
                rows.append(self._attach_compare_metrics(row, summary, extras))
        finally:
            await conn.close()

        self._attach_paired_compare_metrics(rows, games_by_exp)
        return {"experiments": rows}

    async def list_experiments(self) -> list[dict[str, Any]]:
        conn = await self._conn()
        try:
            repo = ExperimentRepository(conn)
            rows = await repo.list_all()
            results: list[dict[str, Any]] = []
            for row in rows:
                summary = await self._build_summary(repo, row)
                results.append({**row, "summary": summary})
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
            if include_games:
                games = await repo.list_games(experiment_id)
                payload["games"] = [_normalize_game_row(g) for g in games]
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
        protocol = experiment.get("protocol")
        if not isinstance(protocol, dict):
            protocol = self._build_protocol(
                player_ids=player_ids,
                source_experiment_id=None,
                pair_deals=False,
                deal_seeds=[],
                frozen_at=now,
            )
        else:
            protocol = deepcopy(protocol)
            if not protocol.get("players"):
                protocol["players"] = self._snapshot_players(player_ids)
                protocol.setdefault("frozen_at", now)
                protocol.setdefault("schema_version", _PROTOCOL_SCHEMA_VERSION)
                protocol.setdefault("prompt_version", self._prompt_version())

        deal_seeds = [int(s) for s in (protocol.get("deal_seeds") or [])]
        pair_deals = bool(protocol.get("pair_deals"))
        frozen_players = list(protocol.get("players") or [])

        game_ids: list[str] = []
        for offset in range(count):
            index = start_index + offset
            paired = False
            if pair_deals and index < len(deal_seeds):
                seed = deal_seeds[index]
                paired = True
            else:
                seed = secrets.randbits(31)
                if index < len(deal_seeds):
                    # Shouldn't happen for pair_deals false with pre-filled seeds,
                    # but keep list length aligned with game order.
                    deal_seeds[index] = seed
                else:
                    deal_seeds.append(seed)

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

        protocol["deal_seeds"] = deal_seeds
        protocol["pair_deals"] = pair_deals
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

    async def _build_summary(
        self,
        repo: ExperimentRepository,
        experiment: dict[str, Any],
    ) -> dict[str, Any]:
        experiment_id = str(experiment["id"])
        target = int(experiment["target_games"])
        games = await repo.list_games(experiment_id)
        eval_metrics = await repo.eval_aggregates(experiment_id)

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

        return {
            "status": status,
            "target_games": target,
            "total_games": len(games),
            "active_games": active,
            "finished_games": finished,
            "games_with_winner": with_winner,
            "train_usable_decisions": train_usable,
            "train_usable_rate": eval_metrics.get("train_usable_rate", 0.0),
            "decision_count": eval_metrics.get("decision_count", 0),
            "avg_rounds": round(avg_rounds, 1),
            "wins_by_config": wins_by_config,
            "wins_by_role": eval_metrics.get("wins_by_role") or {"landlord": 0, "peasant": 0},
            "decisive_games": decisive,
            "landlord_win_rate": eval_metrics.get("landlord_win_rate", 0.0),
            "landlord_win_rate_ci": [round(l_low, 4), round(l_high, 4)],
            "parser_success_rate": eval_metrics.get("parser_success_rate", 0.0),
            "parser_n": eval_metrics.get("parser_n", 0),
            "avg_response_time_ms": eval_metrics.get("avg_response_time_ms", 0.0),
            "p50_response_ms": eval_metrics.get("p50_response_ms", 0.0),
            "p95_response_ms": eval_metrics.get("p95_response_ms", 0.0),
            "total_tokens": eval_metrics.get("total_tokens", 0),
            "tokens_per_game": eval_metrics.get("tokens_per_game", 0.0),
            "avg_tokens_per_round": eval_metrics.get("avg_tokens_per_round", 0.0),
            "status_counts": eval_metrics.get("status_counts") or {},
            "player_stats": player_stats,
            "latest_game_id": latest_game_id,
            "paired_games": paired_games,
        }

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
            "landlord_win_rate_ci": [round(l_low, 4), round(l_high, 4)],
            "status_counts": extras.get("status_counts") or {},
            "player_stats": player_stats,
            "paired_n": 0,
            "paired_seat_wins": [0] * len(row.get("player_ids") or []),
            "paired_landlord_win_rate": 0.0,
        }

    @staticmethod
    def _attach_paired_compare_metrics(
        rows: list[dict[str, Any]],
        games_by_exp: dict[str, list[dict[str, Any]]],
    ) -> None:
        seed_sets: list[set[int]] = []
        for row in rows:
            protocol = row.get("protocol") or {}
            seeds = {int(s) for s in (protocol.get("deal_seeds") or [])}
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

def _normalize_game_row(row: dict[str, Any]) -> dict[str, Any]:
    import json

    out = dict(row)
    if isinstance(out.get("player_ids"), str):
        out["player_ids"] = json.loads(out["player_ids"])
    if isinstance(out.get("metadata"), str):
        out["metadata"] = json.loads(out["metadata"])
    return out
