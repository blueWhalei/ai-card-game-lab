"""Card definitions, encoding, and action types for Doudizhu (斗地主)."""

from enum import StrEnum

# ── Card encoding ────────────────────────────────────
# Format: {Suit}{Rank}  e.g. S3 = Spade 3, HK = Heart King
# Jokers: BJ = Black Joker (小王), RJ = Red Joker (大王)

SUITS = ("S", "H", "D", "C")  # Spade, Heart, Diamond, Club
RANKS = ("3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A", "2")

BLACK_JOKER = "BJ"
RED_JOKER = "RJ"

# Power ordering: 3(0) < 4(1) < ... < K(10) < A(11) < 2(12) < BJ(13) < RJ(14)
RANK_POWER: dict[str, int] = {r: i for i, r in enumerate(RANKS)}
RANK_POWER[BLACK_JOKER] = 13
RANK_POWER[RED_JOKER] = 14

FULL_DECK: list[str] = [f"{s}{r}" for r in RANKS for s in SUITS] + [BLACK_JOKER, RED_JOKER]
assert len(FULL_DECK) == 54  # noqa: S101


def card_rank(card: str) -> str:
    """Extract the rank portion from a card code."""
    if card in (BLACK_JOKER, RED_JOKER):
        return card
    return card[1:]


def card_power(card: str) -> int:
    """Return the numeric power of a card for comparison."""
    return RANK_POWER[card_rank(card)]


def sort_cards(cards: list[str]) -> list[str]:
    """Sort cards by ascending power, then by suit."""
    return sorted(cards, key=lambda c: (card_power(c), c))


# ── Action types ─────────────────────────────────────

class ActionType(StrEnum):
    PASS = "PASS"
    SINGLE = "SINGLE"
    PAIR = "PAIR"
    TRIPLE = "TRIPLE"
    TRIPLE_ONE = "TRIPLE_ONE"       # 三带一
    TRIPLE_TWO = "TRIPLE_TWO"       # 三带二
    BOMB = "BOMB"                   # 炸弹 (4 of a kind)
    ROCKET = "ROCKET"               # 火箭 (双王)
    CHAIN = "CHAIN"                 # 顺子 (>=5 consecutive singles)
    CHAIN_PAIR = "CHAIN_PAIR"       # 连对 (>=3 consecutive pairs)
    AIRPLANE = "AIRPLANE"           # 飞机不带 (>=2 consecutive triples)
    AIRPLANE_SOLO = "AIRPLANE_SOLO" # 飞机带单
    AIRPLANE_PAIR = "AIRPLANE_PAIR" # 飞机带对
    FOUR_TWO = "FOUR_TWO"          # 四带二 (4 + 2 singles or 2 pairs)
    BID = "BID"                     # 叫地主 (bidding phase)
    BID_PASS = "BID_PASS"           # 不叫 (pass in bidding phase)


# Minimum chain lengths
MIN_CHAIN_LENGTH = 5
MIN_CHAIN_PAIR_LENGTH = 3   # 3 consecutive pairs = 6 cards
MIN_AIRPLANE_LENGTH = 2     # 2 consecutive triples
