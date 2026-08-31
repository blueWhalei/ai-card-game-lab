"""Idempotent seed for a finished demo game (zero API key required)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.core.collector.jsonl_writer import JsonlWriter
from app.database import connect_sqlite
from app.repositories.decision_repo import DecisionRepository
from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.repositories.trace_repo import TraceRepository

if TYPE_CHECKING:
    import aiosqlite

logger = structlog.get_logger()

DEMO_GAME_ID = "game_demo_doudizhu"
DEMO_PLAYERS = ("cfg_temp_09", "cfg_temp_06", "cfg_temp_12")
DEMO_LANDLORD = DEMO_PLAYERS[0]

_CREATED_AT = "2026-01-01T00:00:00+00:00"
_FINISHED_AT = "2026-01-01T00:03:00+00:00"

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


class DemoSeedService:
    """Writes one finished doudizhu game for first-run replay without API keys."""

    def __init__(self, sqlite_path: str, data_dir: str) -> None:
        self.sqlite_path = sqlite_path
        self._data_dir = data_dir

    async def seed_demo(self) -> dict[str, Any]:
        """Insert the demo game if missing. Safe to call repeatedly."""
        async with connect_sqlite(self.sqlite_path) as db:
            game_repo = GameRepository(db)
            try:
                await game_repo.get_by_id(DEMO_GAME_ID)
            except KeyError:
                await self._insert_demo(db, game_repo)
                logger.info("demo_game_seeded", game_id=DEMO_GAME_ID)
                return {"game_id": DEMO_GAME_ID, "created": True}

        logger.info("demo_game_already_present", game_id=DEMO_GAME_ID)
        return {"game_id": DEMO_GAME_ID, "created": False}

    async def _insert_demo(self, db: aiosqlite.Connection, game_repo: GameRepository) -> None:
        collector = JsonlWriter(self._data_dir)
        data_file = collector.start_game(DEMO_GAME_ID, "doudizhu", list(DEMO_PLAYERS))
        await game_repo.create(
            DEMO_GAME_ID,
            "doudizhu",
            list(DEMO_PLAYERS),
            data_file,
            _CREATED_AT,
            status="running",
            metadata={"demo": True, "source": "seed-demo"},
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
            legal = [chosen]
            if action_type != "PASS":
                legal.append({"action_type": "PASS", "cards": []})

            collector.record_round(
                DEMO_GAME_ID,
                {
                    "game_id": DEMO_GAME_ID,
                    "round_num": spec["round_num"],
                    "player_id": player_id,
                    "action_type": action_type,
                    "cards": cards,
                    "hand_snapshot": hand_snapshot,
                    "all_hands": all_hands,
                    "prompt": _demo_prompt(int(spec["round_num"])),
                    "thinking": thinking,
                    "raw_response": thinking,
                    "response_time_ms": 420 + int(spec["round_num"]) * 30,
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "total_tokens": 120,
                    "model_provider": "demo",
                    "model_name": "demo-replay",
                },
            )
            await round_repo.create(
                {
                    "game_id": DEMO_GAME_ID,
                    "round_num": spec["round_num"],
                    "player_id": player_id,
                    "action_type": action_type,
                    "cards": cards,
                    "hand_snapshot": hand_snapshot,
                    "all_hands": all_hands,
                    "prompt": _demo_prompt(int(spec["round_num"])),
                    "raw_response": thinking,
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "total_tokens": 120,
                    "response_time_ms": 420 + int(spec["round_num"]) * 30,
                    "model_provider": "demo",
                    "model_name": "demo-replay",
                    "created_at": _CREATED_AT,
                }
            )
            await decision_repo.create(
                decision_id=f"dp_demo_{spec['round_num']}",
                game_id=DEMO_GAME_ID,
                round_number=int(spec["round_num"]),
                player_id=player_id,
                hand_cards=[],
                opponent_hands={
                    pid: len(cards_left)
                    for pid, cards_left in all_hands.items()
                    if pid != player_id
                },
                last_action=None,
                game_phase="playing",
                legal_actions=legal,
                chosen_action=chosen,
                thinking=thinking,
                created_at=_CREATED_AT,
                train_usable=True,
            )
            await trace_repo.create_trace(
                trace_id=f"tr_demo_{spec['round_num']}",
                game_id=DEMO_GAME_ID,
                round_number=int(spec["round_num"]),
                player_id=player_id,
                model="demo-replay",
                prompt_version="demo",
                input_snapshot={"phase": "playing", "hand": hand_snapshot},
                output_data={"action": chosen, "thinking": thinking},
                metrics={
                    "response_time_ms": 420 + int(spec["round_num"]) * 30,
                    "used_langchain_parser": True,
                },
                created_at=_CREATED_AT,
            )

        collector.end_game(
            DEMO_GAME_ID,
            {
                "winner_id": DEMO_LANDLORD,
                "winner_role": "landlord",
                "total_rounds": len(_ROUNDS),
            },
        )
        await game_repo.update_result(
            DEMO_GAME_ID,
            winner_id=DEMO_LANDLORD,
            winner_role="landlord",
            total_rounds=len(_ROUNDS),
            finished_at=_FINISHED_AT,
        )
        await decision_repo.update_outcome_by_winner(DEMO_GAME_ID, DEMO_LANDLORD)
        now = datetime.now(tz=UTC).isoformat()
        logger.info("demo_game_persisted", game_id=DEMO_GAME_ID, finished_at=now)
