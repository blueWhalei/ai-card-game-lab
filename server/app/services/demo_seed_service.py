"""Idempotent seed: trial replay game + main/control experiments for verdict."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.core.collector.jsonl_writer import JsonlWriter
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.eval.evaluator_protocol import freeze_evaluator_snapshot
from app.core.task_protocol import build_protocol
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_config_repo import ExperimentConfigRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.repositories.trace_repo import TraceRepository

if TYPE_CHECKING:
    import aiosqlite

logger = structlog.get_logger()

DEMO_GAME_ID = "game_demo_doudizhu"
DEMO_EXPERIMENT_ID = "exp_demo_main"
DEMO_CONTROL_ID = "exp_demo_control"
DEMO_PLAYERS = ("cfg_temp_09", "cfg_temp_06", "cfg_temp_12")
DEMO_LANDLORD = DEMO_PLAYERS[0]
DEMO_FARMER = DEMO_PLAYERS[1]
DEMO_DEAL_SEEDS = (1001, 1002)
DEMO_TARGET_GAMES = len(DEMO_DEAL_SEEDS)

_CREATED_AT = "2026-01-01T00:00:00+00:00"
_FINISHED_AT = "2026-01-01T00:03:00+00:00"

_PLAYER_META: tuple[tuple[str, str], ...] = (
    (DEMO_PLAYERS[0], "演示地主席"),
    (DEMO_PLAYERS[1], "演示农民甲"),
    (DEMO_PLAYERS[2], "演示农民乙"),
)

_HANDS: dict[str, list[str]] = {
    DEMO_PLAYERS[0]: ["H3", "H4", "H5", "H6", "HA", "H2", "RJ"],
    DEMO_PLAYERS[1]: ["S3", "S7", "S8", "SK", "SA", "C2"],
    DEMO_PLAYERS[2]: ["D4", "D9", "DJ", "DQ", "DA", "BJ"],
}


def _demo_prompt(round_num: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "你是斗地主玩家。根据手牌选择合法动作。"},
        {"role": "user", "content": f"轮次 {round_num}。请出牌。"},
    ]


def _hands_after(played: dict[str, list[str]]) -> dict[str, list[str]]:
    remaining: dict[str, list[str]] = {}
    for pid, cards in _HANDS.items():
        used = set(played.get(pid, []))
        remaining[pid] = [c for c in cards if c not in used]
    return remaining


_ROUNDS: list[dict[str, Any]] = [
    {
        "round_num": 1,
        "player_id": DEMO_PLAYERS[0],
        "action_type": "SINGLE",
        "cards": ["H3"],
        "thinking": "决定出单牌探路。先看看农民跟不跟。",
        "played": {DEMO_PLAYERS[0]: ["H3"]},
    },
    {
        "round_num": 2,
        "player_id": DEMO_PLAYERS[1],
        "action_type": "PASS",
        "cards": [],
        "thinking": "选择不出。这张 3 不值得跟。留着大牌。",
        "played": {DEMO_PLAYERS[0]: ["H3"]},
    },
    {
        "round_num": 3,
        "player_id": DEMO_PLAYERS[2],
        "action_type": "SINGLE",
        "cards": ["D4"],
        "thinking": "决定出单牌压过 3。避免地主连走。",
        "played": {DEMO_PLAYERS[0]: ["H3"], DEMO_PLAYERS[2]: ["D4"]},
    },
    {
        "round_num": 4,
        "player_id": DEMO_PLAYERS[0],
        "action_type": "SINGLE",
        "cards": ["HA"],
        "thinking": "决定出单牌 A 压制场面。争取再拿回主动。",
        "played": {
            DEMO_PLAYERS[0]: ["H3", "HA"],
            DEMO_PLAYERS[2]: ["D4"],
        },
    },
    {
        "round_num": 5,
        "player_id": DEMO_PLAYERS[1],
        "action_type": "PASS",
        "cards": [],
        "thinking": "选择不出。A 太大。过牌等下一轮。",
        "played": {
            DEMO_PLAYERS[0]: ["H3", "HA"],
            DEMO_PLAYERS[2]: ["D4"],
        },
    },
]


def _frozen_players() -> list[dict[str, Any]]:
    return [
        {
            "id": pid,
            "name": name,
            "notes": "demo heuristic seat",
            "policy_kind": "heuristic",
            "model_config": {
                "provider": "baseline",
                "model_name": "heuristic",
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 1,
            },
        }
        for pid, name in _PLAYER_META
    ]


def _demo_protocol(
    *,
    source_experiment_id: str | None,
    pair_deals: bool,
) -> dict[str, Any]:
    engine = DoudizhuEngine()
    return build_protocol(
        players=_frozen_players(),
        source_experiment_id=source_experiment_id,
        pair_deals=pair_deals,
        deal_seeds=list(DEMO_DEAL_SEEDS),
        frozen_at=_CREATED_AT,
        prompt_version="demo",
        collect_mode="free",
        protocol_fingerprint=engine.capability.protocol_fingerprint(),
        evaluator=freeze_evaluator_snapshot(determinizations=4, max_candidates=8),
    )


class DemoSeedService:
    """Seeds a trial game plus a main/control experiment pair (zero API keys)."""

    def __init__(self, sqlite_path: str, data_dir: str) -> None:
        self.sqlite_path = sqlite_path
        self._data_dir = data_dir

    async def seed_demo(self) -> dict[str, Any]:
        """Insert demo artifacts if missing. Safe to call repeatedly."""
        async with connect_sqlite(self.sqlite_path) as db:
            await self._ensure_players(db)
            game_repo = GameRepository(db)
            exp_repo = ExperimentRepository(db)

            created_any = False
            try:
                await game_repo.get_by_id(DEMO_GAME_ID)
            except KeyError:
                await self._insert_scripted_game(
                    db,
                    game_repo,
                    game_id=DEMO_GAME_ID,
                    experiment_id=None,
                    deal_seed=None,
                    paired=False,
                    winner_id=DEMO_LANDLORD,
                    winner_role="landlord",
                    id_prefix="demo",
                    metadata_extra={"demo": True, "source": "seed-demo"},
                )
                created_any = True
                logger.info("demo_game_seeded", game_id=DEMO_GAME_ID)

            try:
                await exp_repo.get_by_id(DEMO_EXPERIMENT_ID)
            except KeyError:
                await self._insert_experiment_pair(db, game_repo, exp_repo)
                created_any = True
                logger.info(
                    "demo_experiments_seeded",
                    main=DEMO_EXPERIMENT_ID,
                    control=DEMO_CONTROL_ID,
                )

        return {
            "experiment_id": DEMO_EXPERIMENT_ID,
            "game_id": DEMO_GAME_ID,
            "created": created_any,
        }

    async def _ensure_players(self, db: aiosqlite.Connection) -> None:
        cfg_repo = ExperimentConfigRepository(db)
        for pid, name in _PLAYER_META:
            existing = await cfg_repo.get(pid)
            if existing is not None:
                continue
            await cfg_repo.upsert(
                {
                    "id": pid,
                    "name": name,
                    "notes": "零 API 演示选手（启发式）",
                    "policy_kind": "heuristic",
                    "model_config": {
                        "provider": "baseline",
                        "model_name": "heuristic",
                        "temperature": 0.0,
                        "top_p": 1.0,
                        "max_tokens": 1,
                    },
                }
            )

    async def _insert_experiment_pair(
        self,
        db: aiosqlite.Connection,
        game_repo: GameRepository,
        exp_repo: ExperimentRepository,
    ) -> None:
        await exp_repo.create(
            experiment_id=DEMO_EXPERIMENT_ID,
            name="演示实验（主）",
            notes="Load demo 生成的主实验；与对照配对后可直接看 verdict。",
            hypothesis="启发式座位在固定牌局上可复现；对照实验用于展示 Δ。",
            tags=["demo"],
            game_type="doudizhu",
            player_ids=list(DEMO_PLAYERS),
            target_games=DEMO_TARGET_GAMES,
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
            protocol=_demo_protocol(source_experiment_id=None, pair_deals=False),
        )
        await exp_repo.create(
            experiment_id=DEMO_CONTROL_ID,
            name="演示实验（对照）",
            notes="同种子配对对照；地主胜率故意压低以便页面上有可见 Δ。",
            hypothesis="对照侧地主更弱。",
            tags=["demo", "control"],
            game_type="doudizhu",
            player_ids=list(DEMO_PLAYERS),
            target_games=DEMO_TARGET_GAMES,
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
            protocol=_demo_protocol(
                source_experiment_id=DEMO_EXPERIMENT_ID,
                pair_deals=True,
            ),
        )

        for index, seed in enumerate(DEMO_DEAL_SEEDS, start=1):
            await self._insert_scripted_game(
                db,
                game_repo,
                game_id=f"game_demo_main_{index}",
                experiment_id=DEMO_EXPERIMENT_ID,
                deal_seed=seed,
                paired=True,
                winner_id=DEMO_LANDLORD,
                winner_role="landlord",
                id_prefix=f"main{index}",
                metadata_extra={"demo": True, "source": "seed-demo"},
            )
            await self._insert_scripted_game(
                db,
                game_repo,
                game_id=f"game_demo_ctl_{index}",
                experiment_id=DEMO_CONTROL_ID,
                deal_seed=seed,
                paired=True,
                winner_id=DEMO_FARMER,
                winner_role="farmer",
                id_prefix=f"ctl{index}",
                metadata_extra={"demo": True, "source": "seed-demo"},
            )

    async def _insert_scripted_game(
        self,
        db: aiosqlite.Connection,
        game_repo: GameRepository,
        *,
        game_id: str,
        experiment_id: str | None,
        deal_seed: int | None,
        paired: bool,
        winner_id: str,
        winner_role: str,
        id_prefix: str,
        metadata_extra: dict[str, Any],
    ) -> None:
        collector = JsonlWriter(self._data_dir)
        data_file = collector.start_game(game_id, "doudizhu", list(DEMO_PLAYERS))
        metadata: dict[str, Any] = {
            **metadata_extra,
            "landlord_id": DEMO_LANDLORD,
            "paired": paired,
        }
        if deal_seed is not None:
            metadata["deal_seed"] = deal_seed

        await game_repo.create(
            game_id,
            "doudizhu",
            list(DEMO_PLAYERS),
            data_file,
            _CREATED_AT,
            status="running",
            metadata=metadata,
            experiment_id=experiment_id,
        )

        round_repo = RoundRepository(db)
        decision_repo = DecisionRepository(db)
        trace_repo = TraceRepository(db)

        for spec in _ROUNDS:
            player_id = str(spec["player_id"])
            cards = list(spec["cards"])
            action_type = str(spec["action_type"])
            thinking = str(spec["thinking"])
            all_hands = _hands_after(spec["played"])
            hand_snapshot = all_hands.get(player_id, [])
            chosen = {"action_type": action_type, "cards": cards}
            action_id = f"{action_type}|{' '.join(cards)}|"
            legal = [{"id": action_id, **chosen}]
            if action_type != "PASS":
                legal.append({"id": "PASS||", "action_type": "PASS", "cards": []})
            prompt_messages = _demo_prompt(int(spec["round_num"]))
            round_num = int(spec["round_num"])

            collector.record_round(
                game_id,
                {
                    "game_id": game_id,
                    "round_num": round_num,
                    "player_id": player_id,
                    "action_type": action_type,
                    "cards": cards,
                    "hand_snapshot": hand_snapshot,
                    "all_hands": all_hands,
                    "prompt": prompt_messages,
                    "thinking": thinking,
                    "raw_response": thinking,
                    "response_time_ms": 420 + round_num * 30,
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "total_tokens": 120,
                    "model_provider": "demo",
                    "model_name": "demo-replay",
                },
            )
            await round_repo.create(
                {
                    "game_id": game_id,
                    "round_num": round_num,
                    "player_id": player_id,
                    "action_type": action_type,
                    "cards": cards,
                    "hand_snapshot": hand_snapshot,
                    "all_hands": all_hands,
                    "prompt": prompt_messages,
                    "raw_response": thinking,
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "total_tokens": 120,
                    "response_time_ms": 420 + round_num * 30,
                    "model_provider": "demo",
                    "model_name": "demo-replay",
                    "created_at": _CREATED_AT,
                }
            )
            await decision_repo.create(
                decision_id=f"dp_{id_prefix}_{round_num}",
                game_id=game_id,
                round_number=round_num,
                player_id=player_id,
                hand_cards=hand_snapshot,
                opponent_hands={
                    pid: len(cards_left)
                    for pid, cards_left in all_hands.items()
                    if pid != player_id
                },
                last_action=None,
                game_phase="playing",
                legal_actions=legal,
                chosen_action=chosen,
                action_id=action_id,
                prompt_messages=prompt_messages,
                thinking=thinking,
                created_at=_CREATED_AT,
                train_usable=True,
                policy_kind="heuristic",
            )
            await trace_repo.create_trace(
                trace_id=f"tr_{id_prefix}_{round_num}",
                game_id=game_id,
                round_number=round_num,
                player_id=player_id,
                model="demo-replay",
                prompt_version="demo",
                input_snapshot={"phase": "playing", "hand": hand_snapshot},
                output_data={"action": chosen, "thinking": thinking},
                metrics={
                    "response_time_ms": 420 + round_num * 30,
                    "parser_ok": True,
                },
                created_at=_CREATED_AT,
            )

        collector.end_game(
            game_id,
            {
                "winner_id": winner_id,
                "winner_role": winner_role,
                "total_rounds": len(_ROUNDS),
            },
        )
        await game_repo.update_result(
            game_id,
            winner_id=winner_id,
            winner_role=winner_role,
            total_rounds=len(_ROUNDS),
            finished_at=_FINISHED_AT,
        )
        await decision_repo.update_outcome_by_winner(game_id, winner_id)
        now = datetime.now(tz=UTC).isoformat()
        logger.info("demo_game_persisted", game_id=game_id, finished_at=now)
