"""Doudizhu (斗地主) game engine implementation."""

from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.engine.doudizhu.cards import (
    FULL_DECK,
    ActionType,
    card_rank,
    sort_cards,
)
from app.core.engine.doudizhu.hand_evaluator import classify, get_legal_plays
from app.utils.exceptions import InvalidActionError

RANK_DISPLAY: dict[str, str] = {
    "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
    "8": "8", "9": "9", "T": "10", "J": "J", "Q": "Q",
    "K": "K", "A": "A", "2": "2", "BJ": "小王", "RJ": "大王",
}

SUIT_DISPLAY: dict[str, str] = {
    "S": "♠", "H": "♥", "D": "♦", "C": "♣",
}


def _display_card(card: str) -> str:
    if card in ("BJ", "RJ"):
        return RANK_DISPLAY[card]
    suit, rank = card[0], card[1:]
    return f"{SUIT_DISPLAY.get(suit, '')}{RANK_DISPLAY.get(rank, rank)}"


def _display_cards(cards: list[str]) -> str:
    return " ".join(_display_card(c) for c in sort_cards(cards))


@dataclass
class DoudizhuState(GameState):
    """Extended game state for Doudizhu."""

    hands: dict[str, list[str]] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    landlord_cards: list[str] = field(default_factory=list)
    last_play: tuple[str, ActionType, int, list[str]] | None = None  # (player_id, type, power, cards)
    consecutive_passes: int = 0
    play_history: list[dict[str, Any]] = field(default_factory=list)
    turn_order: list[str] = field(default_factory=list)
    current_turn_index: int = 0
    # Bidding phase fields
    phase: str = "playing"  # "bidding" | "playing"
    bid_order: list[str] = field(default_factory=list)
    bid_index: int = 0
    current_bids: dict[str, int] = field(default_factory=dict)  # player_id -> score (0=not bid yet / passed)
    current_highest_bid: int = 0
    current_highest_bidder: str = ""


class DoudizhuEngine(GameEngine):
    """Doudizhu game engine supporting 3 players."""

    @property
    def game_type(self) -> str:
        return "doudizhu"

    def initialize(self, player_ids: list[str], **params: Any) -> DoudizhuState:
        if len(player_ids) != 3:
            raise InvalidActionError("initialize", "Doudizhu requires exactly 3 players")

        deck = FULL_DECK.copy()
        random.shuffle(deck)

        hands = {
            player_ids[0]: sort_cards(deck[0:17]),
            player_ids[1]: sort_cards(deck[17:34]),
            player_ids[2]: sort_cards(deck[34:51]),
        }
        landlord_cards = sort_cards(deck[51:54])

        # Random starting bidder
        bid_start = random.randint(0, 2)
        bid_order = player_ids[bid_start:] + player_ids[:bid_start]

        return DoudizhuState(
            game_type="doudizhu",
            round=0,
            player_ids=player_ids,
            current_player=bid_order[0],
            is_terminal=False,
            hands=hands,
            roles={},
            landlord_cards=landlord_cards,
            last_play=None,
            consecutive_passes=0,
            play_history=[],
            turn_order=[],
            current_turn_index=0,
            phase="bidding",
            bid_order=bid_order,
            bid_index=0,
            current_bids={pid: 0 for pid in player_ids},
            current_highest_bid=0,
            current_highest_bidder="",
        )

    def get_legal_actions(self, state: GameState, player_id: str) -> list[GameAction]:
        s = self._cast(state)

        # Bidding phase
        if s.phase == "bidding":
            if player_id != s.current_player:
                return []
            actions = [GameAction(player_id=player_id, action_type=ActionType.BID_PASS)]
            for score in (1, 2, 3):
                if score > s.current_highest_bid:
                    actions.append(GameAction(player_id=player_id, action_type=ActionType.BID, cards=[], target=str(score)))
            return actions

        # Playing phase
        hand = s.hands.get(player_id, [])
        if not hand:
            return [GameAction(player_id=player_id, action_type=ActionType.PASS)]

        # Determine context: if 2 consecutive passes or no play yet, player leads
        if s.last_play is None or s.consecutive_passes >= 2:
            last = None
        else:
            _, lt, lp, lc = s.last_play
            last = (lt, lp, lc)

        plays = get_legal_plays(hand, last, player_id)
        if not plays:
            plays = [GameAction(player_id=player_id, action_type=ActionType.PASS)]
        return plays

    def apply_action(self, state: GameState, action: GameAction) -> GameState:
        s = deepcopy(self._cast(state))

        if s.phase == "bidding":
            return self._apply_bid(s, action)

        s.round += 1

        if action.action_type == ActionType.PASS:
            s.consecutive_passes += 1
        else:
            # Remove cards from hand
            remaining = list(s.hands[action.player_id])
            for card in action.cards:
                remaining.remove(card)
            s.hands[action.player_id] = remaining

            cl = classify(action.cards)
            if cl is None:
                raise InvalidActionError(action.action_type, "Invalid card combination")
            atype, power = cl
            s.last_play = (action.player_id, atype, power, action.cards)
            s.consecutive_passes = 0

        s.play_history.append({
            "round": s.round,
            "player_id": action.player_id,
            "action_type": action.action_type,
            "cards": action.cards,
        })

        # Check terminal
        if not s.hands.get(action.player_id):
            s.is_terminal = True
            s.winner = action.player_id
            s.winner_role = s.roles.get(action.player_id)
        else:
            # Advance turn
            s.current_turn_index = (s.current_turn_index + 1) % 3
            s.current_player = s.turn_order[s.current_turn_index]

        return s

    def _apply_bid(self, s: DoudizhuState, action: GameAction) -> DoudizhuState:
        """Process a bidding action and advance bidding phase."""
        player_id = action.player_id

        if player_id != s.current_player:
            raise InvalidActionError(str(action.action_type), "Not this player's turn to bid")

        s.round += 1

        if action.action_type == ActionType.BID:
            score = int(action.target or 1)
            if score <= s.current_highest_bid:
                raise InvalidActionError(str(action.action_type), "Bid must exceed current highest bid")
            s.current_bids[player_id] = score
            s.current_highest_bid = score
            s.current_highest_bidder = player_id
            # If score == 3, bidding ends immediately
            if score == 3:
                return self._finalize_bidding(s)
        elif action.action_type == ActionType.BID_PASS:
            s.current_bids[player_id] = -1  # -1 means explicitly passed
        else:
            raise InvalidActionError(str(action.action_type), "Invalid bidding action")

        s.play_history.append({
            "round": s.round,
            "player_id": player_id,
            "action_type": action.action_type,
            "cards": [],
            "bid_score": int(action.target or 0) if action.action_type == ActionType.BID else 0,
        })

        # Advance to next bidder
        s.bid_index += 1

        # Check if all players have bid
        if s.bid_index >= len(s.bid_order):
            # All done
            if s.current_highest_bid == 0:
                # No one bid — re-deal (mark terminal so game_service can restart)
                s.is_terminal = True
                s.winner = None
                s.winner_role = "no_bid"
                return s
            return self._finalize_bidding(s)

        # Next bidder
        s.current_player = s.bid_order[s.bid_index]
        return s

    def _finalize_bidding(self, s: DoudizhuState) -> DoudizhuState:
        """Assign landlord, give bottom cards, transition to playing phase."""
        landlord_id = s.current_highest_bidder
        s.hands[landlord_id] = sort_cards(s.hands[landlord_id] + s.landlord_cards)

        for pid in s.player_ids:
            s.roles[pid] = "landlord" if pid == landlord_id else "peasant"

        # Build turn order: landlord goes first
        turn_order = s.player_ids.copy()
        idx = turn_order.index(landlord_id)
        s.turn_order = turn_order[idx:] + turn_order[:idx]
        s.current_turn_index = 0
        s.current_player = landlord_id
        s.phase = "playing"
        return s

    def is_terminal(self, state: GameState) -> bool:
        return state.is_terminal

    def get_winner(self, state: GameState) -> str | None:
        return state.winner

    def get_current_player(self, state: GameState) -> str:
        return state.current_player

    def format_for_prompt(self, state: GameState, player_id: str) -> str:
        """Format game state for LLM prompt with clear identity and context."""
        s = self._cast(state)
        hand = s.hands.get(player_id, [])

        # Bidding phase prompt
        if s.phase == "bidding":
            lines = [
                "## 叫地主阶段",
                f"- 你的玩家ID：{player_id}",
                f"- 你的手牌（{len(hand)}张）：{_display_cards(hand)}",
                "",
                f"- 当前最高叫分：{s.current_highest_bid}分"
                + (f"（{s.current_highest_bidder}）" if s.current_highest_bidder else ""),
            ]
            bid_records = [
                f"{pid}叫了{score}分" if score > 0 else f"{pid}不叫"
                for pid, score in s.current_bids.items()
                if score != 0
            ]
            lines.append(f"- 叫分记录：{'、'.join(bid_records) if bid_records else '暂无'}")
            return "\n".join(lines)

        # Playing phase prompt
        role = s.roles.get(player_id, "unknown")
        role_cn = "地主" if role == "landlord" else "农民"

        lines = [
            "## 你的信息",
            f"- 身份：{role_cn}",
            f"- 玩家ID：{player_id}",
            f"- 手牌（{len(hand)}张）：{_display_cards(hand)}",
            "",
            "## 对手信息",
        ]

        # Other players info with relationship marker
        for pid in s.player_ids:
            if pid != player_id:
                other_role = "地主" if s.roles.get(pid) == "landlord" else "农民"
                cards_left = len(s.hands.get(pid, []))
                # Mark relationship for farmers
                if role == "peasant":
                    relation = "队友" if other_role == "农民" else "对手"
                else:
                    relation = "对手"
                # Highlight low card count
                urgency = " ⚠️即将出完" if cards_left <= 2 else ""
                lines.append(f"- {pid}（{other_role}，{relation}）：剩余 {cards_left} 张{urgency}")

        # Landlord bonus cards
        lines.append(f"\n## 底牌\n{_display_cards(s.landlord_cards)}")

        # Current turn context - explain WHY player has control
        lines.append("\n## 当前轮次")

        if s.consecutive_passes >= 2 or s.last_play is None:
            # Player has control (can lead)
            if s.last_play is None:
                lines.append("- 状态：本局首次出牌")
            elif s.last_play[0] == player_id:
                lp_type = s.last_play[1]
                lp_cards = s.last_play[3]
                lines.append(f"- 你上轮出了 {lp_type}：{_display_cards(lp_cards)}")
                lines.append("- 其他玩家都PASS，你继续获得出牌权")
            else:
                lp_player, lp_type, _, lp_cards = s.last_play
                lines.append(f"- {lp_player} 出了 {lp_type}：{_display_cards(lp_cards)}")
                lines.append("- 连续两人PASS，你获得出牌权")
            lines.append("- 决策：你可以自由出任意合法牌型")
        else:
            # Player needs to respond
            lp_player, lp_type, _, lp_cards = s.last_play
            lp_role = s.roles.get(lp_player, "unknown")
            lp_role_cn = "地主" if lp_role == "landlord" else "农民"

            lines.append(f"- 上家 {lp_player}（{lp_role_cn}）出了 {lp_type}：{_display_cards(lp_cards)}")

            # Add strategic hint based on relationship
            if role == "peasant":
                if lp_role == "peasant":
                    lines.append("- ⚠️ 上家是队友，如果队友牌少可以考虑让牌")
                else:
                    lines.append("- ⚠️ 上家是地主，考虑是否管牌")
                    if len(s.hands.get(lp_player, [])) <= 2:
                        lines.append("- 🚨 地主即将出完，必须管牌！")
            else:  # landlord
                lines.append("- 作为地主，主动压制农民")

            lines.append("- 决策：出更大的牌 或 PASS")

        # Recent history (last 3 plays for brevity)
        recent = s.play_history[-3:] if s.play_history else []
        if recent:
            lines.append("\n## 最近出牌记录")
            for entry in recent:
                if entry["action_type"] == ActionType.PASS:
                    lines.append(f"- {entry['player_id']}：PASS")
                elif entry["action_type"] in (ActionType.BID, ActionType.BID_PASS):
                    continue  # Skip bidding records in playing phase display
                else:
                    lines.append(
                        f"- {entry['player_id']}：{entry['action_type']} "
                        f"{_display_cards(entry['cards'])}"
                    )

        return "\n".join(lines)

    def _parse_json_action(
        self, llm_output: str, legal_actions: list[GameAction]
    ) -> GameAction | None:
        """Try to parse action from JSON format."""
        json_match = re.search(r'\{[\s\S]*\}', llm_output)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError, ValueError):
            return None

        action_data = data.get("action", data)
        action_type = str(action_data.get("type", action_data.get("action_type", ""))).upper()
        cards = action_data.get("cards", [])

        # Handle PASS action
        if action_type == ActionType.PASS:
            return next((a for a in legal_actions if a.action_type == ActionType.PASS), None)

        # Handle bidding actions
        if action_type in (ActionType.BID, ActionType.BID_PASS):
            value = action_data.get("value", action_data.get("target", 0))
            for a in legal_actions:
                if str(a.action_type).upper() == action_type:
                    if action_type == ActionType.BID_PASS:
                        return a
                    if a.target == str(value):
                        return a
            # Fallback: return any BID action
            return next(
                (a for a in legal_actions if str(a.action_type).upper() == action_type),
                None,
            )

        # Find matching legal action
        for a in legal_actions:
            if (
                str(a.action_type).upper() == action_type
                and sorted(a.cards) == sorted(cards)
            ):
                return a

        # Try matching just by cards
        if cards:
            for a in legal_actions:
                if sorted(a.cards) == sorted(cards):
                    return a

        return None

    def _find_action_by_keyword(
        self, llm_output: str, legal_actions: list[GameAction]
    ) -> GameAction | None:
        """Find action using keyword matching."""
        # Look for PASS keyword
        if "不出" in llm_output or "PASS" in llm_output.upper():
            return next((a for a in legal_actions if a.action_type == ActionType.PASS), None)

        # Try to find card codes in text
        card_pattern = re.findall(r'[SHDC][3-9TJQKA2]|BJ|RJ', llm_output)
        if card_pattern:
            for a in legal_actions:
                if a.action_type != ActionType.PASS and sorted(a.cards) == sorted(card_pattern):
                    return a

        return None

    def _find_fallback_action(self, legal_actions: list[GameAction]) -> GameAction:
        """Return a fallback action when all parsing fails."""
        non_pass = [a for a in legal_actions if a.action_type != ActionType.PASS]
        if non_pass:
            return non_pass[0]
        return legal_actions[0]

    def parse_action(self, llm_output: str, legal_actions: list[GameAction]) -> GameAction:
        """Parse LLM output into a legal action.

        Tries JSON parsing first, then falls back to text matching.
        If all fails, picks PASS or a random legal action.
        """
        action = self._parse_json_action(llm_output, legal_actions)
        if action:
            return action

        action = self._find_action_by_keyword(llm_output, legal_actions)
        if action:
            return action

        return self._find_fallback_action(legal_actions)

    def get_public_info(
        self, state: GameState, viewer_id: str, is_observer: bool = False
    ) -> dict[str, Any]:
        s = self._cast(state)
        show_hands = is_observer or viewer_id == "observer"

        last_play_action: dict[str, Any] | None = None
        if s.last_play:
            lp_player, lp_type, _, lp_cards = s.last_play
            last_play_action = {
                "type": str(lp_type),
                "cards": list(lp_cards),
                "label": "不出" if str(lp_type) == "PASS" else None,
            }
            # Drop null label for cleaner payloads
            if last_play_action["label"] is None:
                del last_play_action["label"]

        players: list[dict[str, Any]] = []
        for pid in s.player_ids:
            hand = list(s.hands.get(pid, []))
            role = s.roles.get(pid, "unknown")
            badges: list[str] = []
            if role and role != "unknown":
                badges.append(str(role))
            entry: dict[str, Any] = {
                "id": pid,
                "role": role,
                "is_active": s.current_player == pid,
                "hand_count": len(hand),
                "badges": badges,
            }
            if show_hands:
                entry["hand_cards"] = hand
            if last_play_action and s.last_play and s.last_play[0] == pid:
                entry["last_action"] = last_play_action
            players.append(entry)

        slots: list[dict[str, Any]] = []
        if s.phase == "playing" and s.landlord_cards:
            slots.append(
                {
                    "key": "landlord",
                    "label": "底牌",
                    "cards": list(s.landlord_cards),
                }
            )
        if last_play_action and last_play_action.get("cards"):
            slots.append(
                {
                    "key": "last_play",
                    "label": "上一手",
                    "cards": list(last_play_action["cards"]),
                }
            )

        result: dict[str, Any] = {
            "game_type": s.game_type,
            "phase": s.phase,
            "round": s.round,
            "current_player_id": s.current_player,
            "players": players,
            "table": {"slots": slots},
            "extras": {
                "is_terminal": s.is_terminal,
                "winner": s.winner,
                "winner_role": s.winner_role,
                "current_highest_bid": s.current_highest_bid,
                "current_highest_bidder": s.current_highest_bidder,
                "current_bids": s.current_bids,
            },
        }

        return result

    @staticmethod
    def _cast(state: GameState) -> DoudizhuState:
        if not isinstance(state, DoudizhuState):
            raise TypeError(f"Expected DoudizhuState, got {type(state).__name__}")
        return state
